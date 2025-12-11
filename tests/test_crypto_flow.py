import unittest
import json
import base64
import os
import shutil
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.crypto import CryptoManager
from src.core.packet import Packet
from src.core.mix import MixNode

# Mock helper for MixNode to avoid starting threads/networking
class MockMix(MixNode):
    def __init__(self, name):
        # Minimal init
        self.hostname = name
        self.crypto = CryptoManager()
        self.public_key_pem = self.crypto.generate_key_pair()
        self.replay_cache = set()
        # No network map or starting threads

    def process(self, packet):
        # Simulate handle_packet logic mainly for crypto
        if packet.type == "ONION":
            try:
                next_hop, inner_content = self.crypto.decrypt_onion_layer(packet.payload)
                packet.payload = inner_content
                packet.next_hop_temp = next_hop
                return packet, next_hop
            except Exception as e:
                print(f"[{self.hostname}] Decryption error: {e}")
                raise e
        return packet, None

class TestCryptoFlow(unittest.TestCase):
    def setUp(self):
        self.mix1 = MockMix("mix1")
        self.mix2 = MockMix("mix2")
        
        # Receiver setup
        self.receiver_crypto = CryptoManager() 
        # This generates keys and stores private key internally in self.receiver_crypto
        self.receiver_public_key_pem = self.receiver_crypto.generate_key_pair()
        
        self.keys_map = {
            "mix1": self.mix1.public_key_pem,
            "mix2": self.mix2.public_key_pem,
            "receiver": self.receiver_public_key_pem
        }

    def test_onion_flow(self):
        print("\n--- Testing Onion Flow ---")
        payload = "Hello Secret World"
        route = ["mix1", "mix2", "receiver"]
        
        # 1. Client Encrypts
        sender_crypto = CryptoManager()
        
        # Original Packet (Inner)
        inner_packet = Packet(payload, "receiver", route)
        inner_bytes = inner_packet.to_json().encode('utf-8')
        
        # Create Onion
        print("Encrypting onion layers...")
        onion_blob = sender_crypto.create_onion_packet(route, "receiver", inner_bytes, self.keys_map)
        
        # Outer Packet
        packet = Packet(onion_blob, "receiver", route=["mix1"], type="ONION")
        print(f"Outer Packet created. Size: {len(onion_blob)} bytes")

        # 2. Mix 1 Processing
        print("Mix1 receiving...")
        packet, next_hop = self.mix1.process(packet)
        self.assertEqual(next_hop, "mix2")
        self.assertTrue(packet.type == "ONION")
        print("Mix1 decrypted layer. Next hop: mix2")

        # 3. Mix 2 Processing
        print("Mix2 receiving...")
        packet, next_hop = self.mix2.process(packet)
        self.assertEqual(next_hop, "receiver")
        print("Mix2 decrypted layer. Next hop: receiver")

        # 4. Receiver Processing
        print("Receiver receiving...")
        next_hop, final_content = self.receiver_crypto.decrypt_onion_layer(packet.payload)
        
        # Interpret final content
        if isinstance(final_content, bytes):
            final_content = final_content.decode('utf-8')
        
        final_packet = Packet.from_json(final_content)
        
        print(f"Receiver decrypted: {final_packet.payload}")
        self.assertEqual(final_packet.payload, payload)
        self.assertEqual(final_packet.packet_id, inner_packet.packet_id)

if __name__ == "__main__":
    unittest.main()
