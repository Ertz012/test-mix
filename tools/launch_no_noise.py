import os
import subprocess
import sys

def main():
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(tools_dir)
    experiments_file = os.path.join(base_dir, "config", "experiments_no_noise.json")
    run_series_script = os.path.join(tools_dir, "run_series.py")
    
    print(f"Launching No-Noise Test Series...")
    print(f"Config: {experiments_file}")
    
    cmd = [sys.executable, run_series_script, "--experiments", experiments_file]
    
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        print(f"Error executing run_series.py: {e}")
        sys.exit(1)
        
if __name__ == "__main__":
    main()
