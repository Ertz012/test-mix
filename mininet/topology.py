from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Host
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel, info
from mininet.cli import CLI

import datetime
import time
import json
import os


# I will replace the build() method entirely to use a single switch.
class SingleSwitchTopo(Topo):
    "Single Switch Topology for MixNet Overlay"
    def build(self):
        switch = self.addSwitch('sw1')
        
        # Load Config if possible to get counts, else defaults
        # Since Topo is instantiated by `mn`, passing args is tricky without custom classes.
        # We'll try to load config.json directly.
        config_path = "config/config.json"
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                topo_conf = config.get('topology', {})
                num_clients = topo_conf.get('num_clients', 5)
                num_providers = topo_conf.get('num_providers', 3)
                layer_size = topo_conf.get('nodes_per_layer', 3)
        else:
            num_clients = 5
            num_providers = 3
            layer_size = 3
        
        # Hosts
        host_idx = 1
        
        # Helper to add
        def add_mix_node(prefix, count):
            nonlocal host_idx
            for i in range(1, count + 1):
                h = self.addHost(f'{prefix}{i}', ip=f'10.0.0.{host_idx}/24')
                self.addLink(h, switch)
                host_idx += 1
                
        # Loopix Topology
        add_mix_node('c', num_clients)    # Clients
        add_mix_node('p', num_providers)  # Providers
        add_mix_node('e', layer_size)     # Entry Mixes
        add_mix_node('i', layer_size)     # Intermediate Mixes
        add_mix_node('x', layer_size)     # Exit Mixes

    
topos = { 'mixnet': ( lambda: SingleSwitchTopo() ) }

