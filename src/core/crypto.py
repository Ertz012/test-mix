from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.fernet import Fernet
import json
import base64
import os
import uuid

class RealCryptoImplementation:
    def __init__(self):
        self.private_key = None
        self.public_key = None

    def generate_key_pair(self):
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        self.public_key = self.private_key.public_key()
        return self.get_public_key_pem()

    def get_public_key_pem(self):
        if not self.public_key:
            return None
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def load_private_key_from_file(self, path):
        with open(path, 'rb') as f:
            pem_data = f.read()
            self.private_key = serialization.load_pem_private_key(pem_data, password=None)
            self.public_key = self.private_key.public_key()

    def save_private_key_to_file(self, path):
        if not self.private_key:
            raise ValueError("No private key to save.")
        pem_data = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        with open(path, 'wb') as f:
            f.write(pem_data)

    def load_public_key(self, pem_data):
        return serialization.load_pem_public_key(pem_data)

    def encrypt_onion_layer(self, content: bytes, next_hop_address: str, next_node_pub_key_pem: bytes, delay: float = 0.0) -> bytes:
        sym_key = Fernet.generate_key()
        f = Fernet(sym_key)

        payload = {
            "next_hop": next_hop_address,
            "delay": delay,
            "content": base64.b64encode(content).decode('utf-8')
        }
        payload_bytes = json.dumps(payload).encode('utf-8')
        encrypted_payload = f.encrypt(payload_bytes)

        public_key = self.load_public_key(next_node_pub_key_pem)
        encrypted_sym_key = public_key.encrypt(
            sym_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        layer_data = {
            "esk": base64.b64encode(encrypted_sym_key).decode('utf-8'),
            "ep": base64.b64encode(encrypted_payload).decode('utf-8')
        }
        return json.dumps(layer_data).encode('utf-8')

    def decrypt_onion_layer(self, packet_data: bytes):
        if not self.private_key:
            raise ValueError("Private key not set.")

        try:
            layer_json = json.loads(packet_data.decode('utf-8'))
            encrypted_sym_key = base64.b64decode(layer_json['esk'])
            encrypted_payload = base64.b64decode(layer_json['ep'])

            sym_key = self.private_key.decrypt(
                encrypted_sym_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )

            f = Fernet(sym_key)
            payload_bytes = f.decrypt(encrypted_payload)
            payload = json.loads(payload_bytes.decode('utf-8'))

            next_hop = payload['next_hop']
            delay = payload.get('delay', 0.0)
            inner_content = base64.b64decode(payload['content'])

            return next_hop, delay, inner_content
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")


class MockCryptoImplementation:
    def __init__(self):
        self.key_id = str(uuid.uuid4()) # Mock identity

    def generate_key_pair(self):
        # Return a dummy PEM string
        return f"MOCK_PUB_KEY_{self.key_id}".encode('utf-8')

    def get_public_key_pem(self):
        return f"MOCK_PUB_KEY_{self.key_id}".encode('utf-8')

    def load_private_key_from_file(self, path):
        # No actual loading needed, just simulation
        pass

    def save_private_key_to_file(self, path):
        # Touch file to satisfy checks
        with open(path, 'wb') as f:
            f.write(f"MOCK_PRIV_KEY_{self.key_id}".encode('utf-8'))

    def encrypt_onion_layer(self, content: bytes, next_hop_address: str, next_node_pub_key_pem: bytes, delay: float = 0.0) -> bytes:
        # Simple JSON wrap without encryption
        # We base64 encode content to keep interface consistent (bytes in/out)
        payload = {
            "next_hop": next_hop_address,
            "delay": delay,
            "content": base64.b64encode(content).decode('utf-8'),
            "mock_marker": "MOCK_ENCRYPTED"
        }
        return json.dumps(payload).encode('utf-8')

    def decrypt_onion_layer(self, packet_data: bytes):
        try:
            payload = json.loads(packet_data.decode('utf-8'))
            if payload.get("mock_marker") != "MOCK_ENCRYPTED":
                 raise ValueError("Not a valid mock packet")
            
            next_hop = payload['next_hop']
            delay = payload.get('delay', 0.0)
            inner_content = base64.b64decode(payload['content'])
            
            return next_hop, delay, inner_content
        except Exception as e:
            raise ValueError(f"Mock Decryption failed: {e}")


class CryptoManager:
    def __init__(self, mock_mode=False):
        self.mock_mode = mock_mode
        if self.mock_mode:
            self.impl = MockCryptoImplementation()
        else:
            self.impl = RealCryptoImplementation()

    def generate_key_pair(self):
        return self.impl.generate_key_pair()

    def get_public_key_pem(self):
        return self.impl.get_public_key_pem()

    def load_private_key_from_file(self, path):
        self.impl.load_private_key_from_file(path)

    def save_private_key_to_file(self, path):
        self.impl.save_private_key_to_file(path)

    def encrypt_onion_layer(self, content, next_hop, pub_key, delay=0.0):
        return self.impl.encrypt_onion_layer(content, next_hop, pub_key, delay)

    def decrypt_onion_layer(self, packet_data):
        return self.impl.decrypt_onion_layer(packet_data)

    def create_onion_packet(self, path_nodes: list, destination_node: str, final_payload: bytes, keys_map: dict, delays: dict = None) -> bytes:
        """
        Constructs the full onion packet using the selected implementation.
        """
        current_blob = final_payload
        next_hop = destination_node
        
        if delays is None:
            delays = {}

        # Iterate backwards through the path
        for node_name in reversed(path_nodes):
            if node_name not in keys_map:
                raise ValueError(f"Missing public key for {node_name}")
            
            pub_key = keys_map[node_name]
            delay = delays.get(node_name, 0.0)
            
            # Encrypt current blob for this node
            current_blob = self.encrypt_onion_layer(current_blob, next_hop, pub_key, delay)
            next_hop = node_name 

        return current_blob
