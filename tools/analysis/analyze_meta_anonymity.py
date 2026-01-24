
import os
import glob
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import re

# Global Configuration
LOGS_ROOT = r"d:\Uni Hamburg\Module\MASTER\test-mix\logs"
OUTPUT_DIR = os.path.join(LOGS_ROOT, "analysis_results")

# Threshold for Time-To-Compromise (LLR > 10 => ~22000:1 odds)
TTC_THRESHOLD = 10.0

def parse_run_name(run_name):
    """
    Parses directory name to extract Mechanism and Noise Level.
    Format: Testrun_YYYYMMDD_HHMMSS_ID_mechanism_name_noise_level
    """
    # Known Mechanisms
    mechanisms = [
        "baseline_no_errors",
        "baseline_errors",
        "retransmission",
        "path_reestablishment",
        "parallel_paths",
        "backup_mixes"
    ]
    
    # Defaults
    mech = "unknown"
    noise = "normal" # Default to normal/long if not specified
    
    # Detect Mechanism
    for m in mechanisms:
        if m in run_name:
            mech = m
            break
            
    # Detect Noise
    if "no_noise" in run_name:
        noise = "no_noise"
    elif "high_noise" in run_name:
        noise = "high_noise"
    elif "long" in run_name:
        noise = "normal"
        
    return mech, noise

def calculate_entropy(results_list):
    """
    Calculates Shannon Entropy of the normalized likelihoods of the top N links.
    """
    if not results_list:
        return 0.0
        
    # Get top 20 LLRs (or fewer)
    llrs = np.array([r['llr'] for r in results_list[:20]])
    
    # Convert LLR to Likelihood (relative)
    # L = exp(LLR). To avoid overflow, subtract max first: exp(LLR - max)
    # This is valid for normalization: P_i = exp(L_i) / sum(exp(L_j))
    # = exp(LLR_i - max) / sum(exp(LLR_j - max))
    
    max_llr = np.max(llrs)
    # Clip lower bound to avoid -inf issues if outlier
    llrs = np.maximum(llrs, max_llr - 100)
    
    likelihoods = np.exp(llrs - max_llr)
    probs = likelihoods / np.sum(likelihoods)
    
    # Entropy = - sum(p * log(p))
    entropy = -np.sum(probs * np.log(probs + 1e-50)) # Add small epsilon
    return entropy

def calculate_ttc(evolution_data):
    """
    Finds the first packet index where Cumulative LLR > Threshold.
    Stats: data is list of [timestamp, packet_idx, score]
    """
    if not evolution_data:
        return None
        
    for item in evolution_data:
        # item is [ts, pkt_idx, score]
        if item[2] > TTC_THRESHOLD:
            return item[1] # Return packet index
            
    return None # Never reached threshold (Anoymous within window)

def main():
    print("--- Meta-Analysis: Fault Tolerance Anonymity ---")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 1. Collect Data
    data_records = []
    
    # Find all evolution JSONs
    # Pattern: logs/Testrun_*/analysis_results/*_evolution.json
    search_pattern = os.path.join(LOGS_ROOT, "Testrun_*", "analysis_results", "*_evolution.json")
    files = glob.glob(search_pattern)
    print(f"Found {len(files)} result files. Processing...")
    
    for filepath in files:
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                
            run_dir = os.path.dirname(os.path.dirname(filepath))
            run_name = os.path.basename(run_dir)
            
            mech, noise = parse_run_name(run_name)
            target = data['metadata']['target']
            
            results = data['results']
            if not results:
                continue
                
            # Sort by LLR desc (should be already, but ensure)
            results.sort(key=lambda x: x['llr'], reverse=True)
            top_link = results[0]
            
            # Metrics
            max_llr = top_link['llr']
            entropy = calculate_entropy(results)
            ttc = calculate_ttc(top_link['evolution'])
            
            obs_count = top_link['obs_count']
            
            data_records.append({
                'Mechanism': mech,
                'Noise': noise,
                'Target': target,
                'Max_LLR': max_llr,
                'Entropy': entropy,
                'TTC': ttc if ttc is not None else obs_count * 2, # Penalize validly anonymous? Or use max? Using obs*2 as placeholder for "Safe"
                'Is_Compromised': ttc is not None,
                'Run': run_name
            })
            
        except Exception as e:
            print(f"Error processing {filepath}: {e}")
            
    df = pd.DataFrame(data_records)
    
    # Save Raw Data
    df.to_csv(os.path.join(OUTPUT_DIR, "meta_analysis_raw.csv"), index=False)
    print(f"Saved raw data to {os.path.join(OUTPUT_DIR, 'meta_analysis_raw.csv')}")
    
    # 2. Aggregation & Visualization
    # Clean up Mechanism names for plotting
    df['Mechanism'] = df['Mechanism'].str.replace('baseline_', '').str.replace('_', '\n')
    
    # Metric 1: Max LLR (Confidence)
    plt.figure(figsize=(12, 6))
    sns.barplot(data=df, x='Mechanism', y='Max_LLR', hue='Noise', palette='viridis')
    plt.title("Attacker Confidence (Max LLR) by Tolerance Mechanism")
    plt.ylabel("Max LLR Score (Higher = Less Anon)")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "plot_max_llr.png"))
    plt.close()
    
    # Metric 2: Entropy (Indistinguishability)
    plt.figure(figsize=(12, 6))
    sns.barplot(data=df, x='Mechanism', y='Entropy', hue='Noise', palette='magma')
    plt.title("Anonymity Set Entropy (Top 20 candidates)")
    plt.ylabel("Entropy (Higher = Better Anon)")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "plot_entropy.png"))
    plt.close()
    
    # Metric 3: Time-to-Compromise (Only for compromised)
    # Filter for compromised or handle None
    # If not compromised, TTC is high (good). 
    # Let's plot "Packets until Compromise".
    
    # For visualization, we can impute non-compromised:
    # If not compromised within window, data has 'obs_count*2'.
    # This might skew averages. 
    # Alternative: Plot Success Rate of Attack?
    
    # Let's Plot TTC, but careful with huge bars.
    plt.figure(figsize=(12, 6))
    sns.barplot(data=df, x='Mechanism', y='TTC', hue='Noise', palette='rocket')
    plt.title("Time-To-Compromise (Packets until LLR > 10)")
    plt.ylabel("Packets Needed (Higher = Better)")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "plot_ttc.png"))
    plt.close()
    
    # Summary Tables
    summary = df.groupby(['Mechanism', 'Noise'])[['Max_LLR', 'Entropy', 'TTC', 'Is_Compromised']].mean()
    summary.to_csv(os.path.join(OUTPUT_DIR, "meta_analysis_summary.csv"))
    print("\nSummary Table:")
    print(summary)

if __name__ == "__main__":
    main()
