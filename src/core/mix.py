import hashlib
import os
import threading
import time
import random
import heapq
from src.core.node import Node
from src.core.crypto import CryptoManager

class ScheduledPacket:
    def __init__(self, packet, send_time, next_hop):
        self.packet = packet
        self.send_time = send_time
        self.next_hop = next_hop
        
    def __lt__(self, other):
        return self.send_time < other.send_time

class MixNode(Node):
    def __init__(self, hostname, port, config, network_map):
        super().__init__(hostname, port, config)
        self.network_map = network_map # Dict mapping logical names to (ip, port)
        self.scheduler = [] # Heap of ScheduledPacket
        self.lock = threading.Lock()
        
        self.strategy = config.get('mix_settings', {}).get('strategy', 'poisson')
        # Legacy pool fallback
        self.pool_size = config.get('mix_settings', {}).get('pool_size', 10)
        self.timeout = config.get('mix_settings', {}).get('timeout', 1.0)
        
        # Crypto & Security
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
            
        self.replay_cache = set()

        # Save Public Key (always overwrite/ensure existing)
        with open(pub_key_path, "wb") as f:
            f.write(self.public_key_pem)
        
    def start(self):
        super().start()
        # Start mixing loop
        threading.Thread(target=self._mixing_loop, daemon=True).start()
        self.logger.log("Mixing loop started")

    def handle_packet(self, packet):
        self.logger.log_traffic("RECEIVED", packet)
        
        # Replay Protection
        # Ideally, we should check replay AFTER decryption to prevent tagging attacks,
        # but checking outer hash first prevents cheap flooding.
        # Loopix recommends checking unique ID embedded in the packet.
        
        # For this simulation, we check the hash of the payload we just received.
        packet_hash = hashlib.sha256(str(packet.packet_id).encode() + str(packet.payload).encode()).hexdigest()
        if packet_hash in self.replay_cache:
            self.logger.log(f"Replay detected for packet {packet.packet_id}. Dropping.", "WARNING")
            return
        self.replay_cache.add(packet_hash)
        
        delay = 0.0
        next_hop = None

        # Decryption if Onion
        if packet.type == "ONION":
            try:
                next_hop, delay, inner_content = self.crypto.decrypt_onion_layer(packet.payload)
                # Update packet for next hop
                packet.payload = inner_content
            except Exception as e:
                self.logger.log(f"Decryption failed for packet {packet.packet_id}: {e}", "ERROR")
                return
        else:
            # LEGACY / PLAIN MODE
            if not packet.route:
                self.logger.log("Packet has no route!", "ERROR")
                return

            try:
                current_index = packet.route.index(self.hostname)
                if current_index < len(packet.route) - 1:
                    next_hop = packet.route[current_index + 1]
                else:
                    self.logger.log("Packet reached end of route at mix? Should be Receiver.", "WARNING")
                    return
            except ValueError:
                 self.logger.log(f"Current node {self.hostname} not in packet route {packet.route}", "ERROR")
                 return
            
            # Legacy: If strategy is poisson but no delay in packet, assign a local random delay
            if self.strategy == 'poisson':
                mu = self.config.get('mix_settings', {}).get('mu', 0.5)
                delay = random.expovariate(1.0/mu)

        # Schedule
        send_time = time.time() + delay
        scheduled = ScheduledPacket(packet, send_time, next_hop)
        
        with self.lock:
            heapq.heappush(self.scheduler, scheduled)
            self.logger.log(f"Packet scheduled for +{delay:.4f}s. Queue size: {len(self.scheduler)}")

    def _mixing_loop(self):
        # Continuous loop to check scheduler
        while self.running:
            now = time.time()
            to_send = []
            
            with self.lock:
                while self.scheduler and self.scheduler[0].send_time <= now:
                    to_send.append(heapq.heappop(self.scheduler))
            
            for item in to_send:
                self._forward_packet(item.packet, item.next_hop)
                
            # Sleep briefly to prevent tight loop, but fine enough for granularity
            # If queue is empty, sleep longer. If items exist, sleep until next item or default small.
            sleep_time = 0.01
            with self.lock:
                if self.scheduler:
                    next_time = self.scheduler[0].send_time
                    gap = next_time - time.time()
                    if gap > 0:
                        sleep_time = min(gap, 0.1) # Caps sleep at 0.1s
            
            time.sleep(sleep_time)

    def _forward_packet(self, packet, next_hop_name):
        # Simulate Packet Loss
        loss_rate = self.config.get('network', {}).get('packet_loss_rate', 0.0)
        if random.random() < loss_rate:
            self.logger.log_traffic("DROPPED_SIM", packet)
            self.logger.log(f"Simulating packet loss for {packet.packet_id}", "INFO")
            return

        if next_hop_name:
            if next_hop_name in self.network_map:
                next_ip, next_port = self.network_map[next_hop_name]
                self.logger.log(f"Forwarding packet {packet.packet_id} to {next_hop_name}")
                self.send_packet(packet, next_ip, next_port)
            else:
                self.logger.log(f"Next hop {next_hop_name} not in map. Assuming final destination or unknown.", "WARNING")
