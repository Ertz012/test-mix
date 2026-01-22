import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from scipy.stats import erlang

def detect_target(df_in):
    """
    Identifies the most active source in the input dataframe.
    """
    if df_in.empty or 'src' not in df_in.columns:
        return None
    
    # Count occurrences of each src
    src_counts = df_in['src'].value_counts()
    if src_counts.empty:
        return None
        
    return src_counts.idxmax()

def run_traffic_analysis(file_ingress, file_egress, target_src_id, mix_delay_mu, k_hops=3):
    """
    Führt die Traffic Analysis basierend auf Danezis' Paper durch.
    
    Args:
        file_ingress: Pfad zur CSV mit eingehenden Nachrichten.
        file_egress: Pfad zur CSV mit ausgehenden Nachrichten.
        target_src_id: Die 'src' ID, die wir verfolgen wollen (das Opfer).
        mix_delay_mu: Der Parameter mu der Exponentialverteilung (Rate) PRO HOP. 
        k_hops: Anzahl der Mix-Hops (bestimmt den Shape-Parameter der Erlang-Verteilung).
    """
    
    # 1. Daten laden
    print(f"Lade Daten...")
    try:
        df_in = pd.read_csv(file_ingress)
        df_out = pd.read_csv(file_egress)
    except FileNotFoundError as e:
        print(f"Fehler: Datei nicht gefunden - {e}")
        return pd.DataFrame(), None

    # Auto-detect target if not provided
    if not target_src_id:
        print("Ziel nicht spezifiziert. Versuche automatische Erkennung...")
        target_src_id = detect_target(df_in)
        if target_src_id:
            print(f"Automatisch erkanntes Ziel: {target_src_id}")
        else:
            print("Fehler: Konnte Ziel nicht automatisch erkennen.")
            return pd.DataFrame(), None

    # Sortieren nach Zeit
    df_in = df_in.sort_values('timestamp')
    df_out = df_out.sort_values('timestamp')

    # Globale Zeitgrenzen bestimmen
    if df_in.empty or df_out.empty:
        print("Fehler: Eine der Dateien ist leer.")
        return pd.DataFrame(), None

    t_start = min(df_in['timestamp'].min(), df_out['timestamp'].min())
    t_end = max(df_in['timestamp'].max(), df_out['timestamp'].max())
    duration = t_end - t_start
    if duration <= 0: duration = 1.0
    
    # Normalisieren der Zeitstempel auf t=0
    df_in['t_norm'] = df_in['timestamp'] - t_start
    df_out['t_norm'] = df_out['timestamp'] - t_start

    print(f"Parameter: mu={mix_delay_mu}, k={k_hops}")
    print(f"  -> Erwartete Gesamtverzögerung (Erlang): {k_hops/mix_delay_mu:.2f}s")

    # 2. Das Eingangssignal f(t) des Ziels extrahieren
    target_traffic = df_in[df_in['src'] == target_src_id]
    if target_traffic.empty:
        print(f"Keine Nachrichten für src {target_src_id} gefunden.")
        return pd.DataFrame(), None

    print(f"Analysiere Ziel '{target_src_id}' mit {len(target_traffic)} Nachrichten.")

    # 3. Diskretisierung und Faltung
    # Parameter für die Auflösung
    bin_size = 0.1 # 100ms
    num_bins = int(np.ceil(duration / bin_size)) + 1
    
    # Histogramm des Inputs (f(t)) -> Normalize to PDF
    input_counts, _ = np.histogram(target_traffic['t_norm'], bins=num_bins, range=(0, duration))
    total_input_packets = len(target_traffic)
    input_pdf = input_counts / (total_input_packets * bin_size) # Integral = 1.0

    # Delay Charakteristik d(x) = Erlang(k, mu)
    # Erlang PDF für 3 Hops (Summe von 3 Exponentials)
    # Simulation uses random.expovariate(1.0/mu), so Mean = mu.
    # We want Sum of k variables each with Mean = mu.
    # Scipy Erlang(k, scale=S) has Mean = k*S. So S = mu.
    max_delay_influence = erlang.ppf(0.999, k_hops, scale=mix_delay_mu) 
    kernel_bins = int(np.ceil(max_delay_influence / bin_size))
    kernel_x = np.linspace(0, max_delay_influence, kernel_bins)
    
    delay_kernel = erlang.pdf(kernel_x, k_hops, scale=mix_delay_mu)
    delay_kernel /= delay_kernel.sum() # Normalize for discrete convolution

    # Faltung: (d * f)(t) -> PDF Result
    convolved_pdf = np.convolve(input_pdf, delay_kernel, mode='full')[:num_bins]
    
    # 4. Likelihood Berechnung für jeden möglichen Ausgang
    results = []
    unique_dsts = df_out['dst'].unique()
    
    lambda_f = total_input_packets / duration # Rate des Ziels
    u_prob = 1.0 / duration # Gleichverteilung (PDF)

    print(f"Berechne Likelihoods für {len(unique_dsts)} mögliche Ziele...")

    for dst in unique_dsts:
        dst_traffic = df_out[df_out['dst'] == dst]
        if len(dst_traffic) == 0:
            continue
            
        observations = dst_traffic['t_norm'].values
        
        # Mapping auf Bins
        # Mapping auf Bins
        bin_indices = (observations / bin_size).astype(int)
        bin_indices = np.clip(bin_indices, 0, num_bins - 1)
        
        lambda_x = len(dst_traffic) / duration
        
        # Signal PDF-Werte an den Beobachtungszeitpunkten
        pdf_vals_signal = convolved_pdf[bin_indices]        

        # Mischmodell Gewichte
        # Wenn lambda_f (Input Rate) > lambda_x (Output Rate), dann haben wir Verlust oder Filterung.
        # Wir können nicht mehr Signal im Output haben als Pakete da sind.
        # Daher clampen wir die effektive Signal-Rate auf lambda_x.
        lambda_f_effective = min(lambda_f, lambda_x * 0.99) # 0.99 um numerische Probleme (div/0) zu vermeiden und immer etwas Rauschen zuzulassen
        
        w_signal = lambda_f_effective / lambda_x
        w_noise = (lambda_x - lambda_f_effective) / lambda_x
        w_noise = max(w_noise, 0) # Clamp negative noise weights
        
        # C_X(t) Mischverteilung
        c_x_vals = w_signal * pdf_vals_signal + w_noise * u_prob
        c_x_vals = np.maximum(c_x_vals, 1e-50) # Avoid log(0)
        
        # Log-Likelihood Ratio per packet
        # Calculate (Log L_H0 - Log L_H1) per packet to avoid large number subtraction issues
        llr_per_packet = np.log(c_x_vals) - np.log(u_prob)
        
        # Decision Metric
        decision_metric = np.sum(llr_per_packet)
        
        # Keep raw score for reference (optional)
        score_h0 = np.sum(np.log(c_x_vals))
    
        results.append({
                'dst': dst,
                'score': decision_metric,
                'raw_score_h0': score_h0,
                'packet_count': len(dst_traffic)
            })

    # 5. Ergebnisse ausgeben
    results_df = pd.DataFrame(results)
    if not results_df.empty:
        results_df = results_df.sort_values('score', ascending=False).reset_index(drop=True)
    return results_df, target_src_id

def analyze_and_plot(file_ingress, file_egress, target_src_id, mix_delay_mu, output_dir=None, k_hops=3):
    # --- 1. Daten Laden & Vorbereiten ---
    print("Lade Daten für Plot...")
    try:
        df_in = pd.read_csv(file_ingress)
        df_out = pd.read_csv(file_egress)
    except Exception as e:
        print(f"Fehler: {e}")
        return

    # Auto-detect target if not provided (should be consistent with run_traffic_analysis)
    if not target_src_id:
        target_src_id = detect_target(df_in)
        if not target_src_id:
            print("Kein Ziel für Plot erkannt.")
            return

    df_in = df_in.sort_values('timestamp')
    df_out = df_out.sort_values('timestamp')
    
    t_start = min(df_in['timestamp'].min(), df_out['timestamp'].min())
    t_end = max(df_in['timestamp'].max(), df_out['timestamp'].max())
    duration = t_end - t_start
    if duration <= 0: duration = 1.0
    
    df_in['t_norm'] = df_in['timestamp'] - t_start
    df_out['t_norm'] = df_out['timestamp'] - t_start

    # --- 2. Modellierung (Faltung) ---
    bin_size = 0.1 
    num_bins = int(np.ceil(duration / bin_size)) + 1
    time_axis = np.linspace(0, duration, num_bins)

    target_df = df_in[df_in['src'] == target_src_id]
    if target_df.empty:
        print("Kein Input-Traffic.")
        return

    # Histogramm des Inputs -> PDF
    input_counts, _ = np.histogram(target_df['t_norm'], bins=num_bins, range=(0, duration))
    total_input = len(target_df)
    input_pdf = input_counts / (total_input * bin_size)

    # Kernel erstellen (Erlang-Verteilung für k Hops)
    # Simulation uses random.expovariate(1.0/mu), so Mean = mu.
    # We want Sum of k variables each with Mean = mu.
    # Scipy Erlang(k, scale=S) has Mean = k*S.
    # So we need S = mu.
    # Previous code used scale=1/mu (assuming mu was Rate), which caused mismatch.
    max_delay = erlang.ppf(0.999, k_hops, scale=mix_delay_mu)
    num_kernel_bins = int(np.ceil(max_delay / bin_size))
    t_kernel = np.linspace(0, max_delay, num_kernel_bins)
    delay_kernel = erlang.pdf(t_kernel, k_hops, scale=mix_delay_mu)
    delay_kernel /= delay_kernel.sum() # Normalize so sum is 1 (probability mass)
    convolved_pdf = np.convolve(input_pdf, delay_kernel, mode='full')[:num_bins]

    # --- 3. Analyse mit exakter Decision Metric ---
    results = []
    unique_dsts = df_out['dst'].unique()
    
    lambda_f = total_input / duration
    u_prob = 1.0 / duration 

    debug_data = {} 
    
    print(f"Analysiere {len(unique_dsts)} Ziele für Plot...")

    for dst in unique_dsts:
        dst_df = df_out[df_out['dst'] == dst]
        if dst_df.empty: continue
        
        obs = dst_df['t_norm'].values
        bin_idx = np.clip((obs / bin_size).astype(int), 0, num_bins - 1)
        
        lambda_x = len(dst_df) / duration
        
        # Werte des Modells an den Paket-Zeitpunkten
        pdf_vals = convolved_pdf[bin_idx]
        
        if dst == 'c1' and target_src_id == 'c2':
             pass # Removed debug

        # --- KERNSTÜCK: Berechnung der Log-Likelihood Ratio ---
        
        # Hypothese H0: Signal + Rauschen
        # Weighted Mixture: w_signal * P_signal + w_noise * P_noise
        lambda_f_effective = min(lambda_f, lambda_x * 0.99)
        
        w_sig = lambda_f_effective / lambda_x
        w_noise = (lambda_x - lambda_f_effective) / lambda_x
        w_noise = max(w_noise, 0)

        p_h0 = w_sig * pdf_vals + w_noise * u_prob
        p_h0 = np.maximum(p_h0, 1e-50) 
        
        # Hypothese H1: Nur Rauschen
        p_h1 = u_prob
        
        # Log-Likelihood Ratio per packet
        llr_per_packet = np.log(p_h0) - np.log(p_h1)

        # Kumulative Summe für den Plot
        cum_score = np.cumsum(llr_per_packet)
        total_score = cum_score[-1]
        
        results.append({
            'dst': dst, 
            'score': total_score,
            'packet_count': len(dst_df)
        })
        
        debug_data[dst] = {
            'times': obs,
            'cum_score': cum_score,
            'final_score': total_score
        }

    # Ergebnisse sortieren
    if not results:
        print("Keine Ergebnisse für Plot.")
        return

    results_df = pd.DataFrame(results).sort_values('score', ascending=False)
    
    # Top Kandidat und Vergleichskandidat
    winner = results_df.iloc[0]['dst']
    loser = results_df.iloc[1]['dst'] if len(results_df) > 1 else winner
    
    print(f"\n--- Ergebnis Plot ---")
    print(f"Top Treffer: {winner} (Score: {results_df.iloc[0]['score']:.2f})")

    # --- 4. Plotting ---
    fig, axs = plt.subplots(4, 1, figsize=(12, 14), sharex=True)
    
    # Plot 1: Input
    axs[0].vlines(target_df['t_norm'], 0, 1, color='blue', alpha=0.5)
    axs[0].set_title(f'1. Input Signal (Source: {target_src_id})')
    axs[0].set_ylabel('Events')
    axs[0].grid(True, alpha=0.3)

    # Plot 2: Convolution
    axs[1].plot(time_axis, convolved_pdf, color='red', lw=1.5)
    axs[1].fill_between(time_axis, convolved_pdf, color='red', alpha=0.1)
    axs[1].set_title(f'2. Erwartetes Muster (Convolution PDF, k={k_hops})')
    axs[1].set_ylabel('Wahrscheinlichkeitsdichte')
    axs[1].grid(True, alpha=0.3)

    # Plot 3: Output Winner
    winner_data = debug_data[winner]
    axs[2].vlines(winner_data['times'], 0, 1, color='green', alpha=0.5, label='Pakete')
    # Muster im Hintergrund zur visuellen Prüfung
    axs[2].plot(time_axis, convolved_pdf / convolved_pdf.max(), 'r--', alpha=0.3, label='Muster (scaled)')
    axs[2].set_title(f'3. Output Traffic auf {winner} (Top Candidate)')
    axs[2].legend(loc='upper right')
    axs[2].grid(True, alpha=0.3)

    # Plot 4: Decision Metric (Log-Likelihood Ratio)
    # Hier sieht man jetzt schön den Unterschied:
    # 0 ist die Nulllinie. Geht es hoch, ist es das Ziel. Geht es runter/seitwärts, ist es Rauschen.
    axs[3].axhline(y=0, color='black', linestyle='-', linewidth=1, alpha=0.5)
    
    # Winner
    axs[3].step(winner_data['times'], winner_data['cum_score'], where='post', 
                label=f'{winner} (Score: {winner_data["final_score"]:.0f})', color='green', linewidth=2)
    
    # Loser (Vergleich)
    if winner != loser:
        loser_data = debug_data[loser]
        axs[3].step(loser_data['times'], loser_data['cum_score'], where='post', 
                    label=f'{loser} (Score: {loser_data["final_score"]:.0f})', color='gray', alpha=0.6)

    axs[3].set_title('4. Decision Metric (Log-Likelihood Ratio)\nSteigt an = Ziel erkannt | Seitwärts/Abwärts = Rauschen')
    axs[3].set_ylabel('Kumulativer Score')
    axs[3].set_xlabel('Zeit (s)')
    axs[3].legend(loc='upper left')
    axs[3].grid(True, alpha=0.3)

    plt.tight_layout()
    
    if output_dir:
        plot_filename = os.path.join(output_dir, f'traffic_analysis_binned_{target_src_id}.png')
    else:
        plot_filename = f'traffic_analysis_binned_{target_src_id}.png'
        
    plt.savefig(plot_filename)
    print(f"\nGrafik gespeichert als '{plot_filename}'")
    # plt.show() # Disabled for batch processing

# --- CLI Aufruf ---
if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Run traffic analysis on consolidated logs.")
    parser.add_argument("--run-dir", help="Directory containing system_in.csv and system_out.csv", required=True)
    parser.add_argument("--target", help="Target Source ID (e.g., c1). Auto-detected if not provided.", default=None)
    parser.add_argument("--mu", help="Mixing parameter mu (rate). Default: 0.5", type=float, default=0.5)
    parser.add_argument("--hops", help="Number of hops (k) for Erlang distribution. Default: 3", type=int, default=3)
    
    args = parser.parse_args()
    
    IN_FILE = os.path.join(args.run_dir, 'system_in.csv')
    OUT_FILE = os.path.join(args.run_dir, 'system_out.csv')
    
    if not os.path.exists(IN_FILE) or not os.path.exists(OUT_FILE):
        print(f"Error: consolidated logs not found in {args.run_dir}. Run consolidate_traffic_logs.py first.")
        sys.exit(1)
    
    # Analyse starten
    ranking, detected_target = run_traffic_analysis(IN_FILE, OUT_FILE, args.target, args.mu, k_hops=args.hops)
    
    if ranking is not None and not ranking.empty:
        print("\n--- Top 5 Verdächtige ---")
        print(ranking.head(5))
        
        # Save ranking to text file
        # Use analysis_results directory and _exact.txt suffix to match analyze_all_results.py
        out_results_dir = os.path.join(args.run_dir, 'analysis_results')
        os.makedirs(out_results_dir, exist_ok=True)
        ranking_file = os.path.join(out_results_dir, f'traffic_analysis_binned_{detected_target}.txt')
        
        with open(ranking_file, 'w') as f:
            f.write(f"Traffic Analysis Result for Target: {detected_target}\n")
            f.write(f"Mu: {args.mu}, K: {args.hops}\n\n")
            f.write(ranking.to_string())
        print(f"Ranking gespeichert in: {ranking_file}")
            
    else:
        print("Keine Ergebnisse.")
        
    analyze_and_plot(IN_FILE, OUT_FILE, detected_target, args.mu, output_dir=os.path.join(args.run_dir, 'analysis_results'), k_hops=args.hops)
