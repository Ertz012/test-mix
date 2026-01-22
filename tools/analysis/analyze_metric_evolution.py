import os
import argparse
import pandas as pd
import json
import numpy as np
import logging
from analyze_traffic_exact import load_logs, load_config, perform_strict_math_attack

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MetricEvolution")

def analyze_evolution(run_path, target_src, step_size=100):
    """
    Analyzes the evolution of anonymity metrics over time (packet count).
    """
    logger.info(f"Analyzing evolution for {target_src} in {os.path.basename(run_path)}")
    
    # 1. Load Data
    full_df = load_logs(run_path)
    if full_df.empty:
        logger.error("No logs found.")
        return
        
    config = load_config(run_path)
    mu = config.get('mix_settings', {}).get('mu', 0.5)
    k_hops = config.get('network_settings', {}).get('num_hops', 3)
    
    # 2. Filter for relevant events to ensure consistent slicing
    # We want to slice based on "Observed Time" or "Packet Count"?
    # Packet Count is easier to standardize.
    # We slice the WHOLE dataframe to simulate "Attack stopped at time t"
    
    # Sort by timestamp (should be already, but ensure)
    full_df.sort_values('timestamp', inplace=True)
    
    total_packets = len(full_df)
    results = []
    
    # 3. Iterate in steps
    # Start from at least some packets to avoid empty stats
    current_idx = step_size
    
    while current_idx <= total_packets + step_size: # Go a bit over to catch remainder
        
        # Clamp bounds
        slice_idx = min(current_idx, total_packets)
        
        # Create Slice
        df_slice = full_df.iloc[:slice_idx].copy()
        
        # Run Attack
        # Note: target_src must exist in the slice to be analyzed.
        # If the target hasn't sent anything yet, this might return empty.
        metrics = perform_strict_math_attack(df_slice, mu, target_src=target_src, k=k_hops)
        
        if metrics:
            # Extract key metrics
            record = {
                'packets_observed': slice_idx,
                'duration_observed': df_slice['timestamp'].max() - df_slice['timestamp'].min(),
                'diaz_anonymity': metrics['global_metrics']['diaz_anonymity'],
                'danezis_metric_A': metrics['global_metrics']['danezis_metric_A'],
                'entropy_bits': metrics['global_metrics']['entropy_bits'],
                'max_entropy_bits': metrics['global_metrics']['max_entropy_bits'],
                'target_llr': metrics['outcome']['detected_llr'], # LLR of the DETECTED one (might not be True receiver)
                'detected_receiver': metrics['outcome']['detected_receiver'],
                'true_receiver': metrics['outcome']['true_receiver'],
                'success': metrics['outcome']['success']
            }
            results.append(record)
        
        if slice_idx >= total_packets:
            break
            
        current_idx += step_size
        
    # 4. Save Results
    out_dir = os.path.join(run_path, "analysis_results")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"anonymity_evolution_{target_src}.csv")
    
    res_df = pd.DataFrame(results)
    res_df.to_csv(out_file, index=False)
    logger.info(f"Saved evolution data to {out_file}")
    return res_df

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", help="Path to the testrun directory")
    parser.add_argument("--target", help="Target client to analyze", required=True)
    parser.add_argument("--step", type=int, default=200, help="Step size in packets (default: 200)")
    args = parser.parse_args()
    
    if os.path.isdir(args.run_dir):
        analyze_evolution(args.run_dir, args.target, args.step)
    else:
        print(f"Invalid directory: {args.run_dir}")

if __name__ == "__main__":
    main()
