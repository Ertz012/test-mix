import os
import argparse
import pandas as pd
import numpy as np
import json
import logging
import math
from scipy.stats import erlang

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("StrictDanezisAnalysis")

def load_logs(log_dir):
    all_files = [os.path.join(log_dir, f) for f in os.listdir(log_dir) if f.endswith('_traffic.csv')]
    dfs = []
    for f in all_files:
        try:
            df = pd.read_csv(f)
            df['node_id'] = os.path.basename(f).replace('_traffic.csv', '')
            dfs.append(df)
        except Exception as e:
            logger.warning(f"Could not read {f}: {e}")
            
    if not dfs:
        return pd.DataFrame()
    
    full_df = pd.concat(dfs, ignore_index=True)
    full_df['timestamp'] = pd.to_numeric(full_df['timestamp'], errors='coerce')
    full_df.sort_values('timestamp', inplace=True)
    full_df = pd.concat(dfs, ignore_index=True)
    full_df['timestamp'] = pd.to_numeric(full_df['timestamp'], errors='coerce')
    full_df.sort_values('timestamp', inplace=True)
    return full_df

def load_config(log_dir):
    config_path = os.path.join(log_dir, "config.json")
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}

def delay_pdf(t, k, mu):
    """
    Wahrscheinlichkeitsdichte der Verzögerung.
    Gibt den Wert der PDF zurück (Integral über alle t ist 1.0).
    """
    # Fix: Simulation uses Expovariate(1/mu), implies Mean=mu. 
    # Scipy Erlang(scale) implies Mean=k*scale. So scale should be mu.
    if t <= 0: return 0.0
    return erlang.pdf(t, k, loc=0, scale=mu)

def calculate_normalized_convolution(t_check, input_timestamps, k, mu, max_lookback=None):
    """
    Berechnet (d * f)(t) als echte Wahrscheinlichkeitsdichte.
    Optimiert mit NumPy Vectorization.
    """
    if max_lookback is None:
        max_lookback = 20.0 * mu if mu > 0 else 100.0

    # Assume input_timestamps is numpy array (ensure in caller)
    # deltas = t_check - input_timestamps
    # We only care about inputs occurring BEFORE t_check (delta > 0)
    # and within lookback (delta < max_lookback)
    
    # Pre-filtering indices to avoid full array subtraction if possible?
    # inputs are sorted. We can searchsorted.
    
    idx_end = np.searchsorted(input_timestamps, t_check)
    # We need inputs < t_check, so inputs[:idx_end]
    # But we also need inputs > t_check - max_lookback
    cutoff = t_check - max_lookback
    idx_start = np.searchsorted(input_timestamps, cutoff)
    
    relevant_timestamps = input_timestamps[idx_start:idx_end]
    
    if relevant_timestamps.size == 0:
        return 0.0
        
    deltas = t_check - relevant_timestamps
    
    # Vectorized PDF calc
    # erlang.pdf(x, k, loc=0, scale=mu)
    pdf_vals = erlang.pdf(deltas, k, loc=0, scale=mu)
    
    sum_pdf = np.sum(pdf_vals)
    
    n_input = len(input_timestamps)
    return sum_pdf / n_input

def perform_strict_math_attack(traffic_df, mu, target_src=None, k=3):
    """
    Implementiert die Gleichungen 23, 24, 25 und 28 unter strenger Beachtung der Normalisierung.
    """
    # Daten filtern
    inputs_df = traffic_df[traffic_df['event_type'] == 'CREATED']
    # Wir betrachten hier Clients als Output (End-to-End Trace)
    outputs_df = traffic_df[(traffic_df['event_type'] == 'RECEIVED') & 
                            (traffic_df['node_id'].str.startswith(('c', 'Client')))]

    if inputs_df.empty or outputs_df.empty:
        return {}

    # Target Logic
    if target_src is None:
        target_src = inputs_df['src'].value_counts().idxmax()
        
    target_input_timestamps = inputs_df[inputs_df['src'] == target_src]['timestamp'].values
    num_input_packets = len(target_input_timestamps)
    
    if num_input_packets == 0:
        logger.warning(f"No input packets found for target {target_src}")
        return {}

    # Simulationsdauer T für die Ratenberechnung
    t_min = traffic_df['timestamp'].min()
    t_max = traffic_df['timestamp'].max()
    T_duration = t_max - t_min
    if T_duration <= 0: T_duration = 1.0
    
    # Rate lambda_f (Input Rate)
    lambda_f = num_input_packets / T_duration
    
    potential_receivers = outputs_df['node_id'].unique()
    results = []
    
    # Uniform Noise Distribution u = 1/T (über das Intervall [0, T])
    u = 1.0 / T_duration

    logger.info(f"Target: {target_src} (Rate: {lambda_f:.4f} pkts/s)")

    for receiver in potential_receivers:
        receiver_data = outputs_df[outputs_df['node_id'] == receiver]
        observed_timestamps = receiver_data['timestamp'].values # Das sind die X_i
        
        n_obs = len(observed_timestamps)
        lambda_X = n_obs / T_duration
        
        # Berechnung Log-Likelihood Ratio nach Gl. 28
        
        # Berechnung Log-Likelihood Ratio nach Gl. 28
        
        sum_log_CX = 0.0
        
        # FIX: Handling für Packet Loss / Filterung.
        # Wenn lambda_f > lambda_X, ist es unmöglich, dass ALLE Pakete Signal sind.
        # Wir clampen die effektive Signalrate.
        lambda_f_effective = min(lambda_f, lambda_X * 0.99)
        
        for t_obs in observed_timestamps:
            # (d * f)(t) - normiert!
            conv_pdf = calculate_normalized_convolution(t_obs, target_input_timestamps, k, mu)
            
            # Gl. 23: C_X(t)
            # Mischmodell: Wahrscheinlichkeit, dass das Paket vom Signal kommt + Wahrscheinlichkeit Noise
            
            w_signal = lambda_f_effective / lambda_X
            w_noise = (lambda_X - lambda_f_effective) / lambda_X
            w_noise = max(w_noise, 0)
            
            signal_component = w_signal * conv_pdf
            noise_component = w_noise * u
            
            c_x_t = signal_component + noise_component
            
            if c_x_t <= 0:
                # Sollte numerisch nicht passieren, es sei denn conv_pdf=0 und noise=0
                c_x_t = 1e-15 
            
            sum_log_CX += math.log(c_x_t)

        # Term 2: Sum( log( U(X_i) ) ) -> Das ist das Modell unter H1 (nur Noise)
        # Wenn wir testen "Ist Stream in Link A (H0) oder ist Link A nur Rauschen (H1)"?
        # Sum( log( u ) ) = n_obs * log(u)
        sum_log_U = n_obs * math.log(u)
        
        # Likelihood Ratio: log(L_H0 / L_H1) = Sum(log CX) - Sum(log U)
        # (Dies entspricht der Logik von Gl. 28, wenn man Y als "den gleichen Link unter der Annahme Noise" betrachtet)
        ll_ratio = sum_log_CX - sum_log_U
        
        results.append({
            'receiver': receiver,
            'log_likelihood_ratio': ll_ratio,
            'lambda_X': lambda_X
        })

    # --- DIAZ METRIC CALCULATION ---
    # 1. Collect Log-Likelihood Ratios (LLRs)
    # LLR_i = log( P(Data | H0_i) / P(Data | H1) )
    # We want P(H0_i | Data).
    # Assuming Prior P(H0_i) is uniform (1/N), then:
    # P(H0_i | Data) ~ P(Data | H0_i)
    # log P(H0_i | Data) = log P(Data | H0_i) - log Sum(P(Data | H0_j))
    # Note: Our LLR is log(P(D|H0)) - log(P(D|H1)).
    # So log(P(D|H0)) = LLR + log(P(D|H1)).
    # The term log(P(D|H1)) is constant for all candidates (it's the noise-only baseline).
    # Therefore, P(H0_i | Data) is proportional to e^LLR_i.
    
    # Extract LLRs
    llrs = np.array([r['log_likelihood_ratio'] for r in results])
    
    # 2. Normalize using Log-Sum-Exp for numerical stability
    # log_sum_exp = log( sum( e^LLR ) )
    if len(llrs) > 0:
        max_llr = np.max(llrs)
        # log_sum_exp = max_llr + log( sum( e^(llr - max_llr) ) )
        log_sum_exp = max_llr + np.log(np.sum(np.exp(llrs - max_llr)))
        
        # log_probs = LLR - log_sum_exp
        log_probs = llrs - log_sum_exp
        probs = np.exp(log_probs)
        
        # 3. Calculate Entropy H(X)
        # H(X) = - sum( p * log2(p) )
        # Using natural log for calculation then converting to bits: log2(x) = ln(x) / ln(2)
        # p * ln(p) = exp(log_p) * log_p
        entropy_nat = -np.sum(probs * log_probs)
        entropy_bits = entropy_nat / np.log(2)
        
        # 4. Calculate Max Entropy H_M
        N = len(llrs)
        max_entropy_bits = np.log2(N) if N > 0 else 0
        
        # 5. Calculate Diaz Degree 'd'
        # d = 1 - (HM - H) / HM = H / HM
        if max_entropy_bits > 0:
            diaz_d = entropy_bits / max_entropy_bits
        else:
            diaz_d = 0.0 if N <= 1 else 1.0 # Edge case
            
    else:
        probs = []
        entropy_bits = 0.0
        max_entropy_bits = 0.0
        diaz_d = 0.0

    # Add derived probs back to results structure
    for i, r in enumerate(results):
        r['normalized_probability'] = float(probs[i]) if len(probs) > 0 else 0.0
        
    # SORT RESULTS by LLR (Descending) - Critical Step!
    results.sort(key=lambda x: x['log_likelihood_ratio'], reverse=True)
    
    # --- RESULT COMPILATION ---
    top_candidate = results[0] if results else None
    
    actual_dst_packets = outputs_df[(outputs_df['src'] == target_src)]
    true_receiver = actual_dst_packets['node_id'].mode()[0] if not actual_dst_packets.empty else "Unknown"
    
    detected = (top_candidate is not None and top_candidate['log_likelihood_ratio'] > 0)
    
    # Full Metadata Structure
    metadata = {
        'attack_config': {
            'algorithm': 'Danezis-Strict-Math',
            'target_src': target_src,
            'mu': mu,
            'k_hops': k
        },
        'input_traffic_stats': {
            'total_packets': int(num_input_packets),
            'duration': float(T_duration),
            'lambda_f': float(lambda_f)
        },
        'global_metrics': {
            'entropy_bits': float(entropy_bits),
            'max_entropy_bits': float(max_entropy_bits),
            'diaz_anonymity': float(diaz_d),
            'danezis_metric_A': -math.log((lambda_f * math.e) / mu) if (mu > 0 and lambda_f > 0 and (lambda_f * math.e / mu) > 0) else "N/A"
        },
        'candidates': results, # Now includes normalized_probability
        'outcome': {
            'true_receiver': true_receiver,
            'detected_receiver': top_candidate['receiver'] if top_candidate else None,
            'detected_llr': top_candidate['log_likelihood_ratio'] if top_candidate else None,
            'success': (top_candidate['receiver'] == true_receiver and detected) if top_candidate else False,
            'is_detection_valid': bool(detected)
        }
    }
    
    # Backwards compatibility flat return for caller checks
    metadata['success'] = metadata['outcome']['success']
    metadata['true_receiver'] = metadata['outcome']['true_receiver']
    metadata['detected_receiver'] = metadata['outcome']['detected_receiver']
    metadata['likelihood_score'] = metadata['outcome']['detected_llr']
    metadata['target_src'] = target_src
    
    return metadata

def analyze_target_exact(run_path, target_src=None):
    try:
        config = load_config(run_path)
        
        # Determine mu
        mu = config.get('mix_settings', {}).get('mu')
        if mu is None:
             mu = 0.5 
             
        k = config.get('network_settings', {}).get('num_hops', 3) 
        
        df = load_logs(run_path)
        if df.empty: 
            return None
            
        # Identify all potential targets (c*)
        if target_src:
            targets = [target_src]
        else:
            # Determine unique sources starting with 'c'
            all_srcs = df[df['event_type'] == 'CREATED']['src'].unique()
            targets = [s for s in all_srcs if str(s).startswith(('c', 'Client'))]
            
        if not targets:
            return None
            
        results_list = []
        out_dir = os.path.join(run_path, "analysis_results")
        os.makedirs(out_dir, exist_ok=True)
            
        for t in targets:
            metrics = perform_strict_math_attack(df, mu, target_src=t, k=k)
            if not metrics: 
                continue
                
            results_list.append(metrics)
            
            # Save Dump
            target_name = metrics['target_src']
            out_file = os.path.join(out_dir, f"traffic_analysis_dump_{target_name}.json")
            
            with open(out_file, "w") as f:
                f.write(json.dumps(metrics, indent=4, default=str))
                
            # Legacy compatibility
            legacy_file = os.path.join(out_dir, f"traffic_analysis_exact_{target_name}.txt")
            with open(legacy_file, "w") as f:
                f.write(json.dumps(metrics, indent=4, default=str))

        # Return the "best" result for single-return backward compatibility, or the last one?
        # Maybe return the list?
        # But existing callers might expect a single dict if they passed a single target.
        # If we return a list, we break `analyze_all_results.py`.
        # However, `analyze_all_results` logic was: `metrics = analyze_traffic_exact.analyze_target_exact(exp_path, target_src=client)`.
        # It calls it with a SPECIFIC client in the loop.
        # So if called with specific client, `targets` has 1 item, return that item.
        # If called without target (e.g. CLI or batch), return list?
        
        if len(results_list) == 1:
            return results_list[0]
        return results_list

    except Exception as e:
        logger.error(f"Error in {run_path}: {e}")
        return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--logs-root", help="Root directory containing Testrun folders")
    parser.add_argument("--run-dir", help="Single run directory to analyze")
    parser.add_argument("--target", help="Specific target to analyze (optional)", default=None)
    args = parser.parse_args()
    
    runs = []
    if args.run_dir:
        if os.path.isdir(args.run_dir):
            runs.append(args.run_dir)
        else:
            print(f"Error: {args.run_dir} is not a directory")
            return
    elif args.logs_root:
        if os.path.isdir(args.logs_root):
            runs = [os.path.join(args.logs_root, d) for d in os.listdir(args.logs_root) 
                    if os.path.isdir(os.path.join(args.logs_root, d)) and d.startswith("Testrun")]
        else:
             print(f"Error: {args.logs_root} is not a directory")
             return
    else:
        print("Error: Must specify either --logs-root or --run-dir")
        return

    print(f"{'Run Name':<40} | {'Src':<5} | {'True Dst':<10} | {'Detected':<10} | {'Log-LR':<10} | {'Success'}")
    print("-" * 100)
    
    for run in runs:
        metrics_or_list = analyze_target_exact(run, target_src=args.target)
        
        if isinstance(metrics_or_list, list):
            items = metrics_or_list
        elif metrics_or_list:
             items = [metrics_or_list]
        else:
             items = []
             
        for metrics in items:
             print(f"{os.path.basename(run):<40} | {metrics['target_src']:<5} | {metrics['true_receiver']:<10} | {metrics['detected_receiver']:<10} | {metrics['likelihood_score']:<10.2f} | {metrics['success']}")

if __name__ == "__main__":
    main()
