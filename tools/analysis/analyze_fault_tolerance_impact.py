import os
import json
import pandas as pd
import matplotlib.pyplot as plt
import glob
import argparse
import numpy as np

def get_mechanism_name(config):
    """Determines the active fault tolerance mechanism from config."""
    features = config.get('features', {})
    
    if features.get('parallel_paths', False):
        return "Parallel Paths"
    elif features.get('path_reestablishment', False):
        return "Path Reestablishment"
    elif features.get('backup_mixes', False):
        return "Backup Mixes"
    elif features.get('retransmission', False):
        return "Retransmission"
    else:
        return "Baseline"

def get_scenario_label(config):
    """Creates a label for the scenario based on noise and packet loss."""
    features = config.get('features', {})
    traffic = config.get('traffic', {})
    network = config.get('network', {})
    
    loop_rate = traffic.get('loop_rate_packets_per_sec', 0.0)
    drop_rate = traffic.get('drop_rate_packets_per_sec', 0.0)
    packet_loss = network.get('packet_loss_rate', 0.0)
    
    total_noise = loop_rate + drop_rate
    if total_noise > 0:
        noise_label = f"Noise {total_noise:.0f}pkt/s"
    else:
        noise_label = "No Noise"
            
    loss_label = f"Loss {packet_loss*100:.0f}%" if packet_loss > 0 else "No Loss"
    
    return f"{noise_label}, {loss_label}"

def analyze_fault_tolerance_impact(logs_dir, output_dir=None):
    """
    Analyzes the anonymity impact of different fault tolerance mechanisms.
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
                
            mechanism = get_mechanism_name(config)
            scenario = get_scenario_label(config)
            
            # Extract metrics
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
                        last_row = df.iloc[-1]
                        run_diaz_scores.append(last_row.get('diaz_anonymity', 0))
                        run_entropy_scores.append(last_row.get('entropy_bits', 0))
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
                    'mechanism': mechanism,
                    'scenario': scenario,
                    'avg_diaz': avg_diaz,
                    'avg_entropy': avg_entropy,
                    'success_rate': success_rate
                })
                
        except Exception as e:
            print(f"Error processing {run_dir}: {e}")

    if not results:
        print("No valid results found.")
        return

    df_results = pd.DataFrame(results)
    
    # Sort for better readability
    df_results = df_results.sort_values(['scenario', 'mechanism'])
    
    # Output Table
    print("\n--- Fault Tolerance Impact Analysis ---")
    print(df_results[['scenario', 'mechanism', 'avg_diaz', 'avg_entropy', 'success_rate']].to_string())
    
    table_path = os.path.join(output_dir, "fault_tolerance_impact_table.csv")
    df_results.to_csv(table_path, index=False)
    print(f"\nTable saved to {table_path}")

    # Visualizations
    # We create a grouped bar chart
    # Groups: Scenarios
    # Bars within group: Mechanisms
    
    scenarios = df_results['scenario'].unique()
    
    # Metrics to plot
    metrics = [
        ('avg_diaz', 'Average Diaz Anonymity', 'fault_tolerance_diaz.png'),
        ('avg_entropy', 'Average Entropy (Bits)', 'fault_tolerance_entropy.png'),
        ('success_rate', 'Attack Success Rate', 'fault_tolerance_success.png')
    ]
    
    for metric_col, metric_label, filename in metrics:
        plt.figure(figsize=(12, 6))
        
        # Pivot table for easy plotting
        # Index: Scenario, Columns: Mechanism, Values: Metric
        pivot_df = df_results.pivot_table(index='scenario', columns='mechanism', values=metric_col, aggfunc='mean')
        
        pivot_df.plot(kind='bar', figsize=(12, 6), rot=0)
        
        plt.title(f'Impact of Fault Tolerance on {metric_label}')
        plt.xlabel('Scenario')
        plt.ylabel(metric_label)
        plt.grid(True, axis='y', alpha=0.3)
        plt.legend(title='Mechanism', bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()
        
        plot_path = os.path.join(output_dir, filename)
        plt.savefig(plot_path)
        print(f"Plot saved to {plot_path}")
        plt.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare fault tolerance mechanisms.")
    parser.add_argument("--logs_dir", default="logs", help="Directory containing Testrun_* folders")
    parser.add_argument("--output_dir", default=None, help="Directory to save results")
    
    args = parser.parse_args()
    
    analyze_fault_tolerance_impact(args.logs_dir, args.output_dir)
