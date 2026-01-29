
import os
import sys
import glob
import concurrent.futures
import json
import argparse
from tqdm import tqdm

# Add tools directory to path to import analyze_general_stats
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(os.path.join(parent_dir, "tools", "analysis"))

import analyze_general_stats

def process_run(run_path):
    try:
        traffic_df, mix_df = analyze_general_stats.parse_logs(run_path)
        if traffic_df.empty:
            return f"Skipped {os.path.basename(run_path)} (No logs)"
            
        metrics = analyze_general_stats.calculate_metrics(traffic_df)
        
        output_dir = os.path.join(run_path, "analysis_results")
        if not os.path.exists(output_dir): os.makedirs(output_dir)
        
        with open(os.path.join(output_dir, "general_metrics.json"), 'w') as f:
            json.dump(metrics, f, indent=4)
            
        return None # Success
    except Exception as e:
        return f"Error in {os.path.basename(run_path)}: {e}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("logs_root", help="Root directory containing test runs")
    args = parser.parse_args()
    
    runs = [f.path for f in os.scandir(args.logs_root) if f.is_dir() and "Testrun_" in f.name]
    print(f"Found {len(runs)} runs. Starting recalculation...")
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=10) as executor:
        results = list(tqdm(executor.map(process_run, runs), total=len(runs)))
        
    errors = [r for r in results if r]
    if errors:
        print(f"\nEncountered {len(errors)} errors:")
        for e in errors:
            print(e)
    else:
        print("\nAll runs processed successfully.")

if __name__ == "__main__":
    main()
