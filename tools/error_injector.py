import argparse
import time
import random
import os
import subprocess
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ErrorInjector")

def get_node_pid(node_name):
    """
    Get the PID of the process running provided node logic.
    In Mininet, hosts are usually separate processes or namespaces.
    We look for the python process running `src/run.py` with argument `--config ... --hostname node_name`.
    """
    try:
        # Pgrep for the python process with the specific hostname argument
        # -f matches against full command line
    cmd = f"pgrep -f 'src/run.py.*--hostname {node_name}'"
    try:
        pid = subprocess.check_output(cmd, shell=True).decode().strip()
        return pid
    except subprocess.CalledProcessError:
        # Fallback/Debug: try finding any run.py process
        # logger.warning(f"pgrep strict match failed for {node_name}. Checking widespread...")
        return None
    except Exception as e:
        logger.error(f"Error finding PID for {node_name}: {e}")
        return None

def kill_node(node_name):
    """
    Kill the python process for the given node.
    """
    pid = get_node_pid(node_name)
    if pid:
        pids = pid.replace('\n', ' ')
        logger.info(f"Killing {node_name} (PIDs {pids})...")
        os.system(f"kill -9 {pids}")
    else:
        logger.warning(f"Could not find PID for {node_name} with pgrep pattern. Attempting partial match logging.")
        # Diagnostic: List all run.py processes to dedug
        os.system("ps aux | grep src/run.py | head -n 5")

def inject_loss(node_name, loss_percent):
    """
    Use tc to inject packet loss on the node's interface.
    Mininet hosts usually valid interfaces link eth0.
    """
    logger.info(f"Setting {loss_percent}% packet loss on {node_name}-eth0...")
    # This requires sudo and being executed in the root namespace or having access to the intf.
    # In Mininet standard run, we can typically just use 'mnexec' or run 'tc' if we are root.
    # But usually interfaces are named like s1-eth0 etc in the root namespace or accessible inside ns.
    # Simpler approach: execute command INSIDE the node namespace if possible, or on the veth pair.
    # For now, let's assume we run this script as root and just use `tc` on the host side interface?
    # Actually, in Mininet `SingleSwitchTopo`, links are `node-eth0` <-> `sw1-port`.
    # We can run tc on `node-eth0` from within the node namespace.
    # Ideally we'd use `mnexec` but we don't have the Mininet object here.
    
    # Alternative: Use standard linux networking commands assuming we are on the host execution environment
    # and the interfaces are visible.
    # Wait, Mininet hides `h1-eth0` inside a network namespace.
    # We can access it via `ip netns exec <pid> ...` ?
    # Or simplified: We just Assume "Kill" is the main failure mode for "Substitute Mixes" and "Multipath".
    # Packet loss is harder to inject reliably without the Mininet API object.
    pass

def main():
    parser = argparse.ArgumentParser(description="Inject errors into Mixnet")
    parser.add_argument("--config", help="Traffic config file to read topology (optional)")
    parser.add_argument("--mode", choices=['kill', 'random_kill'], required=True)
    parser.add_argument("--target", help="Specific node to target (for 'kill' mode)")
    parser.add_argument("--count", type=int, default=1, help="Number of nodes to kill (for 'random_kill')")
    parser.add_argument("--delay", type=float, default=0, help="Delay before injection (seconds)")
    
    args = parser.parse_args()

    if args.delay > 0:
        logger.info(f"Waiting {args.delay} seconds before injection...")
        time.sleep(args.delay)

    if args.mode == 'kill':
        if not args.target:
            logger.error("Target required for kill mode")
            return
        kill_node(args.target)

    elif args.mode == 'random_kill':
        # Hardcoded set of candidates if config not provided, or better logic?
        # Target all mix layers: Entry (e), Intermediate (i), Exit (x)
        # 12 nodes per layer
        candidates = []
        for n in range(1, 13):
            candidates.append(f"e{n}")
            candidates.append(f"i{n}")
            candidates.append(f"x{n}")
        
        targets = random.sample(candidates, min(args.count, len(candidates)))
        for t in targets:
            kill_node(t)

if __name__ == "__main__":
    main()
