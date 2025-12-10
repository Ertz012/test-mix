from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Host
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel, info
from mininet.cli import CLI

import time
import json
import os

class StratifiedTopo(Topo):
    "Stratified MixNet Topology"
    
    def build(self):
        # Config
        num_senders = 3
        num_receivers = 3
        layer_size = 12
        
        senders = []
        entries = []
        inters = []
        exits = []
        receivers = []
        
        # Create Hosts
        for i in range(1, num_senders + 1):
            h = self.addHost(f'h_sender_{i}')
            senders.append(h)
            
        for i in range(1, layer_size + 1):
            h = self.addHost(f'h_entry_{i}')
            entries.append(h)
            
        for i in range(1, layer_size + 1):
            h = self.addHost(f'h_inter_{i}')
            inters.append(h)
            
        for i in range(1, layer_size + 1):
            h = self.addHost(f'h_exit_{i}')
            exits.append(h)
            
        for i in range(1, num_receivers + 1):
            h = self.addHost(f'h_recv_{i}')
            receivers.append(h)
            
        # Create Links (Fully Connected between layers)
        
        # Sender -> Entry
        for s in senders:
            for e in entries:
                self.addLink(s, e)
                
        # Entry -> Inter
        for e in entries:
            for i in inters:
                self.addLink(e, i)
                
        # Inter -> Exit
        for i in inters:
            for x in exits:
                self.addLink(i, x)
                
        # Exit -> Receiver
        for x in exits:
            for r in receivers:
                self.addLink(x, r)

def run_experiment():
    topo = StratifiedTopo()
    net = Mininet(topo=topo, host=Host, link=TCLink)
    net.start()
    
    info("Dumping host connections\n")
    dumpNodeConnections(net.hosts)
    
    # Generate Network Map
    info("Generating Network Map...\n")
    network_map = {}
    base_port = 8000
    
    for host in net.hosts:
        # Assuming port 8000 for all agents
        # Mininet hosts have unique IPs, so same port is fine.
        network_map[host.name] = (host.IP(), base_port)
        
    with open("network_map.json", "w") as f:
        json.dump(network_map, f, indent=4)
        
    info(f"Network Map saved to network_map.json\n")
    
    # Create logs directory
    os.makedirs("logs", exist_ok=True)
    
    # Start Agents
    info("Starting MixNet Agents...\n")
    
    # Define roles
    for host in net.hosts:
        role = "mix"
        if "sender" in host.name:
            role = "sender"
        elif "recv" in host.name:
            role = "receiver"
        
        # Cmd
        cmd = f"python3 src/run.py --role {role} --config config/config.json --hostname {host.name} --network-map network_map.json > logs/{host.name}.log 2>&1 &"
        host.cmd(cmd)
        
    info(f"Agents running. Traffic generation will be handled by config.\n")
    
    # CLI for manual interaction
    CLI(net)
    
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run_experiment()
