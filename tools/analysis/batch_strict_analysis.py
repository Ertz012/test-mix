import os
import argparse
import subprocess
import glob
import multiprocessing
import json

def find_testruns(logs_root):
    """
    Finds all Testrun_* folders in logs_root.
    """
    runs = glob.glob(os.path.join(logs_root, "Testrun_*"))
    runs = [r for r in runs if os.path.isdir(r)]
    return sorted(runs)

def find_clients_in_run(run_dir):
    """
    Finds all client IDs (c*) that were active in the run.
    Uses system_in.csv if available for best accuracy (src column).
    """
    # Prefer source of truth: system_in.csv (all sent packets)
    sys_in = os.path.join(run_dir, "system_in.csv")
    targets = set()
    
    if os.path.exists(sys_in):
        try:
            import pandas as pd
            df = pd.read_csv(sys_in)
            # Find all unique sources starting with 'c' or 'Client'
            all_srcs = df['src'].unique()
            for s in all_srcs:
                s_str = str(s)
                if s_str.startswith(('c', 'Client')):
                    targets.add(s_str)
        except Exception as e:
            print(f"Warning: Failed to read {sys_in}: {e}")
            
    # Fallback/Additional check: look for c*_traffic.csv files
    # Only if system_in missed something or doesn't exist
    client_files = glob.glob(os.path.join(run_dir, "c*_traffic.csv")) + glob.glob(os.path.join(run_dir, "Client*_traffic.csv"))
    for f in client_files:
        c_id = os.path.basename(f).replace("_traffic.csv", "")
        targets.add(c_id)
        
    return sorted(list(targets))

def run_analysis_task(task_args):
    """
    Worker function to run analysis script.
    """
    run_dir, target, mu, k_hops, script_path = task_args
    
    import sys
    cmd = [
        sys.executable, script_path,
        "--run-dir", run_dir,
        "--target", target,
        "--mu", str(mu),
        "--k-hops", str(k_hops)
    ]
    
    # print(f"DEBUG: Running {' '.join(cmd)}") # Uncomment to spam console
    
    try:
        # Run process, suppress full stdout unless error
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return f"FAILED: {os.path.basename(run_dir)} Target={target} - OUT: {result.stdout} ERR: {result.stderr}"
        else:
            return f"SUCCESS: {os.path.basename(run_dir)} Target={target} - OUT: {result.stdout}"
    except Exception as e:
        return f"ERROR: {run_dir} Target={target} - {e}"

def main():
    parser = argparse.ArgumentParser(description="Batch Runner for Strict Traffic Analysis")
    parser.add_argument("--logs-root", default="../Testruns", help="Root folder containing Testrun_* directories")
    parser.add_argument("--mu", type=float, default=0.5, help="Mix rate mu")
    parser.add_argument("--k-hops", type=int, default=1, help="Hop depth to analyze (default 1 for link trace)")
    parser.add_argument("--workers", type=int, default=max(1, multiprocessing.cpu_count() - 2), help="Number of parallel workers")
    
    args = parser.parse_args()
    
    script_path = os.path.join(os.path.dirname(__file__), "analyze_traffic_strict_link_trace.py")
    if not os.path.exists(script_path):
        print(f"Error: Analysis script not found at {script_path}")
        return

    print(f"--- Batch Strict Analysis ---")
    print(f"Logs Root: {args.logs_root}")
    print(f"Workers: {args.workers}")
    print(f"Attacking with Mu={args.mu}, k={args.k_hops}")
    
    runs = find_testruns(args.logs_root)
    if not runs:
        print("No Testrun_* directories found.")
        return
        
    tasks = []
    
    print(f"\nScanning for tasks...")
    for run in runs:
        targets = find_clients_in_run(run)
        if not targets:
            print(f"  [Skipping] {os.path.basename(run)} - No clients found.")
            continue
            
        print(f"  [{os.path.basename(run)}] Found {len(targets)} targets: {', '.join(targets)}")
        
        for t in targets:
            tasks.append((run, t, args.mu, args.k_hops, script_path))
            
    print(f"\nTotal Tasks: {len(tasks)}")
    print("Starting execution...\n")
    
    with multiprocessing.Pool(processes=args.workers) as pool:
        for i, result in enumerate(pool.imap_unordered(run_analysis_task, tasks), 1):
            print(f"[{i}/{len(tasks)}] {result}")
            
    print("\nBatch processing complete.")

if __name__ == "__main__":
    main()
