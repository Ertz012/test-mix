import os
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import glob
import numpy as np
import networkx as nx
from collections import defaultdict
import math
import json

def parse_logs(log_dir):
    """
    Parses sender, receiver, and mix node logs.
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
    # Look for any traffic file not starting with c/s/r
    all_traffic_files = glob.glob(os.path.join(log_dir, "*_traffic.csv"))
    for f in all_traffic_files:
        filename = os.path.basename(f)
        if filename.startswith('c') or filename.startswith('s') or filename.startswith('r'):
            continue 
        
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

    all_events = pd.concat([traffic_df, mix_df], ignore_index=True)
    cols = ['timestamp', 'packet_id', 'event_type', 'node_id', 'src', 'dst', 'next_hop', 'size']
    for c in cols:
        if c not in all_events.columns:
            all_events[c] = None
    all_events = all_events[cols]
    all_events = all_events.sort_values('timestamp')

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
            
            is_delivered = any(e['event_type'] == 'RECEIVED' and str(e['node_id']).startswith('c') for e in events)
            has_loss = any(e['event_type'] == 'DROPPED_SIM' for e in events)
            has_retransmit = any(e['event_type'] == 'RESENT' for e in events)
            has_redirect = any(e['event_type'] == 'REDIRECTED' for e in events)
            
            if is_delivered: success_count += 1
            if has_retransmit: retransmit_count += 1
            if has_redirect: redirect_count += 1
            
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
                last_event = events[-1]
                f.write(f"  --> TRACE ENDED: Last seen at {last_event['node_id']} ({last_event['event_type']})\n")
                loss_count += 1
            
            f.write("\n")

def generate_network_graph(traffic_df, mix_df, output_path):
    if traffic_df.empty and mix_df.empty: return
    df = pd.concat([traffic_df, mix_df], ignore_index=True)
    G = nx.DiGraph()
    edges = defaultdict(lambda: {'attempts': 0, 'success': 0, 'redirects': 0})
    grouped = df.groupby('packet_id')
    
    for pid, group in grouped:
        if pd.isna(pid) or pid == "packet_id": continue
        events = group.sort_values('timestamp').to_dict('records')
        for i, e in enumerate(events):
            src_node = str(e['node_id'])
            if e['event_type'] in ['FORWARDED', 'CREATED', 'REDIRECTED', 'SENT']:
                target = e.get('next_hop')
                if not target or pd.isna(target): continue
                target = str(target)
                edge_key = (src_node, target)
                edges[edge_key]['attempts'] += 1
                if e['event_type'] == 'REDIRECTED': edges[edge_key]['redirects'] += 1
                found_recv = False
                for j in range(i+1, len(events)):
                    if str(events[j]['node_id']) == target and events[j]['event_type'].startswith('RECEIVED'):
                        found_recv = True; break
                if found_recv: edges[edge_key]['success'] += 1

    for (u, v), stats in edges.items():
        if u == 'nan' or v == 'nan': continue
        sr = stats['success'] / stats['attempts'] if stats['attempts'] > 0 else 0
        lr = 1.0 - sr
        color = 'green'
        if stats['redirects'] > 0: color = 'orange'
        elif lr > 0.2: color = 'red'
        elif lr > 0.05: color = '#CC9900'
        
        width = 1.0 + math.log(stats['attempts'] + 1) * 0.5
        G.add_edge(u, v, weight=stats['attempts'], color=color, penwidth=width)

    if len(G.nodes) == 0: return
    plt.figure(figsize=(12, 12))
    pos = nx.spring_layout(G)
    nx.draw_networkx_nodes(G, pos, node_color='lightblue', node_size=500, alpha=0.9)
    colors = [d['color'] for u, v, d in G.edges(data=True)]
    widths = [d.get('penwidth', 1) for u, v, d in G.edges(data=True)]
    nx.draw_networkx_edges(G, pos, edge_color=colors, width=widths, arrowstyle='->', arrowsize=15)
    nx.draw_networkx_labels(G, pos, font_size=8)
    plt.axis('off')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

def calculate_metrics(df, config=None):
    if df.empty: return None
    analysis_df = df.copy()
    if 'flags' in df.columns:
        ack_mask = df['flags'].astype(str).str.contains('type=ACK', case=False, na=False)
        analysis_df = df[~ack_mask]

    sent_df = analysis_df[analysis_df['event_type'] == 'CREATED'].drop_duplicates(subset=['packet_id'])
    recv_df = analysis_df[(analysis_df['event_type'] == 'RECEIVED') & (analysis_df['node_id'].str.startswith(('c', 'Client')))].drop_duplicates(subset=['packet_id'])
    
    total_sent = len(sent_df)
    total_received = len(recv_df)
    loss_rate = 1.0 - (total_received / total_sent) if total_sent > 0 else 0.0

    merged = pd.merge(sent_df[['packet_id', 'timestamp']], recv_df[['packet_id', 'timestamp']], on='packet_id', suffixes=('_sent', '_recv'))
    merged['latency'] = merged['timestamp_recv'] - merged['timestamp_sent']
    
    metrics = {
        'total_sent': total_sent,
        'total_received': total_received,
        'loss_rate': loss_rate,
        'avg_latency': merged['latency'].mean() if not merged.empty else 0,
        'max_latency': merged['latency'].max() if not merged.empty else 0,
        'min_latency': merged['latency'].min() if not merged.empty else 0,
        'retrans_count': 0,
        'redirect_count': len(df[df['event_type'] == 'REDIRECTED'])
    }
    
    if 'flags' in df.columns:
         metrics['retrans_count'] = df['flags'].astype(str).str.count('retransmission').sum()

    return metrics

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("log_dir", help="Path to log directory")
    args = parser.parse_args()
    log_dir = args.log_dir
    
    output_dir = os.path.join(log_dir, "analysis_results")
    if not os.path.exists(output_dir): os.makedirs(output_dir)
    
    print(f"Parsing Logs in {log_dir}...")
    traffic_df, mix_df = parse_logs(log_dir)
    
    if traffic_df.empty:
        print("No traffic logs found.")
        return
        
    print("Calculating General Metrics...")
    metrics = calculate_metrics(traffic_df)
    
    # Save Metrics to JSON
    with open(os.path.join(output_dir, "general_metrics.json"), 'w') as f:
        json.dump(metrics, f, indent=4)
        
    print("Generating Trace Report...")
    generate_trace_report(traffic_df, mix_df, os.path.join(output_dir, "packet_trace.txt"))
    
    print("Generating Network Graph...")
    try:
        generate_network_graph(traffic_df, mix_df, os.path.join(output_dir, "traffic_graph.png"))
    except Exception as e:
        print(f"Graph error: {e}")

    print("General Analysis Complete.")

if __name__ == "__main__":
    main()
