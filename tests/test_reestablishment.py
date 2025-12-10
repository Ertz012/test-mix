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

def reestablishment_test():
    # Setup Config with Retransmission AND Path Re-establishment AND Packet Loss
    config = {
        "topology": {"layers": ["entry", "intermediate", "exit"], "nodes_per_layer": 1},
        "mix_settings": {"strategy": "timed_pool", "pool_size": 1, "timeout": 0.2},
        "features": {"retransmission": True, "path_reestablishment": True},
        "network": {"packet_loss_rate": 0.5},
        "traffic": {"rate_packets_per_sec": 2, "duration_sec": 2, "mode": "random", "precalc_file": ""},
        "logging": {"level": "INFO", "log_dir": "logs_reest"}
    }
    
    # Network Map (Port 9300)
    base_port = 9300
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
    
    # Start Nodes
    for n in nodes:
        n.start()
        
    print("Nodes started. Loss: 0.5. Re-est: True")
    
    # Start Traffic
    time.sleep(1)
    sender.start_sending()
    
    # Wait for completion + retransmissions
    time.sleep(8)
    print("Test finished.")
    
    pass

if __name__ == "__main__":
    reestablishment_test()
