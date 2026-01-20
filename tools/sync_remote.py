
import paramiko
import os
import sys
from stat import S_ISDIR

def create_ssh_client(server, port, user, password):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(server, port, user, password)
    return client

def sftp_walk(sftp, remote_path):
    """
    Recursively list files in a remote directory.
    Yields (file_path, is_directory)
    """
    path = remote_path
    files = []
    
    try:
        # Check if it is a directory
        mode = sftp.stat(path).st_mode
        if not S_ISDIR(mode):
            yield path, False
            return

        for entry in sftp.listdir_attr(path):
            mode = entry.st_mode
            filename = entry.filename
            remote_file_path = os.path.join(path, filename).replace('\\', '/')
            
            if S_ISDIR(mode):
                yield remote_file_path, True
                yield from sftp_walk(sftp, remote_file_path)
            else:
                yield remote_file_path, False
                
    except IOError as e:
        print(f"Error accessing {path}: {e}")

def download_dir(sftp, remote_dir, local_dir):
    """
    Downloads a remote directory to a local directory.
    """
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)
        
    print(f"Syncing logs from {remote_dir} to {local_dir}...")
    
    # We need to explicitly walk because standard sftp doesn't have mget/recursive get
    # But sftp_walk might be slow for many files.
    # Let's try a simpler approach: list the remote logs directory, find new folders.
    
    # Assuming logs structure is logs/Testrun_...
    try:
        sftp.chdir(remote_dir)
        remote_items = sftp.listdir()
    except IOError:
        print(f"Remote directory {remote_dir} does not exist.")
        return

    for item in remote_items:
         # simple heuristic: only download directories starting with Testrun
        remote_item_path = remote_dir + "/" + item
        local_item_path = os.path.join(local_dir, item)
        
        try:
             mode = sftp.stat(remote_item_path).st_mode
             if S_ISDIR(mode):
                 if "Testrun" in item:
                     if not os.path.exists(local_item_path):
                         print(f"Downloading new test run: {item}")
                         # Use get_r (recursive get) implementation or similar
                         # Since paramiko doesn't have a built-in recursive get, we'll do a simple walk for this folder
                         _download_recursive(sftp, remote_item_path, local_item_path)
                     else:
                         print(f"Skipping existing test run: {item}")
        except Exception as e:
            print(f"Error processing {item}: {e}")

def _download_recursive(sftp, remote_dir, local_dir):
    os.makedirs(local_dir, exist_ok=True)
    for entry in sftp.listdir_attr(remote_dir):
        remote_path = remote_dir + "/" + entry.filename
        local_path = os.path.join(local_dir, entry.filename)
        if S_ISDIR(entry.st_mode):
            _download_recursive(sftp, remote_path, local_path)
        else:
            try:
                sftp.get(remote_path, local_path)
            except Exception as e:
                 print(f"Failed to download {remote_path}: {e}")

def main():
    HOST = "192.168.178.64"
    USER = "simon"
    PASS = "-"
    PORT = 22
    
    # Attempt to find the correct repo path.
    # Common locations + user home
    REPO_NAME = "test-mix"
    
    try:
        print(f"Connecting to {HOST}...")
        client = create_ssh_client(HOST, PORT, USER, PASS)
        sftp = client.open_sftp()
        
        # 1. Locate Repo
        print("Locating remote repository...")
        stdin, stdout, stderr = client.exec_command(f"find /home/{USER} -type d -name '{REPO_NAME}' -print -quit")
        remote_repo_path = stdout.read().decode().strip()
        
        if not remote_repo_path:
            print(f"Could not find repository '{REPO_NAME}' on remote.")
            # Fallback check
            stdin, stdout, stderr = client.exec_command(f"ls -d /home/{USER}/{REPO_NAME}")
            if stdout.channel.recv_exit_status() == 0:
                 remote_repo_path = f"/home/{USER}/{REPO_NAME}"
            else:
                 sys.exit(1)
        
        print(f"Found repository at: {remote_repo_path}")
        
        # 2. Download logs
        remote_logs_path = f"{remote_repo_path}/logs"
        local_logs_path = os.path.join(os.getcwd(), "logs")
        
        # download_dir(sftp, remote_logs_path, local_logs_path) # Disabled: User requested Git Only sync
        
        # 3. Clean up and Sync Git
        print("Fixing permissions and resetting remote repository state...")
        
        # We need to construct a command string that handles sudo with the password
        # and then runs the git commands.
        # Note: 'sudo -S' reads password from stdin.
        
        fix_perms_cmd = f"echo '{PASS}' | sudo -S chown -R {USER}:{USER} {remote_repo_path}"
        
        commands = [
            fix_perms_cmd,
            f"cd {remote_repo_path}",
            "git fetch origin",
            "git reset --hard origin/main",
            "git clean -fd" 
        ]
        
        # --- GIT SYNC FOR LOGS ---
        print("Syncing logs via Git (User Request)...")
        
        # Placeholder for run_id, you might want to generate this dynamically
        run_id = "latest_run" 
        REMOTE_REPO = remote_repo_path # Define REMOTE_REPO for clarity
        remote_log_path = "logs" # Relative path within the repo
        
        # 1. Trigger remote to add/commit/push logs
        # We create a temporary script or just run commands via SSH
        remote_cmds = [
            f"cd {REMOTE_REPO}",
            "git config user.name 'Remote Runner'",
            "git config user.email 'remote@mixnet'",
            f"find {remote_log_path} -type f -exec git add -f {{}} +", # Force add all files including ignored .log/.out
            f"git commit -m 'Logs: {run_id}'",
            "git push origin main"
        ]
        
        cmd_str = " && ".join(remote_cmds)
        stdin, stdout, stderr = client.exec_command(cmd_str)
        exit_status = stdout.channel.recv_exit_status()
        
        if exit_status != 0:
            print(f"Remote git push failed: {stderr.read().decode()}")
            print("Note: Ensure remote has SSH keys for git push.")
        else:
            print("Remote logs pushed to origin.")
            
            # 2. Pull locally
            print("Pulling logs locally...")
            # Assuming we are in the local repo root
            os.system("git pull origin main")
            print("Logs synced.")

        # We execute permissions fix separately to ensure it completes before we try git
        print(f"Executing permission fix...")
        stdin, stdout, stderr = client.exec_command(fix_perms_cmd)
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            print(f"Warning: chown failed. Stderr: {stderr.read().decode()}")
        
        # Now git commands for repo reset
        git_cmds = " && ".join(commands[1:])
        print(f"Executing: {git_cmds}")
        
        stdin, stdout, stderr = client.exec_command(git_cmds)
        exit_status = stdout.channel.recv_exit_status()
        
        if exit_status == 0:
            print("Remote repository successfully synced to origin/main.")
            print(stdout.read().decode())
        else:
            print("Error syncing remote repository:")
            print(stderr.read().decode())
            
        client.close()
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
