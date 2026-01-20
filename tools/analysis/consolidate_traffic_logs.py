
import os
import sys
import glob
import pandas as pd
import argparse

def process_logs(run_dir):
    """
    Consolidates traffic logs from Entry and Exit nodes into system_in.csv and system_out.csv.
    """
    print(f"Processing logs in: {run_dir}")

    # --- Process System Input (Entry Nodes) ---
    entry_files = glob.glob(os.path.join(run_dir, "e*_traffic.csv"))
    print(f"Found {len(entry_files)} entry node logs.")
    
    system_in_frames = []
    for f in entry_files:
        try:
            df = pd.read_csv(f)
            # Filter for RECEIVED packets coming from Clients or Providers
            # Note: We check if prev_hop is a client (c*) or provider (p*)
            # event_type must be RECEIVED
            if 'event_type' in df.columns and 'prev_hop' in df.columns:
                mask = (
                    (df['event_type'] == 'RECEIVED') & 
                    (df['prev_hop'].str.startswith(('c', 'p'), na=False))
                )
                filtered_df = df[mask].copy()
                
                # We want message_id, timestamp, src, and dst
                if not filtered_df.empty:
                    system_in_frames.append(filtered_df[['message_id', 'timestamp', 'src', 'dst']])
        except Exception as e:
            print(f"Error processing {f}: {e}")

    if system_in_frames:
        system_in_df = pd.concat(system_in_frames)
        system_in_df.sort_values(by='timestamp', inplace=True)
        out_path = os.path.join(run_dir, "system_in.csv")
        system_in_df.to_csv(out_path, index=False)
        print(f"Created {out_path} with {len(system_in_df)} entries.")
    else:
        print("No input traffic found or no entry logs valid.")


    # --- Process System Output (Exit Nodes) ---
    exit_files = glob.glob(os.path.join(run_dir, "x*_traffic.csv"))
    print(f"Found {len(exit_files)} exit node logs.")

    system_out_frames = []
    for f in exit_files:
        try:
            df = pd.read_csv(f)
            # Filter for SENT packets going to Clients or Providers
            # Note: We check if next_hop is a client (c*) or provider (p*)
            # event_type must be SENT
            if 'event_type' in df.columns and 'next_hop' in df.columns:
                mask = (
                    (df['event_type'] == 'SENT') & 
                    (df['next_hop'].str.startswith(('c', 'p'), na=False))
                )
                filtered_df = df[mask].copy()
                
                # We want message_id, timestamp, dst, and src
                if not filtered_df.empty:
                    system_out_frames.append(filtered_df[['message_id', 'timestamp', 'dst', 'src']])
        except Exception as e:
            print(f"Error processing {f}: {e}")

    if system_out_frames:
        system_out_df = pd.concat(system_out_frames)
        system_out_df.sort_values(by='timestamp', inplace=True)
        out_path = os.path.join(run_dir, "system_out.csv")
        system_out_df.to_csv(out_path, index=False)
        print(f"Created {out_path} with {len(system_out_df)} entries.")
    else:
        print("No output traffic found or no exit logs valid.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Consolidate mixnet traffic logs.")
    parser.add_argument("run_dir", help="Path to the test run directory containing node logs.")
    args = parser.parse_args()

    if not os.path.isdir(args.run_dir):
        print(f"Error: Directory not found: {args.run_dir}")
        sys.exit(1)

    process_logs(args.run_dir)
