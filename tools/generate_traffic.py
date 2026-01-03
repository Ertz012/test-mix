
import json
import random
import pickle
import time
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from src.core.packet import Packet
from src.core.crypto import CryptoManager
from src.modules.routing import Routing

def load_config(path='config/config.json'):
    with open(path, 'r') as f:
        return json.load(f)

def load_network_map(path='network_map.json'):
    if not os.path.exists(path):
        print(f"Error: {path} not found. Run topology first.")
        sys.exit(1)
    with open(path, 'r') as f:
        return json.load(f)

def load_node_keys(nodes):
    keys = {}
    # If mock mode is likely used, keys might not exist or be needed in the same way, 
    # but we load if available.
    for node in nodes:
        key_path = f"keys/{node}.pem"
        if os.path.exists(key_path):
            with open(key_path, 'rb') as f:
                keys[node] = f.read()
    # Return empty dict if no keys found, which is fine for mock mode usually
    return keys

def generate_traffic(config_path='config/config.json', output_file='traffic_data.bin'):
    config = load_config(config_path)
    network_map = load_network_map()
    
    # Setup Routing
    routing = Routing(config, network_map)
    # Parameters
    rate = config['traffic']['rate_packets_per_sec']
    duration = config['traffic']['duration_sec']
    
    # Identify senders/receivers (support both legacy s/r and Loopix c/c)
    senders = [n for n in network_map if n.startswith('s') or n.startswith('c')]
    receivers = [n for n in network_map if n.startswith('r') or n.startswith('c')]
    
    # Use mock encryption if configured
    mock_mode = config['features'].get('mock_encryption', False)
    crypto = CryptoManager(mock_mode=mock_mode)

    
    if not senders or not receivers:
        print("Error: No senders or receivers found.")
        return

    print(f"Generating traffic for {len(senders)} senders over {duration} seconds at {rate} pkt/s (MockMode={mock_mode})...")

    
    # Data Storage: {sender_name: [Packet, ...]}
    traffic_data = {s: [] for s in senders}
    
    # Generate
    total_packets = int(rate * duration)
    
    # Pre-loading keys for all nodes in potential routes might be heavy?
    # No, we load all needed keys.
    # We need keys for all Mixes + Receivers.
    all_nodes = [n for n in network_map if not n.startswith('s')] # Sender doesn't need Own Key for encryption usually.
    all_keys = load_node_keys(all_nodes)
    
    use_encryption = config['features'].get('layered_encryption', False)
    
    for sender in senders:
        print(f"  Processing {sender}...")
        for i in range(total_packets):
            # Timestamp relative to start (0.0 to duration)
            # Add some randomness? Poison distribution? 
            # For now: simple constant rate + jitter
            timestamp = (i / rate) + random.uniform(0, 0.01)
            
            receiver = random.choice(receivers)
            payload = f"Msg from {sender} to {receiver} [Precalc {i}]"
            
            # Route
            route = routing.get_path(sender, receiver)
            
            # Packet
            pkt = Packet(payload, receiver, route)
            pkt.timestamp = timestamp # Relative timestamp
            
            # Encryption (copied from client.py logic)
            final_packet = pkt
            if use_encryption:
                inner_bytes = pkt.to_json().encode('utf-8')
                route_nodes = pkt.route
                
                # Filter keys
                keys_map = {n: all_keys[n] for n in route_nodes if n in all_keys}
                
                if len(keys_map) == len(route_nodes):
                    try:
                        onion_blob = crypto.create_onion_packet(
                            route_nodes, 
                            pkt.destination, 
                            inner_bytes, 
                            keys_map
                        )
                        first_hop = pkt.route[0]
                        final_packet = Packet(onion_blob, pkt.destination, route=[first_hop], type="ONION")
                        # Outer packet inherits relative timestamp
                        final_packet.timestamp = timestamp
                    except Exception as e:
                        print(f"    Encryption failed: {e}")
                else:
                    print("    Missing keys for onion routing. Skipping encryption.")

            traffic_data[sender].append(final_packet)
            
    # Save
    with open(output_file, 'wb') as f:
        pickle.dump(traffic_data, f)
        
    print(f"Saved generated traffic to {output_file}")

if __name__ == "__main__":
    generate_traffic()
