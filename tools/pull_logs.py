import paramiko
import os
import sys
from stat import S_ISDIR

def create_ssh_client(server, port, user, password=None):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(server, port, user, password)
    except paramiko.AuthenticationException:
        print(f"Authentication failed for {user}@{server}. Please check your SSH keys or password.")
        sys.exit(1)
    except Exception as e:
        print(f"Could not connect to {server}: {e}")
        sys.exit(1)
    return client

def get_remote_repo_path(client, user, repo_name):
    # Try to find the repo
    check_cmds = [
        f"find /home/{user} -type d -name '{repo_name}' -print -quit",
        f"ls -d /home/{user}/{repo_name}"
    ]
    
    for cmd in check_cmds:
        stdin, stdout, stderr = client.exec_command(cmd)
        path = stdout.read().decode().strip()
        if path:
            return path
            
    return None

def download_recursive(sftp, remote_dir, local_dir):
    """
    Recursively downloads a directory from remote to local.
    Skips files if they already exist and have the same size.
    """
    try:
        # Create local directory if it doesn't exist
        os.makedirs(local_dir, exist_ok=True)
        
        # List remote directory directory
        for entry in sftp.listdir_attr(remote_dir):
            remote_path = remote_dir + "/" + entry.filename
            local_path = os.path.join(local_dir, entry.filename)
            
            mode = entry.st_mode
            if S_ISDIR(mode):
                # Recurse
                download_recursive(sftp, remote_path, local_path)
            else:
                # Check if we need to download
                should_download = True
                if os.path.exists(local_path):
                    local_size = os.path.getsize(local_path)
                    remote_size = entry.st_size
                    if local_size == remote_size:
                        should_download = False
                        # print(f"Skipping {entry.filename} (already exists and same size)")

                if should_download:
                    print(f"Downloading {entry.filename} from {remote_dir}...")
                    try:
                        sftp.get(remote_path, local_path)
                    except Exception as e:
                        print(f"Failed to download {remote_path}: {e}")

    except Exception as e:
        print(f"Error accessing {remote_dir}: {e}")

def pull_logs_from_host(host, user="simon", repo_name="test-mix"):
    print(f"--- Connecting to {host} ---")
    client = create_ssh_client(host, 22, user)
    sftp = client.open_sftp()
    
    try:
        # Locate Repo
        print("Locating remote repository...")
        remote_repo_path = get_remote_repo_path(client, user, repo_name)
        
        if not remote_repo_path:
            print(f"Could not find repository '{repo_name}' on {host}. Skipping.")
            return

        print(f"Found repository at: {remote_repo_path}")
        
        remote_logs_path = f"{remote_repo_path}/logs"
        
        # Check if logs dir exists
        try:
            sftp.stat(remote_logs_path)
        except IOError:
            print(f"No 'logs' directory found at {remote_logs_path}. Skipping.")
            return

        # Prepare local logs directory
        # We append the host IP to the folder to avoid conflicts if needed, 
        # or we can merge. 
        # Strategy: Merge into local 'logs' folder. 
        # If files conflict (e.g. same experiment name), let's assume they are unique 
        # or that we want to unify them.
        # User request: "copy logs ... to my local system".
        # Let's mirror the structure: local_root/logs/Testrun_...
        
        local_logs_root = os.path.join(os.getcwd(), "logs")
        
        print(f"Syncing logs from {remote_logs_path} to {local_logs_root}...")
        download_recursive(sftp, remote_logs_path, local_logs_root)
        print(f"Done with {host}.")

    finally:
        sftp.close()
        client.close()

def main():
    hosts = ["192.168.178.64", "192.168.178.68"]
    user = "simon"
    repo_name = "test-mix"
    
    for host in hosts:
        pull_logs_from_host(host, user, repo_name)

if __name__ == "__main__":
    main()
