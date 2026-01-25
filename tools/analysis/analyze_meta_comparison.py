import os
import json
import matplotlib.pyplot as plt
import pandas as pd
import argparse
import glob

def load_run_metrics(log_dir):
    """
    Loads metrics from a single run directory.
    Returns: dict with 'name', 'general', 'anonymity'
    """
    run_name = os.path.basename(log_dir)
    
    general_file = os.path.join(log_dir, "analysis_results", "general_metrics.json")
    anonymity_file = os.path.join(log_dir, "analysis_results", "anonymity_stats.json")
    
    metrics = {'name': run_name}
    
    if os.path.exists(general_file):
        with open(general_file, 'r') as f:
            metrics['general'] = json.load(f)
    else:
        metrics['general'] = {}
        
    if os.path.exists(anonymity_file):
        with open(anonymity_file, 'r') as f:
            metrics['anonymity'] = json.load(f)
    else:
        metrics['anonymity'] = {}
        
    return metrics

def plot_comparison(data_df, metric_col, title, output_path, ylabel="Value"):
    if metric_col not in data_df.columns: return

    plt.figure(figsize=(12, 6))
    
    # Sort by Name
    df = data_df.sort_values('name')
    
    bars = plt.bar(df['name'], df[metric_col], color='skyblue')
    
    plt.title(title)
    plt.ylabel(ylabel)
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    # Value labels
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                 f'{height:.4f}',
                 ha='center', va='bottom', rotation=0)
                 
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("logs_root", help="Root directory containing multiple test run folders")
    args = parser.parse_args()
    
    runs = []
    
    # Find all subdirectories
    for entry in os.scandir(args.logs_root):
        if entry.is_dir() and os.path.exists(os.path.join(entry.path, "analysis_results")):
            runs.append(load_run_metrics(entry.path))
            
    if not runs:
        print("No analyzed runs found.")
        return
        
    # Flatten Data for Plotting
    rows = []
    for r in runs:
        row = {'name': r['name']}
        
        # General
        g = r.get('general', {})
        row['loss_rate'] = g.get('loss_rate', 0)
        row['avg_latency'] = g.get('avg_latency', 0)
        row['throughput'] = g.get('total_received', 0) # Packets received
        
        # Anonymity (Strict Link Trace)
        a = r.get('anonymity', {})
        # Assuming anonymity_stats.json has 'system_entropy' or similar
        # Or 'mix_entropy'? Let's check strict analysis output format later.
        # For now, put placeholders or check keys if I knew them.
        # Strict analysis usually outputs 'global_metrics' -> 'diaz_anonymity'
        
        # Refinement needed here once strict analysis is standardized.
        if 'global_metrics' in a:
             row['diaz_anonymity'] = a['global_metrics'].get('diaz_anonymity', 0)
             row['attacker_confidence'] = a['global_metrics'].get('attacker_confidence', 0) # e.g. Max LLR
        
        rows.append(row)
        
    df = pd.DataFrame(rows)
    
    output_dir = os.path.join(args.logs_root, "meta_comparison")
    if not os.path.exists(output_dir): os.makedirs(output_dir)
    
    # Plotting
    plot_comparison(df, 'loss_rate', 'Packet Loss Rate per Run', os.path.join(output_dir, "cmp_loss_rate.png"), "Loss Rate (0-1)")
    plot_comparison(df, 'avg_latency', 'Average Latency per Run', os.path.join(output_dir, "cmp_latency.png"), "Seconds")
    plot_comparison(df, 'diaz_anonymity', 'Diaz Anonymity (Entropy) per Run', os.path.join(output_dir, "cmp_anonymity.png"), "Entropy (0-1)")
    
    print(f"Meta Analysis complete. Comparison plots saved to {output_dir}")

if __name__ == "__main__":
    main()
