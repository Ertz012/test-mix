import logging
import os
import datetime
import time

class ExperimentLogger:
    _instance = None
    
    def __init__(self, log_dir="logs", hostname="unknown"):
        self.log_dir = log_dir
        self.hostname = hostname
        self.run_dir = self._get_run_dir()
        self.logger = self._setup_logger()
        self.traffic_logger = self._setup_traffic_logger()

    def _get_run_dir(self):
        # In a real distributed run, we might want to pass the timestamp 
        # as an env var so all nodes log to the same timestamped folder name.
        # For now, we'll try to discover it or create one.
        # Ideally, the orchestration script sets an env var "TESTRUN_ID"
        run_id = os.environ.get("TESTRUN_ID", f"Testrun_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
        path = os.path.join(self.log_dir, run_id)
        os.makedirs(path, exist_ok=True)
        return path

    def _setup_logger(self):
        logger = logging.getLogger(f"Node_{self.hostname}")
        logger.setLevel(logging.INFO)
        
        # File handler
        fh = logging.FileHandler(os.path.join(self.run_dir, f"{self.hostname}.log"))
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
        # Stream handler (optional, maybe noisy for mininet)
        # sh = logging.StreamHandler()
        # sh.setFormatter(formatter)
        # logger.addHandler(sh)
        
        return logger

    def _setup_traffic_logger(self):
        # CSV Logger for traffic analysis
        logger = logging.getLogger(f"Traffic_{self.hostname}")
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler(os.path.join(self.run_dir, f"{self.hostname}_traffic.csv"))
        # Header: timestamp, event_type, packet_id, src, dst, size, metadata
        fh.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(fh)
        logger.propagate = False
        
        # Write header if new file
        if os.stat(os.path.join(self.run_dir, f"{self.hostname}_traffic.csv")).st_size == 0:
            logger.info("timestamp,event_type,packet_id,src,dst,size,flags")
            
        return logger

    def log(self, message, level="INFO"):
        if level == "INFO":
            self.logger.info(message)
        elif level == "ERROR":
            self.logger.error(message)
        elif level == "DEBUG":
            self.logger.debug(message)

    def log_traffic(self, event_type, packet):
        # event_type: SENT, RECEIVED, FORWARDED, DROPPED
        flags_str = ";".join([f"{k}={v}" for k, v in packet.flags.items()])
        msg = f"{time.time()},{event_type},{packet.packet_id},?,?,{len(packet.payload)},{flags_str}"
        self.traffic_logger.info(msg)

# Singleton helper
def get_logger(hostname, log_dir="logs"):
    return ExperimentLogger(log_dir, hostname)
