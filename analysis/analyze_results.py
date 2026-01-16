import os
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import glob
import numpy as np
import networkx as nx
from collections import defaultdict
import math

def parse_logs(log_dir):
    """
    Parses sender, receiver, and mix node logs.
    Returns:
        traffic_df: DataFrame with all client events
        mix_df: DataFrame with all mix node events
    """
    traffic_dfs = []
    mix_dfs = []

    # --- Client Logs ---
    client_files = glob.glob(os.path.join(log_dir, "c*_traffic.csv"))
    for f in client_files:
        try:
            df = pd.read_csv(f)
            df['node_id'] = os.path.basename(f).split('_')[0]
            traffic_dfs.append(df)
        except Exception as e:
            print(f"Error reading {f}: {e}")

    # --- Mix Node Logs ---
    mix_files = glob.glob(os.path.join(log_dir, "x*_traffic.csv")) # Assuming x* for mix nodes? Or m*?
    # In codebase it seemed to be 'x' for mix sometimes, or 'm'. 
    # Let's check typical mix filenames. In 'run_series.py' or 'vm_manager', logs are pulled.
    # The file list earlier showed 'x*_traffic.csv' pattern logic in original script.
    # But usually mixes are m1, m2... or e1, i1...
    # The original script looked for "x*_traffic.csv". 
    # Let's expand to look for anything ending in _traffic.csv that is NOT client/sender/receiver?
    # Or just look for specific prefixes based on config?
    # Let's stick to a broader glob and filter.
    
    all_traffic_files = glob.glob(os.path.join(log_dir, "*_traffic.csv"))
    for f in all_traffic_files:
        filename = os.path.basename(f)
        if filename.startswith('c') or filename.startswith('s') or filename.startswith('r'):
            continue # Already handled or legacy
        
        # Assume it's a mix/node log
        try:
            df = pd.read_csv(f)
            df['node_id'] = filename.split('_')[0]
            mix_dfs.append(df)
        except Exception as e:
            print(f"Error reading {f}: {e}")

    traffic_df = pd.concat(traffic_dfs, ignore_index=True) if traffic_dfs else pd.DataFrame()
    mix_df = pd.concat(mix_dfs, ignore_index=True) if mix_dfs else pd.DataFrame()

    return traffic_df, mix_df

def generate_trace_report(traffic_df, mix_df, output_path):
    """
    Generates a human-readable trace of packets through the network.
    """
    if traffic_df.empty and mix_df.empty:
        return

    # Combine all events
    all_events = pd.concat([traffic_df, mix_df], ignore_index=True)
    
    # Filter relevant columns
    cols = ['timestamp', 'packet_id', 'event_type', 'node_id', 'src', 'dst', 'next_hop', 'size']
    # Ensure columns exist
    for c in cols:
        if c not in all_events.columns:
            all_events[c] = None
            
    all_events = all_events[cols]
    all_events = all_events.sort_values('timestamp')

    # Group by Packet ID
    grouped = all_events.groupby('packet_id')
    
    with open(output_path, 'w') as f:
        f.write("Packet Trace Report\n")
        f.write("===================\n\n")
        
        loss_count = 0
        retransmit_count = 0
        redirect_count = 0
        success_count = 0
        
        for pid, group in grouped:
            if pd.isna(pid) or pid == "packet_id": continue
            
            group = group.sort_values('timestamp')
            events = group.to_dict('records')
            
            # Summary Status
            is_delivered = any(e['event_type'] == 'RECEIVED' and str(e['node_id']).startswith('c') for e in events)
            has_loss = any(e['event_type'] == 'DROPPED_SIM' for e in events)
            has_retransmit = any(e['event_type'] == 'RESENT' for e in events)
            has_redirect = any(e['event_type'] == 'REDIRECTED' for e in events)
            
            if is_delivered: success_count += 1
            if has_retransmit: retransmit_count += 1
            if has_redirect: redirect_count += 1
            
            # Determine End State
            status = "DELIVERED" if is_delivered else "LOST"
            if has_loss: status += " (SIMULATED DROP)"
            
            f.write(f"Packet: {pid} [{status}]\n")
            
            for e in events:
                t = f"{e['timestamp']:.4f}"
                node = e['node_id']
                evt = e['event_type']
                details = ""
                
                if evt == "CREATED":
                    details = f"Src: {e['src']} -> Dst: {e['dst']}"
                elif evt == "FORWARDED":
                     details = f"-> {e['next_hop']}"
                elif evt == "RECEIVED":
                     if str(node).startswith('m') or str(node).startswith('e') or str(node).startswith('i') or str(node).startswith('x'):
                        details = "(Mix Processing)"
                     else:
                        details = "FINAL DELIVERY"
                elif evt == "DROPPED_SIM":
                     details = "!!! ARTIFICIAL LOSS !!!"
                elif evt == "REDIRECTED":
                     details = f"!!! BACKUP ACTIVATED !!! -> {e['next_hop']}"
                elif evt == "RESENT":
                     details = "!!! RETRANSMISSION !!!"
                
                f.write(f"  [{t}] {node}: {evt} {details}\n")
                
            if not is_delivered and not has_loss:
                # Infer loss location
                last_event = events[-1]
                f.write(f"  --> TRACE ENDED: Last seen at {last_event['node_id']} ({last_event['event_type']})\n")
                if last_event['event_type'] == 'FORWARDED':
                    f.write(f"      Potential Link Loss: {last_event['node_id']} -> {last_event['next_hop']}\n")
                loss_count += 1
            
            f.write("\n")
            
        f.write("-" * 30 + "\n")
        f.write("Summary Statistics:\n")
        f.write(f"Total Traced: {len(grouped)}\n")
        f.write(f"Delivered: {success_count}\n")
        f.write(f"Losses (inferred + simulated): {len(grouped) - success_count}\n")
        f.write(f"Retransmissions: {retransmit_count}\n")
        f.write(f"Backup Redirects: {redirect_count}\n")

def generate_network_graph(traffic_df, mix_df, output_path):
    """
    Generates a network graph visualizing traffic flow, loss, and redirects.
    """
    if traffic_df.empty and mix_df.empty:
        return

    # Combine events
    df = pd.concat([traffic_df, mix_df], ignore_index=True)
    
    # 1. Build Edge Data (Counts)
    # Forwarding: Node -> NextHop
    # Redirect: Node -> NextHop (Colored differently)
    # Loss: Node -> NextHop (Inferred?) - Harder to confirm specific link for loss without exact next hop known at drop time.
    # But we can assume if 'FORWARDED' -> next_hop and no 'RECEIVED' at next_hop, it's a loss on that link.
    
    G = nx.DiGraph()
    
    # Track edges: (u, v) -> {'attempts': 0, 'success': 0, 'redirects': 0}
    edges = defaultdict(lambda: {'attempts': 0, 'success': 0, 'redirects': 0})
    
    # We need to link FORWARDED events to subsequent RECEIVED events for the SAME packet.
    # Group by packet_id
    grouped = df.groupby('packet_id')
    
    for pid, group in grouped:
        if pd.isna(pid) or pid == "packet_id": continue
        events = group.sort_values('timestamp').to_dict('records')
        
        for i, e in enumerate(events):
            src_node = str(e['node_id'])
            
            if e['event_type'] == 'FORWARDED' or e['event_type'] == 'CREATED' or e['event_type'] == 'REDIRECTED' or e['event_type'] == 'SENT':
                target = e.get('next_hop')
                
                # Handle direct sends if PREV hop is missing?
                # But here we focus on FROM node -> TO node.
                # If SENT, next_hop is usually First Hop.
                
                if not target or pd.isna(target):
                    continue
                    
                target = str(target)
                edge_key = (src_node, target)
                
                edges[edge_key]['attempts'] += 1
                
                if e['event_type'] == 'REDIRECTED':
                    edges[edge_key]['redirects'] += 1
                
                # Check for success (RECEIVED at target)
                # Look ahead in events
                found_recv = False
                for j in range(i+1, len(events)):
                    next_e = events[j]
                    if str(next_e['node_id']) == target and \
                       (next_e['event_type'] == 'RECEIVED' or next_e['event_type'] == 'RECEIVED FINAL DELIVERY'):
                        found_recv = True
                        break
                
                if found_recv:
                    edges[edge_key]['success'] += 1
                    
    # 2. Construct Graph
    for (u, v), stats in edges.items():
        if u == 'nan' or v == 'nan' or u == 'None' or v == 'None': continue
        
        success_rate = stats['success'] / stats['attempts'] if stats['attempts'] > 0 else 0
        loss_rate = 1.0 - success_rate
        
        # Color: Green -> Red based on loss
        # Orange for Redirects
        
        color = 'black' # default
        if stats['redirects'] > 0:
            color = 'orange'
        elif loss_rate > 0.0:
            if loss_rate > 0.2: color = 'red'
            elif loss_rate > 0.05: color = '#CC9900' # Gold (Moderate Loss)
            else: color = 'green'
        else:
            color = 'green'
            
        width = 1.0 + math.log(stats['attempts'] + 1) * 0.5
        
        G.add_edge(u, v, weight=stats['attempts'], color=color, 
                   label=f"{stats['attempts']} (L:{loss_rate:.1%})",
                   penwidth=width)

    # 3. Draw
    if len(G.nodes) == 0: return

    plt.figure(figsize=(12, 12))
    
    # Layout - Layered if possible
    # Detect layers by name heuristic
    # c* -> Layer 0
    # p* -> Layer 1
    # e* -> Layer 2
    # i* -> Layer 3
    # x* -> Layer 4
    # (recipients also c*, handled by layer 0 or 5?)
    
    layers = {}
    for node in G.nodes():
        if node.startswith('c'): layers[node] = 0
        elif node.startswith('p'): layers[node] = 1
        elif node.startswith('e'): layers[node] = 2
        elif node.startswith('i'): layers[node] = 3
        elif node.startswith('x'): layers[node] = 4
        else: layers[node] = 5
        
    # Organize into shells
    shells = [[], [], [], [], [], []]
    for node, layer in layers.items():
        if layer < len(shells):
            shells[layer].append(node)
            
    # Remove empty shells
    shells = [s for s in shells if s]
    
    try:
        pos = nx.shell_layout(G, nlist=shells)
    except:
        pos = nx.spring_layout(G)
        
    edges = G.edges(data=True)
    colors = [d['color'] for u, v, d in edges]
    widths = [d.get('penwidth', 1) for u, v, d in edges]
    
    # Nodes
    nx.draw_networkx_nodes(G, pos, node_color='lightblue', node_size=500, alpha=0.9)
    # Edges
    nx.draw_networkx_edges(G, pos, edge_color=colors, width=widths, arrowstyle='->', arrowsize=15, connectionstyle='arc3,rad=0.1')
    # Labels
    nx.draw_networkx_labels(G, pos, font_size=8, font_family='sans-serif')
    
    # Edge Labels (only for heavy traffic or high loss to avoid clutter)
    # edge_labels = { (u,v): d['label'] for u,v,d in edges if d['weight'] > 5 }
    # nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=6)
    
    plt.title("Network Traffic Flow & Anomalies (Red=Loss, Orange=Redirect)")
    plt.axis('off')
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

# --- Original Analysis Functions (Kept for compatibility/metrics) ---

def calculate_metrics(df, config=None):
    """
    Calculates metrics including:
    - Packet Loss Rate (Network Level)
    - Message Delivery Rate (Application Level - Heuristic Grouping)
    - Latency statistics
    - Fault Tolerance counts (Retransmissions, Redirects)
    """
    if df.empty:
        return None

    # 1. Network Level Metrics (Raw Packets)
    # Sent: CREATED events (Source Intent)
    sent_df = df[df['event_type'] == 'CREATED'].drop_duplicates(subset=['packet_id'])
    # Received: RECEIVED events at Clients (Final Delivery)
    # Using 'RECEIVED FINAL DELIVERY' if available (added in Trace logic?) or just RECEIVED at Client
    # Trace logic relies on raw logs. Let's see what parse_logs does.
    # Assuming 'RECEIVED' at client is final.
    recv_df = df[(df['event_type'] == 'RECEIVED') & (df['node_id'].str.startswith(('c', 'Client')))].drop_duplicates(subset=['packet_id'])
    
    total_sent = len(sent_df)
    total_received = len(recv_df)
    
    # Packet Loss
    loss_rate = 1.0 - (total_received / total_sent) if total_sent > 0 else 0.0

    # Latency (Raw)
    merged = pd.merge(sent_df[['packet_id', 'timestamp']], recv_df[['packet_id', 'timestamp']], on='packet_id', suffixes=('_sent', '_recv'))
    merged['latency'] = merged['timestamp_recv'] - merged['timestamp_sent']
    
    packet_metrics = {
        'total_sent': total_sent,
        'total_received': total_received,
        'loss_rate': loss_rate,
        'avg_latency': merged['latency'].mean() if not merged.empty else 0,
        'max_latency': merged['latency'].max() if not merged.empty else 0,
        'min_latency': merged['latency'].min() if not merged.empty else 0,
    }

    # 2. Application Level Metrics (Messages)
    # If message_id is available, use it for exact counting
    if 'message_id' in sent_df.columns and not sent_df['message_id'].isna().all():
        # Precise Counting
        unique_msgs_sent = sent_df['message_id'].nunique()
        # Delivered? Check if ANY packet with that message_id arrived
        # Received DF needs message_id too. Merging?
        # Received events usually have the same fields as Created if parsed correctly.
        # Check recv_df
        if 'message_id' in recv_df.columns:
            delivered_msg_ids = set(recv_df['message_id'])
            unique_msgs_delivered = len(set(sent_df['message_id']).intersection(delivered_msg_ids))
        else:
            # Fallback: Link by packet_id
            # Mapping packet_id -> message_id from sent_df
            pid_to_mid = pd.Series(sent_df.message_id.values, index=sent_df.packet_id).to_dict()
            delivered_pids = set(recv_df['packet_id'])
            delivered_mids = set()
            for pid in delivered_pids:
                if pid in pid_to_mid:
                    delivered_mids.add(pid_to_mid[pid])
            unique_msgs_delivered = len(delivered_mids)

        unique_messages = unique_msgs_sent
        messages_delivered = unique_msgs_delivered
            
    else:
        # Heuristic: Group SENT/CREATED packets from same Src->Dst within small time window (e.g. 100ms)
        # Use sent_df which has CREATED events
        train = sent_df.sort_values(['src', 'dst', 'timestamp'])
        
        unique_messages = 0
        messages_delivered = 0
        
        if len(train) > 0:
            values = train.to_dict('records')
            current_group = [values[0]]
            
            # Helper set of delivered packet IDs
            delivered_ids = set(recv_df['packet_id'])
            
            for i in range(1, len(values)):
                prev = current_group[-1]
                curr = values[i]
                
                # Condition: Same Src, Same Dst, Time Diff < 0.1s
                is_same_msg = (curr['src'] == prev['src']) and \
                              (curr['dst'] == prev['dst']) and \
                              (curr['timestamp'] - prev['timestamp'] < 0.1)
                              
                if is_same_msg:
                    current_group.append(curr)
                else:
                    # Process finished group
                    unique_messages += 1
                    if any(p['packet_id'] in delivered_ids for p in current_group):
                        messages_delivered += 1
                    current_group = [curr]
            
            # Last group
            unique_messages += 1
            if any(p['packet_id'] in delivered_ids for p in current_group):
                messages_delivered += 1

    msg_loss_rate = 1.0 - (messages_delivered / unique_messages) if unique_messages > 0 else 0.0
        
    packet_metrics.update({
        'msgs_sent': unique_messages,
        'msgs_received': messages_delivered,
        'msg_loss_rate': msg_loss_rate
    })
    
    # 3. Fault Tolerance Counts
    packet_metrics['redirect_count'] = len(df[df['event_type'] == 'REDIRECTED'])
    
    if 'flags' in df.columns:
        resent_mask = df['flags'].astype(str).str.contains('retransmission', case=False, na=False)
        packet_metrics['retrans_count'] = resent_mask.sum()
    else:
        packet_metrics['retrans_count'] = 0

    return packet_metrics

def analyze_single_run(log_dir):
    print(f"\nAnalyzing logs in: {log_dir}")
    output_dir = os.path.join(log_dir, "analysis_results")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    traffic_df, mix_df = parse_logs(log_dir)
    
    if traffic_df.empty:
        print("No traffic data found.")
        return

    # 1. Trace Report (The new feature)
    trace_path = os.path.join(output_dir, "packet_trace.txt")
    generate_trace_report(traffic_df, mix_df, trace_path)
    print(f"Trace report generated at {trace_path}")

    # 2. Network Graph (The requested visualization)
    graph_path = os.path.join(output_dir, "traffic_graph.png")
    try:
        generate_network_graph(traffic_df, mix_df, graph_path)
        print(f"Graph generated at {graph_path}")
    except Exception as e:
        print(f"Graph generation failed: {e}")

    # 3. Standard Metrics
    # Load config to check for parallel_paths k
    config_path = os.path.join(log_dir, "config.json")
    config = {}
    if os.path.exists(config_path):
        import json
        try:
             with open(config_path, 'r') as f:
                config = json.load(f)
        except: pass
        
    metrics = calculate_metrics(traffic_df, config)
    
    if metrics:
        print("-" * 30)
        print(f"Packets Sent: {metrics['total_sent']}")
        print(f"Packets Arrived: {metrics['total_received']}")
        print(f"Loss Rate: {metrics['loss_rate']:.2%}")
        print(f"Messages Sent: {metrics['msgs_sent']}")
        print(f"Messages Arrived: {metrics['msgs_received']}")
        print(f"Msg Loss Rate: {metrics['msg_loss_rate']:.2%}")
        
        with open(os.path.join(output_dir, "analysis_summary.txt"), "w") as f:
            f.write("Analysis Metrics:\n")
            f.write(f"packets sent: {metrics['total_sent']}\n")
            f.write(f"packets arrived: {metrics['total_received']}\n")
            f.write(f"packet loss: {metrics['total_sent'] - metrics['total_received']}\n")
            f.write(f"loss rate: {metrics['loss_rate']:.2%}\n\n")
            
            f.write(f"individual packets sent: {metrics['msgs_sent']}\n")
            f.write(f"individual packets arrived: {metrics['msgs_received']}\n")
            f.write(f"individual packet loss: {metrics['msgs_sent'] - metrics['msgs_received']}\n")
            f.write(f"individual loss rate: {metrics['msg_loss_rate']:.2%}\n\n")
            
            f.write(f"highest latency: {metrics['max_latency']:.4f}s\n")
            f.write(f"lowest latency: {metrics['min_latency']:.4f}s\n")
            f.write(f"average latency: {metrics['avg_latency']:.4f}s\n\n")
            
            f.write("Mechanisms:\n")
            f.write(f"packets retransmitted: {metrics.get('retrans_count', 0)}\n")
            f.write(f"backup events: {metrics.get('redirect_count', 0)}\n")
            
            # Config info
            parallel = 1
            if config.get('features', {}).get('parallel_paths', False):
                # How to guess k if not in config? Assuming 2 or 3.
                # Or calculate avg packets per msg?
                avg_copies = metrics['total_sent'] / metrics['msgs_sent'] if metrics['msgs_sent'] > 0 else 0
                f.write(f"parallel k (inferred): {avg_copies:.2f}\n")
            else:
                f.write("parallel k: 1 (disabled)\n")
                
            f.write(f"paths reestablished: N/A\n") # Placeholder as requested if not tracking

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="Path to logs")
    args = parser.parse_args()
    
    target = args.path
    
    # Logic to handle single run or directory of runs
    if os.path.isdir(target):
        # Check if it's a single run (has csvs)
        if glob.glob(os.path.join(target, "*_traffic.csv")):
            analyze_single_run(target)
        else:
            # Recursive / Batch
            print(f"Scanning {target}...")
            for entry in os.scandir(target):
                if entry.is_dir() and "Testrun" in entry.name:
                    analyze_single_run(entry.path)

if __name__ == "__main__":
    main()
