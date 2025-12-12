import sys
import os
import time
import json
import datetime
import shutil
from mininet.net import Mininet
from mininet.node import Host
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel, info
from mininet.cli import CLI

# Import Topology
from topology import SingleSwitchTopo

def run_experiment():
    topo = SingleSwitchTopo()
    # No controller needed for simple switching? 
    # Providing controller just in case, default is fine.
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
    
    # Copy Config to Run Dir
    try:
        shutil.copy("config/config.json", run_dir)
        info("Copied config.json to log directory\n")
    except Exception as e:
        info(f"Failed to copy config.json: {e}\n")

    # Copy Traffic Data (if exists)
    if os.path.exists("traffic_data.bin"):
        try:
            shutil.copy("traffic_data.bin", run_dir)
            info("Copied traffic_data.bin to log directory\n")
        except Exception as e:
            info(f"Failed to copy traffic_data.bin: {e}\n")
    
    # Start Agents
    info("Starting MixNet Agents...\n")
    
    for host in net.hosts:
        role = "mix"
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
    # Wait for traffic duration
    with open("config/config.json", "r") as f:
        conf = json.load(f)
    duration = conf.get('traffic', {}).get('duration_sec', 30)
    info(f"Running experiment for {duration} seconds (plus 10s buffer)...\n")
    time.sleep(duration + 10)
    
    # CLI(net)
    
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run_experiment()
