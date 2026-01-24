import os
import glob
import concurrent.futures
from tqdm import tqdm
import sys

# Ensure local imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import analyze_traffic_exact
import analyze_results
import analyze_metric_evolution

# Determine base paths
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(TOOLS_DIR))
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")

def process_run(run_path):
    """
    Worker function to process a single run.
    """
    run_name = os.path.basename(run_path)
    try:
        # 1. Run Exact Analysis (Generates JSON with Diaz metric)
        # This is the heavy lifting, optimized with numpy
        analyze_traffic_exact.analyze_target_exact(run_path)
        
        # 1b. Run Metric Evolution (Generates CSVs)
        # We need this before analyze_results updates the summary
        analyze_metric_evolution.analyze_evolution(run_path, step_size=2500)
        
        # 2. Run General Analysis (Updates analysis_summary.txt)
        # This is fast, just parsing logs and writing summary
        # We redirect stdout to avoid cluttering the progress bar
        with open(os.devnull, 'w') as fnull:
            original_stdout = sys.stdout
            try:
                sys.stdout = fnull
                analyze_results.analyze_single_run(run_path)
            finally:
                sys.stdout = original_stdout
                
        return f"OK"
    except Exception as e:
        return f"ERR: {run_name} - {e}"

def main():
    if not os.path.exists(LOGS_DIR):
        print(f"Error: Logs directory not found at {LOGS_DIR}")
        return

    # Find all test runs
    runs = glob.glob(os.path.join(LOGS_DIR, "Testrun_*"))
    runs = [r for r in runs if os.path.isdir(r)]
    
    print(f"Found {len(runs)} test runs in {LOGS_DIR}")
    print("Starting batch update of anonymity metrics...")
    
    workers = os.cpu_count() or 4
    results = []
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        # Submit all tasks
        futures = {executor.submit(process_run, run): run for run in runs}
        
        # Monitor with tqdm
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(runs), unit="run"):
            res = future.result()
            results.append(res)
            
    # Summary
    errors = [r for r in results if r.startswith("ERR")]
    print(f"\nProcessing Complete.")
    print(f"Total: {len(runs)}")
    print(f"Successful: {len(runs) - len(errors)}")
    print(f"Errors: {len(errors)}")
    
    if errors:
        print("\nError Details:")
        for e in errors:
            print(e)

if __name__ == "__main__":
    # Windows support
    import multiprocessing
    multiprocessing.freeze_support()
    main()
