import os
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AnalyzeAll")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
ANALYSIS_SCRIPT = os.path.join(BASE_DIR, "analysis", "analyze_results.py")

def main():
    if not os.path.exists(RESULTS_DIR):
        logger.error(f"{RESULTS_DIR} does not exist.")
        return

    subdirs = sorted([d for d in os.listdir(RESULTS_DIR) if os.path.isdir(os.path.join(RESULTS_DIR, d))])
    
    for exp_name in subdirs:
        exp_path = os.path.join(RESULTS_DIR, exp_name)
        logger.info(f"Analyzing {exp_name}...")
        try:
            subprocess.check_call(["python3", ANALYSIS_SCRIPT, exp_path])
        except subprocess.CalledProcessError as e:
            logger.error(f"Analysis failed for {exp_name}: {e}")

if __name__ == "__main__":
    main()
