import time
import threading
import random
import os
from src.core.node import Node
from src.modules.routing import Routing
from src.core.packet import Packet
from src.core.crypto import CryptoManager

from src.modules.reliability import Reliability
from src.modules.crypto import SURB

class Sender(Node):
    def __init__(self, hostname, port, config, network_map):
        super().__init__(hostname, port, config)
        self.network_map = network_map
        self.routing = Routing(config, network_map)
        self.reliability = Reliability(config, self) # Integrate Reliability
        self.sending = False
        
        # Traffic Config
        self.rate = config['traffic']['rate_packets_per_sec']
        self.duration = config['traffic']['duration_sec']
        self.receivers = [n for n in network_map if n.startswith('r')]
        
        # Crypto
        self.crypto = CryptoManager()

    def start_sending(self):
        self.sending = True
        threading.Thread(target=self._sender_loop, daemon=True).start()

    def _load_node_keys(self, nodes):
        """Helper to load public keys for nodes in the route from disk."""
        keys = {}
        # Assuming keys are stored in 'keys/<hostname>.pem' by MixNodes
        # This requires MixNodes to write them on startup.
        # Check if keys dir exists
        if not os.path.exists("keys"):
            return {}
            
        for node in nodes:
            try:
                with open(f"keys/{node}.pem", "rb") as f:
                    keys[node] = f.read()
            except FileNotFoundError:
                # In simulation, if key missing, maybe skip encryption or fail?
                # For robustness, we might log warning.
                pass
        return keys

    def _sender_loop(self):
        start_time = time.time()
        self.logger.log("Starting traffic generation loop...")
        
        use_encryption = self.config.get('features', {}).get('layered_encryption', False)
        
        while self.sending and (time.time() - start_time < self.duration):
            receiver = random.choice(self.receivers)
            payload = f"Msg from {self.hostname} to {receiver} at {time.time()}"
            
            packets_to_send = []
            
            # Anonymous Return Address (SURB)
            # ... (omitted logic for brevity if unchanged, but need to keep it)
            # To keep replacement clean, I'll copy the logic but respect the block limit.
            # Wait, I am replacing the whole file content or block? The tool is replace_file_content.
            # I must reproduce the logic correctly.
            
            surb_data = None
            if self.config['features'].get('anonymous_return_addresses', False):
                return_route = self.routing.get_path(receiver, self.hostname)
                surb = SURB(self.hostname, return_route)
                surb_data = surb.to_dict()

            if self.config['features'].get('parallel_paths', False):
                k = 2
                paths = self.routing.get_disjoint_paths(self.hostname, receiver, k)
                if not paths:
                    self.logger.log("No disjoint paths found", "WARNING")
                    paths = [self.routing.get_path(self.hostname, receiver)]
                
                base_id = None
                base_ts = time.time()
                for route in paths:
                    pkt = Packet(payload, receiver, route)
                    pkt.timestamp = base_ts
                    if base_id is None:
                        base_id = pkt.packet_id
                    else:
                        pkt.packet_id = base_id
                    
                    if surb_data:
                        pkt.flags['surb'] = surb_data
                        
                    packets_to_send.append(pkt)
            else:
                route = self.routing.get_path(self.hostname, receiver)
                packet = Packet(payload, receiver, route)
                
                if surb_data:
                    packet.flags['surb'] = surb_data
                    
                packets_to_send.append(packet)

            # Process Packets (Encryption & Sending)
            for packet in packets_to_send:
                # Encryption Logic
                final_packet = packet
                if use_encryption:
                    # We encrypt the serialized inner packet
                    inner_bytes = packet.to_json().encode('utf-8')
                    # Route for encryption: [Mix1, Mix2, ..., Receiver] or just Mixes?
                    # The route in packet.route contains [Mix1, Mix2, Receiver] usually.
                    # We need keys for all except maybe Receiver if we don't encrypt for it?
                    # Usually Receiver also has a key.
                    
                    # Ensure we have keys
                    route_nodes = packet.route
                    # We filter out nodes that might not have keys (like client itself if in route?)
                    # Usually route is strict.
                    
                    keys_map = self._load_node_keys(route_nodes)
                    if len(keys_map) == len(route_nodes):
                        try:
                            onion_blob = self.crypto.create_onion_packet(
                                route_nodes, 
                                packet.destination, 
                                inner_bytes, 
                                keys_map
                            )
                            # Create outer packet
                            # Route strictly needs to point to first hop
                            first_hop = packet.route[0]
                            final_packet = Packet(onion_blob, packet.destination, route=[first_hop], type="ONION")
                            # Preserve ID? No, outer packet ID is different usually.
                            # But for tracking? We track 'packet' (inner).
                            # The network sees final_packet.
                            
                        except Exception as e:
                            self.logger.log(f"Encryption failed: {e}. Sending PLAIN.", "ERROR")
                    else:
                        self.logger.log("Missing keys for onion routing. Sending PLAIN.", "WARNING")

                # Track for retransmission (if enabled)
                self.reliability.track_packet(packet) # Track the ORIGINAL packet (inner ID)
                
                # Send
                first_hop = final_packet.route[0]
                if first_hop in self.network_map:
                    ip, port = self.network_map[first_hop]
                    self.send_packet(final_packet, ip, port)
                    self.logger.log_traffic("CREATED", final_packet)
                else:
                    self.logger.log(f"First hop {first_hop} unknown", "ERROR")

            time.sleep(1.0 / self.rate)
        
        self.logger.log("Traffic generation finished.")

    def handle_packet(self, packet):
        # Handle ACK
        if packet.flags.get('type') == 'ACK':
            original_id = packet.flags.get('ack_id')
            self.reliability.receive_ack(original_id)
            self.logger.log_traffic("ACK_RECEIVED", packet)
        else:
            self.logger.log(f"Unexpected packet received: {packet}", "WARNING")


class Receiver(Node):
    def __init__(self, hostname, port, config, network_map):
        super().__init__(hostname, port, config)
        self.network_map = network_map
        self.routing = Routing(config, network_map) # Receiver needs routing for ACKs
        
        # Crypto
        self.crypto = CryptoManager()
        
        # Check if keys exist
        if not os.path.exists("keys"):
            os.makedirs("keys")
            
        priv_key_path = f"keys/{hostname}_private.pem"
        pub_key_path = f"keys/{hostname}.pem"
        
        if os.path.exists(priv_key_path):
            self.logger.log(f"Loading existing keys from {priv_key_path}")
            self.crypto.load_private_key_from_file(priv_key_path)
            self.public_key_pem = self.crypto.get_public_key_pem()
        else:
            self.logger.log(f"Generating new keys for {hostname}")
            self.public_key_pem = self.crypto.generate_key_pair()
            self.crypto.save_private_key_to_file(priv_key_path)
            
        # Write public key to disk
        with open(pub_key_path, "wb") as f:
            f.write(self.public_key_pem)

    def handle_packet(self, packet):
        self.logger.log_traffic("RECEIVED", packet)
        
        # Handle Encrypted Packet
        if packet.type == "ONION":
            try:
                # Decrypt the last layer
                # For the last hop, 'next_hop' might be irrelevant or self.
                _, inner_content = self.crypto.decrypt_onion_layer(packet.payload)
                
                # The inner content is the JSON of the original packet
                if isinstance(inner_content, bytes):
                    inner_content = inner_content.decode('utf-8')
                
                packet = Packet.from_json(inner_content)
                self.logger.log(f"Decrypted onion packet. Inner ID: {packet.packet_id}")
            except Exception as e:
                self.logger.log(f"Failed to decrypt packet at receiver: {e}", "ERROR")
                return

        # Calculate latency
        latency = time.time() - packet.timestamp
        self.logger.log(f"Received packet {packet.packet_id}. Latency: {latency:.4f}s")
        
        # Send ACK if needed
        # Check config features
        if self.config['features'].get('retransmission', False):
            # Send ACK back to sender
            try:
                route = None
                src_host = None
                
                # Check for SURB
                surb_data = packet.flags.get('surb')
                if surb_data:
                    route = surb_data['route']
                    # src_host is at the end of route?
                    src_host = route[-1]
                    self.logger.log(f"Using SURB for ACK to {src_host}")
                else:
                     # Extract sender from payload or metadata? 
                    src_host = packet.payload.split(" ")[2] # "Msg from <src> ..."
                    # Route: Receiver -> MixNet -> Sender
                    route = self.routing.get_path(self.hostname, src_host)
                
                # Generate ACK
                ack_payload = f"ACK for {packet.packet_id}"
                
                ack_pkt = Packet(ack_payload, src_host, route)
                ack_pkt.flags['type'] = 'ACK'
                ack_pkt.flags['ack_id'] = packet.packet_id
                
                # Send
                first_hop = route[0]
                if first_hop in self.network_map:
                    ip, port = self.network_map[first_hop]
                    self.send_packet(ack_pkt, ip, port)
                    self.logger.log_traffic("ACK_SENT", ack_pkt)
            except Exception as e:
                self.logger.log(f"Failed to send ACK: {e}", "ERROR")
