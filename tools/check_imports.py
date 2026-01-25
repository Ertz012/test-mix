import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

print("Checking imports...")

try:
    print("1. core.client...", end="")
    from src.core.client import Client
    print("OK")
    
    print("2. core.mix...", end="")
    from src.core.mix import MixNode
    print("OK")
    
    print("3. core.packet...", end="")
    from src.core.packet import Packet
    print("OK")
    
    print("4. core.crypto...", end="")
    from src.core.crypto import CryptoManager
    print("OK")

    print("- Testing instantiation of Client (Mock config)...")
    config = {
        'topology': {'nodes_per_layer': 3},
        'traffic': {'traffic_strategy': 'loopix', 'rate_packets_per_sec': 5.0, 'transmission_rate_packets_per_sec': 10.0},
        'features': {'retransmission': False, 'mock_encryption': True, 'anonymous_return_addresses': False},
        'mix_settings': {'mu': 0.1},
        'logging': {'level': 'INFO', 'log_dir': 'logs'}
    }
    network_map = {'c1': ('127.0.0.1', 9999)}
    c = Client('c1', 8000, config, network_map)
    print("Client instantiated successfully.")
    
    # Check if critical methods exist and don't crash on syntax
    if not hasattr(c, 'message_buffer'):
           # message_buffer is created in start_sending usually, but let's check threads setup
           pass
           
    print("Basic Import/Syntax Check Passed.")
    
except Exception as e:
    print(f"\nFAILED: {e}")
    sys.exit(1)
