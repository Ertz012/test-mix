
import os
import sys

def main():
    """
    Script to launch the NO NOISE experiment series locally (on the remote machine).
    Prerequisites:
    1. Repository is synced.
    2. config/experiments_no_noise.json exists.
    """
    
    base_dir = os.getcwd()
    config_rel_path = os.path.join("config", "experiments_no_noise.json")
    config_path = os.path.join(base_dir, config_rel_path)
    runner_script = os.path.join(base_dir, "tools", "run_series.py")
    
    if not os.path.exists(config_path):
        print(f"Error: Config not found at {config_path}")
        sys.exit(1)
        
    print(f"Launching NO NOISE Experiment Series...")
    print(f"Config: {config_path}")
    
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
