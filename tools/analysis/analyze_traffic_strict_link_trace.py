import os
import sys
import argparse
import pandas as pd
import numpy as np
import logging
from scipy.stats import erlang

# Configure strict logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("StrictLinkTrace")

def load_all_traffic_logs(run_dir):
    """
    Loads all *_traffic.csv files in the directory to reconstruct ALL links in the system.
    Returns:
        dict: { link_id_string: DataFrame_of_observations }
        where link_id_string is "NodeID->NextHopID"
    """
    links = {}
    
    # Iterate over all files
    all_files = [f for f in os.listdir(run_dir) if f.endswith('_traffic.csv')]
    
    logger.info(f"Found {len(all_files)} traffic log files. Parsing for links...")
    
    for filename in all_files:
        node_id = filename.replace('_traffic.csv', '')
        filepath = os.path.join(run_dir, filename)
        
        try:
            df = pd.read_csv(filepath)
            
            # Filter for SENT events to identify outgoing links
            # We are looking for packets leaving a node towards a Next Hop.
            # Columns expected: timestamp, event_type, next_hop, ...
            # 'next_hop' column is critical.
            
            if 'event_type' not in df.columns or 'next_hop' not in df.columns:
                # If fields missing, skip (might be incomplete log)
                continue
                
            sent_df = df[df['event_type'] == 'SENT'].copy()
            sent_df.dropna(subset=['next_hop'], inplace=True)
            
            # Identify unique links from this node
            unique_next_hops = sent_df['next_hop'].unique()
            
            for nh in unique_next_hops:
                link_id = f"{node_id}->{nh}"
                link_traffic = sent_df[sent_df['next_hop'] == nh].copy()
                
                # We only need timestamps for the attack
                # Sort by timestamp
                link_traffic.sort_values('timestamp', inplace=True)
                
                links[link_id] = link_traffic
                
        except Exception as e:
            logger.warning(f"Could not parse {filename}: {e}")
            
    logger.info(f"Identified {len(links)} distinct links in the network.")
    return links

def get_target_input_stream(run_dir, target_src):
    """
    Extracts the input stream f(t) for the target source.
    Reads system_in.csv.
    """
    sys_in_path = os.path.join(run_dir, "system_in.csv")
    if not os.path.exists(sys_in_path):
        logger.error(f"system_in.csv not found in {run_dir}. Run consolidate_traffic_logs.py first?")
        return None
        
    df = pd.read_csv(sys_in_path)
    # Target traffic: src matches target, event is effectively "Input to system"
    # system_in.csv contains RECEIVED events at Entry Nodes from Clients.
    
    target_df = df[df['src'] == target_src].sort_values('timestamp')
    if target_df.empty:
        logger.warning(f"No traffic found for target {target_src}")
        return None
        
    return target_df['timestamp'].values

def compute_convolution(input_timestamps, mu, k, duration, time_resolution=0.1):
    """
    Computes (d * f)(t) as per Equation 24.
    d(t) = Erlang(k, mu) -> Note: Paper uses Exponential(mu) for single hop, 
                            but implies d(x) is the delay characteristic.
                            For k=1, Erlang(1, mu) == Exponential(mu).
    
    Args:
        input_timestamps: Array of t where input packets arrived.
        mu: Rate parameter of the mix (1/Mean Delay per hop).
        k: Number of hops (Shape parameter).
        duration: Total duration of the observation.
        time_resolution: Step size for discretization (dt).
        
    Returns:
        convolved_signal: Array representing PDF values at each time step.
        time_axis: Array of time steps.
    """
    # Create discretized time axis
    num_bins = int(np.ceil(duration / time_resolution)) + 1
    
    # 1. Create Input PDF f(t) (Discretized)
    # Histogram of inputs
    counts, bin_edges = np.histogram(input_timestamps, bins=num_bins, range=(0, duration))
    # Normalize to PDF: sum(counts) / (Total * dt) might NOT be 1 if Total != counts (loss?)
    # But strictly, f(t) is the PROBABILITY that a specific packet arrives at t.
    # The rate is lambda_f. f(t) is normalized so Integral f(t) dt = 1.
    
    if len(input_timestamps) == 0:
        return np.zeros(num_bins), bin_edges[:-1]
        
    f_t = counts / (len(input_timestamps) * time_resolution)
    
    # 2. Create Delay Kernel d(t)
    # Erlang PDF
    # Scipy 'erlang' uses shape=a, scale=s. Mean = a*s. Var = a*s^2.
    # We want Erlang-k with rate mu (per hop).
    # If 1 hop: Exp(mu). Mean = 1/mu.
    # So Scale = 1/mu.
    scale = 1.0 / mu
    
    # Kernel length: Covers 99.9% of delay prob
    max_delay = erlang.ppf(0.999, k, scale=scale)
    kernel_bins = int(np.ceil(max_delay / time_resolution))
    kernel_x = np.linspace(0, max_delay, kernel_bins)
    
    d_t = erlang.pdf(kernel_x, k, scale=scale)
    d_t /= np.sum(d_t) * time_resolution # Normalize discrete sum approx
    
    # 3. Convolve
    # (d * f)(t)
    conv_full = np.convolve(f_t, d_t, mode='full')
    conv_result = conv_full[:num_bins] * time_resolution # Scale by dt for discrete convolution
    
    # Ensure numerical stability (no negative probs)
    conv_result = np.maximum(conv_result, 0)
    
    # Renormalize to ensure it's a valid PDF (Integral approx 1)
    # sum(conv) * dt should be approx 1
    current_sum = np.sum(conv_result) * time_resolution
    if current_sum > 0:
        conv_result /= current_sum
        
    return conv_result, bin_edges[:-1]

def strict_likelihood_ratio_test(links_data, convolved_pdf, time_resolution, 
                                 lambda_f, total_duration, duration_offset):
    """
    Implements Equation 28: log L = Sum( log C_X(Xi) ) - Sum( log U(u) )
    Returns detailed results including cumulative LLR evolution.
    """
    results = []
    
    # U(t) = u = 1/T
    u = 1.0 / total_duration
    log_u = np.log(u)
    
    for link_id, df in links_data.items():
        if df.empty:
            continue
            
        timestamps = df['timestamp'].values
        # Parse timestamps relative to T_start (0)
        t_norm = timestamps - duration_offset
        
        # Valid observations within [0, T]
        valid_indices = (t_norm >= 0) & (t_norm < total_duration)
        if not np.any(valid_indices):
            continue
            
        observations = t_norm[valid_indices]
        valid_timestamps = timestamps[valid_indices]
        
        n_obs = len(observations)
        lambda_link = n_obs / total_duration
        
        # Determine mixture weights
        lambda_f_eff = min(lambda_f, lambda_link * 0.999) # prevent div/0
        
        w_signal = lambda_f_eff / lambda_link
        w_noise = (lambda_link - lambda_f_eff) / lambda_link
        
        # Map observations to PDF bins
        bin_indices = (observations / time_resolution).astype(int)
        bin_indices = np.clip(bin_indices, 0, len(convolved_pdf) - 1)
        
        # Get PDF values at observation times
        pdf_vals = convolved_pdf[bin_indices]
        
        # Calculate C_X(t)
        c_x_vals = w_signal * pdf_vals + w_noise * u
        c_x_vals = np.maximum(c_x_vals, 1e-100) # Avoid log(0)
        
        # LLR per packet: log(C_X(t)) - log(u)
        llr_per_packet = np.log(c_x_vals) - log_u
        
        # Cumulative Evolution
        cum_llr = np.cumsum(llr_per_packet)
        final_score = cum_llr[-1]
        
        # Pack evolution data: [timestamp, packet_index, cumulative_llr]
        # To save space, maybe only store every Nth point or just the full array?
        # User said "rechenkapazität ist kein problem", "alle zwischenergebnisse".
        # We store full evolution.
        evolution = []
        for i in range(n_obs):
            evolution.append((float(valid_timestamps[i]), i+1, float(cum_llr[i])))

        results.append({
            'link': link_id,
            'llr': final_score,
            'obs_count': n_obs,
            'rate': lambda_link,
            'evolution': evolution
        })
        
    return pd.DataFrame(results)

def main():
    parser = argparse.ArgumentParser(description="Strict Link Trace Traffic Analysis (Paper Sec 3.4)")
    parser.add_argument("--run-dir", required=True, help="Path to run directory")
    parser.add_argument("--target", required=True, help="Target Source ID (e.g. c1)")
    parser.add_argument("--mu", type=float, default=0.5, help="Mix rate mu (packets/sec/hop)")
    parser.add_argument("--k-hops", type=int, default=1, help="Number of hops for delay model (1 for direct link trace)")
    parser.add_argument("--resolution", type=float, default=0.1, help="Time resolution in seconds")
    
    args = parser.parse_args()
    
    import sys
    
    # 1. Load Data
    print(f"--- Strict Link Trace Analysis ---", flush=True)
    print(f"Target: {args.target}, Mu: {args.mu}, K: {args.k_hops}", flush=True)
    
    input_timestamps = get_target_input_stream(args.run_dir, args.target)
    if input_timestamps is None:
        print("Error: Could not load target input stream.", flush=True)
        sys.exit(1)
        
    links = load_all_traffic_logs(args.run_dir)
    if not links:
        print("Error: No links found in logs.", flush=True)
        sys.exit(1)

    # 2. Setup Time Definitions
    all_timestamps = np.concatenate([df['timestamp'].values for df in links.values()] + [input_timestamps])
    global_start = all_timestamps.min()
    global_end = all_timestamps.max()
    duration = global_end - global_start
    if duration <= 0: duration = 1.0
    
    lambda_f = len(input_timestamps) / duration
    print(f"Analysis Window: {duration:.2f}s. Target Rate: {lambda_f:.2f} pkts/s")
    
    # 3. Model Construction (Convolution)
    input_ts_norm = input_timestamps - global_start
    convolved_pdf, _ = compute_convolution(input_ts_norm, args.mu, args.k_hops, duration, args.resolution)
    
    # 4. Global Hypothesis Testing
    results_df = strict_likelihood_ratio_test(links, convolved_pdf, args.resolution, 
                                              lambda_f, duration, global_start)
    
    if results_df.empty:
        print(f"No results calculated. Analysis Window: {global_start} to {global_end} ({duration}s).", flush=True)
        print(f"Input packets: {len(input_timestamps)}. Link count: {len(links)}.", flush=True)
        sys.exit(1)
        
    # Sort by Score
    results_df.sort_values('llr', ascending=False, inplace=True)
    
    # 5. Output
    print("\n--- Link Trace Results (Top 20) ---")
    print(f"{'Link':<30} | {'LLR Score':<10} | {'Pkts':<6}")
    print("-" * 55)
    
    for _, row in results_df.head(20).iterrows():
        print(f"{row['link']:<30} | {row['llr']:<10.2f} | {int(row['obs_count']):<6}")
        
    # Create output directory
    output_dir = os.path.join(args.run_dir, "analysis_results")
    os.makedirs(output_dir, exist_ok=True)

    # Standard CSV (summary)
    out_csv = os.path.join(output_dir, f"strict_link_trace_k{args.k_hops}_{args.target}.csv")
    csv_df = results_df.drop(columns=['evolution'])
    csv_df.to_csv(out_csv, index=False)
    print(f"\nSummary results saved to: {out_csv}")
    
    # Detailed JSON (with evolution)
    # Convert to list of dicts
    import json
    out_json = os.path.join(output_dir, f"strict_link_trace_k{args.k_hops}_{args.target}_evolution.json")
    
    # Prepare data for JSON (handle numpy types)
    json_data = {
        "metadata": {
            "target": args.target,
            "mu": args.mu,
            "k_hops": args.k_hops,
            "duration": float(duration),
            "target_packets": len(input_timestamps),
            "lambda_f": float(lambda_f)
        },
        "results": []
    }
    
    # Save top 50 links to avoid massive JSONs if graph is huge (user likely only cares about candidates)
    # Or save all? User said "alle zwischenergebnisse".
    # Let's save all, user said storage/compute is no problem.
    
    for _, row in results_df.iterrows():
        json_data["results"].append({
            "link": row['link'],
            "llr": float(row['llr']),
            "obs_count": int(row['obs_count']),
            "rate": float(row['rate']),
            "evolution": row['evolution'] # List of [ts, idx, score]
        })
        
    with open(out_json, 'w') as f:
        json.dump(json_data, f, indent=2)
    print(f"Detailed evolution data saved to: {out_json}")

if __name__ == "__main__":
    main()
