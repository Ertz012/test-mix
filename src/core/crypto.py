from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.fernet import Fernet
import json
import base64
import os

class CryptoManager:
    def __init__(self):
        self.private_key = None
        self.public_key = None

    def generate_key_pair(self):
        """Generates an RSA key pair for the node."""
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        self.public_key = self.private_key.public_key()
        return self.get_public_key_pem()

    def get_public_key_pem(self):
        """Returns the public key in PEM format (bytes)."""
        if not self.public_key:
            return None
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def load_private_key(self, pem_data):
        """Loads a private key from PEM data."""
        self.private_key = serialization.load_pem_private_key(
            pem_data,
            password=None
        )
        self.public_key = self.private_key.public_key()

    def load_public_key(self, pem_data):
        """Loads a public key from PEM data."""
        return serialization.load_pem_public_key(pem_data)

    def encrypt_onion_layer(self, content: bytes, next_hop_address: str, next_node_pub_key_pem: bytes) -> bytes:
        """
        Encrypts a layer for a specific mix node.
        Logic:
        1. Generate a symmetric key (Fernet).
        2. Encrypt the content (next_hop + inner_packet) with the symmetric key.
        3. Encrypt the symmetric key with the node's Public RSA Key.
        4. Return: EncryptedSymKey (fixed size) + EncryptedContent
        """
        # 1. Symmetric Key
        sym_key = Fernet.generate_key()
        f = Fernet(sym_key)

        # 2. Payload Structure: JSON containing next hop and the inner encrypted blob
        payload = {
            "next_hop": next_hop_address, # "IP:Port" or "NodeName"
            "content": base64.b64encode(content).decode('utf-8') # Inner onion
        }
        payload_bytes = json.dumps(payload).encode('utf-8')
        encrypted_payload = f.encrypt(payload_bytes)

        # 3. Encrypt Symmetric Key with RSA
        public_key = self.load_public_key(next_node_pub_key_pem)
        encrypted_sym_key = public_key.encrypt(
            sym_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        # 4. Combine (Length of RSA 2048 encrypted key is 256 bytes)
        # We prepend the length of the encrypted sym key just to be safe, though it's constant for 2048 bit keys.
        # Actually, let's just create a structured container
        layer_data = {
            "esk": base64.b64encode(encrypted_sym_key).decode('utf-8'),
            "ep": base64.b64encode(encrypted_payload).decode('utf-8')
        }
        return json.dumps(layer_data).encode('utf-8')

    def decrypt_onion_layer(self, packet_data: bytes):
        """
        Peels one layer of the onion.
        Returns: (next_hop, inner_content)
        """
        if not self.private_key:
            raise ValueError("Private key not set.")

        try:
            layer_json = json.loads(packet_data.decode('utf-8'))
            encrypted_sym_key = base64.b64decode(layer_json['esk'])
            encrypted_payload = base64.b64decode(layer_json['ep'])

            # Decrypt Symmetric Key
            sym_key = self.private_key.decrypt(
                encrypted_sym_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )

            # Decrypt Payload
            f = Fernet(sym_key)
            payload_bytes = f.decrypt(encrypted_payload)
            payload = json.loads(payload_bytes.decode('utf-8'))

            next_hop = payload['next_hop']
            inner_content = base64.b64decode(payload['content'])

            return next_hop, inner_content
        except Exception as e:
            # Integrity check failed or decryption error
            raise ValueError(f"Decryption failed: {e}")

    @staticmethod
    def create_onion_packet(path_nodes: list, destination_node: str, final_payload: bytes, keys_map: dict) -> bytes:
        """
        Constructs the full onion packet.
        path_nodes: List of node names/IDs in order [Mix1, Mix2, ...]
        destination_node: The final target ID.
        keys_map: Dict {node_name: public_key_pem}
        """
        crypto = CryptoManager() # Helper instance

        # Start from the innermost layer (Destination)
        # The payload for the final mix node is the actual message and the Final Destination
        # Or does the Mixnet assume the last Mix delivers to the receiver directly?
        # Let's assume the route list includes the destination as the last item?
        # Standard: Client -> Mix1 -> Mix2 -> Mix3 -> Receiver
        # Inner most layer is for Mix3. It should see "next_hop = Receiver" and "content = Message"

        # Let's adjust inputs.
        # path includes intermediate mixes. 
        # We assume the last hop in route delivers to destination.
        
        current_blob = final_payload
        next_hop = destination_node

        # Iterate backwards through the path
        for node_name in reversed(path_nodes):
            if node_name not in keys_map:
                raise ValueError(f"Missing public key for {node_name}")
            
            pub_key = keys_map[node_name]
            # Encrypt current blob for this node, instructing it to send to 'next_hop'
            current_blob = crypto.encrypt_onion_layer(current_blob, next_hop, pub_key)
            next_hop = node_name # The current node becomes the next hop for the previous one

        return current_blob
