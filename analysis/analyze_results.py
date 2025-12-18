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

def calculate_mix_metrics(mix_df):
    """
    Calculates residence time and anonymity set size (entropy) for mix nodes.
    """
    if mix_df.empty:
        return {}, pd.DataFrame()

    # Separate SENT and RECEIVED events at mixers
    # RECEIVED at mix = Ingress
    # SENT at mix = Egress
    # We allow tracking by packet_id assuming it doesn't change OR we track by correlation if needed.
    # In this simulation, packet_id seems preserved.
    
    mix_in = mix_df[mix_df['event_type'] == 'RECEIVED'].rename(columns={'timestamp': 't_in'})
    mix_out = mix_df[mix_df['event_type'] == 'SENT'].rename(columns={'timestamp': 't_out'})
    
    # Merge on packet_id AND mix_id to match specific visits
    mix_events = pd.merge(mix_in[['packet_id', 'mix_id', 't_in']], 
                          mix_out[['packet_id', 'mix_id', 't_out']], 
                          on=['packet_id', 'mix_id'], 
                          how='inner')
    
    mix_events['residence_time'] = mix_events['t_out'] - mix_events['t_in']
    
    # --- Entropy / Anonymity Set Calculation ---
    # For each 'SENT' (egress) event from a mix, how many packets were currently in the pool?
    # Pool = Packets satisfying: t_in < t_current_out AND t_out >= t_current_out
    # (i.e., inside the mix at the moment of emission)
    
    # This calculation can be slow O(N^2) if not optimized. We'll do a per-mix-node sort.
    anonymity_metrics = []
    
    for mix_id, group in mix_events.groupby('mix_id'):
        # Sort events by time to simulate state
        # Create a timeline of events: (time, type, packet_id)
        # Type: +1 for IN, -1 for OUT (but we care about the moment BEFORE the OUT)
        
        # Simpler approach for moderate dataset:
        # Iterate through each egress event, count ingress events < t_out and egress events > t_out
        # wait, egress events > t_out means they are STILL in the mix.
        # But we also need to exclude packets that ALREADY left.
        # Packets in Mix = (All Ingress < t) - (All Egress < t)
        
        group = group.sort_values('t_out')
        
        # We can just iterate the sorted output and check the pool size
        # Or simpler:
        # For row i (egress at t_out_i):
        #   count rows j where t_in_j < t_out_i AND t_out_j >= t_out_i
        #   (t_out_j >= t_out_i includes the packet itself, so min size is 1)
        
        # Vectorized approach:
        t_outs = group['t_out'].values
        t_ins = group['t_in'].values
        
        # For each t_out, sum(1 if t_in < t_out and t_out_j >= t_out)
        # Broadercasting:
        # Mask: (t_ins[:, None] < t_outs) & (t_outs_all[:, None] >= t_outs) -- wait, no.
        
        # Let's iterate, 450 packets is small enough.
        for idx, row in group.iterrows():
            t_current = row['t_out']
            # Pool size = count of packets that arrived before valid current outgoing time
            # AND haven't left before current outgoing time.
            pool_size = ((group['t_in'] < t_current) & (group['t_out'] >= t_current)).sum()
            
            entropy = np.log2(pool_size) if pool_size > 0 else 0
            anonymity_metrics.append({
                'mix_id': mix_id,
                'packet_id': row['packet_id'],
                't_out': row['t_out'],
                'pool_size': pool_size,
                'entropy': entropy
            })
            

    mix_stats_df = pd.DataFrame(anonymity_metrics)
    
    metrics = {
        'avg_residence_time': mix_events['residence_time'].mean(),
        'max_residence_time': mix_events['residence_time'].max(),
        'avg_pool_size': mix_stats_df['pool_size'].mean() if not mix_stats_df.empty else 0,
        'avg_entropy': mix_stats_df['entropy'].mean() if not mix_stats_df.empty else 0 
    }
    
    return metrics, mix_stats_df

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

def plot_entropy_distribution(mix_stats_df, output_path):
    if mix_stats_df.empty:
        return
    plt.figure(figsize=(10, 6))
    plt.hist(mix_stats_df['entropy'], bins=20, alpha=0.7, color='green', edgecolor='black')
    plt.title('Mix Entropy (Anonymity) Distribution')
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
    mix_metrics, mix_stats_df = calculate_mix_metrics(mix_df)
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
        
        if mix_stats_df is not None and not mix_stats_df.empty:
            plot_entropy_distribution(mix_stats_df, os.path.join(output_dir, "entropy_distribution.png"))

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
            if mix_stats_df is not None and not mix_stats_df.empty:
                f.write(f"Avg Mix Residence Time: {mix_metrics['avg_residence_time']:.4f} s\n")
                f.write(f"Avg Anonymity Set Size: {mix_metrics['avg_pool_size']:.2f} packets\n")
                f.write(f"Avg Mix Entropy: {mix_metrics['avg_entropy']:.4f} bits\n")

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
