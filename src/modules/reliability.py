import time
import threading
import random

class Reliability:
    def __init__(self, config, sender_instance):
        self.config = config
        self.sender = sender_instance
        self.retransmission_enabled = config['features'].get('retransmission', False)
        self.sent_packets = {}  # packet_id -> {packet, timestamp, retries}
        self.ack_map = {}       # packet_id -> bool
        
        # Settings
        self.timeout = 5.0      # seconds to wait for ack
        self.max_retries = 3
        
        if self.retransmission_enabled:
            # Start monitoring thread
            threading.Thread(target=self._monitor_loop, daemon=True).start()

    def track_packet(self, packet):
        if not self.retransmission_enabled:
            return
        
        with threading.Lock():
            self.sent_packets[packet.packet_id] = {
                "packet": packet,
                "ts": time.time(),
                "retries": 0
            }

    def receive_ack(self, packet_id):
        if not self.retransmission_enabled:
            return
            
        with threading.Lock():
            if packet_id in self.sent_packets:
                del self.sent_packets[packet_id]
                self.sender.logger.log(f"ACK received for {packet_id}")

    def _monitor_loop(self):
        while self.sender.running:
            time.sleep(1.0)
            now = time.time()
            to_resend = []
            
            # Check for timeouts
            # Note: Need lock for iteration if modifying? 
            # We copy keys first.
            
            with threading.Lock():
                keys = list(self.sent_packets.keys())
                for pid in keys:
                    info = self.sent_packets[pid]
                    if now - info['ts'] > self.timeout:
                        if info['retries'] < self.max_retries:
                            info['retries'] += 1
                            info['ts'] = now
                            to_resend.append(info['packet'])
                            self.sender.logger.log(f"Timeout for {pid}, retrying ({info['retries']}/{self.max_retries})")
                        else:
                            self.sender.logger.log(f"Packet {pid} failed after max retries", "WARNING")
                            del self.sent_packets[pid]
                            
            for pkt in to_resend:
                # Path Re-establishment
                if self.config['features'].get('path_reestablishment', False):
                    # Destination is pkt.destination?
                    # Packet object has .destination attribute
                    new_route = self.sender.routing.get_path(self.sender.hostname, pkt.destination)
                    pkt.route = new_route
                    self.sender.logger.log(f"Re-established path for {pkt.packet_id}: {new_route}")

                # Resend using sender's mechanism
                # We need to find the first hop again? 
                # Packet route is preserved or updated.
                first_hop = pkt.route[0]
                if first_hop in self.sender.network_map:
                    ip, port = self.sender.network_map[first_hop]
                    self.sender.send_packet(pkt, ip, port)
                    self.sender.logger.log_traffic("RESENT", pkt)
