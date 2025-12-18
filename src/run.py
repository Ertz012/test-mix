import argparse
import json
import time
import sys
import os

# Add current directory to path so we can import src modules
sys.path.append(os.getcwd())

from src.core.mix import MixNode
from src.core.client import Client
from src.core.provider import Provider

def load_config(path):
    with open(path, 'r') as f:
        return json.load(f)

def main():
    parser = argparse.ArgumentParser(description="Run a Mix-Net node")
    parser.add_argument("--role", required=True, choices=['mix', 'sender', 'receiver', 'client', 'provider'], help="Role of this node")
    parser.add_argument("--config", required=True, help="Path to config file")
    parser.add_argument("--hostname", required=True, help="Hostname (e.g., h_entry_1)")
    parser.add_argument("--network-map", required=False, help="JSON file with network map (host->ip:port)")
    
    args = parser.parse_args()
    config = load_config(args.config)
    
    # Load Network Map
    network_map = {}
    if args.network_map:
        with open(args.network_map, 'r') as f:
            network_map = json.load(f)
            
    # Determine Port
    port = 8000
    if args.hostname in network_map:
        port = network_map[args.hostname][1]
    
    node = None
    if args.role == 'mix':
        node = MixNode(args.hostname, port, config, network_map)
    elif args.role == 'client':
        node = Client(args.hostname, port, config, network_map)
    elif args.role == 'provider':
        node = Provider(args.hostname, port, config, network_map)
    # Maintain legacy compatibility or map legacy roles to Client
    elif args.role == 'sender':
        node = Client(args.hostname, port, config, network_map) # Map to Client
    elif args.role == 'receiver':
        node = Client(args.hostname, port, config, network_map) # Map to Client
    
    if node:
        node.start()
        
        if args.role == 'client' or args.role == 'sender':
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
