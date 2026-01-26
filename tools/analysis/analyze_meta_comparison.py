import os
import json
import matplotlib.pyplot as plt
import pandas as pd
import argparse
import glob
import re

def load_run_metrics(log_dir):
    """
    Loads metrics from a single run directory.
    Returns: dict with 'name', 'general', 'anonymity'
    """
    run_name = os.path.basename(log_dir)
    
    metrics = {'name': run_name}
    
    # Load General Metrics
    general_file = os.path.join(log_dir, "analysis_results", "general_metrics.json")
    metrics['general'] = {} # Initialize as empty dict
    if os.path.exists(general_file):
        try:
            with open(general_file, 'r') as f:
                content = f.read()
                if content.strip(): # Only try to load if content is not empty
                    metrics['general'] = json.loads(content)
        except json.JSONDecodeError as e:
            print(f"Warning: Corrupt JSON in {general_file}: {e}")
        
    # Load Anonymity Stats
    anonymity_file = os.path.join(log_dir, "analysis_results", "anonymity_stats.json")
    metrics['anonymity'] = {} # Initialize as empty dict
    if os.path.exists(anonymity_file):
        try:
            with open(anonymity_file, 'r') as f:
                content = f.read()
                if content.strip(): # Only try to load if content is not empty
                    metrics['anonymity'] = json.loads(content)
        except json.JSONDecodeError as e:
            print(f"Warning: Corrupt JSON in {anonymity_file}: {e}")
            
    # Determine Ground Truth Target (who was c1 actually determining?)
    # We try to read c1_traffic.csv to find the most frequent destination.
    target_client = "c1"
    true_recipient = "c3" # Default fallback
    
    traffic_file = os.path.join(log_dir, f"{target_client}_traffic.csv")
    if os.path.exists(traffic_file):
        try:
            # Manual parse to avoid CSV errors with unquoted SURBs containing commas
            dst_counts = {}
            with open(traffic_file, 'r', encoding='utf-8', errors='replace') as f:
                next(f, None) # Skip header
                for line in f:
                    parts = line.split(',')
                    if len(parts) > 6: # Ensure we have enough columns
                        # timestamp(0), event(1), pid(2), mid(3), src(4), dst(5)
                        if parts[1] == 'SENT' and parts[4] == target_client:
                            dst = parts[5]
                            if dst.startswith('c') and dst != target_client:
                                dst_counts[dst] = dst_counts.get(dst, 0) + 1
            
            if dst_counts:
                # Get max key
                true_recipient = max(dst_counts, key=dst_counts.get)
                # print(f"  [Info] Run {run_name}: Detected True Recipient for {target_client} -> {true_recipient} (Count: {dst_counts[true_recipient]})")
        except Exception as e:
            print(f"Warning: Could not determine ground truth from {traffic_file}: {e}")

    # Check Attack Success (Top Link -> True Recipient?)
    # Look for the strict trace CSV
    csv_pattern = os.path.join(log_dir, "analysis_results", "strict_link_trace_*.csv")
    csv_files = glob.glob(csv_pattern)
    metrics['attack_success'] = None 
    metrics['true_recipient'] = true_recipient # Store for debugging/display
    
    if csv_files:
        try:
            # Assume one trace file per run for now
            df_trace = pd.read_csv(csv_files[0])
            if not df_trace.empty and 'link' in df_trace.columns:
                # Check Top 1
                top_link = df_trace.iloc[0]['link']
                # Allow bidirectional match (target endpoint found)
                link_str = str(top_link)
                if f"->{true_recipient}" in link_str or f"{true_recipient}->" in link_str:
                    metrics['attack_success'] = True
                else:
                    metrics['attack_success'] = False
                    
                # Check Top 2 (Secondary Candidate)
                metrics['attack_success_top2'] = False # Default
                if len(df_trace) > 1:
                    second_link = df_trace.iloc[1]['link']
                    link_str_2 = str(second_link)
                    if f"->{true_recipient}" in link_str_2 or f"{true_recipient}->" in link_str_2:
                        metrics['attack_success_top2'] = True
        except Exception as e:
            print(f"Error checking attack success in {csv_files[0]}: {e}")
        
    return metrics

def plot_comparison(data_df, metric_col, title, output_path, ylabel="Value", color_col=None):
    if metric_col not in data_df.columns: return

    plt.figure(figsize=(12, 6))
    
    # Sort by Name
    df = data_df.sort_values('name')
    
    # Shorten names for display (Remove Testrun_Timestamp prefix)
    # Pattern: Testrun_20260125_190457_... -> ...
    short_names = df['name'].apply(lambda x: re.sub(r'^Testrun_\d{8}_\d{6}_', '', x))
    
    colors = 'skyblue'
    if color_col and color_col in df.columns:
        # Map success to colors
        # True -> Green (#2ecc71), False -> Red (#e74c3c), None -> Gray
        colors = df[color_col].apply(lambda x: '#2ecc71' if x is True else ('#e74c3c' if x is False else '#95a5a6')).tolist()
    
    bars = plt.bar(short_names, df[metric_col], color=colors)
    
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
             row['shannon_entropy'] = a['global_metrics'].get('system_entropy', 0)
             row['attacker_confidence'] = a['global_metrics'].get('attacker_confidence', 0) # e.g. Max LLR
        
        row['attack_success'] = r.get('attack_success')
        row['attack_success_top2'] = r.get('attack_success_top2')
        
        rows.append(row)
        
    df = pd.DataFrame(rows)
    
    output_dir = os.path.join(args.logs_root, "meta_comparison")
    if not os.path.exists(output_dir): os.makedirs(output_dir)
    
    # Plotting
    plot_comparison(df, 'loss_rate', 'Packet Loss Rate per Run', os.path.join(output_dir, "cmp_loss_rate.png"), "Loss Rate (0-1)")
    plot_comparison(df, 'avg_latency', 'Average Latency per Run', os.path.join(output_dir, "cmp_latency.png"), "Seconds")
    plot_comparison(df, 'diaz_anonymity', 'Diaz Anonymity (Normalized Entropy) per Run', os.path.join(output_dir, "cmp_anonymity.png"), "Entropy (0-1)")
    plot_comparison(df, 'shannon_entropy', 'Shannon Entropy per Run', os.path.join(output_dir, "cmp_shannon.png"), "Bits")
    
    # Attacker Confidence Chart (Color-coded by Success)
    # We prefer Top-2 success if available, else standard success for coloring?
    # User asked for "success", usually standard. Let's use 'attack_success'.
    plot_comparison(df, 'attacker_confidence', 'Attacker Confidence (Max LLR)', 
                   os.path.join(output_dir, "cmp_confidence.png"), "Log Likelihood Ratio",
                   color_col='attack_success')
    
    # Generate HTML Dashboard
    generate_dashboard_html(df, output_dir)
    
    print(f"Meta Analysis complete. Comparison plots saved to {output_dir}")

def generate_dashboard_html(df, output_dir):
    """
    Generates a single HTML dashboard file summarizing the results.
    """
    html_path = os.path.join(output_dir, "dashboard.html")
    
    # Format DataFrame for Display
    display_df = df.copy()
    if 'loss_rate' in display_df.columns:
        display_df['loss_rate'] = display_df['loss_rate'].apply(lambda x: f"{x*100:.2f}%" if pd.notnull(x) else "N/A")
    if 'avg_latency' in display_df.columns:
        display_df['avg_latency'] = display_df['avg_latency'].round(4)
    if 'diaz_anonymity' in display_df.columns:
        display_df['diaz_anonymity'] = display_df['diaz_anonymity'].round(4)
    if 'attacker_confidence' in display_df.columns:
        display_df['attacker_confidence'] = display_df['attacker_confidence'].round(4)
        
    # Attack Success Formatting (Icons)
    if 'attack_success' in display_df.columns:
        display_df['attack_success'] = display_df['attack_success'].apply(
            lambda x: "✅ YES" if x is True else ("❌ NO" if x is False else "❓ N/A")
        )
    
    if 'attack_success_top2' in display_df.columns:
        display_df['attack_success_top2'] = display_df['attack_success_top2'].apply(
            lambda x: "✅ YES" if x is True else ("❌ NO" if x is False else "❓ N/A")
        )
        
    # Python to HTML Table
    table_html = display_df.to_html(index=False, classes='table table-striped table-hover', escape=False) # escape=False for HTML inside cells
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Loopix Analysis Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ padding: 20px; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
            .metric-card {{ background: #f8f9fa; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            h1, h2 {{ color: #2c3e50; }}
            .plot-container {{ text-align: center; margin-bottom: 40px; }}
            .plot-container img {{ max-width: 100%; height: auto; border: 1px solid #ddd; border-radius: 4px; padding: 5px; }}
            table {{ margin-top: 20px; }}
            th {{ background-color: #34495e !important; color: white; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="text-center mb-5">🚀 Loopix Network Analysis Dashboard</h1>
            
            <div class="metric-card">
                <h2>📊 Experiment Summary</h2>
                <div class="table-responsive">
                    {table_html}
                </div>
            </div>
            
            <div class="row">
                <div class="col-md-6">
                    <div class="metric-card">
                        <h2>🛡️ Anonymity (Diaz)</h2>
                        <div class="plot-container">
                            <img src="cmp_anonymity.png" alt="Anonymity Comparison">
                        </div>
                        <p class="text-muted">Higher is better. Measures the entropy of the anonymity set.</p>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="metric-card">
                        <h2>🎯 Attacker Confidence</h2>
                        <div class="plot-container">
                            <img src="cmp_confidence.png" alt="Attacker Confidence">
                        </div>
                        <p class="text-muted">Higher bars = Attacker is more sure. <span style="color:#2ecc71">Green</span> = Success, <span style="color:#e74c3c">Red</span> = Fail.</p>
                    </div>
                </div>
            </div>
            
            <div class="row">
                <div class="col-md-6">
                    <div class="metric-card">
                        <h2>🎲 Shannon Entropy</h2>
                        <div class="plot-container">
                            <img src="cmp_shannon.png" alt="Shannon Entropy Comparison">
                        </div>
                        <p class="text-muted">Higher is better. Absolute measure of uncertainty (in bits).</p>
                    </div>
                </div>
            </div>

            <div class="row mt-4">
                <div class="col-md-6">
                    <div class="metric-card">
                        <h2>📉 Packet Loss Rate</h2>
                        <div class="plot-container">
                            <img src="cmp_loss_rate.png" alt="Loss Rate Comparison">
                        </div>
                        <p class="text-muted">Lower is better. High loss indicates network failures or active attacks.</p>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="metric-card">
                        <h2>⏱️ Average Latency</h2>
                        <div class="plot-container">
                            <img src="cmp_latency.png" alt="Latency Comparison">
                        </div>
                        <p class="text-muted">Lower is generally better, but trade-off with anonymity exists.</p>
                    </div>
                </div>
            </div>
            
            <footer class="mt-5 text-center text-muted">
                <p>Generated by Loopix Analysis Suite</p>
            </footer>
        </div>
    </body>
    </html>
    """
    
    with open(html_path, "w", encoding='utf-8') as f:
        f.write(html_content)
        
    print(f"Dashboard generated: {html_path}")

if __name__ == "__main__":
    main()
