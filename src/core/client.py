import time
import threading
import random
import os
import math
import uuid
import queue
from src.core.node import Node
from src.modules.routing import Routing
from src.core.packet import Packet
from src.core.crypto import CryptoManager
from src.modules.reliability import Reliability
from src.modules.crypto import SURB

class Client(Node):
    def __init__(self, hostname, port, config, network_map):
        super().__init__(hostname, port, config)
        self.network_map = network_map
        self.routing = Routing(config, network_map)
        self.reliability = Reliability(config, self)
        
        # Identity
        self.is_client = True
        
        # Load Traffic Config
        self.traffic_config = config.get('traffic', {})
        self.rate_real = self.traffic_config.get('rate_packets_per_sec', 0.0)
        self.rate_loop = self.traffic_config.get('loop_rate_packets_per_sec', 0.0)
        self.rate_drop = self.traffic_config.get('drop_rate_packets_per_sec', 0.0)
        self.duration = self.traffic_config.get('duration_sec', 30)
        self.traffic_distribution = self.traffic_config.get('traffic_distribution', 'uniform_random')
        self.assigned_partner = None
        
        # Crypto
        self.mock_crypto = config['features'].get('mock_encryption', False)
        self.crypto = CryptoManager(mock_mode=self.mock_crypto)
        self._setup_keys()
        
        self.sending = False
        self.receivers = [n for n in network_map if n.startswith('c') and n != hostname] # Other clients
        self.providers = [n for n in network_map if n.startswith('p')]
        self.mixes = [n for n in network_map if n.startswith('m') or n.startswith('x') or n.startswith('e') or n.startswith('i')]

        # Delay Param
        self.mu = config.get('mix_settings', {}).get('mu', 1.0)

    def _setup_keys(self):
        if not os.path.exists("keys"):
            os.makedirs("keys")
        priv = f"keys/{self.hostname}_private.pem"
        pub = f"keys/{self.hostname}.pem"
        if os.path.exists(priv):
            self.crypto.load_private_key_from_file(priv)
            self.public_key_pem = self.crypto.get_public_key_pem()
        else:
            self.public_key_pem = self.crypto.generate_key_pair()
            self.crypto.save_private_key_to_file(priv)
        with open(pub, "wb") as f:
            f.write(self.public_key_pem)

    def start(self):
        super().start()
        # No processing loop needed for client receive for now (handled by listener thread in Node)

    def start_sending(self):
        self.sending = True
        self.logger.log("Starting traffic generation threads...")

        if self.traffic_distribution == 'fixed_partner' and self.receivers:
            self.assigned_partner = random.choice(self.receivers)
            self.logger.log(f"Assigned fixed partner: {self.assigned_partner}")
            
        # Strategy selection
        strategy = self.traffic_config.get('traffic_strategy', 'loopix')
        self.logger.log(f"Traffic Strategy: {strategy}")

        if strategy == 'loopix':
            # --- Loopix Mode (Strict) ---
            # Paper Model: Users send at Poisson rate lambda (Total Emission).
            # Real messages (lambda_P) are generated. If no real message ready, send drop.
            
            # 1. Config Loading
            # In Loopix mode, we interpret 'transmission_rate_packets_per_sec' as the Master Rate.
            # Fallback for backward compat: use 'drop_rate_packets_per_sec' if transmission_rate not set.
            # (User complained about 'drop_rate' being confusing, so we prefer transmission_rate)
            
            tx_rate = self.traffic_config.get('transmission_rate_packets_per_sec', 0.0)
            if tx_rate <= 0:
                 # Fallback to drop_rate if user hasn't updated config yet, or purely legacy config
                 tx_rate = self.traffic_config.get('drop_rate_packets_per_sec', 0.0)
                 
            # If still 0, default to Real Rate (No cover traffic capacity)
            if tx_rate <= 0:
                tx_rate = self.rate_real
                self.logger.log("No transmission/drop rate configured. Defaulting to Real Rate (Zero Cover Traffic).", "WARNING")

            # SAFETY: Limit Check
            # We cannot effectively send Real Messages if Tx Rate < Real Rate (queue would explode).
            # We force Tx >= Real.
            if tx_rate < self.rate_real:
                self.logger.log(f"Transmission Rate ({tx_rate}) < Real Rate ({self.rate_real}). Adjusting up.", "WARNING")
                tx_rate = self.rate_real

            self.logger.log(f"Loopix Mode: Emission Rate = {tx_rate} pps (Real: {self.rate_real})")

            # 2. Threads
            self.message_buffer = queue.Queue()
            
            # Producer (Real)
            if self.rate_real > 0:
                threading.Thread(target=self._real_traffic_producer, daemon=True).start()
                
            # Consumer/Emitter (Pacer)
            if tx_rate > 0:
                threading.Thread(target=self._transmission_loop_pacer, args=(tx_rate,), daemon=True).start()
            
            # 3. Loops (Independent)
            if self.rate_loop > 0:
                threading.Thread(target=self._loop_traffic_loop, daemon=True).start()
                
        else:
            # --- Legacy Mode (Additive) ---
            self.logger.log("Legacy Mode: Additive Traffic")
            if self.rate_real > 0:
                threading.Thread(target=self._real_traffic_loop, daemon=True).start()
            if self.rate_loop > 0:
                threading.Thread(target=self._loop_traffic_loop, daemon=True).start()
            if self.rate_drop > 0:
                threading.Thread(target=self._drop_traffic_loop, daemon=True).start()

    def _get_delay(self):
        # Exponential delay for mixing
        return random.expovariate(1.0 / self.mu)

    def _sleep_poisson(self, rate):
        if rate <= 0: return float('inf')
        return random.expovariate(rate)

    def _load_node_keys(self, nodes):
        keys = {}
        for node in nodes:
            try:
                with open(f"keys/{node}.pem", "rb") as f:
                    keys[node] = f.read()
            except:
                pass
        return keys

    def _send_onion_packet(self, payload, path, final_dest):
        # path is list of mix nodes/providers.
        # final_dest is the Client we usually want to reach?
        # In Loopix, the path ends at the Provider of the recipient.
        # The Recipient pulls from Provider.
        # Here we push. So last hop in `path` sends to `final_dest`.
        
        # We need delays for each hop in the path.
        delays = {node: self._get_delay() for node in path}
        
        # Keys
        keys_map = self._load_node_keys(path)
        if len(keys_map) != len(path):
            self.logger.log(f"Missing keys for path {path}. Aborting send.", "WARNING")
            return

        # Create inner packet (serialized)
        # Note: If we are sending to a Client, the inner payload is the Packet object?
        # Or just raw data? The mixnet delivers 'final_payload' to 'final_dest'.
        # If 'final_dest' is a client, it expects a Packet object (JSON) usually
        # to parse timestamp, id, etc.
        
        inner_packet = Packet(payload, final_dest, route=path, src=self.hostname) # Route in inner packet is mostly metadata now
        inner_bytes = inner_packet.to_json().encode('utf-8')
        
        try:
            onion_blob = self.crypto.create_onion_packet(
                path, 
                final_dest, 
                inner_bytes, 
                keys_map, 
                delays=delays
            )
            
            # Helper to find first hop IP
            first_hop = path[0]
            if first_hop in self.network_map:
                ip, port = self.network_map[first_hop]
                # Outer packet
                # Outer packet
                outer = Packet(onion_blob, final_dest, route=[first_hop], type="ONION", src=self.hostname)
                self.send_packet(outer, ip, port, next_hop_name=first_hop)
                self.logger.log_traffic("CREATED", inner_packet) # Log the intent
            else:
                self.logger.log(f"First hop {first_hop} unknown", "ERROR")
                
        except Exception as e:
            self.logger.log(f"Onion creation failed: {e}", "ERROR")

    # --- Traffic Loops ---

    def _real_traffic_producer(self):
        """
        Produces real messages and puts them into the buffer queue.
        Does NOT send them directly.
        """
        start_time = time.time()
        while self.sending and (time.time() - start_time < self.duration):
            time.sleep(self._sleep_poisson(self.rate_real))
            if not self.receivers: continue
            
            # Generate Message Content (Same logic as _real_traffic_loop)
            try:
                if self.traffic_distribution == 'fixed_partner' and self.assigned_partner:
                    dest = self.assigned_partner
                else:
                    dest = random.choice(self.receivers)
                payload = f"Real Msg {time.time()}"
                
                # --- FEATURE: Parallel Paths ---
                paths = []
                if self.config['features'].get('parallel_paths', False):
                    paths = self.routing.get_disjoint_paths(self.hostname, dest, k=2)
                    if not paths:
                        p = self.routing.get_path(self.hostname, dest)
                        if p: paths = [p]
                else:
                    p = self.routing.get_path(self.hostname, dest)
                    if p: paths = [p]
                    
                if not paths: continue

                # Create Packets
                msg_uuid = str(uuid.uuid4())
                
                # SURB logic
                surb_data = None
                if self.config['features'].get('anonymous_return_addresses', False):
                    return_route = self.routing.get_path(dest, self.hostname)
                    if return_route:
                        surb = SURB(self.hostname, return_route)
                        surb_data = surb.to_dict()

                for path in paths:
                    if not path: continue
                    packet = Packet(payload, dest, route=path, src=self.hostname, message_id=msg_uuid)
                    if surb_data: packet.flags['surb'] = surb_data
                    
                    if self.config['features'].get('retransmission', False):
                        self.reliability.track_packet(packet)
                        
                    # PUSH TO BUFFER
                    self.message_buffer.put((packet, path))
                    
            except Exception as e:
                self.logger.log(f"Producer error: {e}", "ERROR")

    def _transmission_loop_pacer(self, rate):
        """
        Consumes from buffer or sends Drop traffic to maintain constant rate.
        """
        start_time = time.time()
        while self.sending and (time.time() - start_time < self.duration):
            time.sleep(self._sleep_poisson(rate))
            
            if not self.message_buffer.empty():
                # Send Real
                try:
                    packet, path = self.message_buffer.get_nowait()
                    self._send_prepared_project(packet, path)
                except queue.Empty:
                    pass
            else:
                # Buffer Empty -> Gap Filling -> Send Drop
                self._send_drop_packet()

    def _send_drop_packet(self):
        # Use Drop Logic (extracted from old _drop_traffic_loop)
        if not self.mixes: return
        random_mix = random.choice(self.mixes)
        path = self.routing.get_path(self.hostname, random_mix)
        payload = f"Drop Msg {time.time()}"
        self._send_onion_packet(payload, path, "DROP")
    

    # --- Traffic Loops ---
    
    def _real_traffic_loop(self):
        start_time = time.time()
        mode = self.traffic_config.get('mode', 'random')
        
        if mode == 'precalculated':
            # Simplified precalc logic
            # ... (omitted for brevity in this step, focusing on Loopix logic)
            # If user needs exact precalc, I should port it.
            # Let's port the logic structure:
            pass # TODO: Add back if critical. User asked for experiment capability.
            # The prompt says "experimente so wiederholen kann wie ich es getan habe".
            # So I MUST include precalculated support.
            
            precalc_file = self.traffic_config.get('precalc_file')
            try:
                import pickle
                with open(precalc_file, 'rb') as f:
                    all_traffic = pickle.load(f)
                my_packets = all_traffic.get(self.hostname, [])
                my_packets.sort(key=lambda p: p.timestamp)
                
                for p in my_packets:
                    if not self.sending: break
                    target = start_time + p.timestamp
                    gap = target - time.time()
                    if gap > 0: time.sleep(gap)
                    
                    # Send p
                    if not p.route:
                         # Recalculate route if missing or old?
                         # Precalc usually has routes. Assuming valid.
                         pass
                    
                    self._send_onion_packet(p.payload, p.route, p.destination)
                    
            except Exception as e:
                self.logger.log(f"Precalc error: {e}", "ERROR")
            return

        # Random Mode
        while self.sending and (time.time() - start_time < self.duration):
            time.sleep(self._sleep_poisson(self.rate_real))
            if not self.receivers: continue
            
            try:
                if self.traffic_distribution == 'fixed_partner' and self.assigned_partner:
                    dest = self.assigned_partner
                else:
                    dest = random.choice(self.receivers)
                payload = f"Real Msg {time.time()}"
                
                # --- FEATURE: Parallel Paths ---
                paths = []
                if self.config['features'].get('parallel_paths', False):
                    paths = self.routing.get_disjoint_paths(self.hostname, dest, k=2)
                    # Fallback if no disjoint paths
                    if not paths:
                        p = self.routing.get_path(self.hostname, dest)
                        if p: paths = [p]
                else:
                    p = self.routing.get_path(self.hostname, dest)
                    if p: paths = [p]
                    
                if not paths:
                    self.logger.log(f"No path found to {dest}", "WARNING")
                    continue
                    
                # --- FEATURE: Anonymous Return Addresses ---
                surb_data = None
                if self.config['features'].get('anonymous_return_addresses', False):
                    # Return route: Dst -> ... -> Src
                    # In Loopix, SURB allows receiver to reply.
                    # Simplified: Include a return path in the packet metadata.
                    return_route = self.routing.get_path(dest, self.hostname)
                    if return_route:
                        surb = SURB(self.hostname, return_route)
                        surb_data = surb.to_dict()
                    else:
                        self.logger.log(f"No return path from {dest}", "WARNING")

                # Generate a specific Message ID for this logical message
                msg_uuid = str(uuid.uuid4())
                
                for i, path in enumerate(paths):
                    if not path: continue # Skip empty paths
                    
                    # Create Inner Packet
                    # Each packet gets a unique packet_id (physical), but shares message_id (logical)
                    packet = Packet(payload, dest, route=path, src=self.hostname, message_id=msg_uuid)
                    
                    if surb_data:
                        packet.flags['surb'] = surb_data

                    # --- FEATURE: Reliability ---
                    # Track the packet for retransmission (using message_id?)
                    if self.config['features'].get('retransmission', False):
                        self.reliability.track_packet(packet)
                    
                    # Send (Wrap in Onion)
                    # Use helper that accepts the pre-built packet
                    self._send_prepared_project(packet, path)
            except Exception as e:
                self.logger.log(f"Error in traffic loop: {e}", "ERROR")

    def _send_prepared_project(self, packet, path):
         # Keys
        keys_map = self._load_node_keys(path)
        
        # Delays
        delays = {node: self._get_delay() for node in path}
        
        inner_bytes = packet.to_json().encode('utf-8')
        
        try:
            onion_blob = self.crypto.create_onion_packet(
                path, 
                packet.destination, 
                inner_bytes, 
                keys_map, 
                delays=delays
            )
            
            first_hop = path[0]
            if first_hop in self.network_map:
                ip, port = self.network_map[first_hop]
                outer = Packet(onion_blob, packet.destination, route=[first_hop], type="ONION", src=self.hostname)
                self.send_packet(outer, ip, port, next_hop_name=first_hop)
                self.logger.log_traffic("CREATED", packet)
            else:
                self.logger.log(f"First hop {first_hop} unknown", "ERROR")
        except Exception as e:
            self.logger.log(f"Onion send error: {e}", "ERROR")

    def _loop_traffic_loop(self):
        # Sends packet to Self
        start_time = time.time()
        while self.sending and (time.time() - start_time < self.duration):
            time.sleep(self._sleep_poisson(self.rate_loop))
            
            path = self.routing.get_path(self.hostname, self.hostname) # Loop path
            payload = f"Loop Msg {time.time()}"
            self._send_onion_packet(payload, path, self.hostname)

    def _drop_traffic_loop(self):
        # Sends packet to a random Mix and asks it to drop?
        # Loopix "Drop" messages are usually indistinguishable but have a flag or are just destined to a mix?
        # Actually, if we send to a Mix node as 'final_dest', the MixNode logs "unknown destination" and drops it?
        # Or we can send to a random node with a specific instruction.
        # Simple implementation: Send to a random MixNode in the network.
        # That MixNode will try to forward to 'final_dest'. If 'final_dest' is 'DROP', maybe?
        
        start_time = time.time()
        while self.sending and (time.time() - start_time < self.duration):
            time.sleep(self._sleep_poisson(self.rate_drop))
            
            # Pick a random mix to hold the packet
            # random path
            dest = "DROP" # Magic destination?
            # Or just send to random mix?
            # If I set final_dest="DROP", the last mix will try to look up "DROP". Fail. Drop.
            # This works for simulation.
            
            if not self.mixes: continue
            random_mix = random.choice(self.mixes)
            # Short path?
            path = self.routing.get_path(self.hostname, random_mix)
            
            payload = f"Drop Msg {time.time()}"
            self._send_onion_packet(payload, path, dest)

    def _resolve_node_id(self, ip, port):
        # Reverse lookup from network_map
        for name, (node_ip, node_port) in self.network_map.items():
            if node_ip == ip: 
                return name
        return f"{ip}:{port}"

    def handle_packet(self, packet, source_address):
        # self.logger.log_traffic("RECEIVED", packet) # Moved below to log decrypted ID
        prev_hop_id = self._resolve_node_id(source_address[0], source_address[1])
        
        if packet.type == "ONION":
            try:
                _, _, inner_content = self.crypto.decrypt_onion_layer(packet.payload)
                if isinstance(inner_content, bytes):
                    inner_content = inner_content.decode('utf-8')
                packet = Packet.from_json(inner_content)
            except Exception as e:
                self.logger.log(f"Decrypt error: {e}", "ERROR")
                return

        self.logger.log_traffic("RECEIVED", packet, prev_hop=prev_hop_id) # Log the decrypted/final packet

        latency = time.time() - packet.timestamp
        self.logger.log(f"Received msg: {packet.payload[:20]}... Latency: {latency:.4f}s")
        
        # Reliability (ACKs)
        if self.config['features'].get('retransmission', False):
            if packet.flags.get('type') == 'ACK':
                self.reliability.receive_ack(packet.flags.get('ack_id'))
            else:
                # Send ACK
                ack_dest = packet.src
                if ack_dest and ack_dest != "unknown":
                    # Simple ACK: Reverse path or direct?
                    # In mixnet, we usually need a fresh path or SURB.
                    # If SURB exists, use it. Else, try routing if we know the src name.
                    
                    if 'surb' in packet.flags:
                        # Use SURB to send ACK
                        self._send_surb_reply("ACK_PAYLOAD", packet.flags['surb'], ack_id=packet.packet_id, is_ack=True)
                    else:
                        # Try standard routing to src
                        try:
                            path = self.routing.get_path(self.hostname, ack_dest)
                            # Create ACK packet
                            ack_pkt = Packet("ACK", ack_dest, route=path, src=self.hostname)
                            ack_pkt.flags['type'] = 'ACK'
                            ack_pkt.flags['ack_id'] = packet.packet_id
                            self._send_prepared_project(ack_pkt, path)
                            self.logger.log(f"Sent ACK for {packet.packet_id} to {ack_dest}")
                        except Exception as e:
                           self.logger.log(f"Could not send ACK: {e}", "WARNING")

        # Reply via SURB if requested (and not just an ACK)
        if 'surb' in packet.flags and packet.flags.get('type') != 'ACK':
             # Simulate application response (independent of ACK)
             # Only if we want to reply to data strings
             if "Real Msg" in str(packet.payload):
                 self._send_surb_reply(f"RE: {packet.payload}", packet.flags['surb'])

    def _send_surb_reply(self, payload_str, surb_dict, ack_id=None, is_ack=False):
        """
        Send a reply using a Single Use Reply Block.
        """
        try:
            surb = SURB.from_dict(surb_dict)
            # Route provided by SURB (Sender->...->Client) is reversed? 
            # No, SURB contains the route FROM Receiver TO Sender. 
            # So we just use it.
            
            # The SURB route endpoints:
            # surb.route[0] should be the first hop (Entry for me)
            # surb.route[-1] is the Final Dest (The original Sender)
            
            # Note: Loopix SURB is pre-encrypted headers. Here we mock it by just taking the route.
            path = surb.route
            destination = surb.sender # OR path[-1]? In SURB, path usually includes dest?
            
            # Reliability: Check if we strictly follow the route or if destination is separate?
            # In our SURB mockup, 'route' is [Entry, ... , Sender].
            # So final dest is indeed the end of that list or 'surb.sender'.
            # Let's trust surb.sender as final dest.
            
            packet = Packet(payload_str, destination, route=path, src=self.hostname)
            
            if is_ack:
                 packet.flags['type'] = 'ACK'
                 packet.flags['ack_id'] = ack_id
            
            self._send_prepared_project(packet, path)
            self.logger.log(f"Sent SURB reply to {destination}")
            
        except Exception as e:
            self.logger.log(f"SURB reply failed: {e}", "ERROR")

# Alias for compatibility if needed, but we try to use Client everywhere
Sender = Client
Receiver = Client
