
import os
import shutil
import glob

LOGS_ROOT = r"d:\Uni Hamburg\Module\MASTER\test-mix\logs"

def main():
    print(f"Scanning {LOGS_ROOT}...")
    
    # Iterate over all Testrun directories
    run_dirs = glob.glob(os.path.join(LOGS_ROOT, "Testrun_*"))
    
    for run_dir in run_dirs:
        if not os.path.isdir(run_dir):
            continue
            
        print(f"Processing {os.path.basename(run_dir)}...")
        
        # Create analysis_results subfolder
        results_dir = os.path.join(run_dir, "analysis_results")
        os.makedirs(results_dir, exist_ok=True)
        
        # Find all strict_link_trace files (csv and json)
        files = glob.glob(os.path.join(run_dir, "strict_link_trace_*"))
        
        moved_count = 0
        for file_path in files:
            file_name = os.path.basename(file_path)
            dest_path = os.path.join(results_dir, file_name)
            
            try:
                shutil.move(file_path, dest_path)
                moved_count += 1
            except Exception as e:
                print(f"  Error moving {file_name}: {e}")
                
        if moved_count > 0:
            print(f"  Moved {moved_count} files to analysis_results/")
        else:
            print(f"  No files to move.")

if __name__ == "__main__":
    main()
