import socket
import threading
import json
import time
from src.utils.logger import get_logger
from src.core.packet import Packet

class Node:
    def __init__(self, hostname, port, config):
        self.hostname = hostname
        self.port = port
        self.config = config
        log_dir = config.get('logging', {}).get('log_dir', 'logs')
        self.logger = get_logger(hostname, log_dir)
        self.running = False
        self.sock = None

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(('0.0.0.0', self.port))
        self.sock.listen(5)
        self.running = True
        self.logger.log(f"Started node on port {self.port}")
        
        server_thread = threading.Thread(target=self._accept_loop, daemon=True)
        server_thread.start()

    def _accept_loop(self):
        while self.running:
            try:
                client_sock, addr = self.sock.accept()
                threading.Thread(target=self._handle_client, args=(client_sock, addr)).start()
            except Exception as e:
                if self.running:
                    self.logger.log(f"Error accepting connection: {e}", "ERROR")

    def _handle_client(self, client_sock, addr):
        try:
            # Simple length-prefixed or delimiter-based protocol needed for stream
            # For prototype, we'll read all (assuming connection per packet)
            # or do a simple length header.
            # Let's do simple: Connect, Send JSON, Close.
            data = b""
            while True:
                chunk = client_sock.recv(4096)
                if not chunk:
                    break
                data += chunk
            
            if data:
                try:
                    packet = Packet.from_json(data.decode('utf-8'))
                    self.handle_packet(packet, addr)
                except json.JSONDecodeError:
                    self.logger.log("Failed to decode packet JSON", "ERROR")
                    
        except Exception as e:
            self.logger.log(f"Error handling client: {e}", "ERROR")
        finally:
            client_sock.close()

    def handle_packet(self, packet, source_address):
        raise NotImplementedError("Subclasses must implement handle_packet")

    def send_packet(self, packet, next_hop_ip, next_hop_port, next_hop_name=None):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((next_hop_ip, next_hop_port))
            s.sendall(packet.to_json().encode('utf-8'))
            s.close()
            
            # Log successful send with details
            self.logger.log(f"Sent packet {packet.packet_id} to {next_hop_name or 'unknown'} ({next_hop_ip}:{next_hop_port})")
            
            # Log traffic event with resolved next_hop if available
            nh_log = next_hop_name if next_hop_name else f"{next_hop_ip}:{next_hop_port}"
            # For SENT events, next_hop is where we sent it.
            self.logger.log_traffic("SENT", packet, next_hop=nh_log)
            return True 
        except Exception as e:
            self.logger.log(f"Failed to send to {next_hop_ip}:{next_hop_port}: {e}", "ERROR")
            return False
