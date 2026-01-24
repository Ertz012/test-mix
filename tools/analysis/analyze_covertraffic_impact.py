import os
import json
import pandas as pd
import matplotlib.pyplot as plt
import glob
import argparse
import numpy as np

def analyze_covertraffic_impact(logs_dir, output_dir=None):
    """
    Analyzes the impact of cover traffic on anonymity metrics across multiple test runs.
    """
    if output_dir is None:
        output_dir = os.path.join(logs_dir, "analysis_results")
        
    os.makedirs(output_dir, exist_ok=True)
    
    results = []

    # Find all test run directories
    run_dirs = glob.glob(os.path.join(logs_dir, "Testrun_*"))
    
    print(f"Found {len(run_dirs)} test runs.")

    for run_dir in run_dirs:
        config_path = os.path.join(run_dir, "config.json")
        if not os.path.exists(config_path):
            continue
            
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                
            # Extract traffic parameters
            traffic_conf = config.get('traffic', {})
            features_conf = config.get('features', {})
            
            # Check if dummy traffic is enabled
            # Note: We ignore the 'dummy_traffic' flag here because some runs had it False 
            # but still generated traffic (client.py checks rates > 0).
            loop_rate = traffic_conf.get('loop_rate_packets_per_sec', 0.0)
            drop_rate = traffic_conf.get('drop_rate_packets_per_sec', 0.0)
            cover_traffic_rate = loop_rate + drop_rate
                
            # Extract Anonymity Metrics
            # We look for anonymity_evolution_c*.csv files and average the final results
            analysis_dir = os.path.join(run_dir, "analysis_results")
            if not os.path.exists(analysis_dir):
                continue
                
            evolution_files = glob.glob(os.path.join(analysis_dir, "anonymity_evolution_c*.csv"))
            
            if not evolution_files:
                continue
                
            run_diaz_scores = []
            run_entropy_scores = []
            run_successes = []
            
            for ev_file in evolution_files:
                try:
                    df = pd.read_csv(ev_file)
                    if not df.empty:
                        # Get values from the last row (final state)
                        last_row = df.iloc[-1]
                        
                        run_diaz_scores.append(last_row.get('diaz_anonymity', 0))
                        run_entropy_scores.append(last_row.get('entropy_bits', 0))
                        # Success is boolean or equivalent
                        success = last_row.get('success', False)
                        run_successes.append(1 if success else 0)
                except Exception as e:
                    print(f"Error reading {ev_file}: {e}")
            
            if run_diaz_scores:
                avg_diaz = np.mean(run_diaz_scores)
                avg_entropy = np.mean(run_entropy_scores)
                success_rate = np.mean(run_successes)
                
                results.append({
                    'run_id': os.path.basename(run_dir),
                    'cover_traffic_rate': cover_traffic_rate,
                    'loop_rate': loop_rate,
                    'drop_rate': drop_rate,
                    'avg_diaz': avg_diaz,
                    'avg_entropy': avg_entropy,
                    'success_rate': success_rate,
                    'num_clients_analyzed': len(run_diaz_scores)
                })
                
        except Exception as e:
            print(f"Error processing {run_dir}: {e}")

    if not results:
        print("No valid results found.")
        return

    df_results = pd.DataFrame(results)
    
    # Sort by cover traffic rate
    df_results = df_results.sort_values('cover_traffic_rate')
    
    # Output Table
    print("\n--- Cover Traffic Impact Analysis ---")
    print(df_results[['run_id', 'cover_traffic_rate', 'avg_diaz', 'avg_entropy', 'success_rate']].to_string())
    
    # Save Table
    table_path = os.path.join(output_dir, "cover_traffic_impact_table.csv")
    df_results.to_csv(table_path, index=False)
    print(f"\nTable saved to {table_path}")

    # Visualizations
    # We group by cover traffic rate to handle multiple runs with same settings (average them)
    df_grouped = df_results.groupby('cover_traffic_rate').agg({
        'avg_diaz': 'mean',
        'avg_entropy': 'mean',
        'success_rate': 'mean'
    }).reset_index()

    # Plot 1: Anonymity (Diaz & Entropy) vs Cover Traffic
    fig, ax1 = plt.subplots(figsize=(10, 6))
    
    color = 'tab:blue'
    ax1.set_xlabel('Total Cover Traffic Rate (pkt/s)')
    ax1.set_ylabel('Average Diaz Anonymity', color=color)
    ax1.plot(df_grouped['cover_traffic_rate'], df_grouped['avg_diaz'], marker='o', color=color, label='Diaz Anonymity')
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.grid(True, alpha=0.3)

    ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis
    color = 'tab:orange'
    ax2.set_ylabel('Average Entropy (Bits)', color=color)  # we already handled the x-label with ax1
    ax2.plot(df_grouped['cover_traffic_rate'], df_grouped['avg_entropy'], marker='s', linestyle='--', color=color, label='Entropy')
    ax2.tick_params(axis='y', labelcolor=color)

    plt.title('Impact of Cover Traffic on Anonymity Metrics')
    fig.tight_layout()  # otherwise the right y-label is slightly clipped
    
    plot_path_anon = os.path.join(output_dir, "cover_traffic_anonymity_impact.png")
    plt.savefig(plot_path_anon)
    print(f"Plot saved to {plot_path_anon}")
    
    # Plot 2: Success Rate vs Cover Traffic
    plt.figure(figsize=(10, 6))
    plt.plot(df_grouped['cover_traffic_rate'], df_grouped['success_rate'], marker='x', color='red', linewidth=2)
    plt.xlabel('Total Cover Traffic Rate (pkt/s)')
    plt.ylabel('Attack Success Rate')
    plt.title('Impact of Cover Traffic on Attack Success')
    plt.grid(True, alpha=0.3)
    plt.ylim(-0.05, 1.05)
    
    plot_path_success = os.path.join(output_dir, "cover_traffic_success_impact.png")
    plt.savefig(plot_path_success)
    print(f"Plot saved to {plot_path_success}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze impact of cover traffic on anonymity.")
    parser.add_argument("--logs_dir", default="logs", help="Directory containing Testrun_* folders")
    parser.add_argument("--output_dir", default=None, help="Directory to save results")
    
    args = parser.parse_args()
    
    analyze_covertraffic_impact(args.logs_dir, args.output_dir)
