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

def run_experiment():
    topo = SingleSwitchTopo()
    net = Mininet(topo=topo, host=Host, link=TCLink)
    net.start()
    
    # net.staticArp() # Pre-populate ARP
    # No, let's trust flooding for ARP or pingAll
    
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
    
    # Generate Run ID
    run_id = f"Testrun_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = os.path.join("logs", run_id)
    os.makedirs(run_dir, exist_ok=True)
    info(f"Logging to {run_dir}\n")
    
    # Start Agents
    info("Starting MixNet Agents...\n")
    
    # Define roles
    for host in net.hosts:
        role = "mix"
        if "s" in host.name and "sender" not in host.name: # Short names: s1, s2...
            role = "sender"
        elif "r" in host.name and "recv" not in host.name: # Short names: r1...
            role = "receiver"
        # Also handle original long names just in case? No, we switched.
        # But wait, logic above: "s" in host.name is broad.
        # host.name is "s1", "e1", "i1", "x1", "r1".
        
        if host.name.startswith('s'): role = 'sender'
        elif host.name.startswith('r'): role = 'receiver'
        else: role = 'mix'
        
        # Cmd
        # Pass TESTRUN_ID as env var
        # Redirect stdout/stderr to the run_dir
        cmd = f"TESTRUN_ID={run_id} python3 src/run.py --role {role} --config config/config.json --hostname {host.name} --network-map network_map.json > {run_dir}/{host.name}.out 2>&1 &"
        host.cmd(cmd)
        
    info(f"Agents running. Traffic generation will be handled by config.\n")
    
    # CLI for manual interaction
    CLI(net)
    
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run_experiment()
