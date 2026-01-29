import argparse
import time
import random
import os
import subprocess
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ErrorInjector")

def get_node_info(node_name):
    """
    Get (PID, CMD) for the given node.
    """
    try:
        cmd_pgrep = f"pgrep -a -f 'src/run.py.*--hostname {node_name}'"
        result = subprocess.check_output(cmd_pgrep, shell=True).decode().strip()
        if not result: return None, None
        
        # Format usually: PID COMMAND...
        # We might have multiple lines if pgrep matches subtly, take the first one that looks right?
        line = result.split('\n')[0]
        parts = line.split(' ', 1)
        if len(parts) < 2: return None, None
        
        pid = parts[0]
        cmd = parts[1]
        
        # pgrep -a output might be stripped or weird? 
        # Better to get PID then pull cmdline from /proc
        return pid, cmd
    except Exception:
        return None, None

def kill_node_by_pid(pid):
    try:
        os.system(f"kill -9 {pid}")
    except:
        pass

def restart_node(cmd_str):
    """
    Restart the node using the captured command string.
    We need to ensure it runs in the background.
    """
    logger.info(f"Restarting node with: {cmd_str[:50]}...")
    # Use explicit shell execution to handle redirections if they were part of the cmd matches?
    # pgrep match usually contains the python command, NOT the shell redirection parts ( > out.log).
    # Since we use Mininet hosts that are essentially just processes in root namespace in this setup 
    # (orchestrate.py starts python directly on host if using default Mininet?),
    # NO, Mininet hosts run in namespaces.
    # WAIT. If I kill the process, the namespace persists (the shell inside Mininet).
    # But if I kill the python process, I need to start it INSIDE the namespace if "mnexec" was used?
    # `orchestrate.py` uses `host.cmd(...)`.
    # If I just run `python src/run.py ...` from root, it runs in root namespace (wrong IP!).
    # Critical Logic Check:
    # `orchestrate.py` starts agents via `host.cmd()`. 
    # Mininet `host.cmd` executes inside the host's namespace.
    # The `pgrep` on the main OS usually sees the process (as root).
    # But if I restart it, I MUST use `mnexec -a <pid_of_shell> ...` or similar to get back into namespace?
    # OR, rely on Mininet API? `error_injector` doesn't have Mininet API access.
    
    # HACK: If we are running SingleSwitchTopo locally, usually we can identify the Node's bash shell PID using `pgrep -f "mininet:host_name"`.
    # Then we can use `mnexec -a <pid> <cmd>`.
    pass 

def churn_loop(targets, interval, downtime, duration):
    """
    Toggle targets on/off.
    """
    end_time = time.time() + duration
    
    # Resolve initial PIDs and Commands
    node_data = {} # name -> {cmd: str}
    
    for t in targets:
        pid, cmd = get_node_info(t)
        if cmd:
            # Clean up cmd: remove 'python3' if double?
            # Ensure we have the full command needed.
            node_data[t] = cmd
            logger.info(f"Captured command for {t}: {cmd}")
        else:
            logger.error(f"Could not find initial process for {t}, cannot churn.")
            return

    while time.time() < end_time:
        # OFF PHASE
        logger.info(f"CHURN: Killing {targets}")
        for t in targets:
            pid, _ = get_node_info(t)
            if pid: kill_node_by_pid(pid)
            
        time.sleep(downtime)
        
        if time.time() >= end_time: break
        
        # ON PHASE
        logger.info(f"CHURN: Restarting {targets}")
        for t in targets:
            cmd = node_data.get(t)
            if cmd:
                # We need to execute this inside the node namespace using mnexec.
                # Find the bash shell for the node
                # Mininet names processes like "bash --norc ... mininet:h1"
                # Actually, simplest way if we don't have mnexec logic handy:
                # Just execute the command?
                # If namespaces are used, direct execution fails.
                # Assuming standard Mininet:
                
                # Fetch PID of the Shell for this host
                try:
                    # pgrep for mininet host shell
                    # Mininet sets process title often
                    bash_pid = subprocess.check_output(f"pgrep -f 'mininet:{t}'", shell=True).decode().strip().split('\n')[0]
                    if bash_pid:
                        # Construct mnexec command
                        # cmd usually starts with "python3 ..."
                        # We might need to handle stdout redir again?
                        # The captured cmd from pgrep usually does contain arguments but NOT > redirection.
                        # We should append logging again.
                        
                        log_file = f"logs/churn_{t}.out" # separate log for churn restarts?
                        # Or verify if we can append to original? We don't know original path easily unless we parse cmd more.
                        # Let's just log to a new file to avoid permission/overwrite issues.
                        
                        full_cmd = f"mnexec -a {bash_pid} {cmd} >> {log_file} 2>&1 &"
                        os.system(full_cmd)
                    else:
                        logger.error(f"Could not find shell PID for {t}")
                except Exception as e:
                    logger.error(f"Restart failed for {t}: {e}")

        time.sleep(interval)

def main():
    parser = argparse.ArgumentParser(description="Inject errors into Mixnet")
    parser.add_argument("--config", help="Traffic config file to read topology (optional)")
    parser.add_argument("--mode", choices=['kill', 'random_kill', 'churn'], required=True)
    parser.add_argument("--target", help="Specific node(s) to target (comma-separated for churn)")
    parser.add_argument("--count", type=int, default=1, help="Number of nodes to kill (for 'random_kill')")
    parser.add_argument("--delay", type=float, default=0, help="Delay before injection (seconds)")
    parser.add_argument("--interval", type=float, default=30.0, help="Time ON in churn cycle (seconds)")
    parser.add_argument("--downtime", type=float, default=10.0, help="Time OFF in churn cycle (seconds)")
    parser.add_argument("--duration", type=float, default=600.0, help="Total duration of churn simulation")
    
    args = parser.parse_args()
    
    if args.delay > 0:
        logger.info(f"Waiting {args.delay} seconds before injection...")
        time.sleep(args.delay)

    if args.mode == 'churn':
        targets = []
        if args.target:
            targets = args.target.split(',')
        else:
             # Random selection logic (copied from random_kill)
            candidates = []
            for n in range(1, 13):
                candidates.append(f"e{n}")
                candidates.append(f"i{n}")
                candidates.append(f"x{n}")
            targets = random.sample(candidates, min(args.count, len(candidates)))
            logger.info(f"Selected random targets for churn: {targets}")

        churn_loop(targets, args.interval, args.downtime, args.duration)

    elif args.mode == 'kill':
        if not args.target:
            logger.error("Target required for kill mode")
            return
        kill_node(args.target)
    
    elif args.mode == 'random_kill':
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
