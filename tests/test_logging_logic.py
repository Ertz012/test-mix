import unittest
from unittest.mock import MagicMock, patch
import os
import builtins
from src.core.packet import Packet
from src.core.mix import MixNode

class TestLoggingLogic(unittest.TestCase):
    def test_mixnode_logging_v2(self):
        print("Starting V2 Test")
        
        # Patch setup using context managers for explicit control
        with patch('src.core.node.get_logger') as mock_get_logger, \
             patch('src.core.mix.os.makedirs') as mock_makedirs, \
             patch('builtins.open') as mock_open, \
             patch('src.core.mix.os.path.exists') as mock_exists, \
             patch('src.core.crypto.CryptoManager') as mock_crypto:
             
            # Setup Mock Logger
            mock_logger_instance = MagicMock()
            mock_get_logger.return_value = mock_logger_instance
            
            # Setup Mock Keys
            mock_exists.return_value = True

            # Config
            config = {
                'mix_settings': {'strategy': 'poisson', 'mu': 0.5},
                'features': {'mock_encryption': True},
                'network': {'packet_loss_rate': 0.0},
                'logging': {'log_dir': 'test_logs'}
            }
            network_map = {'sender': ('10.0.0.1', 8000), 'm1': ('10.0.0.2', 8000), 'receiver': ('10.0.0.3', 8000)}

            # Initialize MixNode
            node = MixNode('m1', 8000, config, network_map)
            
            # Create a Packet from 'sender'
            packet = Packet(payload=b"test", destination="receiver", src="sender", route=['m1', 'receiver'])
            
            # Simulate receiving packet from 'sender' IP
            sender_ip = network_map['sender'][0]
            sender_port = network_map['sender'][1]
            
            # Call handle_packet
            node.handle_packet(packet, (sender_ip, sender_port))
            
            # Verify RECEIVE log
            mock_logger_instance.log_traffic.assert_any_call("RECEIVED", packet, prev_hop="sender")
            print("Verified RECEIVED log")
            
            # Simulate Forwarding
            packet_to_forward = packet
            node._forward_packet(packet_to_forward, "receiver")
            
            # Verify FORWARD log
            mock_logger_instance.log_traffic.assert_any_call("FORWARDED", packet, next_hop="receiver")
            print("Verified FORWARDED log")
            
        print("Logging verification successful!")

if __name__ == '__main__':
    unittest.main()
