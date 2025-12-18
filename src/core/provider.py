from src.core.mix import MixNode

class Provider(MixNode):
    """
    Provider Node in Loopix Architecture.
    Acts as an entry/exit point for Clients.
    In this simulation, it behaves like a MixNode but conceptually
    handles Client interactions.
    """
    def __init__(self, hostname, port, config, network_map):
        super().__init__(hostname, port, config, network_map)
        self.logger.log(f"Provider {hostname} initialized.")

    # Future: Implement mailbox storage if clients are offline (polling model).
    # For now, we assume clients are online and we push packets to them.
