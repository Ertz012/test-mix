import pandas as pd
import glob
import os
import sys

def analyze_loss_timings(log_dir):
    print(f"Analyzing {log_dir}...")
    
    # 1. Load CREATED packets (Clients)
    sent_dfs = []
    client_files = glob.glob(os.path.join(log_dir, "c*_traffic.csv"))
    if not client_files:
        print("No client logs found.")
        return

    for f in client_files:
        try:
            df = pd.read_csv(f, names=["timestamp", "event_type", "packet_id", "src", "dst", "payload_size", "latency"], header=None)
            df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
            # Filter for CREATED
            created = df[df['event_type'] == 'CREATED'].copy()
            sent_dfs.append(created)
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    if not sent_dfs:
        print("No sent packets found.")
        return
        
    sent_df = pd.concat(sent_dfs)
    # Deduplicate sent packets
    sent_df = sent_df.sort_values('timestamp').drop_duplicates(subset=['packet_id'], keep='first')
    
    # 2. Load RECEIVED packets (Clients)
    recv_dfs = []
    # In Client.py, we moved RECEIVED logging to log the inner ID.
    # So we should look at c*_traffic.csv for RECEIVED events too.
    for f in client_files:
        try:
            df = pd.read_csv(f, names=["timestamp", "event_type", "packet_id", "src", "dst", "payload_size", "latency"], header=None)
            received = df[df['event_type'] == 'RECEIVED'].copy()
            recv_dfs.append(received)
        except:
            pass
            
    if recv_dfs:
        recv_df = pd.concat(recv_dfs)
    else:
        recv_df = pd.DataFrame(columns=["timestamp", "event_type", "packet_id"])

    # 3. Find Lost Packets
    sent_ids = set(sent_df['packet_id'])
    recv_ids = set(recv_df['packet_id'])
    lost_ids = sent_ids - recv_ids
    
    lost_df = sent_df[sent_df['packet_id'].isin(lost_ids)].copy()
    
    print(f"Total Sent: {len(sent_df)}")
    print(f"Total Received: {len(recv_df)}")
    print(f"Total Lost: {len(lost_df)}")
    print(f"Calculated Loss Rate: {len(lost_df)/len(sent_df)*100:.2f}%")
    
    # 4. Analyze Timing of Lost Packets
    # Normalize time to start=0
    start_time = sent_df['timestamp'].min()
    lost_df['relative_time'] = lost_df['timestamp'] - start_time
    
    print("\n--- Loss Timing Distribution ---")
    print(lost_df['relative_time'].describe())
    
    # Check "Tail Drop" (last 5 seconds)
    last_packet_time = sent_df['timestamp'].max() - start_time
    print(f"\nLast Packet Sent at: {last_packet_time:.2f}s")
    
    tail_drops = lost_df[lost_df['relative_time'] > (last_packet_time - 5)]
    print(f"Lost packets in last 5 seconds: {len(tail_drops)} ({len(tail_drops)/len(lost_df)*100:.2f}% of total loss)")

    # Check "Early Drop" (first 5 seconds)
    early_drops = lost_df[lost_df['relative_time'] < 5]
    print(f"Lost packets in first 5 seconds: {len(early_drops)} ({len(early_drops)/len(lost_df)*100:.2f}% of total loss)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_loss_timings.py <log_dir>")
    else:
        analyze_loss_timings(sys.argv[1])
