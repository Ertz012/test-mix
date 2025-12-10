import argparse
import json
import time
import sys
import os

# Add current directory to path so we can import src modules
sys.path.append(os.getcwd())

from src.core.mix import MixNode
from src.core.client import Sender, Receiver

def load_config(path):
    with open(path, 'r') as f:
        return json.load(f)

def main():
    parser = argparse.ArgumentParser(description="Run a Mix-Net node")
    parser.add_argument("--role", required=True, choices=['mix', 'sender', 'receiver'], help="Role of this node")
    parser.add_argument("--config", required=True, help="Path to config file")
    parser.add_argument("--hostname", required=True, help="Hostname (e.g., h_entry_1)")
    parser.add_argument("--network-map", required=False, help="JSON file with network map (host->ip:port)")
    # For simple local testing, we might pass network map differently or assume localhost with port offsetting?
    # In Mininet, DNS/Hosts file handles names, but we need ports.
    # Let's assume for now we might pass a JSON string or file for the map.
    
    args = parser.parse_args()
    config = load_config(args.config)
    
    # Load Network Map
    # For now, let's allow passing it as a file
    network_map = {}
    if args.network_map:
        with open(args.network_map, 'r') as f:
            network_map = json.load(f)
            
    # Determine Port
    # If network map provided, look up my port.
    # Else use default or derive from hostname (for testing).
    port = 8000
    if args.hostname in network_map:
        port = network_map[args.hostname][1]
    else:
        # Fallback/Auto-assign for local testing if not in map
        # This is a bit hacky but useful for single-machine tests without strict map
        pass

    if args.role == 'mix':
        node = MixNode(args.hostname, port, config, network_map)
    elif args.role == 'sender':
        node = Sender(args.hostname, port, config, network_map)
    elif args.role == 'receiver':
        node = Receiver(args.hostname, port, config, network_map)
    
    node.start()
    
    if args.role == 'sender':
        # Sender needs to trigger traffic
        # Give some time for network to settle?
        time.sleep(2)
        node.start_sending()
        
    # Keep alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")

if __name__ == "__main__":
    main()
