import os
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import glob
import numpy as np


def parse_logs(log_dir):
    """
    Parses sender, receiver, and mix node logs.
    Returns:
        traffic_df: DataFrame with end-to-end traffic (s* -> r*)
        mix_df: DataFrame with mix node operations (x*)
    """
    # --- End-to-End Traffic ---
    # --- End-to-End Traffic ---
    # Try to find Client logs (Loopix style)
    client_files = glob.glob(os.path.join(log_dir, "c*_traffic.csv"))
    
    # Fallback to legacy Sender/Receiver logs
    sent_files = glob.glob(os.path.join(log_dir, "s*_traffic.csv"))
    recv_files = glob.glob(os.path.join(log_dir, "r*_traffic.csv"))

    print(f"Found {len(client_files)} client logs, {len(sent_files)} sender logs, {len(recv_files)} receiver logs.")

    sent_dfs = []
    recv_dfs = []
    
    # Process Client Logs (Both Sent and Received)
    for f in client_files:
        try:
            df = pd.read_csv(f)
            # SENT events
            sent_part = df[df['event_type'].isin(['SENT', 'SENT_PRECALC', 'CREATED'])] 
            # Note: CREATED is usually the event for generating the packet. SENT might be lower level.
            # In Client.py I logged "CREATED" for the inner packet and "SENT_PRECALC" for precalc.
            # And send_packet logs? Node.send_packet usually logs something?
            # Src/run.py logger checks.
            # Let's assume CREATED is the start.
            # But wait, if I use CREATED, I need to match IDs.
            # If I look at Client.py, I explicitly log "CREATED" for generated traffic.
            if not sent_part.empty:
                sent_dfs.append(sent_part)
                
            # RECEIVED events
            recv_part = df[df['event_type'] == 'RECEIVED']
            if not recv_part.empty:
                recv_dfs.append(recv_part)
        except Exception as e:
            print(f"Error reading {f}: {e}")

    # Process Legacy Logs
    for f in sent_files:
        try:
            df = pd.read_csv(f)
            df = df[df['event_type'] == 'SENT']
            sent_dfs.append(df)
        except Exception as e:
            print(f"Error reading {f}: {e}")

    for f in recv_files:
        try:
            df = pd.read_csv(f)
            df = df[df['event_type'] == 'RECEIVED']
            recv_dfs.append(df)
        except Exception as e:
            print(f"Error reading {f}: {e}")

    if sent_dfs:
        sent_df = pd.concat(sent_dfs, ignore_index=True)
        if recv_dfs:
            recv_df = pd.concat(recv_dfs, ignore_index=True)
        else:
            recv_df = pd.DataFrame(columns=sent_df.columns)

        sent_df = sent_df.rename(columns={'timestamp': 't_sent'})
        recv_df = recv_df.rename(columns={'timestamp': 't_received'})

        traffic_df = pd.merge(sent_df[['packet_id', 't_sent', 'src', 'dst', 'size']], 
                              recv_df[['packet_id', 't_received']], 
                              on='packet_id', 
                              how='left')
    else:
        print("No sender data found.")
        traffic_df = pd.DataFrame()

    # --- Mix Node Logs ---
    mix_files = glob.glob(os.path.join(log_dir, "x*_traffic.csv"))
    print(f"Found {len(mix_files)} mix node logs.")
    
    mix_dfs = []
    for f in mix_files:
        try:
            df = pd.read_csv(f)
            df['mix_id'] = os.path.basename(f).split('_')[0] # e.g., 'x1' from 'x1_traffic.csv'
            mix_dfs.append(df)
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    if mix_dfs:
        mix_df = pd.concat(mix_dfs, ignore_index=True)
    else:
        mix_df = pd.DataFrame()

    return traffic_df, mix_df

def calculate_global_metrics(traffic_df):
    """
    Calculates Global Shannon Entropy.
    For each packet P (recv), we count how many other packets P' (sent) 
    were active (overlap) during P's lifetime [t_sent_P, t_recv_P].
    
    H(P) = log2(N_overlap)
    """
    if traffic_df.empty:
        return {}, pd.DataFrame()

    received_df = traffic_df.dropna(subset=['t_received']).copy()
    
    if received_df.empty:
        return {}, pd.DataFrame()

    sent_df = traffic_df[['packet_id', 't_sent', 't_received']].copy() # Includes all packets (even lost ones contributed to anonymity until lost?)
    # Strictly speaking, only packets IN the network contribute to the crowd.
    # Lost packets left the network at some point, but we don't know when.
    # We will assume lost packets contribute until 'max latency' or just ignore them for overlap?
    # Conservative: Only consider successfully received packets for the anonymity set.
    # Aggressive: Consider all sent packets, assuming lost ones lived for a while.
    # Let's stick to received packets for the "proven" anonymity set.
    
    # Vectorized overlap check is O(N^2), might be heavy for very large logs but fine for typical 10k experiments.
    # Optimization: Sort by start time.
    
    t_starts = received_df['t_sent'].values
    t_ends = received_df['t_received'].values
    
    # Broadcating approach:
    # Overlap Matrix: Start_i <= End_j AND End_i >= Start_j
    # Here we want to know for each packet i, how many j overlap.
    # The set includes itself, so min 1.
    
    # Memory efficient implementation for larger N: Loop with numpy
    entropy_values = []
    pool_sizes = []
    
    for i in range(len(received_df)):
        s_i = t_starts[i]
        e_i = t_ends[i]
        
        # Count j where (s_j <= e_i) AND (e_j >= s_i)
        # i.e., interval j started before i ended, and ended after i started.
        overlaps = np.sum((t_starts <= e_i) & (t_ends >= s_i))
        
        pool_sizes.append(overlaps)
        entropy_values.append(np.log2(overlaps))
        
    received_df['global_pool_size'] = pool_sizes
    received_df['global_entropy'] = entropy_values
    
    metrics = {
        'avg_global_entropy': np.mean(entropy_values),
        'min_global_entropy': np.min(entropy_values),
        'max_global_entropy': np.max(entropy_values),
        'avg_global_pool_size': np.mean(pool_sizes)
    }
    
    return metrics, received_df

def calculate_overhead(traffic_df, mix_df):
    """
    Calculates network overhead.
    Overhead Ratio = (Total Bytes Sent by Clients + Total Bytes Sent by Mixes) / Total Bytes Received by Receivers
    """
    if traffic_df.empty:
        return 0
        
    # Bytes sent by clients
    client_sent_bytes = traffic_df['size_x'].sum() if 'size_x' in traffic_df.columns else 0
    # Note: merge renamed 'size' to 'size_x' (from sent_df) or 'size_y' (from received_df)
    # Let's check parse_logs merge again. 
    # merged_df = pd.merge(sent_df[['packet_id', 't_sent', 'src', 'dst', 'size']], ...)
    # So 'size' is in traffic_df.
    if 'size' in traffic_df.columns:
        client_sent_bytes = traffic_df['size'].sum()
    
    # Bytes sent by mixes (Egress)
    mix_sent_bytes = 0
    if not mix_df.empty:
        # Assuming 'size' column exists in x logs. Let's check x1_traffic.csv from earlier view.
        # It has 'size'.
        mix_sent_df = mix_df[mix_df['event_type'] == 'SENT']
        mix_sent_bytes = mix_sent_df['size'].sum()
        
    total_transmitted = client_sent_bytes + mix_sent_bytes
    
    # Payload bytes received
    # We use 'size' from confirmed received packets
    received_packets = traffic_df.dropna(subset=['t_received'])
    payload_received_bytes = received_packets['size'].sum() if 'size' in received_packets.columns else 0
    
    if payload_received_bytes == 0:
        return 0
        
    overhead_ratio = total_transmitted / payload_received_bytes
    return overhead_ratio

def calculate_metrics(df):
    """
    Calculates latency, loss, and other metrics.
    """
    if df.empty:
        return {}

    total_sent = len(df)
    received_df = df.dropna(subset=['t_received'])
    total_received = len(received_df)
    
    loss_rate = (total_sent - total_received) / total_sent if total_sent > 0 else 0
    
    # Suppress SettingWithCopyWarning
    received_df = received_df.copy()
    received_df.loc[:, 'latency'] = received_df['t_received'] - received_df['t_sent']
    
    avg_latency = received_df['latency'].mean()
    max_latency = received_df['latency'].max()
    min_latency = received_df['latency'].min()
    jitter = received_df['latency'].std()

    return {
        'total_sent': total_sent,
        'total_received': total_received,
        'loss_rate': loss_rate,
        'avg_latency': avg_latency,
        'max_latency': max_latency,
        'min_latency': min_latency,
        'jitter': jitter,
        'received_df': received_df
    }

def plot_latency_histogram(df, output_path):
    plt.figure(figsize=(10, 6))
    plt.hist(df['latency'], bins=50, alpha=0.7, color='blue', edgecolor='black')
    plt.title('Message Latency Distribution')
    plt.xlabel('Latency (s)')
    plt.ylabel('Frequency')
    plt.grid(True, alpha=0.3)
    plt.savefig(output_path)
    plt.close()

def plot_entropy_distribution(entropy_series, output_path):
    if entropy_series.empty:
        return
    plt.figure(figsize=(10, 6))
    plt.hist(entropy_series, bins=20, alpha=0.7, color='purple', edgecolor='black')
    plt.title('Global Entropy (Anonymity Set) Distribution')
    plt.xlabel('Entropy (bits)')
    plt.ylabel('Frequency')
    plt.grid(True, alpha=0.3)
    plt.savefig(output_path)
    plt.close()

def plot_throughput(received_df, output_path, bin_size=1.0):
    if received_df.empty:
        return
        
    start_time = received_df['t_received'].min()
    end_time = received_df['t_received'].max()
    
    if pd.isna(start_time) or pd.isna(end_time):
        return

    bins = np.arange(start_time, end_time + bin_size, bin_size)
    
    # Count packets per bin
    counts, _ = np.histogram(received_df['t_received'], bins=bins)
    
    # Convert bin edges to relative time
    relative_time = bins[:-1] - start_time
    
    plt.figure(figsize=(10, 6))
    plt.plot(relative_time, counts, marker='o', linestyle='-')
    plt.title('Throughput over Time')
    plt.xlabel('Time (s)')
    plt.ylabel('Packets Received / sec')
    plt.grid(True, alpha=0.3)
    plt.savefig(output_path)
    plt.close()

def analyze_single_run(log_dir):
    """Analyzes a single test run directory."""
    print(f"\nAnalyzing logs in: {log_dir}")
    
    # Create analysis_results subdirectory
    output_dir = os.path.join(log_dir, "analysis_results")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    traffic_df, mix_df = parse_logs(log_dir)
    
    if traffic_df.empty:
        print("No traffic data found to analyze.")
        return

    metrics = calculate_metrics(traffic_df)
    global_metrics, entropy_df = calculate_global_metrics(traffic_df)
    # mix_metrics, mix_stats_df = calculate_mix_metrics(mix_df) # REMOVED in favor of global
    overhead_ratio = calculate_overhead(traffic_df, mix_df)
    
    print("-" * 30)
    print("Analysis Results:")
    print(f"Total Packets Sent: {metrics['total_sent']}")
    print(f"Total Packets Received: {metrics['total_received']}")
    print(f"Loss Rate: {metrics['loss_rate']:.2%}")
    print(f"Network Overhead Ratio: {overhead_ratio:.2f}x")
    
    if metrics['total_received'] > 0:
        # Plots
        received_df = metrics['received_df']
        plot_latency_histogram(received_df, os.path.join(output_dir, "latency_histogram.png"))
        plot_throughput(received_df, os.path.join(output_dir, "throughput_timeseries.png"))
        
        if entropy_df is not None and not entropy_df.empty:
            plot_entropy_distribution(entropy_df['global_entropy'], os.path.join(output_dir, "global_entropy_distribution.png"))

        print(f"Plots saved to {output_dir}")
        
        # Save summary to text file
        with open(os.path.join(output_dir, "analysis_summary.txt"), "w") as f:
            f.write("Analysis Results:\n")
            f.write(f"Total Packets Sent: {metrics['total_sent']}\n")
            f.write(f"Total Packets Received: {metrics['total_received']}\n")
            f.write(f"Loss Rate: {metrics['loss_rate']:.2%}\n")
            f.write(f"Network Overhead Ratio: {overhead_ratio:.2f}x\n")
            f.write(f"Average Latency: {metrics['avg_latency']:.4f} s\n")
            f.write(f"Max Latency: {metrics['max_latency']:.4f} s\n")
            f.write(f"Min Latency: {metrics['min_latency']:.4f} s\n")
            f.write(f"Jitter (Std Dev): {metrics['jitter']:.4f} s\n")
            if entropy_df is not None and not entropy_df.empty:
                f.write(f"Avg Global Anonymity Set: {global_metrics['avg_global_pool_size']:.2f} packets\n")
                f.write(f"Avg Global Entropy: {global_metrics['avg_global_entropy']:.4f} bits\n")
                f.write(f"Max Global Entropy: {global_metrics['max_global_entropy']:.4f} bits\n")

    else:
        print("No packets received, cannot calculate latency or throughput.")

def main():
    parser = argparse.ArgumentParser(description="Analyze Mixnet Test Run Logs")
    parser.add_argument("path", help="Path to a single test run or a base logs directory containing multiple runs")
    parser.add_argument("--force", action="store_true", help="Re-analyze even if analysis_results exists")
    args = parser.parse_args()

    target_path = args.path
    if not os.path.exists(target_path):
        print(f"Path not found: {target_path}")
        return

    # Check if this is a single run (contains a csv file directly?) OR check directory name format?
    # Heuristic: If it contains 's*_traffic.csv', it's a run.
    is_single_run = len(glob.glob(os.path.join(target_path, "s*_traffic.csv"))) > 0
    
    if is_single_run:
        analyze_single_run(target_path)
    else:
        # Assume it's a base directory containing 'Testrun_...' subdirs
        print(f"Scanning {target_path} for Testrun directories...")
        processed_count = 0
        
        # List subdirectories that look like Timestamps or start with Testrun
        for entry in os.scandir(target_path):
            if entry.is_dir() and "Testrun" in entry.name:
                run_dir = entry.path
                analysis_path = os.path.join(run_dir, "analysis_results")
                
                if os.path.exists(analysis_path) and not args.force:
                    print(f"Skipping {entry.name} (Already analyzed)")
                    continue
                    
                analyze_single_run(run_dir)
                processed_count += 1
                
        print(f"\nBatch analysis complete. Analyzed {processed_count} runs.")

if __name__ == "__main__":
    main()
