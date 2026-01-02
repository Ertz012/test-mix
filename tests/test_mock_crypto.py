import unittest
import json
import base64
import os
import sys

# Ensure src is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.crypto import CryptoManager

class TestMockCrypto(unittest.TestCase):
    def setUp(self):
        # Enable mock mode
        self.crypto_a = CryptoManager(mock_mode=True)
        self.crypto_b = CryptoManager(mock_mode=True)
        
    def test_key_generation_is_fast_and_mock(self):
        # Should return a mock PEM string, not a huge RSA key
        pub_key = self.crypto_a.generate_key_pair()
        self.assertTrue(b"MOCK_PUB_KEY" in pub_key)
        
    def test_mock_onion_layer_encrypt_decrypt(self):
        payload = b"Secret Payload"
        next_hop = "mix2"
        pub_key_b = self.crypto_b.get_public_key_pem()
        
        # Encrypt
        encrypted = self.crypto_a.encrypt_onion_layer(payload, next_hop, pub_key_b, delay=1.5)
        
        # It should be a JSON containing "mock_marker"
        data = json.loads(encrypted.decode('utf-8'))
        self.assertEqual(data.get("mock_marker"), "MOCK_ENCRYPTED")
        self.assertEqual(data.get("next_hop"), next_hop)
        self.assertEqual(data.get("delay"), 1.5)
        
        # Decrypt
        # Note: In mock mode, we don't strictly need private key matching implementation-wise 
        # (it's up to implementation), but logically B should receive it.
        # Our mock implementation doesn't verify receiver, just unwraps.
        hop, delay, content = self.crypto_b.decrypt_onion_layer(encrypted)
        
        self.assertEqual(hop, next_hop)
        self.assertEqual(delay, 1.5)
        self.assertEqual(content, payload)

    def test_create_onion_packet_mock_flow(self):
        # Setup path
        path = ["mix1", "mix2"]
        dest = "recipient"
        keys_map = {
            "mix1": b"MOCK_PUB_KEY_1",
            "mix2": b"MOCK_PUB_KEY_2"
        }
        
        final_payload = b"Final Message"
        
        # Create full onion
        packet_blob = self.crypto_a.create_onion_packet(path, dest, final_payload, keys_map)
        
        # Let's peel manually to verify layers
        
        # Layer 1 (Outer - for Mix1)
        layer1_json = json.loads(packet_blob.decode('utf-8'))
        self.assertEqual(layer1_json["next_hop"], "mix2") # Logic: Outer layer is FOR mix1, telling it to send to mix2
        # Wait, create_onion_packet logic:
        # loop reversed:
        # 1. mix2: encrypt(payload, dest) -> blob2
        # 2. mix1: encrypt(blob2, mix2) -> blob1
        # RESULT is blob1.
        # But blob1 contains info for Mix1.
        # Mix1 decrypts blob1 -> sees payload=blob2, next_hop=mix2.
        
        # So blob1 (packet_blob) IS what Mix1 receives? 
        # Actually in `create_onion_packet`:
        # current_blob = final_payload
        # next_hop = destination_node (recipient)
        # Loop for mix2: encrypt(current_blob, next_hop=recipient) -> new current_blob
        # next_hop = mix2
        # Loop for mix1: encrypt(current_blob, next_hop=mix2) -> new current_blob
        
        # So checking layer1:
        # In Mock implementation, encrypt_onion_layer produces JSON with "next_hop".
        # So layer1 outer check:
        # It was encrypted FOR mix1. So it contains next_hop = mix2.
        
        self.assertEqual(layer1_json.get("mock_marker"), "MOCK_ENCRYPTED")
        self.assertEqual(layer1_json.get("next_hop"), "mix2") 
        
        # "Decrypt" / Unwrap Layer 1
        inner_blob_b64 = layer1_json["content"]
        inner_blob = base64.b64decode(inner_blob_b64)
        
        # Layer 2 (for Mix2)
        layer2_json = json.loads(inner_blob.decode('utf-8'))
        self.assertEqual(layer2_json.get("next_hop"), dest)
        
        # "Decrypt" / Unwrap Layer 2
        final_content_b64 = layer2_json["content"]
        final_content = base64.b64decode(final_content_b64)
        
        self.assertEqual(final_content, final_payload)

if __name__ == "__main__":
    unittest.main()
