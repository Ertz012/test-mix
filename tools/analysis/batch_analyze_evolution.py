import os
import multiprocessing
import argparse
import time
import pandas as pd
from analyze_metric_evolution import analyze_evolution

def get_runs(logs_root):
    return [os.path.join(logs_root, d) for d in os.listdir(logs_root) 
            if os.path.isdir(os.path.join(logs_root, d)) and d.startswith("Testrun")]

def get_clients_in_run(run_path):
    # Quick scan of csv to find clients? 
    # Or just assume c1..c5? Better to be dynamic.
    # We can check existing analysis dumps?
    analysis_dir = os.path.join(run_path, "analysis_results")
    if not os.path.exists(analysis_dir):
        return []
    
    # Look for traffic_analysis_dump_*.json
    clients = []
    for f in os.listdir(analysis_dir):
        if f.startswith("traffic_analysis_dump_") and f.endswith(".json"):
            # extract client name
            # traffic_analysis_dump_c1.json -> c1
            client = f.replace("traffic_analysis_dump_", "").replace(".json", "")
            clients.append(client)
    
    # Fallback: if no dumps, check CSV (expensive)
    if not clients:
        traffic_file = [f for f in os.listdir(run_path) if f.endswith("_traffic.csv")]
        if traffic_file:
             # Assume standard clients c1-c5 for now to avoid massive CSV read in main thread
             return ['c1', 'c2', 'c3', 'c4', 'c5']
             
    return sorted(list(set(clients)))

def worker(args):
    run_path, client, step = args
    print(f"Starting {os.path.basename(run_path)} - {client}")
    try:
        analyze_evolution(run_path, client, step)
        print(f"Finished {os.path.basename(run_path)} - {client}")
        return True
    except Exception as e:
        print(f"FAILED {os.path.basename(run_path)} - {client}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--logs-root", default="../logs", help="Path to logs directory")
    parser.add_argument("--step", type=int, default=2500, help="Step size for evolution analysis")
    parser.add_argument("--processes", type=int, default=os.cpu_count(), help="Number of processes")
    args = parser.parse_args()
    
    # Resolve relative path
    if args.logs_root == "../logs":
        # Check if we are running from tools/analysis or root
        if os.path.exists("logs"):
            args.logs_root = "logs"
        elif os.path.exists("../logs"):
            args.logs_root = "../logs"
            
    print(f"Scanning {args.logs_root}...")
    runs = get_runs(os.path.abspath(args.logs_root))
    print(f"Found {len(runs)} runs.")
    
    tasks = []
    for run in runs:
        clients = get_clients_in_run(run)
        for client in clients:
            # Check if output already exists? 
            # User said "dont skip anything prematurely", implies force run or at least ensure completeness.
            # I will overwrite.
            tasks.append((run, client, args.step))
            
    print(f"Prepared {len(tasks)} analysis tasks.")
    print(f"Starting pool with {args.processes} processes...")
    
    start_time = time.time()
    
    with multiprocessing.Pool(processes=args.processes) as pool:
        pool.map(worker, tasks)
        
    duration = time.time() - start_time
    print(f"Batch analysis complete in {duration:.2f} seconds.")

if __name__ == "__main__":
    main()
