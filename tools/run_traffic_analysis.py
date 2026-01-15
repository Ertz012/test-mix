import os
import argparse
import pandas as pd
import numpy as np
import json
import logging
import math
from scipy.stats import erlang

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DanezisAttack")

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
    Die Verzögerungscharakteristik d(x).
    Im Paper für einen Mix: Exponential (k=1).
    Für ein Netzwerk aus k Mixen: Erlang-Verteilung (Summe von k Exponentialverteilungen).
    """
    if t <= 0:
        return 0.0
    # Nutzung von scipy für numerische Stabilität bei der Gamma/Erlang Funktion
    return erlang.pdf(t, k, loc=0, scale=1/mu)

def calculate_convolution_value(t_check, input_timestamps, k, mu, max_lookback=None):
    """
    Implementiert (d * f)(t) - Equation 24.
    Da f(t) eine Reihe von diskreten Impulsen (Paketen) ist, ist die Faltung 
    die Summe der verschobenen Verzögerungsfunktionen.
    """
    if max_lookback is None:
        max_lookback = 20.0 / mu if mu > 0 else 100.0

    # Nur Input-Pakete betrachten, die vor t_check ankamen und im relevanten Fenster liegen
    relevant_inputs = [t_in for t_in in input_timestamps 
                       if 0 < (t_check - t_in) < max_lookback]
    
    if not relevant_inputs:
        return 0.0
    
    # Summe der Wahrscheinlichkeitsdichten (Superposition)
    val = sum(delay_pdf(t_check - t_in, k, mu) for t_in in relevant_inputs)
    return val

def perform_stream_attack(traffic_df, mu, k=3):
    """
    Setzt den Traffic Analysis Attack aus Kapitel 3 um.
    Ziel: Für einen gegebenen Sender (Target Input) herausfinden, 
    zu welchem Empfänger (Output Link) er gehört.
    """
    
    # 1. Datenvorbereitung
    # Inputs: Alle CREATED Events
    inputs_df = traffic_df[traffic_df['event_type'] == 'CREATED']
    outputs_df = traffic_df[(traffic_df['event_type'] == 'RECEIVED') & 
                            (traffic_df['node_id'].str.startswith(('c', 'Client', 'p', 'Provider')))]

    if inputs_df.empty or outputs_df.empty:
        logger.warning("Keine ausreichenden Daten für Analyse.")
        return {}

    # Wir wählen den aktivsten Sender als "Target Stream f(t)"
    target_src = inputs_df['src'].value_counts().idxmax()
    target_input_timestamps = inputs_df[inputs_df['src'] == target_src]['timestamp'].values
    
    # Parameter für das Modell
    T_duration = traffic_df['timestamp'].max() - traffic_df['timestamp'].min()
    if T_duration <= 0: T_duration = 1.0
    
    # lambda_f: Rate des Ziel-Streams (Equation 23 ff.)
    lambda_f = len(target_input_timestamps) / T_duration
    
    # Wir testen jeden möglichen Empfänger (Outputs)
    potential_receivers = outputs_df['node_id'].unique()
    
    results = []
    
    logger.info(f"Starte Attacke auf Stream von {target_src} ({len(target_input_timestamps)} Pakete).")
    logger.info(f"Vergleiche mit {len(potential_receivers)} möglichen Empfängern.")

    for receiver in potential_receivers:
        # Beobachtete Zeitstempel am Empfänger (X_i im Paper)
        receiver_data = outputs_df[outputs_df['node_id'] == receiver]
        observed_timestamps = receiver_data['timestamp'].values
        
        n = len(observed_timestamps)
        if n == 0: continue
        
        # lambda_X: Rate am Ausgangskanal
        lambda_X = n / T_duration
        
        # Uniform Distribution u (Noise Rate Annahme für den Rest)
        # Im Paper: U(t) = u. Oft genähert als 1/T oder die Background-Rate.
        u = 1.0 / T_duration 

        # Berechnung der Log-Likelihood Ratio (Equation 28 )
        # Log L = Sum(log Cx(Xi)) - Sum(log Cy(Yj)) ... 
        # Hier vereinfacht: Wir berechnen den Score für Hypothese H0 (Target ist hier)
        # Score = Sum( log( C_X(t) / u ) ) 
        # Wenn Score > 0, spricht es für H0.
        
        log_likelihood_sum = 0.0
        
        for t_obs in observed_timestamps:
            # Convolution (d * f)(t) berechnen
            conv_val = calculate_convolution_value(t_obs, target_input_timestamps, k, mu)
            
            # Equation 23: Cx(t) = (lambda_f * (d*f)(t) + (lambda_X - lambda_f) * u) / lambda_X
            # Wir müssen sicherstellen, dass lambda_X >= lambda_f, sonst ist das Modell "unmöglich" (mehr Output als Input + Noise geht nicht im Modell)
            eff_lambda_X = max(lambda_X, lambda_f) 
            noise_part = (eff_lambda_X - lambda_f) * u
            signal_part = lambda_f * conv_val
            
            c_x_t = (signal_part + noise_part) / eff_lambda_X
            
            # Schutz vor log(0)
            if c_x_t <= 1e-12:
                c_x_t = 1e-12
            if u <= 1e-12:
                u = 1e-12
                
            # Der Beitrag zur Summe in Eq 28 (vereinfacht als Vergleich zu Uniform Noise)
            # log(Cx(t)) - log(u)
            log_likelihood_sum += (math.log(c_x_t) - math.log(u))
            
        results.append({
            'receiver': receiver,
            'log_likelihood_score': log_likelihood_sum,
            'total_packets_received': n
        })

    # Auswertung
    # Sortiere nach höchstem Likelihood Score
    results.sort(key=lambda x: x['log_likelihood_score'], reverse=True)
    
    # Finde den echten Empfänger (Ground Truth aus den Daten extrahieren)
    # Wir schauen, wohin die Pakete von target_src tatsächlich gegangen sind
    actual_dst_packets = traffic_df[(traffic_df['src'] == target_src) & (traffic_df['event_type'] == 'RECEIVED')]
    if not actual_dst_packets.empty:
        true_receiver = actual_dst_packets['node_id'].mode()[0] # Der häufigste Empfänger
    else:
        true_receiver = "Unknown"

    top_match = results[0]['receiver'] if results else None
    
    # Hat der Angriff funktioniert?
    success = (top_match == true_receiver)
    
    return {
        'target_src': target_src,
        'true_receiver': true_receiver,
        'detected_receiver': top_match,
        'likelihood_score': results[0]['log_likelihood_score'] if results else 0,
        'success': success,
        'all_scores': results  # Optional für Debugging
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("logs_root", help="Root directory containing Testrun folders")
    args = parser.parse_args()
    
    runs = [os.path.join(args.logs_root, d) for d in os.listdir(args.logs_root) 
            if os.path.isdir(os.path.join(args.logs_root, d)) and d.startswith("Testrun")]
    
    print(f"{'Run Name':<40} | {'Target':<10} -> {'True Dst':<10} | {'Detected':<10} | {'Score':<10} | {'Success'}")
    print("-" * 110)
    
    total_runs = 0
    successful_runs = 0
    
    for run in runs:
        run_name = os.path.basename(run)
        config = load_config(run)
        
        # Mix Rate mu
        mu = config.get('mix_settings', {}).get('mu', 0.5)
        # Anzahl der Hops k (Standard 3 für Onion Routing ähnliche Pfade)
        # Wenn im Config nicht vorhanden, nehmen wir 3 an
        k = config.get('network_settings', {}).get('num_hops', 3) 
        
        df = load_logs(run)
        if df.empty:
            continue
            
        metrics = perform_stream_attack(df, mu, k=k)
        
        if not metrics:
            continue
            
        total_runs += 1
        if metrics['success']:
            successful_runs += 1
            
        print(f"{run_name:<40} | {metrics['target_src']:<10} -> {metrics['true_receiver']:<10} | {metrics['detected_receiver']:<10} | {metrics['likelihood_score']:<10.2f} | {metrics['success']}")
        
        # Ergebnisse speichern
        out_dir = os.path.join(run, "analysis_results")
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "traffic_analysis_attack_results.txt"), "w") as f:
            f.write(json.dumps(metrics, indent=4, default=str))

    if total_runs > 0:
        print("-" * 110)
        print(f"Overall Attack Success Rate: {successful_runs}/{total_runs} ({successful_runs/total_runs:.2%})")

if __name__ == "__main__":
    main()