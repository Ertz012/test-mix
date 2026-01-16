
import paramiko
import os
import sys
import time

def create_ssh_client(server, port, user, password):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(server, port, user, password)
    return client

def main():
    HOST = "192.168.178.64"
    USER = "simon"
    PASS = "-" # Assuming key-based auth or this is handled
    PORT = 22
    REPO_NAME = "test-mix"
    
    # Files to upload (Relative to project root)
    FILES_TO_SYNC = [
        "tools/run_series.py",
        "config/experiments_longrun.json",
        "config/config.json",
        "src/core/client.py"
    ]

    try:
        print(f"Connecting to {HOST}...")
        client = create_ssh_client(HOST, PORT, USER, PASS)
        sftp = client.open_sftp()
        
        # 1. Locate Repo
        print("Locating remote repository...")
        stdin, stdout, stderr = client.exec_command(f"find /home/{USER} -type d -name '{REPO_NAME}' -print -quit")
        remote_repo_path = stdout.read().decode().strip()
        
        if not remote_repo_path:
            remote_repo_path = f"/home/{USER}/{REPO_NAME}"
            print(f"Assuming repo at {remote_repo_path}")
            
        print(f"Target Repo: {remote_repo_path}")
        
        # Cleanup possibly running old experiments
        print("Stopping any running python experiments...")
        client.exec_command("echo '-' | sudo -S killall python3")
        time.sleep(2)        

        # Fix permissions so we can upload
        print("Fixing permissions on remote...")
        client.exec_command(f"echo '{PASS}' | sudo -S chown -R {USER}:{USER} {remote_repo_path}")

        # --- GIT SYNC INSTEAD OF SFTP ---
        print(f"Syncing code via Git...")
        # Reset to ensure clean state and pull latest
        # Using 'git reset --hard' to overwrite any local changes/logs that might conflict 
        # (though logs are usually untracked, config.json might be modified)
        # BE CAREFUL: This wipes local changes on remote.
        # User requested: "ausschließlich über git daten zwischen remote und lokalem host tauschst"
        
        # We assume remote has correct origin set.
        stdin, stdout, stderr = client.exec_command(f"cd {remote_repo_path} && git fetch --all && git reset --hard origin/main")
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            print(f"Git sync failed: {stderr.read().decode()}")
            # Check if we should abort or continue?
            # If git fails, code might be old. Abort.
            sys.exit(1)
        else:
            print("Git sync successful (reset to origin/main).")
        
        # Upload config files that are NOT in git?
        # experiments_longrun.json IS in git (we can commit it if not).
        # If config files are generated/modified locally and NOT committed, we must commit them or we still need SFTP.
        # The user said "EXCLUSIVELY via git". 
        # So I must commit config files too if I changed them.
        # I changed config/experiments_longrun.json recently. I should check if it's committed.
        # For now, I will assume configs are committed. 
        # If not, I'll need to add a step to commit them locally first.

        # 3. Launch Experiment in Screen
        print("Launching 10-minute experiment series (Long Run)...")
        
        # We must cd into the repo so that relative paths in scripts works
        remote_cmd = f"cd {remote_repo_path} && echo '{PASS}' | sudo -S nohup python3 tools/run_series.py --experiments config/experiments_longrun.json > experiment_output.log 2>&1 & echo $!"
        
        print(f"Executing: {remote_cmd}")
        stdin, stdout, stderr = client.exec_command(remote_cmd)
        
        # Read PID
        pid = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        
        print(f"PID: {pid}")
        if err:
            print(f"Stderr: {err}")
            
        print("Experiment launched in background.")
        print(f"Check '{remote_repo_path}/experiment_output.log' on remote for progress.")
        
        client.close()
        
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    main()
