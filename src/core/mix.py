import time
import threading
import random
from src.core.node import Node

class MixNode(Node):
    def __init__(self, hostname, port, config, network_map):
        super().__init__(hostname, port, config)
        self.network_map = network_map # Dict mapping logical names to (ip, port)
        self.pool = []
        self.lock = threading.Lock()
        
        self.strategy = config['mix_settings']['strategy']
        self.pool_size = config['mix_settings']['pool_size']
        self.timeout = config['mix_settings']['timeout']
        
        # Start mixing loop
        threading.Thread(target=self._mixing_loop, daemon=True).start()

    def handle_packet(self, packet):
        self.logger.log_traffic("RECEIVED", packet)
        
        # In a real mix, we decrypt a layer here.
        # onion_peel = packet.decrypt(...)
        # next_hop = onion_peel.next_hop
        
        # For simplified Stratified Mix:
        # Route is explicitly in packet.route list for simulation? 
        # Or we determine next hop based on topology?
        # Creating a specific "next_hop" extraction logic.
        
        with self.lock:
            self.pool.append(packet)
            self.logger.log(f"Packet added to pool. Size: {len(self.pool)}")

    def _mixing_loop(self):
        while self.running:
            time.sleep(self.timeout)
            self.flush_pool()

    def flush_pool(self):
        with self.lock:
            if len(self.pool) >= self.pool_size or (len(self.pool) > 0 and self.strategy == 'timed_pool'):
                # Basic Timed Pool: Flush random subset or all? 
                to_send = list(self.pool) # Copy
                random.shuffle(to_send)
                self.pool = [] # Clear pool (Batch behavior). For Pool behavior, only take some.
                
                for pkt in to_send:
                    self._forward_packet(pkt)

    def _forward_packet(self, packet):
        # Simulate Packet Loss
        loss_rate = self.config.get('network', {}).get('packet_loss_rate', 0.0)
        if random.random() < loss_rate:
            self.logger.log_traffic("DROPPED_SIM", packet)
            self.logger.log(f"Simulating packet loss for {packet.packet_id}", "INFO")
            return

        # Determine next hop
        # Assuming packet.route contains [node_name_1, node_name_2, ...]
        # And we are node_name_X. Next is X+1.
        
        if not packet.route:
            self.logger.log("Packet has no route!", "ERROR")
            return

        try:
            current_index = packet.route.index(self.hostname)
            if current_index < len(packet.route) - 1:
                next_hop_name = packet.route[current_index + 1]
                if next_hop_name in self.network_map:
                    next_ip, next_port = self.network_map[next_hop_name]
                    self.logger.log(f"Forwarding packet {packet.packet_id} to {next_hop_name}")
                    self.send_packet(packet, next_ip, next_port)
                else:
                    self.logger.log(f"Next hop {next_hop_name} not in map", "ERROR")
            else:
                self.logger.log("Packet reached end of route at mix? Should be Receiver.", "WARNING")
        except ValueError:
             self.logger.log(f"Current node {self.hostname} not in packet route {packet.route}", "ERROR")
