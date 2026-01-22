# Test-Mix System Documentation

## 1. Introduction
The **Test-Mix** system is a modular Mix-Net simulation environment built on top of **Mininet**. It is designed for academic research to study anonymity networks, traffic analysis, and routing strategies. The system allows researchers to deploy a realistic network topology, generate traffic, and analyze the behavior of various Mix-Net components in a controlled environment.

## 2. System Architecture

### 2.1. High-Level Overview
The system emulates a **Stratified Mix-Net** topology where traffic flows through distinct layers of nodes. The network is built using Mininet, which provides lightweight virtualization for each node.

**Data Flow:**
`Sender` -> `Entry Layer` -> `Intermediate Layer(s)` -> `Exit Layer` -> `Receiver`

### 2.2. Topology
The network topology is defined in `mininet/topology.py` class `StratifiedTopo`.
-   **Senders (`sN`)**: Nodes that generate traffic.
-   **Entry Nodes (`eN`)**: First hop for packets entering the Mix-Net.
-   **Mix/Intermediate Nodes (`iN`)**: Core mixing nodes that shuffle and forward packets.
-   **Exit Nodes (`xN`)**: Last hop before the destination.
-   **Receivers (`rN`)**: Destination nodes that collect metrics.

### 2.3. Packet Structure
Packets are JSON-serialized objects containing:
-   `id`: Unique UUID for the packet (preserved across retransmissions if using parallel paths).
-   `ts`: Timestamp of creation.
-   `dst`: Destination hostname.
-   `route`: List of hops (Source Routing).
-   `data`: Payload content.
-   `flags`: System metadata (e.g., `surb` for return addresses, `type: ACK` for acknowledgments).

## 3. Installation & Setup

### Prerequisites
-   **Linux Environment** (Virtual Machine or Native).
-   **Python 3.8+**.
-   **Mininet**: Must be installed and running (requires root privileges).

### Setup
1.  **Clone the Repository**:
    ```bash
    git clone <repository_url>
    cd test-mix
    ```

2.  **Dependencies**:
    Ensure standard Python libraries are available. Mininet comes with its own Python bindings.

## 4. Usage Guide

### 4.1. Configuration
The system is configured via `config/config.json`. Key parameters include:

-   **`mix_settings`**:
    -   `strategy`: Mixing strategy (e.g., `timed_pool`).
    -   `pool_size`: Number of packets to accumulate before flushing (for pool-based strategies).
    -   `timeout`: Max time to wait before flushing (for timed strategies).

-   **`traffic`**:
    -   `rate_packets_per_sec`: Rate at which senders generate messages.
    -   `duration_sec`: Duration of the traffic generation phase.

-   **`features`**:
    -   `parallel_paths`: Enable multipath routing (sending disjoint copies).
    -   `retransmission`: Enable end-to-end reliability via ACKs.
    -   `anonymous_return_addresses`: Use SURBs for reply paths.

### 4.2. Running an Experiment
To start the simulation, run the topology script with root privileges (required by Mininet):

```bash
sudo python3 mininet/topology.py
```

**What happens during execution:**
1.  Mininet creates the network topology (Hosts and Links).
2.  `run.py` is started on every host with the appropriate role (`sender`, `mix`, `receiver`).
3.  Logs are created in a new directory `logs/Testrun_<Timestamp>/`.
4.  Senders generate traffic for `duration_sec`.
5.  Wait for completion (Ctrl+C to stop manually if needed, though script stops network after interaction).

### 4.3. Logs and Output
-   **Location**: `logs/Testrun_YYYYMMDD_HHMMSS/`.
-   **Files**: One log file per node (e.g., `s1.out`, `m1.out`, `r1.out`).
-   **Analysis**: Logs contain structured events (`CREATED`, `RECEIVED`, `ACK_SENT`) that can be parsed for metrics like latency, throughput, and loss.

## 5. Component Reference

### `src/run.py`
The entry point for individual nodes. It loads configuration, determines the node's role based on hostname or arguments, and starts the appropriate agent class.

### `src/core/mix.py` (`MixNode`)
Implements the mixing logic.
-   Maintains a packet pool.
-   Flushes pool based on `strategy` (e.g., timeout or size).
-   Forwards packets to the next hop in the source route.

### `src/core/client.py` (`Sender`, `Receiver`)
-   **Sender**: Generates dummy traffic or real messages. Handles source routing, reliable transmission logic, and SURB creation.
-   **Receiver**: Collects incoming packets, calculates latency, and sends ACKs if reliability is enabled.

### `src/modules/`
-   **`routing.py`**: Helper for calculating paths (Shortest Path, Disjoint Paths).
-   **`reliability.py`**: Manages retransmission timers and ACK tracking for the Sender.
-   **`crypto.py`**: Placeholder/Basic implementation for SURB (Single Use Reply Blocks) and cryptographic operations.

## 6. Developer Guide

### Adding a New Mix Strategy
1.  Modify `src/core/mix.py`.
2.  Add a new condition in `flush_pool` or `_mixing_loop` checking `self.config['mix_settings']['strategy']`.
3.  Update `config.json` to use your new strategy name.

### Extending Packet Fields
Modify `src/core/packet.py` to add new fields to the `__init__`, `to_json`, and `from_json` methods.

### Debugging
-   Run Mininet with `sudo python3 mininet/topology.py`.
-   Use the Mininet CLI (`mininet>`) to inspect network state (e.g., `pingall`, `xterm s1`).
-   Check individual node logs in the `logs/` directory for runtime errors or trace information.
