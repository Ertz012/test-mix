
import os
import sys
import subprocess

def main():
    """
    Script to launch the high noise experiment series locally (on the remote machine).
    Prerequisites:
    1. Repository is synced (manual git pull by user).
    2. config/experiments_high_noise.json exists.
    """
    
    base_dir = os.getcwd()
    config_rel_path = os.path.join("config", "experiments_high_noise.json")
    config_path = os.path.join(base_dir, config_rel_path)
    runner_script = os.path.join(base_dir, "tools", "run_series.py")
    
    if not os.path.exists(config_path):
        print(f"Error: Config not found at {config_path}")
        print(f"Please ensure '{config_rel_path}' exists.")
        sys.exit(1)
        
    print(f"Launching High Noise Experiment Series...")
    print(f"Config: {config_path}")
    
    # Execute run_series.py using sudo
    # We use subprocess.call to allow streaming output to stdout if needed, 
    # but run_series.py handles its own logging mostly.
    # However, for long runs, we often want to detach or just run.
    # User runs this with 'sudo python3 tools/launch_high_noise.py', so we are already root or have sudo rights.
    # But run_series.py calls sudo internally for some things, or expects to be run as root?
    # run_series.py uses `subprocess.Popen` for `orchestrate.py` which needs root (Mininet).
    # So we should ensure we run run_series.py with sudo if we aren't already.
    
    if os.geteuid() != 0:
        print("Switching to sudo...")
        cmd = f"sudo python3 {runner_script} --experiments {config_path}"
    else:
        cmd = f"python3 {runner_script} --experiments {config_path}"
    
    print(f"Running: {cmd}")
    try:
        os.system(cmd)
    except KeyboardInterrupt:
        print("Aborted by user.")

if __name__ == "__main__":
    main()
