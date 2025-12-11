import hashlib
import os
import threading
import time
import random
from src.core.node import Node
from src.core.crypto import CryptoManager

class MixNode(Node):
    def __init__(self, hostname, port, config, network_map):
        super().__init__(hostname, port, config)
        self.network_map = network_map # Dict mapping logical names to (ip, port)
        self.pool = []
        self.lock = threading.Lock()
        
        self.strategy = config['mix_settings']['strategy']
        self.pool_size = config['mix_settings']['pool_size']
        self.timeout = config['mix_settings']['timeout']
        
        # Crypto & Security
        self.crypto = CryptoManager()
        self.public_key_pem = self.crypto.generate_key_pair()
        self.replay_cache = set()

        # Save Public Key
        if not os.path.exists("keys"):
            os.makedirs("keys")
        with open(f"keys/{hostname}.pem", "wb") as f:
            f.write(self.public_key_pem)
        
        # Start mixing loop
        threading.Thread(target=self._mixing_loop, daemon=True).start()

    def handle_packet(self, packet):
        self.logger.log_traffic("RECEIVED", packet)
        
        # Replay Protection
        packet_hash = hashlib.sha256(str(packet.packet_id).encode() + str(packet.payload).encode()).hexdigest()
        if packet_hash in self.replay_cache:
            self.logger.log(f"Replay detected for packet {packet.packet_id}. Dropping.", "WARNING")
            return
        self.replay_cache.add(packet_hash)
        
        # Decryption if Onion
        if packet.type == "ONION":
            try:
                next_hop, inner_content = self.crypto.decrypt_onion_layer(packet.payload)
                # Update packet for next hop
                packet.payload = inner_content
                # We need to store where to send this. 
                # Since 'route' is hidden/empty in Onion packets, we store it temporarily.
                packet.next_hop_temp = next_hop
            except Exception as e:
                self.logger.log(f"Decryption failed for packet {packet.packet_id}: {e}", "ERROR")
                return

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

        next_hop_name = None

        if packet.type == "ONION":
            if hasattr(packet, 'next_hop_temp'):
                next_hop_name = packet.next_hop_temp
            else:
                self.logger.log(f"Onion packet {packet.packet_id} has no next hop info!", "ERROR")
                return
        else:
            # LEGACY / PLAIN MODE
            if not packet.route:
                self.logger.log("Packet has no route!", "ERROR")
                return

            try:
                current_index = packet.route.index(self.hostname)
                if current_index < len(packet.route) - 1:
                    next_hop_name = packet.route[current_index + 1]
                else:
                    self.logger.log("Packet reached end of route at mix? Should be Receiver.", "WARNING")
                    return
            except ValueError:
                 self.logger.log(f"Current node {self.hostname} not in packet route {packet.route}", "ERROR")
                 return

        if next_hop_name:
            if next_hop_name in self.network_map:
                next_ip, next_port = self.network_map[next_hop_name]
                self.logger.log(f"Forwarding packet {packet.packet_id} to {next_hop_name}")
                self.send_packet(packet, next_ip, next_port)
            else:
                # Is it the final destination?
                # In Onion routing, the last mix might see "Receiver" as next hop.
                self.logger.log(f"Next hop {next_hop_name} not in map. Assuming final destination or unknown.", "WARNING")
                # If we had a mechanism to send to Client/Receiver directly, we would do it here.
                # For now, let's just log.
