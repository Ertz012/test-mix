
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

def get_diaz_score(run_dir, target):
    """
    Reads the anonymity_evolution_{target}.csv to get the final Diaz score.
    Returns: Final Diaz Score (0.0 - 1.0) or None if file missing.
    """
    csv_path = os.path.join(run_dir, "analysis_results", f"anonymity_evolution_{target}.csv")
    if not os.path.exists(csv_path):
        return None
        
    try:
        df = pd.read_csv(csv_path)
        if df.empty:
            return None
        # Return the last recorded Diaz Anonymity score
        return df['diaz_anonymity'].iloc[-1]
    except Exception:
        return None

def main():
    print("--- Meta-Analysis: Fault Tolerance Anonymity ---")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 1. Collect Data
    data_records = []
    
    # Find all evolution JSONs (LLR/Entropy Source)
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
            
            # Metrics from Strict Trace (Attacker View)
            max_llr = top_link['llr']
            entropy = calculate_entropy(results)
            ttc = calculate_ttc(top_link['evolution'])
            
            # Metric from Exact Analysis (System View via Danezis/Diaz)
            diaz = get_diaz_score(run_dir, target)
            
            obs_count = top_link['obs_count']
            
            data_records.append({
                'Mechanism': mech,
                'Noise': noise,
                'Target': target,
                'Max_LLR': max_llr,
                'Entropy': entropy,
                'Diaz_Anonymity': diaz, # Can be None
                'TTC': ttc if ttc is not None else obs_count * 2,
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
    plt.ylabel("average Max LLR Scores (Higher = Less Anon)")
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
    
    # Metric 3: Diaz Anonymity (System-wide Normalized)
    # Filter out None values just in case
    df_diaz = df.dropna(subset=['Diaz_Anonymity'])
    if not df_diaz.empty:
        plt.figure(figsize=(12, 6))
        sns.barplot(data=df_diaz, x='Mechanism', y='Diaz_Anonymity', hue='Noise', palette='coolwarm')
        plt.title("Diaz Anonymity (Normalized 0-1)")
        plt.ylabel("Diaz Score (1.0 = Perfect Anon)")
        plt.ylim(0, 1.1) # Diaz is strictly 0-1
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR, "plot_diaz.png"))
        plt.close()
    
    # Metric 4: Time-to-Compromise
    plt.figure(figsize=(12, 6))
    sns.barplot(data=df, x='Mechanism', y='TTC', hue='Noise', palette='rocket')
    plt.title("Time-To-Compromise (Packets until LLR > 10)")
    plt.ylabel("Packets Needed (Higher = Better)")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "plot_ttc.png"))
    plt.close()
    
    # Summary Tables
    summary = df.groupby(['Mechanism', 'Noise'])[['Max_LLR', 'Entropy', 'Diaz_Anonymity', 'TTC', 'Is_Compromised']].mean()
    summary.to_csv(os.path.join(OUTPUT_DIR, "meta_analysis_summary.csv"))
    print("\nSummary Table:")
    print(summary)

if __name__ == "__main__":
    main()
