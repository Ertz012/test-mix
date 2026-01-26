import os
import argparse
import subprocess
import sys
import glob
from multiprocessing import Pool, cpu_count

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT_CONSOLIDATE = os.path.join(BASE_DIR, "consolidate_traffic_logs.py")
SCRIPT_GENERAL = os.path.join(BASE_DIR, "analyze_general_stats.py")
SCRIPT_STRICT = os.path.join(BASE_DIR, "analyze_traffic_strict_link_trace.py")
SCRIPT_META = os.path.join(BASE_DIR, "analyze_meta_comparison.py")

def run_command(cmd_list):
    # Quiet output in parallel mode to avoid interleaved chaos
    try:
        subprocess.check_output(cmd_list, stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError as e:
        print(f"FAILED: {' '.join(cmd_list)}\nOutput: {e.output.decode()}")
        return False

def analyze_single_run(run_dir):
    # 0. Check if already analyzed (Resume Capability)
    if os.path.exists(os.path.join(run_dir, "analysis_results", "anonymity_stats.json")):
        print(f"Skipping: {os.path.basename(run_dir)} (Already Initialized)")
        return

    print(f"Analying: {os.path.basename(run_dir)} ...")
    
    # 1. Consolidate Logs
    if not run_command(["python", SCRIPT_CONSOLIDATE, run_dir]):
        return

    # 2. General Analysis (Latency, Loss, Graphs)
    run_command(["python", SCRIPT_GENERAL, run_dir])
    
    # 3. Strict Traffic Analysis (Anonymity)
    target = "c1" 
    run_command(["python", SCRIPT_STRICT, 
                 "--run-dir", run_dir, 
                 "--target", target,
                 "--mu", "0.5", 
                 "--k-hops", "1"])
                 
    print(f"Done: {os.path.basename(run_dir)}")

def analyze_wrapper(args):
    """Wrapper for pool map to unpack arguments"""
    analyze_single_run(args)

def main():
    parser = argparse.ArgumentParser(description="Full Analysis Pipeline Wrapper (Parallel)")
    parser.add_argument("path", help="Path to a single run directory OR a root directory containing multiple runs.")
    parser.add_argument("--meta-only", action="store_true", help="Skip individual analysis and only run meta-comparison.")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers (default: 4)")
    parser.add_argument("--filter", type=str, default=None, help="Only analyze directories containing this string.")
    args = parser.parse_args()
    
    target_path = os.path.abspath(args.path)
    
    if not os.path.exists(target_path):
        print(f"Path not found: {target_path}")
        sys.exit(1)
        
    # Check if single run or batch
    is_single_run = len(glob.glob(os.path.join(target_path, "*_traffic.csv"))) > 0
    
    if is_single_run:
        if not args.meta_only:
            analyze_single_run(target_path)
    else:
        # Batch Mode
        print(f"Batch Mode: Scanning {target_path}...")
        subdirs = [f.path for f in os.scandir(target_path) if f.is_dir()]
        run_dirs = []
        
        for run_dir in subdirs:
            if args.filter and args.filter not in os.path.basename(run_dir):
                continue
                
            if glob.glob(os.path.join(run_dir, "*_traffic.csv")) or os.path.exists(os.path.join(run_dir, "config.json")):
                 run_dirs.append(run_dir)
        
        if not args.meta_only:
            count = len(run_dirs)
            workers = min(args.workers, count) if count > 0 else 1
            print(f"Found {count} runs matching filter. Starting analysis with {workers} workers...")
            
            with Pool(workers) as p:
                p.map(analyze_wrapper, run_dirs)
        
        # 4. Meta Analysis (Sequential, after all runs done)
        print("\n=== Running Meta-Analysis (Comparison) ===")
        run_command(["python", SCRIPT_META, target_path])

if __name__ == "__main__":
    main()
