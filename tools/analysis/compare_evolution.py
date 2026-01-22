import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import argparse

def get_experiment_type(run_name):
    # Heuristic to classify runs based on name
    name = run_name.lower()
    if "baseline_no_errors" in name: return "Baseline (Ideal)"
    if "baseline_errors" in name: return "Baseline (Lossy)"
    if "retransmission" in name: return "Retransmission"
    if "path_reestablishment" in name: return "Path Re-est."
    if "multiple_paths" in name or "multipath" in name: return "Multipath"
    if "backup_mixes" in name: return "Backup Mixes"
    return "Other"

def load_all_evolutions(logs_root):
    data = []
    
    for root, dirs, files in os.walk(logs_root):
        for f in files:
            if f.startswith("anonymity_evolution_") and f.endswith(".csv"):
                run_dir = os.path.dirname(os.path.dirname(root)) # "analysis_results" -> "Testrun..." -> "logs" (No wait)
                # root is .../Testrun.../analysis_results
                run_name = os.path.basename(os.path.dirname(root))
                
                client = f.replace("anonymity_evolution_", "").replace(".csv", "")
                
                path = os.path.join(root, f)
                try:
                    df = pd.read_csv(path)
                    df['Run'] = run_name
                    df['Client'] = client
                    df['Experiment'] = get_experiment_type(run_name)
                    data.append(df)
                except Exception as e:
                    print(f"Error reading {path}: {e}")
                    
    if not data:
        return pd.DataFrame()
        
    return pd.concat(data, ignore_index=True)

def analyze_ttc(df, threshold=0.1):
    # Time to Compromise: First time Diaz Anonymity drops below threshold
    # Group by Run, Client
    
    ttc_records = []
    
    grouped = df.groupby(['Run', 'Client', 'Experiment'])
    
    for (run, client, exp), group in grouped:
        # Sort by packets
        group = group.sort_values('packets_observed')
        
        # Find first row where diaz < threshold
        compromised = group[group['diaz_anonymity'] < threshold]
        
        if not compromised.empty:
            first_fail = compromised.iloc[0]
            ttc = first_fail['packets_observed']
            duration = first_fail['duration_observed']
            status = "Compromised"
        else:
            ttc = group['packets_observed'].max()
            duration = group['duration_observed'].max()
            status = "Secure (Run Ended)"
            
        ttc_records.append({
            'Run': run,
            'Client': client,
            'Experiment': exp,
            'TTC_Packets': ttc,
            'TTC_Duration': duration,
            'Status': status
        })
        
    return pd.DataFrame(ttc_records)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--logs-root", default="../logs", help="Root logs directory")
    args = parser.parse_args()
    
    print("Loading data...")
    df = load_all_evolutions(args.logs_root)
    
    if df.empty:
        print("No evolution data found.")
        return
        
    print(f"Loaded {len(df)} data points.")
    
    # Filter for interesting clients?
    # Usually we care about the "True Receiver" matching.
    # But for general anonymity, we can look at all targets.
    
    # 1. Plot Average Evolution per Experiment Type
    plt.figure(figsize=(12, 8))
    sns.lineplot(data=df, x='packets_observed', y='diaz_anonymity', hue='Experiment', ci=None) # ci=None for speed, or 'sd' for uncertainty
    plt.title("Anonymity Decay by Mechanism (Average over all clients)")
    plt.ylabel("Diaz Anonymity (d)")
    plt.xlabel("Observed Events")
    plt.ylim(-0.05, 1.05)
    plt.grid(True)
    plt.savefig("anonymity_decay_comparison.png")
    print("Saved anonymity_decay_comparison.png")
    
    # 2. Time To Compromise Analysis
    ttc_df = analyze_ttc(df, threshold=0.1)
    ttc_df.to_csv("ttc_analysis.csv", index=False)
    print("Saved ttc_analysis.csv")
    
    # Summary Table
    summary = ttc_df.groupby('Experiment')['TTC_Packets'].mean().sort_values()
    print("\nAverage Packets to Compromise (d < 0.1):")
    print(summary)

if __name__ == "__main__":
    main()
