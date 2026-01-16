
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
    PASS = "-" 
    PORT = 22
    REPO_NAME = "test-mix"
    
    # Files to upload (Relative to project root)
    FILES_TO_SYNC = [
        "tools/run_series.py",
        "config/experiments_verify.json",
        "config/config.json",
        "src/core/client.py",
        "src/core/packet.py",
        "src/utils/logger.py",
        "src/modules/reliability.py"
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

        # 2. Upload Files
        print("Uploading updated files...")
        local_root = os.getcwd()
        
        for rel_path in FILES_TO_SYNC:
            local_path = os.path.join(local_root, rel_path)
            remote_path = f"{remote_repo_path}/{rel_path}".replace("\\", "/")
            
            if os.path.exists(local_path):
                print(f"  Uploading {rel_path} -> {remote_path}")
                try:
                    sftp.put(local_path, remote_path)
                except Exception as e:
                    print(f"  Failed to upload {rel_path}: {e}")
            else:
                print(f"  Warning: Local file not found: {local_path}")

        # 3. Launch Experiment in Verify Mode
        print("Launching VERIFICATION experiment series...")
        
        # We must cd into the repo so that relative paths in scripts works
        remote_cmd = f"cd {remote_repo_path} && echo '{PASS}' | sudo -S nohup python3 tools/run_series.py --experiments config/experiments_verify.json > experiment_output.log 2>&1 & echo $!"
        
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
