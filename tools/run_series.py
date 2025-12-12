import json
import os
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
ANALYSIS_SCRIPT = os.path.join(BASE_DIR, "analysis", "analyze_results.py")

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
    
    orchestrator_proc = subprocess.Popen(["sudo", "python3", ORCHESTRATE_SCRIPT])
    
    injector_proc = None
    if error_injection_config:
        mode = error_injection_config['mode']
        count = error_injection_config.get('count', 1)
        delay = error_injection_config.get('delay', 10)
        
        # We start injector asynchronously
        logger.info(f"Scheduling Error Injection: {mode} in {delay}s")
        injector_cmd = [
            "sudo", "python3", INJECTOR_SCRIPT,
            "--mode", mode,
            "--count", str(count),
            "--delay", str(delay)
        ]
        injector_proc = subprocess.Popen(injector_cmd)

    # Wait for orchestrator to finish (it waits for traffic duration)
    orchestrator_proc.wait()
    
    if injector_proc:
        injector_proc.wait() # Should have finished by now or we kill it
    
    # 3. Identify the log directory
    # Orchestrator creates a timestamped dir in logs/. We need the LATEST one.
    log_root = os.path.join(BASE_DIR, "logs")
    all_subdirs = [os.path.join(log_root, d) for d in os.listdir(log_root) if os.path.isdir(os.path.join(log_root, d))]
    latest_log_dir = max(all_subdirs, key=os.path.getmtime)
    logger.info(f"Captured logs in: {latest_log_dir}")
    
    # 4. Run Analysis
    logger.info("Running Analysis...")
    run_command(["python3", ANALYSIS_SCRIPT, latest_log_dir])
    
    # 5. Archive Results
    exp_results_dir = os.path.join(RESULTS_DIR, exp_name)
    if os.path.exists(exp_results_dir):
        shutil.rmtree(exp_results_dir)
    shutil.copytree(latest_log_dir, exp_results_dir)
    logger.info(f"Saved results to {exp_results_dir}")
    print(f"DONE: {exp_name}")

def main():
    if not os.path.exists(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)

    experiments = load_json(EXPERIMENTS_FILE)
    
    for exp in experiments:
        update_config(exp['config_overrides'])
        run_experiment(exp['name'], exp['error_injection'])
        
        # Small cooldown
        time.sleep(2)

if __name__ == "__main__":
    main()
