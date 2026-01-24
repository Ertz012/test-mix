
import os
import pandas as pd
import numpy as np
import argparse
import glob

def calculate_binary_entropy(p):
    """
    Calculates H({p, 1-p}) = -p log p - (1-p) log (1-p)
    Using base 2 for bits.
    """
    if p <= 0 or p >= 1:
        return 0.0
    return -p * np.log2(p) - (1-p) * np.log2(1-p)

def process_node_entropy(filepath):
    """
    Parses a single traffic log and computes entropy evolution using Loopix Eq 5.
    Returns DataFrame [timestamp, pool_size, entropy]
    """
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

    # Filter relevant events
    # Inputs: RECEIVED
    # Outputs: SENT
    # needed fields: timestamp, event_type
    
    if 'event_type' not in df.columns:
        return None
        
    inputs = df[df['event_type'] == 'RECEIVED'].copy()
    inputs['type'] = 'in'
    
    outputs = df[df['event_type'] == 'SENT'].copy()
    outputs['type'] = 'out'
    
    # Merge and sort
    events = pd.concat([inputs, outputs]).sort_values('timestamp')
    
    # State
    H_t = 0.0
    l = 0 # Previous pool size
    k = 0 # New arrivals since last send
    
    history = []
    
    for _, row in events.iterrows():
        ts = row['timestamp']
        etype = row['type']
        
        if etype == 'in':
            k += 1
        else:
            # Output event
            # Logic from Appendix A.1
            # l = size from previous rounds
            # k = received since last send
            
            total_pool = k + l
            
            if total_pool == 0:
                # Should not happen in ideal model (sending empty?), or created loop/drop
                # If generated locally, it's virtually an input+output. 
                # Let's assume it doesn't change entropy of the EMPTY pool.
                pass
            else:
                # Weights
                w_new = k / total_pool
                w_old = l / total_pool
                
                # Binary Entropy of mixing old vs new groups
                h_binary = calculate_binary_entropy(w_new)
                
                # Component Entropies
                # New group: Uniform among k -> log2(k)
                # Old group: Inherited H_t-1
                
                h_new_group = np.log2(k) if k > 0 else 0
                h_old_group = H_t
                
                # Eq 5
                H_next = h_binary + w_new * h_new_group + w_old * h_old_group
                
                # Update State
                H_t = H_next
                
                # One message leaves the pool
                # New pool size becomes N-1.
                # The "new" l for the next step is current (k+l) - 1
                l = total_pool - 1
                k = 0 # Reset new counter
                
                history.append({
                    'timestamp': ts,
                    'pool_size': total_pool,
                    'entropy': H_t
                })
                
    return pd.DataFrame(history)

def main():
    parser = argparse.ArgumentParser(description="Calculate Loopix Entropy (Eq 5)")
    parser.add_argument("--logs-root", required=True, help="Path to logs directory")
    args = parser.parse_args()
    
    print(f"Scanning {args.logs_root}...")
    
    # Iterate all Testruns
    run_dirs = glob.glob(os.path.join(args.logs_root, "Testrun_*"))
    
    for run_dir in run_dirs:
        if not os.path.isdir(run_dir):
            continue
            
        print(f"Processing {os.path.basename(run_dir)}...")
        
        # Find all traffic logs (Mixes and Providers)
        # Using naming convention: x*_traffic.csv or *provider*_traffic.csv?
        # Standard mix: x1_traffic.csv. Provider: p1_traffic.csv?
        # Check files
        all_csvs = glob.glob(os.path.join(run_dir, "*_traffic.csv"))
        
        results = []
        
        for csv_path in all_csvs:
            filename = os.path.basename(csv_path)
            node_id = filename.replace('_traffic.csv', '')
            
            # Skip client logs? Loopix entropy is typically for Mixes.
            # Clients (c*) don't mix in the same way (they buffer inputs from user).
            # But technically modeled as a mix.
            # Let's process Mixes (x*, m*) and Providers (p*).
            if filename.startswith('c'):
                continue # Skip clients for now unless requested
                
            df_res = process_node_entropy(csv_path)
            if df_res is not None and not df_res.empty:
                # Calculate mean entropy
                mean_h = df_res['entropy'].mean()
                max_h = df_res['entropy'].max()
                mean_pool = df_res['pool_size'].mean()
                
                results.append({
                    'Node': node_id,
                    'Mean_Entropy': mean_h,
                    'Max_Entropy': max_h,
                    'Mean_Pool': mean_pool
                })
                
                # Optionally save full trace?
                # df_res.to_csv(os.path.join(run_dir, f"entropy_trace_{node_id}.csv"), index=False)
                
        if results:
            # Save Run Summary
            out_file = os.path.join(run_dir, "analysis_results", "loopix_entropy_summary.csv")
            os.makedirs(os.path.dirname(out_file), exist_ok=True)
            pd.DataFrame(results).to_csv(out_file, index=False)
            print(f"  Saved entropy summary to {out_file}")
        else:
            print("  No mix logs found or processed.")

if __name__ == "__main__":
    main()
