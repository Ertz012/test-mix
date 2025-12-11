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
        
        # Config (Re-used)
        num_senders = 3
        num_receivers = 3
        layer_size = 12
        
        # Hosts
        host_idx = 1
        
        # Helper to add
        def add_mix_node(prefix, count):
            nonlocal host_idx
            for i in range(1, count + 1):
                h = self.addHost(f'{prefix}{i}', ip=f'10.0.0.{host_idx}/24')
                self.addLink(h, switch)
                host_idx += 1
                
        add_mix_node('s', num_senders)
        add_mix_node('e', layer_size)
        add_mix_node('i', layer_size)
        add_mix_node('x', layer_size)
        add_mix_node('r', num_receivers)

    
topos = { 'mixnet': ( lambda: SingleSwitchTopo() ) }

