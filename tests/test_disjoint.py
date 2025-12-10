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

def disjoint_test():
    # Setup Config
    config = {
        "topology": {"layers": ["entry", "intermediate", "exit"], "nodes_per_layer": 2}, # Need at least 2 nodes/layer for disjoint
        "mix_settings": {"strategy": "timed_pool", "pool_size": 1, "timeout": 0.1},
        "features": {"parallel_paths": True},
        "traffic": {"rate_packets_per_sec": 1, "duration_sec": 1, "mode": "random", "precalc_file": ""},
        "logging": {"level": "INFO", "log_dir": "logs_disjoint"}
    }
    
    # Network Map (Port 9400)
    base_port = 9400
    # We need 2 entry, 2 inter, 2 exit
    network_map = {
        "h_sender_1": ("127.0.0.1", base_port),
        "h_entry_1": ("127.0.0.1", base_port + 1),
        "h_entry_2": ("127.0.0.1", base_port + 2),
        "h_inter_1": ("127.0.0.1", base_port + 3),
        "h_inter_2": ("127.0.0.1", base_port + 4),
        "h_exit_1": ("127.0.0.1", base_port + 5),
        "h_exit_2": ("127.0.0.1", base_port + 6),
        "h_recv_1": ("127.0.0.1", base_port + 7)
    }
    
    nodes = []
    
    # Instantiate all Mixes
    mixes = ["h_entry_1", "h_entry_2", "h_inter_1", "h_inter_2", "h_exit_1", "h_exit_2"]
    for m in mixes:
        nodes.append(MixNode(m, network_map[m][1], config, network_map))
        
    nodes.append(Receiver("h_recv_1", network_map["h_recv_1"][1], config, network_map))
    sender = Sender("h_sender_1", network_map["h_sender_1"][1], config, network_map)
    nodes.append(sender)
    
    for n in nodes:
        n.start()
        
    print("Nodes started. Parallel Paths: True")
    
    time.sleep(1)
    sender.start_sending()
    
    time.sleep(3)
    print("Test finished.")
    pass

if __name__ == "__main__":
    disjoint_test()
