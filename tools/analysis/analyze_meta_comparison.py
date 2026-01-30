import os
import json
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
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
                true_recipient = max(dst_counts, key=dst_counts.get)
        except Exception as e:
            print(f"Warning: Could not determine ground truth from {traffic_file}: {e}")

    # Check Attack Success (Top Link -> True Recipient?)
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
                        
            # Determine Rank of True Recipient
            metrics['true_recipient_rank'] = None
            if 'anonymity' in metrics and 'top_candidates' in metrics['anonymity']:
                for cand in metrics['anonymity']['top_candidates']:
                    link_str_cand = str(cand.get('link', ''))
                    if f"->{true_recipient}" in link_str_cand or f"{true_recipient}->" in link_str_cand:
                        metrics['true_recipient_rank'] = cand.get('rank')
                        break
        except Exception as e:
            print(f"Error checking attack success in {csv_files[0]}: {e}")
        
    return metrics

def extract_scenario_name(run_name):
    """
    Extracts the scenario name from the run folder name.
    Format: Testrun_YYYYMMDD_HHMMSS_ID_Scenario_Name
    Returns: Scenario_Name (without ID and Timestamp)
    """
    # Regex to match the standard format
    match = re.match(r"^Testrun_\d{8}_\d{6}_\d+_(.*)$", run_name)
    if match:
        return match.group(1)
    
    # Fallback: remove first 3 parts split by underscore
    parts = run_name.split('_')
    if len(parts) > 4:
        return "_".join(parts[4:])
    return run_name

def get_sorted_scenarios(scenarios):
    """
    Sorts scenarios based on:
    1. Noise Level (no_noise < high_noise)
    2. Mechanism ID (01 to 06)
    
    Mapping based on ID:
    01: baseline_no_errors
    02: baseline_errors
    03: retransmission
    04: path_reestablishment
    05: parallel_paths
    06: backup_mixes
    """
    mech_order = {
        'baseline_no_errors': 1,
        'baseline_errors': 2,
        'retransmission': 3,
        'path_reestablishment': 4,
        'parallel_paths': 5,
        'backup_mixes': 6
    }
    
    def sort_key(scenario_name):
        # Determine Noise Level
        noise_rank = 1 if 'no_noise' in scenario_name else 2
        
        # Determine Mechanism Rank
        mech_rank = 99
        for mech, rank in mech_order.items():
            if mech in scenario_name:
                mech_rank = rank
                break
                
        return (noise_rank, mech_rank)
        
    return sorted(list(scenarios), key=sort_key)

def plot_boxplot(data_df, metric_col, title, output_path, ylabel="Value"):
    if metric_col not in data_df.columns: return

    plt.figure(figsize=(14, 7))
    
    # Custom Sort Order
    unique_scenarios = data_df['scenario'].unique()
    scenarios = get_sorted_scenarios(unique_scenarios)
    
    # Create Boxplot
    # Create Boxplot
    sns.boxplot(x='scenario', y=metric_col, data=data_df, order=scenarios, hue='scenario', palette="viridis", legend=False)
    
    # Optional: Add strip plot to show individual points (jittered)
    sns.stripplot(x='scenario', y=metric_col, data=data_df, order=scenarios,
                  size=4, color=".3", linewidth=0, alpha=0.6)

    plt.title(title)
    plt.ylabel(ylabel)
    plt.xlabel("Scenario")
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
                  
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

def plot_confidence_boxplot(data_df, output_path):
    """
    Special boxplot for Attacker Confidence.
    """
    if 'attacker_confidence' not in data_df.columns: return
    
    plt.figure(figsize=(14, 7))
    
    unique_scenarios = data_df['scenario'].unique()
    scenarios = get_sorted_scenarios(unique_scenarios)
    
    sns.boxplot(x='scenario', y='attacker_confidence', data=data_df, order=scenarios, hue='scenario', palette="coolwarm", legend=False)
    sns.stripplot(x='scenario', y='attacker_confidence', data=data_df, order=scenarios,
                  size=4, color=".3", linewidth=0, alpha=0.6, hue='attack_success', legend=False)
    
    plt.title("Attacker Confidence Distribution (Max LLR)")
    plt.ylabel("Log Likelihood Ratio")
    plt.xlabel("Scenario")
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

def generate_dashboard_html(csv_path, output_dir):
    """
    Generates HTML dashboard reading from the CSV.
    """
    df = pd.read_csv(csv_path)
    html_path = os.path.join(output_dir, "dashboard.html")
    
    # Format DataFrame for Display (Table shows individual runs)
    display_df = df.copy()
    
    # Select important columns for table
    cols = ['name', 'loss_rate', 'avg_latency', 'diaz_anonymity', 'shannon_entropy', 'attacker_confidence', 'attack_success', 'attack_success_top2', 'true_recipient_rank']
    display_df = display_df[[c for c in cols if c in display_df.columns]]
    
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
        
    # Format Rank
    if 'true_recipient_rank' in display_df.columns:
        display_df['true_recipient_rank'] = display_df['true_recipient_rank'].apply(
            lambda x: f"<b>#{int(x)}</b>" if pd.notnull(x) else "-"
        )
        
    # Python to HTML Table
    table_html = display_df.to_html(index=False, classes='table table-striped table-hover', escape=False)
    
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
            table {{ margin-top: 20px; font-size: 0.9rem; }}
            th {{ background-color: #34495e !important; color: white; }}
        </style>
    </head>
    <body>
        <div class="container-fluid">
            <h1 class="text-center mb-5">🚀 Loopix Network Analysis Dashboard</h1>
            
            <div class="row">
                <div class="col-md-6">
                    <div class="metric-card">
                        <h2>🛡️ Anonymity Distribution (Diaz)</h2>
                        <div class="plot-container">
                            <img src="cmp_anonymity.png" alt="Anonymity Comparison">
                        </div>
                        <p class="text-muted">Distribution over test runs. Box shows Median & Quartiles.</p>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="metric-card">
                        <h2>🎯 Attacker Confidence (LLR)</h2>
                        <div class="plot-container">
                            <img src="cmp_confidence.png" alt="Attacker Confidence">
                        </div>
                        <p class="text-muted">Distribution of Max LLR. Dots indicate individual runs.</p>
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
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-md-6">
                    <div class="metric-card">
                        <h2>📉 Packet Loss Rate</h2>
                        <div class="plot-container">
                            <img src="cmp_loss_rate.png" alt="Packet Loss Rate Comparison">
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="metric-card">
                        <h2>📩 Message Loss Rate</h2>
                        <div class="plot-container">
                            <img src="cmp_message_loss.png" alt="Message Loss Rate Comparison">
                        </div>
                        <p class="text-muted">Percentage of messages where NO copy arrived.</p>
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-md-6">
                    <div class="metric-card">
                        <h2>⏱️ Average Latency</h2>
                        <div class="plot-container">
                            <img src="cmp_latency.png" alt="Latency Comparison">
                        </div>
                    </div>
                </div>
            </div>

            <div class="metric-card">
                <h2>📊 Detailed Experiment Data</h2>
                <div class="table-responsive" style="max-height: 800px; overflow-y: auto;">
                    {table_html}
                </div>
                <div class="mt-3">
                    <p class="text-muted d-inline me-3">Raw Data (All Runs): <a href="raw_metrics.csv" class="btn btn-sm btn-outline-primary">Download raw_metrics.csv</a></p>
                    <p class="text-muted d-inline">Aggregated Stats (Mean/Median for Plots): <a href="aggregated_stats.csv" class="btn btn-sm btn-outline-success">Download aggregated_stats.csv</a></p>
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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("logs_root", help="Root directory containing multiple test run folders")
    args = parser.parse_args()
    
    runs = []
    
    # 1. Collect Data
    print("Collecting metrics from runs...")
    for entry in os.scandir(args.logs_root):
        if entry.is_dir() and os.path.exists(os.path.join(entry.path, "analysis_results")):
            runs.append(load_run_metrics(entry.path))
            
    if not runs:
        print("No analyzed runs found.")
        return
        
    # 2. Flatten and Export to CSV
    rows = []
    for r in runs:
        row = {'name': r['name']}
        
        # Scenario Extraction
        row['scenario'] = extract_scenario_name(r['name'])
        
        # General
        g = r.get('general', {})
        row['loss_rate'] = g.get('loss_rate', 0)
        row['message_loss_rate'] = g.get('message_loss_rate', 0)
        row['avg_latency'] = g.get('avg_latency', 0)
        row['throughput'] = g.get('total_received', 0)
        
        # Anonymity
        a = r.get('anonymity', {})
        if 'global_metrics' in a:
             row['diaz_anonymity'] = a['global_metrics'].get('diaz_anonymity', 0)
             row['shannon_entropy'] = a['global_metrics'].get('system_entropy', 0)
             row['attacker_confidence'] = a['global_metrics'].get('attacker_confidence', 0)
        
        row['attack_success'] = r.get('attack_success')
        row['attack_success_top2'] = r.get('attack_success_top2')
        row['true_recipient_rank'] = r.get('true_recipient_rank')
        
        rows.append(row)
        
    df = pd.DataFrame(rows)
    
    # Sort for consistency
    df = df.sort_values('name')
    
    output_dir = os.path.join(args.logs_root, "meta_comparison")
    if not os.path.exists(output_dir): os.makedirs(output_dir)
    
    csv_path = os.path.join(output_dir, "raw_metrics.csv")
    df.to_csv(csv_path, index=False)
    print(f"Aggregated metrics saved to {csv_path}")

    # 2b. Generate Aggregated Statistics CSV (Mean, Median, etc.)
    print("Calculating Aggregated Statistics...")
    stats_rows = []
    
    # Define metrics to aggregate
    # Define metrics to aggregate
    numeric_cols = ['loss_rate', 'message_loss_rate', 'avg_latency', 'throughput', 'diaz_anonymity', 'shannon_entropy', 'attacker_confidence']
    
    # Filter only existing columns
    numeric_cols = [c for c in numeric_cols if c in df.columns]
    
    grouped = df.groupby('scenario')
    
    for scenario, group in grouped:
        for col in numeric_cols:
            series = group[col].dropna()
            if series.empty: continue
            
            stats_rows.append({
                'scenario': scenario,
                'metric': col,
                'mean': series.mean(),
                'median': series.median(),
                'std_dev': series.std(),
                'min': series.min(),
                'max': series.max(),
                'count': len(series)
            })
            
    stats_df = pd.DataFrame(stats_rows)
    stats_csv_path = os.path.join(output_dir, "aggregated_stats.csv")
    stats_df.to_csv(stats_csv_path, index=False)
    print(f"Aggregated statistics saved to {stats_csv_path}")
    
    # 3. Generate Plots from Data
    print("Generating Box Plots...")
    plot_boxplot(df, 'loss_rate', 'Packet Loss Rate Distribution', os.path.join(output_dir, "cmp_loss_rate.png"), "Loss Rate")
    plot_boxplot(df, 'message_loss_rate', 'Real Message Loss Rate Distribution', os.path.join(output_dir, "cmp_message_loss.png"), "Message Loss Rate")
    plot_boxplot(df, 'avg_latency', 'Latency Distribution', os.path.join(output_dir, "cmp_latency.png"), "Seconds")
    plot_boxplot(df, 'diaz_anonymity', 'Diaz Anonymity Distribution', os.path.join(output_dir, "cmp_anonymity.png"), "Normalized Entropy")
    plot_boxplot(df, 'shannon_entropy', 'Shannon Entropy Distribution', os.path.join(output_dir, "cmp_shannon.png"), "Bits")
    plot_confidence_boxplot(df, os.path.join(output_dir, "cmp_confidence.png"))
    
    # 4. Generate Dashboard from CSV
    print("Generating HTML Dashboard...")
    generate_dashboard_html(csv_path, output_dir)
    
    print("Comparison analysis complete.")

if __name__ == "__main__":
    main()
