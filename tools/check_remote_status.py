
import paramiko
import sys

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
    REPO_PATH = f"/home/{USER}/test-mix"
    
    try:
        client = create_ssh_client(HOST, PORT, USER, PASS)
        
        # 1. Check Process
        print("--- Process Status ---")
        # Grep for run_series.py to ignore the grep command itself
        stdin, stdout, stderr = client.exec_command("ps aux | grep run_series.py | grep -v grep")
        process_info = stdout.read().decode().strip()
        
        if process_info:
            print("RUNNING:")
            print(process_info)
        else:
            print("NOT RUNNING (Process not found in ps aux)")
            
        # 2. Check Log Tail
        print("\n--- Log Tail (experiment_output.log) ---")
        stdin, stdout, stderr = client.exec_command(f"tail -n 10 {REPO_PATH}/experiment_output.log")
        log_tail = stdout.read().decode().strip()
        print(log_tail)
        
        client.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
