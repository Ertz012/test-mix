import argparse
import sys
import os
import json
import logging
import consolidate_traffic_logs
import clean_traffic_analysis
import run_traffic_analysis_relaxed

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AnalyzeAll")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(BASE_DIR, "logs") # Default to logs, can be overridden

def main():
    parser = argparse.ArgumentParser(description="Analyze all test runs.")
    parser.add_argument("--logs-dir", help="Directory containing test runs", default=RESULTS_DIR)
    parser.add_argument("--relaxed", help="Enable relaxed traffic analysis (run_traffic_analysis_relaxed.py)", action="store_true")
    args = parser.parse_args()

    if not os.path.exists(args.logs_dir):
        logger.error(f"{args.logs_dir} does not exist.")
        return

    subdirs = sorted([d for d in os.listdir(args.logs_dir) if os.path.isdir(os.path.join(args.logs_dir, d)) and d.startswith("Testrun")])
    
    for exp_name in subdirs:
        exp_path = os.path.join(args.logs_dir, exp_name)
        logger.info(f"Analyzing {exp_name}...")
        
        # 1. Consolidate Logs
        try:
            logger.info("  Consolidating logs...")
            consolidate_traffic_logs.process_logs(exp_path)
        except Exception as e:
            logger.error(f"  Consolidation failed: {e}")
            continue

        # 2. Get Configuration (mu)
        mu = 0.5 # Default
        config_path = os.path.join(exp_path, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    mu = config.get('mix_settings', {}).get('mu', 0.5)
            except Exception as e:
                logger.warning(f"  Could not read config.json: {e}")
        
        # 3. Clean Traffic Analysis (Exact)
        try:
            logger.info(f"  Running exact traffic analysis (mu={mu})...")
            in_file = os.path.join(exp_path, 'system_in.csv')
            out_file = os.path.join(exp_path, 'system_out.csv')
            
            if os.path.exists(in_file) and os.path.exists(out_file):
                # Auto-detect target and run
                ranking, detected_target = clean_traffic_analysis.run_traffic_analysis(in_file, out_file, None, mu)
                
                if detected_target:
                   # Save ranking
                   ranking_file = os.path.join(exp_path, 'traffic_analysis_ranking.txt')
                   with open(ranking_file, 'w') as f:
                       f.write(f"Traffic Analysis Result for Target: {detected_target}\n")
                       f.write(f"Mu: {mu}\n\n")
                       if ranking is not None:
                           f.write(ranking.to_string())
                   
                   # Generate and save plot
                   clean_traffic_analysis.analyze_and_plot(in_file, out_file, detected_target, mu, output_dir=exp_path)
                else:
                    logger.warning("  Could not detect target for traffic analysis.")
            else:
                 logger.warning("  system_in.csv or system_out.csv missing. Skipping exact analysis.")
        except Exception as e:
            logger.error(f"  Exact traffic analysis failed: {e}")

        # 4. Relaxed Traffic Analysis (Optional)
        if args.relaxed:
            try:
                logger.info("  Running relaxed traffic analysis...")
                run_traffic_analysis_relaxed.process_single_run(exp_path)
            except Exception as e:
                 logger.error(f"  Relaxed traffic analysis failed: {e}")

        logger.info(f"Analysis of {exp_name} complete.\n")

if __name__ == "__main__":
    main()
