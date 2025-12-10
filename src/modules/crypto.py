import random
import uuid

class SURB:
    """
    Mock Single Use Reply Block.
    In a real system, this contains onion encryption layers.
    Here, it encapsulates a return route to the sender.
    """
    def __init__(self, sender_node, route_to_sender, key="mock_key"):
        self.id = str(uuid.uuid4())
        self.sender = sender_node
        self.route = route_to_sender # [Entry, Inter, Exit, Sender]
        self.encryption_key = key
        
    def to_dict(self):
        return {
            "id": self.id,
            "route": self.route,
            # In real SURB, route is encrypted. Here we expose it for simulation
            # or treat it as an opaque blob that only MixNodes (in theory) or Sender can decrypt?
            # For Stratified MixNet, Sender constructs the route. Receiver just attaches it.
            # So exposing 'route' here is fine for the simulation logic where Receiver uses it as-is.
        }
    
    @classmethod
    def from_dict(cls, data):
        surb = cls(None, data['route'])
        surb.id = data['id']
        return surb
