
import os
import sys

def main():
    """
    Script to launch the short test series locally (on the remote machine).
    Prerequisites:
    1. Repository is synced (manual git pull by user).
    2. config/experiments_short_test.json exists (should be in git).
    """
    
    # Ensure we are in the repo root (assuming script is run as python tools/launch_short_test.py)
    # If run from tools dir, adjust.
    # Prefer relative paths from repo root.
    
    base_dir = os.getcwd()
    config_path = os.path.join(base_dir, "config", "experiments_short_test.json")
    runner_script = os.path.join(base_dir, "tools", "run_series.py")
    
    if not os.path.exists(config_path):
        print(f"Error: Config not found at {config_path}")
        print("Did you commit and pull 'config/experiments_short_test.json'?")
        sys.exit(1)
        
    print(f"Launching Short Test Series (Duration: 3m per scenario)...")
    print(f"Config: {config_path}")
    
    # Execute run_series.py
    # Using sudo because Mininet requires root.
    cmd = f"sudo python3 {runner_script} --experiments {config_path}"
    
    print(f"Running: {cmd}")
    try:
        os.system(cmd)
    except KeyboardInterrupt:
        print("Aborted by user.")

if __name__ == "__main__":
    main()
