import json
import os
import sys
import time
import subprocess
import shutil
import argparse
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SeriesRunner")

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, "config", "config.json")
EXPERIMENTS_FILE = os.path.join(BASE_DIR, "config", "experiments.json")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
ORCHESTRATE_SCRIPT = os.path.join(BASE_DIR, "mininet", "orchestrate.py")
INJECTOR_SCRIPT = os.path.join(BASE_DIR, "tools", "error_injector.py")
# Analysis is now run locally, not here.

def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)

def save_json(data, path):
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)

def update_config(overrides):
    """Update config.json with overrides for the current experiment"""
    config = load_json(CONFIG_FILE)
    
    # Recursive update
    def recursive_update(d, u):
        for k, v in u.items():
            if isinstance(v, dict):
                d[k] = recursive_update(d.get(k, {}), v)
            else:
                d[k] = v
        return d

    config = recursive_update(config, overrides)
    save_json(config, CONFIG_FILE)
    logger.info("Updated config.json")

def run_command(cmd, shell=False):
    logger.info(f"Running: {cmd}")
    ret = subprocess.call(cmd, shell=shell)
    if ret != 0:
        logger.error(f"Command failed with exit code {ret}")
        return False
    return True

def run_experiment(exp_name, error_injection_config):
    logger.info(f"=== Starting Experiment: {exp_name} ===")
    
    # 1. Cleanup Mininet
    run_command("sudo mn -c", shell=True)
    
    # 2. Start Orchestration (in background or blocking? Blocking generally, but orchestrate handles the duration)
    # However, we need to run error injector in parallel if it exists.
    
    orchestrator_proc = subprocess.Popen(["sudo", sys.executable, ORCHESTRATE_SCRIPT, exp_name])
    
    injector_proc = None
    if error_injection_config:
        mode = error_injection_config['mode']
        count = error_injection_config.get('count', 1)
        delay = error_injection_config.get('delay', 10)
        
        # We start injector asynchronously
        logger.info(f"Scheduling Error Injection: {mode} in {delay}s")
        injector_cmd = [
            "sudo", sys.executable, INJECTOR_SCRIPT,
            "--mode", mode,
            "--count", str(count),
            "--delay", str(delay)
        ]
        
        # Optional Churn Params
        if 'interval' in error_injection_config:
            injector_cmd.extend(["--interval", str(error_injection_config['interval'])])
        if 'downtime' in error_injection_config:
            injector_cmd.extend(["--downtime", str(error_injection_config['downtime'])])
            
        injector_proc = subprocess.Popen(injector_cmd)

    # Wait for orchestrator to finish (it waits for traffic duration)
    orchestrator_proc.wait()
    
    if injector_proc:
        # Check if still running
        if injector_proc.poll() is None:
            logger.info("Terminating error injector...")
            # Try terminating cleanly first
            run_command(f"sudo kill {injector_proc.pid}", shell=True)
            try:
                injector_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                 run_command(f"sudo kill -9 {injector_proc.pid}", shell=True)
    
    # 3. Identify the log directory
    # Orchestrator creates a timestamped dir in logs/. We need the LATEST one.
    log_root = os.path.join(BASE_DIR, "logs")
    all_subdirs = [os.path.join(log_root, d) for d in os.listdir(log_root) if os.path.isdir(os.path.join(log_root, d))]
    latest_log_dir = max(all_subdirs, key=os.path.getmtime)
    logger.info(f"Captured logs in: {latest_log_dir}")

    # Move Churn Logs to the experiment folder
    churn_logs = [f for f in os.listdir(log_root) if f.startswith("churn_") and f.endswith(".out")]
    for cl in churn_logs:
        src = os.path.join(log_root, cl)
        dst = os.path.join(latest_log_dir, cl)
        shutil.move(src, dst)
        logger.info(f"Moved {cl} to {latest_log_dir}")
    
    # 4. Analysis Skipped (Run Locally)
    logger.info("Experiment complete. Analysis should be run locally after sync.")
    
    print(f"DONE: {exp_name}")

def main():
    if not os.path.exists(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)

    parser = argparse.ArgumentParser(description="Run Experiment Series")
    parser.add_argument("--experiments", default=EXPERIMENTS_FILE, help="Path to experiments JSON file")
    args = parser.parse_args()

    experiments = load_json(args.experiments)
    
    for exp in experiments:
        update_config(exp['config_overrides'])
        run_experiment(exp['name'], exp['error_injection'])
        
        # Small cooldown
        time.sleep(2)

if __name__ == "__main__":
    main()
