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
    if t <= 0: return 0.0
    return erlang.pdf(t, k, loc=0, scale=1/mu)

def calculate_normalized_convolution(t_check, input_timestamps, k, mu, max_lookback=None):
    """
    Berechnet (d * f)(t) als echte Wahrscheinlichkeitsdichte.
    
    Korrektur zur vorherigen Version:
    Wir summieren die PDFs der einzelnen Pakete, müssen aber durch die 
    Gesamtanzahl der Input-Pakete (N_input) teilen, damit das Integral
    über die Zeit wieder 1 ergibt (Eigenschaft einer Mischverteilung).
    """
    if max_lookback is None:
        max_lookback = 20.0 / mu if mu > 0 else 100.0

    relevant_inputs = [t_in for t_in in input_timestamps 
                       if 0 < (t_check - t_in) < max_lookback]
    
    if not relevant_inputs:
        return 0.0
    
    # Summe der PDF-Werte (Superposition)
    sum_pdf = sum(delay_pdf(t_check - t_in, k, mu) for t_in in relevant_inputs)
    
    # WICHTIG: Normalisierung durch Anzahl der Input-Pakete
    # Damit wird (d*f)(t) zu einer gültigen PDF, wie im Paper gefordert.
    n_input = len(input_timestamps)
    return sum_pdf / n_input

def perform_strict_math_attack(traffic_df, mu, k=3):
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

    # Target: Der aktivste Sender
    target_src = inputs_df['src'].value_counts().idxmax()
    target_input_timestamps = inputs_df[inputs_df['src'] == target_src]['timestamp'].values
    num_input_packets = len(target_input_timestamps)

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
        # Wir vergleichen H0 (Signal ist in diesem Link X) gegen H1 (Signal ist NICHT in diesem Link).
        # Wenn H1 gilt, nehmen wir an, der Link enthält nur Uniform Noise (wie im Paper Y_j ~ U).
        # Das entspricht dem Vergleich: Passt das Modell C_X besser als das Modell U?
        
        # Term 1: Sum( log( C_X(X_i) ) )
        sum_log_CX = 0.0
        
        for t_obs in observed_timestamps:
            # (d * f)(t) - normiert!
            conv_pdf = calculate_normalized_convolution(t_obs, target_input_timestamps, k, mu)
            
            # Gl. 23: C_X(t)
            # Mischmodell: Wahrscheinlichkeit, dass das Paket vom Signal kommt + Wahrscheinlichkeit Noise
            # Hier müssen wir mit den Raten gewichten.
            # Der Anteil des Traffics, der vom Signal kommt, ist lambda_f / lambda_X
            # Der Anteil des Traffics, der Noise ist, ist (lambda_X - lambda_f) / lambda_X
            
            signal_component = (lambda_f / lambda_X) * conv_pdf
            noise_component = ((lambda_X - lambda_f) / lambda_X) * u
            
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

    # Auswertung
    results.sort(key=lambda x: x['log_likelihood_ratio'], reverse=True)
    
    # Ground Truth Check
    actual_dst_packets = traffic_df[(traffic_df['src'] == target_src) & (traffic_df['event_type'] == 'RECEIVED')]
    true_receiver = actual_dst_packets['node_id'].mode()[0] if not actual_dst_packets.empty else "Unknown"
    
    top_match = results[0]['receiver'] if results else None
    
    # Nur ein positiver Ratio bedeutet "Detektion" (Condition 26: Ratio > 1 => Log Ratio > 0)
    detected = (top_match is not None and results[0]['log_likelihood_ratio'] > 0)

    return {
        'target_src': target_src,
        'true_receiver': true_receiver,
        'detected_receiver': top_match if detected else "None (All < 0)",
        'likelihood_score': results[0]['log_likelihood_ratio'] if results else -999,
        'success': (top_match == true_receiver and detected)
    }

def process_single_run(run_path):
    try:
        run_name = os.path.basename(run_path)
        config = load_config(run_path)
        
        # Determine mu
        mu = config.get('mix_settings', {}).get('mu')
        if mu is None:
             # Fallback
             mu = 0.5 
             
        k = config.get('network_settings', {}).get('num_hops', 3) 
        
        df = load_logs(run_path)
        if df.empty: 
            return None
        
        metrics = perform_strict_math_attack(df, mu, k=k)
        if not metrics: 
            return None
        
        out_dir = os.path.join(run_path, "analysis_results")
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "strict_traffic_analysis.txt"), "w") as f:
            f.write(json.dumps(metrics, indent=4, default=str))
            
        return metrics
    except Exception as e:
        logger.error(f"Error in {run_path}: {e}")
        return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--logs-root", help="Root directory containing Testrun folders")
    parser.add_argument("--run-dir", help="Single run directory to analyze")
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

    print(f"{'Run Name':<40} | {'True Dst':<10} | {'Detected':<10} | {'Log-LR':<10} | {'Success'}")
    print("-" * 100)
    
    for run in runs:
        metrics = process_single_run(run)
        if metrics:
             print(f"{os.path.basename(run):<40} | {metrics['true_receiver']:<10} | {metrics['detected_receiver']:<10} | {metrics['likelihood_score']:<10.2f} | {metrics['success']}")

if __name__ == "__main__":
    main()