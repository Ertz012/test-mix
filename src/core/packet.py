import json
import uuid
import time
import base64

class Packet:
    def __init__(self, payload, destination, route=None, packet_id=None, timestamp=None):
        self.packet_id = packet_id or str(uuid.uuid4())
        self.timestamp = timestamp or time.time()
        self.destination = destination
        self.route = route or []  # List of hops
        self.payload = payload    # The actual data (bytes or string)
        self.flags = {}

    def to_json(self):
        return json.dumps({
            "id": self.packet_id,
            "ts": self.timestamp,
            "dst": self.destination,
            "route": self.route,
            "data": self.payload,
            "flags": self.flags
        })

    @classmethod
    def from_json(cls, json_str):
        data = json.loads(json_str)
        pkt = cls(
            payload=data["data"],
            destination=data["dst"],
            route=data.get("route", []),
            packet_id=data["id"],
            timestamp=data["ts"]
        )
        pkt.flags = data.get("flags", {})
        return pkt

    def __repr__(self):
        return f"<Packet {self.packet_id} -> {self.destination}>"
