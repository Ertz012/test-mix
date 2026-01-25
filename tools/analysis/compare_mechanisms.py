
import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from math import pi

LOGS_ROOT = r"d:\Uni Hamburg\Module\MASTER\test-mix\logs"
OUTPUT_DIR = os.path.join(LOGS_ROOT, "analysis_results")

def parse_run_name(run_name):
    # Same logic as before
    mechanisms = [
        "baseline_no_errors",
        "baseline_errors",
        "retransmission",
        "path_reestablishment",
        "parallel_paths",
        "backup_mixes"
    ]
    mech = "unknown"
    noise = "normal"
    
    for m in mechanisms:
        if m in run_name:
            mech = m
            break
            
    if "no_noise" in run_name:
        noise = "no_noise"
    elif "high_noise" in run_name:
        noise = "high_noise"
    elif "long" in run_name:
        noise = "normal"
        
    return mech, noise

def get_latency(run_dir):
    try:
        in_file = os.path.join(run_dir, "system_in.csv")
        out_file = os.path.join(run_dir, "system_out.csv")
        
        if not os.path.exists(in_file) or not os.path.exists(out_file):
            return None
            
        df_in = pd.read_csv(in_file)
        df_out = pd.read_csv(out_file)
        
        # Merge on message_id
        merged = pd.merge(df_in, df_out, on="message_id", suffixes=('_in', '_out'))
        
        # Latency = out - in
        merged['latency'] = merged['timestamp_out'] - merged['timestamp_in']
        
        return merged['latency'].mean()
    except Exception as e:
        print(f"Error calculating latency for {run_dir}: {e}")
        return None

def count_lines(filepath):
    try:
        with open(filepath, 'rb') as f:
            return sum(1 for _ in f) - 1 # Minus header
    except:
        return 0

def get_overhead(run_dir):
    try:
        out_file = os.path.join(run_dir, "system_out.csv")
        if not os.path.exists(out_file):
            return None, None
            
        delivered_count = count_lines(out_file)
        if delivered_count <= 0:
            return None, 0
            
        # Total network traffic (sum of all *_traffic.csv lines)
        total_traffic = 0
        traffic_files = glob.glob(os.path.join(run_dir, "*_traffic.csv"))
        for tf in traffic_files:
            total_traffic += count_lines(tf)
            
        if total_traffic == 0:
            return None, 0
            
        overhead_ratio = total_traffic / delivered_count
        return overhead_ratio, total_traffic
    except Exception as e:
        print(f"Error calculating overhead for {run_dir}: {e}")
        return None, None

def main():
    print("--- Trilemma Analysis: Anonymity vs Latency vs Overhead ---")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 1. Load Anonymity Data (Meta-Analysis)
    meta_file = os.path.join(OUTPUT_DIR, "meta_analysis_raw.csv")
    if os.path.exists(meta_file):
        df_meta = pd.read_csv(meta_file)
    else:
        print("Warning: meta_analysis_raw.csv not found. LLR data might be missing.")
        df_meta = pd.DataFrame()

    # 2. Iterate Runs for Entropy and Performance
    data = []
    
    run_dirs = glob.glob(os.path.join(LOGS_ROOT, "Testrun_*"))
    print(f"Processing {len(run_dirs)} runs...")
    
    for run_dir in run_dirs:
        run_name = os.path.basename(run_dir)
        mech, noise = parse_run_name(run_name)
        
        # Load Entropy
        entropy = None
        entropy_file = os.path.join(run_dir, "analysis_results", "loopix_entropy_summary.csv")
        if os.path.exists(entropy_file):
            try:
                df_ent = pd.read_csv(entropy_file)
                # Filter for Mix nodes only (x*) for fairer comparison? 
                # Or average of all?
                # Mix entropy is the standard metric.
                mix_ent = df_ent[df_ent['Node'].str.startswith('x')]
                if not mix_ent.empty:
                    entropy = mix_ent['Mean_Entropy'].mean()
                else:
                    entropy = df_ent['Mean_Entropy'].mean()
            except:
                pass
                
        # Load Performance
        latency = get_latency(run_dir)
        overhead, total_pkts = get_overhead(run_dir)
        
        # Get LLR from meta (if available)
        llr = None
        if not df_meta.empty:
            match = df_meta[df_meta['Run'] == run_name]
            if not match.empty:
                llr = match.iloc[0]['Max_LLR']
                
        data.append({
            'Run': run_name,
            'Mechanism': mech,
            'Noise': noise,
            'Entropy': entropy,
            'Max_LLR': llr,
            'Latency': latency,
            'Overhead_Ratio': overhead,
            'Total_Packets': total_pkts
        })
        
    df = pd.DataFrame(data)
    df.to_csv(os.path.join(OUTPUT_DIR, "trilemma_raw.csv"), index=False)
    print("Saved raw data.")
    
    # 3. Aggregation & Normalization
    # Group by Mechanism + Noise
    summary = df.groupby(['Mechanism', 'Noise']).mean(numeric_only=True).reset_index()
    
    # Normalize metrics to 0-1 for Radar Chart
    # Anonymity: Higher is better (Entropy). Lower is better (LLR).
    # Performance: Lower is better (Latency, Overhead).
    
    # For standardization, let's invert the "Bad" metrics so "Higher = Better"
    # Or just plot raw normalized coordinates.
    
    # Normalize function
    def normalize(series):
        return (series - series.min()) / (series.max() - series.min())

    # Create normalized columns
    summary['Norm_Entropy'] = normalize(summary['Entropy'])
    summary['Norm_LLR_Inv'] = 1 - normalize(summary['Max_LLR']) # Invert LLR (High LLR = Bad Anonymity)
    summary['Norm_Latency_Inv'] = 1 - normalize(summary['Latency']) # Invert Latency (High Latency = Bad)
    summary['Norm_Overhead_Inv'] = 1 - normalize(summary['Overhead_Ratio']) # Invert Overhead
    
    # Save Summary
    summary.to_csv(os.path.join(OUTPUT_DIR, "trilemma_summary.csv"), index=False)
    print(summary[['Mechanism', 'Noise', 'Entropy', 'Max_LLR', 'Latency', 'Overhead_Ratio']])

    # 4. Visualization
    
    # Clean names
    summary['Mechanism'] = summary['Mechanism'].str.replace('baseline_', '').str.replace('_', '\n')
    
    # Plot 1: Radar Chart (Spider Plot) for "Normal" Noise
    # We compare mechanisms in Normal noise environment
    subset = summary[summary['Noise'] == 'normal'].copy()
    
    if not subset.empty:
        # Categories: Entropy, Low LLR, Low Latency, Low Overhead
        categories = ['Entropy', 'Resistance\n(Inv LLR)', 'Speed\n(Inv Latency)', 'Efficiency\n(Inv Overhead)']
        N = len(categories)
        
        # What value to plot? The normalized values
        # We need to close the loop
        angles = [n / float(N) * 2 * pi for n in range(N)]
        angles += angles[:1]
        
        plt.figure(figsize=(10, 10))
        ax = plt.subplot(111, polar=True)
        
        # Draw one line per mechanism
        # Define palette
        palette = sns.color_palette("bright", len(subset))
        
        for i, (idx, row) in enumerate(subset.iterrows()):
            values = [
                row['Norm_Entropy'], 
                row['Norm_LLR_Inv'], 
                row['Norm_Latency_Inv'], 
                row['Norm_Overhead_Inv']
            ]
            values += values[:1] # Close loop
            
            ax.plot(angles, values, linewidth=2, linestyle='solid', label=row['Mechanism'], color=palette[i])
            ax.fill(angles, values, color=palette[i], alpha=0.1)
            
        plt.xticks(angles[:-1], categories)
        plt.title("The Anonymity Trilemma (1.0 = Best)", size=15, y=1.1)
        plt.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1))
        
        plt.savefig(os.path.join(OUTPUT_DIR, "plot_trilemma_radar_normal.png"))
        plt.close()
        
    # Plot 2: Scatter "Trade-off" (Latency vs Anonymity)
    # X=Latency, Y=Entropy, Size=Overhead
    plt.figure(figsize=(10, 6))
    sns.scatterplot(
        data=summary, 
        x='Latency', 
        y='Entropy', 
        hue='Mechanism', 
        style='Noise',
        size='Overhead_Ratio',
        sizes=(50, 400),
        alpha=0.7
    )
    plt.title("Trade-off: Anonymity vs Latency (Size = Overhead Cost)")
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "plot_tradeoff_scatter.png"))
    plt.close()

if __name__ == "__main__":
    main()
