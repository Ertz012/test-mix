import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from scipy.stats import expon


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

def run_traffic_analysis(file_ingress, file_egress, target_src_id, mix_delay_mu):
    """
    Führt die Traffic Analysis basierend auf Danezis' Paper durch.
    
    Args:
        file_ingress: Pfad zur CSV mit eingehenden Nachrichten.
        file_egress: Pfad zur CSV mit ausgehenden Nachrichten.
        target_src_id: Die 'src' ID, die wir verfolgen wollen (das Opfer).
        mix_delay_mu: Der Parameter mu der Exponentialverteilung (Rate). 
                      ACHTUNG: mu = 1 / durchschnittliche_verzögerung.
                      Für avg_delay=2s muss mix_delay_mu=0.5 sein.
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
    
    # Normalisieren der Zeitstempel auf t=0
    df_in['t_norm'] = df_in['timestamp'] - t_start
    df_out['t_norm'] = df_out['timestamp'] - t_start

    print(f"Verwende festes mu (Rate): {mix_delay_mu}")
    print(f"  -> Entspricht einer durchschnittlichen Verzögerung von: {1.0/mix_delay_mu:.2f}s")

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
    
    # Histogramm des Inputs (f(t))
    input_counts, _ = np.histogram(target_traffic['t_norm'], bins=num_bins, range=(0, duration))
    input_signal = input_counts / bin_size # Dichte

    # Delay Charakteristik d(x) = mu * e^(-mu * x)
    # Paper Referenz: Gleichung (10) [cite: 73]
    # Wir berechnen den Kernel bis die Wahrscheinlichkeit vernachlässigbar ist
    max_delay_influence = expon.ppf(0.999, scale=1/mix_delay_mu) 
    kernel_bins = int(np.ceil(max_delay_influence / bin_size))
    kernel_x = np.linspace(0, max_delay_influence, kernel_bins)
    
    # scipy.stats.expon verwendet scale=1/lambda (also scale=1/mu)
    delay_kernel = expon.pdf(kernel_x, scale=1/mix_delay_mu)
    delay_kernel /= delay_kernel.sum() # Normalisieren für diskrete Faltung

    # Faltung: (d * f)(t) - Referenz Gleichung (24) [cite: 180]
    convolved_signal = np.convolve(input_signal, delay_kernel, mode='full')[:num_bins]
    
    # 4. Likelihood Berechnung für jeden möglichen Ausgang
    results = []
    unique_dsts = df_out['dst'].unique()
    
    lambda_f = len(target_traffic) / duration # Rate des Ziels
    u_prob = 1.0 / duration # Gleichverteilung (Noise Modell)

    print(f"Berechne Likelihoods für {len(unique_dsts)} mögliche Ziele...")

    for dst in unique_dsts:
        dst_traffic = df_out[df_out['dst'] == dst]
        if len(dst_traffic) == 0:
            continue
            
        observations = dst_traffic['t_norm'].values
        
        # Mapping auf Bins
        bin_indices = (observations / bin_size).astype(int)
        bin_indices = np.clip(bin_indices, 0, num_bins - 1)
        
        lambda_x = len(dst_traffic) / duration
        
        # Signalwerte an den Beobachtungszeitpunkten
        signal_vals = convolved_signal[bin_indices]
        
        # Berechnung Wahrscheinlichkeitsdichte C_X(t) - Referenz Gleichung (23) [cite: 176]
        # C_X(t) = (lambda_f * (d*f)(t) + (lambda_x - lambda_f) * U) / lambda_x
        term_signal = lambda_f * signal_vals
        term_noise = (lambda_x - lambda_f) * u_prob
        term_noise = np.maximum(term_noise, 0)
        c_x_vals = (term_signal + term_noise) / lambda_x
        c_x_vals = np.maximum(c_x_vals, 1e-20)
        
        score_h0 = np.sum(np.log(c_x_vals)) # Das ist deine 5791
        
        # 2. Der Score für die Null-Hypothese (H1: Nur Rauschen)
        # Unter H1 ist die Wahrscheinlichkeit für jeden Zeitpunkt einfach die Gleichverteilung u_prob
        # Da C_Y(t) im Paper für H1 als reines Rauschen angenommen wird (bzw. U(t)):
        # Wir vergleichen gegen ein Modell, wo NUR Rauschen auf dem Link ist.
        # P(t) = u_prob
        # Wir müssen aber aufpassen: c_x_vals sind Dichten. 
        # Die Dichte der Gleichverteilung ist 1/Duration.
        
        c_noise_vals = np.full_like(c_x_vals, u_prob)
        score_h1 = np.sum(np.log(c_noise_vals))
        
        # 3. Decision Metric (Log-Likelihood Ratio)
        # Formel (28) im Paper: Sum(log(Cx)) - Sum(log(Cy)) ...
        # Hier: H0 - H1
        decision_metric = score_h0 - score_h1
    
        results.append({
                'dst': dst,
                'score': decision_metric, # Das ist jetzt der Wert wie im Paper
                'raw_score': score_h0,     # Dein alter Wert
                'packet_count': len(dst_traffic)
            })

    # 5. Ergebnisse ausgeben
    results_df = pd.DataFrame(results)
    if not results_df.empty:
        results_df = results_df.sort_values('score', ascending=False).reset_index(drop=True)
    return results_df, target_src_id

def analyze_and_plot(file_ingress, file_egress, target_src_id, mix_delay_mu, output_dir=None):
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

    # Histogramm des Inputs
    input_counts, _ = np.histogram(target_df['t_norm'], bins=num_bins, range=(0, duration))
    input_signal = input_counts / bin_size

    # Delay Kernel
    max_delay = expon.ppf(0.999, scale=1/mix_delay_mu)
    kernel_bins = int(np.ceil(max_delay / bin_size))
    kernel_x = np.linspace(0, max_delay, kernel_bins)
    delay_kernel = expon.pdf(kernel_x, scale=1/mix_delay_mu)
    delay_kernel /= delay_kernel.sum() 

    convolved_signal = np.convolve(input_signal, delay_kernel, mode='full')[:num_bins]

    # --- 3. Analyse mit exakter Decision Metric ---
    results = []
    unique_dsts = df_out['dst'].unique()
    
    lambda_f = len(target_df) / duration
    u_prob = 1.0 / duration # Wahrscheinlichkeitsdichte des Rauschens (1/T)

    debug_data = {} 
    
    print(f"Analysiere {len(unique_dsts)} Ziele für Plot...")

    for dst in unique_dsts:
        dst_df = df_out[df_out['dst'] == dst]
        if dst_df.empty: continue
        
        obs = dst_df['t_norm'].values
        bin_idx = np.clip((obs / bin_size).astype(int), 0, num_bins - 1)
        
        lambda_x = len(dst_df) / duration
        
        # Werte des Modells an den Paket-Zeitpunkten
        sig_vals = convolved_signal[bin_idx]
        
        # --- KERNSTÜCK: Berechnung der Log-Likelihood Ratio ---
        
        # Hypothese H0: Signal + Rauschen
        # C_X(t) = (lambda_f * Signal(t) + (lambda_x - lambda_f) * U) / lambda_x
        term_noise_share = (lambda_x - lambda_f) * u_prob
        term_noise_share = np.maximum(term_noise_share, 0) # Safety clip
        p_h0 = (lambda_f * sig_vals + term_noise_share) / lambda_x
        p_h0 = np.maximum(p_h0, 1e-50) # Schutz vor log(0)
        
        # Hypothese H1: Nur Rauschen
        # C_Y(t) = U = 1/T
        p_h1 = u_prob
        
        # Der Score pro Paket ist der Zuwachs an "Beweislast"
        # Log-Likelihood Ratio: log(P(H0)) - log(P(H1))
        # Positive Werte sprechen für H0 (Ziel), Negative für H1 (Rauschen)
        llr_per_packet = np.log(p_h0) - np.log(p_h1)
        
        # Kumulative Summe für den Plot (Decision Variable über die Zeit)
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
    axs[1].plot(time_axis, convolved_signal, color='red', lw=1.5)
    axs[1].fill_between(time_axis, convolved_signal, color='red', alpha=0.1)
    axs[1].set_title('2. Erwartetes Muster (Convolution)')
    axs[1].set_ylabel('Wahrscheinlichkeit')
    axs[1].grid(True, alpha=0.3)

    # Plot 3: Output Winner
    winner_data = debug_data[winner]
    axs[2].vlines(winner_data['times'], 0, 1, color='green', alpha=0.5, label='Pakete')
    # Muster im Hintergrund zur visuellen Prüfung
    axs[2].plot(time_axis, convolved_signal / convolved_signal.max(), 'r--', alpha=0.3, label='Muster (scaled)')
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
        plot_filename = os.path.join(output_dir, 'traffic_analysis_exact.png')
    else:
        plot_filename = 'traffic_analysis_exact.png'
        
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
    
    args = parser.parse_args()
    
    IN_FILE = os.path.join(args.run_dir, 'system_in.csv')
    OUT_FILE = os.path.join(args.run_dir, 'system_out.csv')
    
    if not os.path.exists(IN_FILE) or not os.path.exists(OUT_FILE):
        print(f"Error: consolidated logs not found in {args.run_dir}. Run consolidate_traffic_logs.py first.")
        sys.exit(1)
    
    # Analyse starten
    ranking, detected_target = run_traffic_analysis(IN_FILE, OUT_FILE, args.target, args.mu)
    
    if ranking is not None and not ranking.empty:
        print("\n--- Top 5 Verdächtige ---")
        print(ranking.head(5))
        
        # Save ranking to text file
        ranking_file = os.path.join(args.run_dir, 'traffic_analysis_ranking.txt')
        with open(ranking_file, 'w') as f:
            f.write(f"Traffic Analysis Result for Target: {detected_target}\n")
            f.write(f"Mu: {args.mu}\n\n")
            f.write(ranking.to_string())
        print(f"Ranking gespeichert in: {ranking_file}")
            
    else:
        print("Keine Ergebnisse.")
        
    analyze_and_plot(IN_FILE, OUT_FILE, detected_target, args.mu, output_dir=args.run_dir)
