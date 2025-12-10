import time
import threading
import random
from src.core.node import Node
from src.modules.routing import Routing
from src.core.packet import Packet

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
        self.receivers = [n for n in network_map if n.startswith('h_recv')]

    def start_sending(self):
        self.sending = True
        threading.Thread(target=self._sender_loop, daemon=True).start()

    def _sender_loop(self):
        start_time = time.time()
        self.logger.log("Starting traffic generation loop...")
        
        while self.sending and (time.time() - start_time < self.duration):
            receiver = random.choice(self.receivers)
            payload = f"Msg from {self.hostname} to {receiver} at {time.time()}"
            
            packets_to_send = []
            
            # Anonymous Return Address (SURB)
            surb_data = None
            if self.config['features'].get('anonymous_return_addresses', False):
                # Return Path: Entry -> Inter -> Exit -> Me
                # Route from Receiver perspective
                # Receiver -> [Entry, Inter, Exit, Me]
                # get_path generates [Entry, Inter, Exit, Dst]
                return_route = self.routing.get_path(receiver, self.hostname)
                surb = SURB(self.hostname, return_route)
                surb_data = surb.to_dict()

            if self.config['features'].get('parallel_paths', False):
                # Parallel Paths
                k = 2
                paths = self.routing.get_disjoint_paths(self.hostname, receiver, k)
                if not paths:
                    self.logger.log("No disjoint paths found", "WARNING")
                    paths = [self.routing.get_path(self.hostname, receiver)]
                
                # Create multiple packets with SAME ID
                base_id = None
                base_ts = time.time()
                for route in paths:
                    pkt = Packet(payload, receiver, route)
                    pkt.timestamp = base_ts # Sync timestamp
                    if base_id is None:
                        base_id = pkt.packet_id
                    else:
                        pkt.packet_id = base_id
                    
                    if surb_data:
                        pkt.flags['surb'] = surb_data
                        
                    packets_to_send.append(pkt)
            else:
                # Single Path
                route = self.routing.get_path(self.hostname, receiver)
                packet = Packet(payload, receiver, route)
                
                if surb_data:
                    packet.flags['surb'] = surb_data
                    
                packets_to_send.append(packet)

            for packet in packets_to_send:
                # Track for retransmission (if enabled)
                # Note: If parallel, tracking same ID multiple times? 
                # Reliability module uses dict by ID. 
                # If we track same ID twice, it just updates timestamp/entry.
                # If ANY copy arrives and sends ACK, we stop retransmitting.
                # This is desired behavior for redundancy.
                self.reliability.track_packet(packet)
                
                # Send to first hop
                first_hop = packet.route[0]
                if first_hop in self.network_map:
                    ip, port = self.network_map[first_hop]
                    self.send_packet(packet, ip, port)
                    self.logger.log_traffic("CREATED", packet)
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

    def handle_packet(self, packet):
        self.logger.log_traffic("RECEIVED", packet)
        
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
