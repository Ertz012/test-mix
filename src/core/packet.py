import json
import uuid
import time
import base64

class Packet:

    def __init__(self, payload, destination, src=None, route=None, packet_id=None, timestamp=None, type="PLAIN"):
        self.packet_id = packet_id or str(uuid.uuid4())
        self.timestamp = timestamp or time.time()
        self.src = src or "unknown"
        self.destination = destination
        self.route = route or []  # List of hops
        self.payload = payload    # The actual data (bytes or string)
        self.type = type          # "PLAIN" or "ONION"
        self.flags = {}

    def to_json(self):
        # If payload is bytes (e.g. onion), encode it
        data_to_send = self.payload
        if isinstance(self.payload, bytes):
            data_to_send = base64.b64encode(self.payload).decode('utf-8')
            
        return json.dumps({
            "id": self.packet_id,
            "ts": self.timestamp,
            "src": self.src,
            "dst": self.destination,
            "route": self.route,
            "data": data_to_send,
            "type": self.type,
            "flags": self.flags
        })

    @classmethod
    def from_json(cls, json_str):
        data = json.loads(json_str)
        
        payload = data["data"]
        pkt_type = data.get("type", "PLAIN")
        
        # If ONION, we expect base64 encoded bytes
        if pkt_type == "ONION" and isinstance(payload, str):
            try:
                payload = base64.b64decode(payload)
            except:
                pass # Keep as string if decode fails?
                
        pkt = cls(
            payload=payload,
            destination=data["dst"],
            src=data.get("src"),
            route=data.get("route", []),
            packet_id=data["id"],
            timestamp=data["ts"],
            type=pkt_type
        )
        pkt.flags = data.get("flags", {})
        return pkt

    def __repr__(self):
        return f"<Packet {self.packet_id} [{self.type}] -> {self.destination}>"
