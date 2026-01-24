import argparse
import sys
import os
import json
import logging
import pandas as pd
import concurrent.futures
from tqdm import tqdm
import multiprocessing

# Add tools directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Import analysis modules
import consolidate_traffic_logs
import analyze_results
import analyze_traffic_binned
import analyze_traffic_exact
import analyze_metric_evolution

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AnalyzeAll")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS_DIR = os.path.join(BASE_DIR, "logs")

def get_clients_from_csv(csv_path):
    """Reads system_in.csv and returns a list of unique Client IDs (c* or Client*)."""
    try:
        df = pd.read_csv(csv_path)
        if 'src' not in df.columns:
            return []
        
        clients = df['src'].unique()
        # Filter for clients (assuming 'c' or 'Client' prefix)
        return [c for c in clients if c.startswith(('c', 'Client'))]
    except Exception:
        return []

def process_single_run(exp_path, force=False):
    """
    Worker function to process a single test run.
    Returns a status string or result object.
    """
    run_name = os.path.basename(exp_path)
    
    # Setup specific logger for this process/run to avoid interleaving (optional, keeping simple print for now)
    # Using print logic inside worker might conflict with tqdm.
    # We will minimize output and just return status.

    summary_file = os.path.join(exp_path, "analysis_results", "analysis_summary.txt")
    if os.path.exists(summary_file) and not force:
        return f"Skipped (Done): {run_name}"

    try:
        # 1. General Analysis (MOVED TO END)
        # analyze_results.analyze_single_run(exp_path)

        # 2. Consolidate Logs
        consolidate_traffic_logs.process_logs(exp_path)
        
        in_file = os.path.join(exp_path, 'system_in.csv')
        out_file = os.path.join(exp_path, 'system_out.csv')
        
        if not os.path.exists(in_file) or not os.path.exists(out_file):
             return f"Failed (No Logs): {run_name}"

        # 3. Get Configuration (mu, hops)
        mu = 0.5
        k_hops = 3
        config_path = os.path.join(exp_path, "config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                mu = config.get('mix_settings', {}).get('mu', 0.5)
                if 'topology' in config and 'layers' in config['topology']:
                    k_hops = len(config['topology']['layers'])
                else:
                    k_hops = config.get('network_settings', {}).get('num_hops', 3)

        # 4. Identify All Clients
        clients = get_clients_from_csv(in_file)
        if not clients:
            return f"Warning (No Clients): {run_name}"

        # 5. Run Analysis for EACH Client
        results_summary = []
        
        for client in clients:
            # A. Binnned Analysis (Graph + Ranking)
            # This generates traffic_analysis_binned_{client}.txt/png
            try:
                ranking, detected = analyze_traffic_binned.run_traffic_analysis(in_file, out_file, client, mu, k_hops=k_hops)
                
                if ranking is not None and not ranking.empty:
                     out_results_dir = os.path.join(exp_path, 'analysis_results')
                     os.makedirs(out_results_dir, exist_ok=True)
                     ranking_file = os.path.join(out_results_dir, f'traffic_analysis_binned_{client}.txt')
                     with open(ranking_file, 'w') as f:
                        f.write(f"Traffic Analysis Result for Target: {client}\n")
                        f.write(f"Mu: {mu}, K: {k_hops}\n\n")
                        f.write(ranking.to_string())

                # Plot generation is handled inside run_traffic_analysis or by calling analyze_and_plot
                out_results_dir = os.path.join(exp_path, 'analysis_results')
                analyze_traffic_binned.analyze_and_plot(in_file, out_file, client, mu, output_dir=out_results_dir, k_hops=k_hops)
            except Exception as e:
                pass # Suppress individual client failure to keep batch running

            # B. Exact Analysis (Metrics JSON)
            # This generates traffic_analysis_exact_{client}.txt
            try:
                metrics = analyze_traffic_exact.analyze_target_exact(exp_path, target_src=client)
                if metrics:
                    results_summary.append(f"{client}: Success={metrics['success']} Diaz={metrics['global_metrics']['diaz_anonymity']:.3f}")
            except Exception as e:
                pass

            # C. Evolution Analysis (Time-to-Compromise)
            # This generates anonymity_evolution_{client}.csv
            try:
                # Step size 2500 is a good balance as established in previous experiments
                analyze_metric_evolution.analyze_evolution(exp_path, target_src=client, step_size=2500)
            except Exception as e:
                pass

        # 6. Generate Summary (NOW runs after all analysis is done)
        analyze_results.analyze_single_run(exp_path)

        return f"Processed: {run_name} ({len(clients)} clients)"

    except Exception as e:
        return f"Error: {run_name} - {str(e)}"

def main():
    parser = argparse.ArgumentParser(description="Analyze all test runs in parallel.")
    parser.add_argument("--logs-dir", help="Directory containing test runs", default=RESULTS_DIR)
    parser.add_argument("--force", help="Force re-analysis of all runs", action="store_true")
    parser.add_argument("--workers", help="Number of parallel workers (default: CPU Count)", type=int, default=os.cpu_count())
    args = parser.parse_args()

    if not os.path.exists(args.logs_dir):
        print(f"{args.logs_dir} does not exist.")
        return

    subdirs = sorted([d for d in os.listdir(args.logs_dir) if os.path.isdir(os.path.join(args.logs_dir, d)) and d.startswith("Testrun")])
    exp_paths = [os.path.join(args.logs_dir, d) for d in subdirs]
    
    print(f"Found {len(exp_paths)} test runs.")
    print(f"Starting analysis with {args.workers} workers...")
    
    # Use ProcessPoolExecutor for parallel execution
    # Use tqdm for progress bar
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        # Submit all tasks
        # We use a dictionary to map futures to run names for error tracking if needed
        future_to_run = {executor.submit(process_single_run, path, args.force): path for path in exp_paths}
        
        # Iterate as they complete with tqdm
        results = []
        for future in tqdm(concurrent.futures.as_completed(future_to_run), total=len(exp_paths), unit="run"):
            run_path = future_to_run[future]
            try:
                data = future.result()
                results.append(data)
            except Exception as exc:
                results.append(f"EXCEPTION in {os.path.basename(run_path)}: {exc}")

    print("\n--- Analysis Complete ---")
    # Print summary of results (optional, maybe just errors)
    for res in results:
        if "Error" in res or "Warning" in res:
             print(res)

if __name__ == "__main__":
    # Windows support for multiprocessing
    multiprocessing.freeze_support()
    main()
