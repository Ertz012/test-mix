import threading
import time
import json
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.getcwd()))

from src.core.mix import MixNode
from src.core.client import Sender, Receiver
from src.utils.logger import get_logger

def anonymous_test():
    # Setup Config
    config = {
        "topology": {"layers": ["entry", "intermediate", "exit"], "nodes_per_layer": 1},
        "mix_settings": {"strategy": "timed_pool", "pool_size": 1, "timeout": 0.1},
        "features": {
            "retransmission": True,              # Need retransmission to trigger ACKs
            "anonymous_return_addresses": True   # Trigger usage of SURBs
        },
        "traffic": {"rate_packets_per_sec": 1, "duration_sec": 1, "mode": "random", "precalc_file": ""},
        "logging": {"level": "INFO", "log_dir": "logs_anonymous"}
    }
    
    # Network Map (Port 9500)
    base_port = 9500
    network_map = {
        "h_sender_1": ("127.0.0.1", base_port),
        "h_entry_1": ("127.0.0.1", base_port + 1),
        "h_inter_1": ("127.0.0.1", base_port + 2),
        "h_exit_1": ("127.0.0.1", base_port + 3),
        "h_recv_1": ("127.0.0.1", base_port + 4)
    }
    
    nodes = []
    
    # Create Nodes
    recv = Receiver("h_recv_1", network_map["h_recv_1"][1], config, network_map)
    nodes.append(recv)
    
    exit_node = MixNode("h_exit_1", network_map["h_exit_1"][1], config, network_map)
    nodes.append(exit_node)
    
    inter_node = MixNode("h_inter_1", network_map["h_inter_1"][1], config, network_map)
    nodes.append(inter_node)
    
    entry_node = MixNode("h_entry_1", network_map["h_entry_1"][1], config, network_map)
    nodes.append(entry_node)
    
    sender = Sender("h_sender_1", network_map["h_sender_1"][1], config, network_map)
    nodes.append(sender)
    
    for n in nodes:
        n.start()
        
    print("Nodes started. Anon SURBs: True")
    
    time.sleep(1)
    sender.start_sending()
    
    time.sleep(3)
    print("Test finished.")
    pass

if __name__ == "__main__":
    anonymous_test()
