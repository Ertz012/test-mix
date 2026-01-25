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
            
    # Check Attack Success (Top Link -> c3?)
    # Look for the strict trace CSV
    csv_pattern = os.path.join(log_dir, "analysis_results", "strict_link_trace_*.csv")
    csv_files = glob.glob(csv_pattern)
    metrics['attack_success'] = None # default
    
    if csv_files:
        try:
            # Assume one trace file per run for now
            df_trace = pd.read_csv(csv_files[0])
            if not df_trace.empty and 'link' in df_trace.columns:
                top_link = df_trace.iloc[0]['link']
                # Link format: "NodeID->NextHopID"
                # We assume c1 -> c3 is the target flow.
                # So if top link ends with '->c3', success.
                if str(top_link).endswith('->c3'):
                    metrics['attack_success'] = True
                else:
                    metrics['attack_success'] = False
        except Exception as e:
            print(f"Error checking attack success in {csv_files[0]}: {e}")
        
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
        
        row['attack_success'] = r.get('attack_success')
        
        rows.append(row)
        
    df = pd.DataFrame(rows)
    
    output_dir = os.path.join(args.logs_root, "meta_comparison")
    if not os.path.exists(output_dir): os.makedirs(output_dir)
    
    # Plotting
    plot_comparison(df, 'loss_rate', 'Packet Loss Rate per Run', os.path.join(output_dir, "cmp_loss_rate.png"), "Loss Rate (0-1)")
    plot_comparison(df, 'avg_latency', 'Average Latency per Run', os.path.join(output_dir, "cmp_latency.png"), "Seconds")
    plot_comparison(df, 'diaz_anonymity', 'Diaz Anonymity (Entropy) per Run', os.path.join(output_dir, "cmp_anonymity.png"), "Entropy (0-1)")
    
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
                        <h2>🕵️ Attacker Confidence</h2>
                        <p class="text-muted">Does the attacker know who you are talking to? See table for 'Max LLR' and 'Attack Success'.</p>
                        <div class="alert alert-info">
                            <strong>Attack Success:</strong> Determines if the highest-ranked suspect was indeed the true receiver (c3).
                        </div>
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
