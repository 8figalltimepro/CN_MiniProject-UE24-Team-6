"""
server.py — Telemetry Collection and Aggregation Server

Runs three concurrent threads:
  1. Secure Control Plane  : SSL/TLS TCP server — authenticates clients.
  2. Data Plane            : UDP server — ingests high-rate telemetry packets.
  3. Aggregation Reporter  : Prints per-client statistics every 5 seconds.
"""

import socket
import ssl
import threading
import time
import protocol
from collections import defaultdict


# Configuration

HOST      = '0.0.0.0'
PORT      = 8888
CERT_FILE = "server.crt"
KEY_FILE  = "server.key"
REPORT_INTERVAL = 5


# Shared State  (protected by a lock for thread safety)

stats_lock = threading.Lock()

def _default_stats():
    return {
        'received'        : 0,
        'lost'            : 0,
        'expected_seq'    : None,   # None = waiting for first packet
        'latency_sum_ms'  : 0.0,    # cumulative one-way latency (ms)
        'latency_count'   : 0,
        'window_start'    : None,   # start of current 1-second throughput window
        'window_packets'  : 0,      # packets received in current window
        'throughput_pps'  : 0.0,    # last measured packets-per-second
        'malformed'       : 0,
    }

client_stats = defaultdict(_default_stats)



# Thread 1 — Secure Control Plane (SSL/TLS over TCP)

def handle_secure_control_plane():
    """
    Listens for TCP connections and performs a minimal SSL/TLS handshake.
    On success sends AUTH_OK; client may then start the UDP data stream.
    """
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    try:
        context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
    except FileNotFoundError:
        print(f"[!] Certificate files not found ({CERT_FILE}, {KEY_FILE}).")
        print("[!] Generate them with the command in README.md and restart.")
        return

    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_sock.bind((HOST, PORT))
    tcp_sock.listen(10)
    print(f"[*] Secure Control Plane (SSL/TLS) listening on TCP {PORT}")

    while True:
        try:
            conn, addr = tcp_sock.accept()
        except OSError as e:
            print(f"[!] TCP accept error: {e}")
            continue

        try:
            secure_conn = context.wrap_socket(conn, server_side=True)
            raw = secure_conn.recv(1024).decode('utf-8', errors='ignore').strip()

            if raw.startswith("HELLO:"):
                parts = raw.split(":", 1)
                if len(parts) == 2 and parts[1].isdigit():
                    client_id = parts[1]
                    print(f"[+] Client {client_id} authenticated via SSL/TLS from {addr[0]}")
                    secure_conn.send(b"AUTH_OK")
                else:
                    print(f"[!] Malformed HELLO from {addr[0]}: {raw!r}")
                    secure_conn.send(b"AUTH_FAIL")
            else:
                print(f"[!] Unexpected control message from {addr[0]}: {raw!r}")
                secure_conn.send(b"AUTH_FAIL")

            secure_conn.close()

        except ssl.SSLError as e:
            print(f"[!] SSL error with {addr[0]}: {e}")
        except Exception as e:
            print(f"[!] Control plane error from {addr[0]}: {e}")



# Thread 2 — Data Plane (UDP Telemetry Ingestion)

def handle_data_plane():
    """
    Ingests UDP telemetry packets.
    For each valid packet updates:
      - Sequence tracking and loss detection
      - One-way latency (packet timestamp vs server receive time)
      - Throughput window (packets per second)
    """
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.bind((HOST, PORT))
    print(f"[*] Data Plane (UDP Telemetry) listening on UDP {PORT}")

    while True:
        try:
            raw_data, addr = udp_sock.recvfrom(4096)
        except OSError as e:
            print(f"[!] UDP receive error: {e}")
            continue

        recv_time = time.time()
        pkt = protocol.parse_packet(raw_data)

        if pkt is None:
            # Malformed packet — log and continue; do not crash
            print(f"[!] Malformed/invalid packet received from {addr[0]}, discarding.")
            # We don't know which client sent it, so tally under a generic key
            with stats_lock:
                client_stats['UNKNOWN']['malformed'] += 1
            continue

        cid = pkt['client_id']
        seq = pkt['seq']
        ts  = pkt['timestamp']

        with stats_lock:
            s = client_stats[cid]

            # Sequence Tracking & Loss Detection
            if s['expected_seq'] is None:
                # First packet from this client — use its seq as baseline
                s['expected_seq'] = seq

            if seq > s['expected_seq']:
                # Gap detected: packets between expected and current are lost
                lost_count = seq - s['expected_seq']
                s['lost'] += lost_count

            elif seq < s['expected_seq']:
                # Late/duplicate packet — do not update expected
                pass

            s['received']     += 1
            s['expected_seq']  = seq + 1

            # Latency Measurement
            # One-way latency
            latency_ms = (recv_time - ts) * 1000.0
            if latency_ms >= 0:
                s['latency_sum_ms'] += latency_ms
                s['latency_count']  += 1

            # Throughput Window (packets per second)
            if s['window_start'] is None:
                s['window_start']   = recv_time
                s['window_packets'] = 1
            else:
                s['window_packets'] += 1
                elapsed = recv_time - s['window_start']
                if elapsed >= 1.0:
                    s['throughput_pps'] = s['window_packets'] / elapsed
                    s['window_start']   = recv_time
                    s['window_packets'] = 0



# Thread 3 — Aggregation Reporter

def print_aggregation_report():
    """Prints a formatted per-client statistics table every REPORT_INTERVAL seconds."""
    while True:
        time.sleep(REPORT_INTERVAL)

        with stats_lock:
            snapshot = {cid: dict(s) for cid, s in client_stats.items()}

        if not snapshot:
            print("[*] No clients connected yet...")
            continue

        w = 70
        print("\n" + "=" * w)
        print(f"  TELEMETRY AGGREGATION REPORT  —  {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * w)
        print(f"{'Client':<10} {'Recv':>8} {'Lost':>8} {'Loss%':>8} {'Latency(ms)':>13} {'PPS':>8} {'Bad':>6}")
        print("-" * w)

        for cid, s in sorted(snapshot.items(), key=lambda x: str(x[0])):
            total     = s['received'] + s['lost']
            loss_pct  = (s['lost'] / total * 100) if total > 0 else 0.0
            avg_lat   = (s['latency_sum_ms'] / s['latency_count']) if s['latency_count'] > 0 else 0.0
            pps       = s['throughput_pps']
            bad       = s['malformed']
            print(f"{str(cid):<10} {s['received']:>8} {s['lost']:>8} {loss_pct:>7.2f}% {avg_lat:>12.3f} {pps:>8.1f} {bad:>6}")

        print("=" * w + "\n")



# Entry Point
if __name__ == "__main__":
    print("[*] Starting Telemetry Collection and Aggregation Server...")
    print(f"[*] Host: {HOST}  |  Port: {PORT}  |  Protocol: TCP (control) + UDP (data)")
    print("-" * 50)

    t1 = threading.Thread(target=handle_secure_control_plane, name="ControlPlane", daemon=True)
    t2 = threading.Thread(target=handle_data_plane,           name="DataPlane",    daemon=True)
    t3 = threading.Thread(target=print_aggregation_report,    name="Reporter",     daemon=True)

    t1.start()
    t2.start()
    t3.start()

    try:
        t1.join()   # Block main thread; server runs until Ctrl+C
    except KeyboardInterrupt:
        print("\n[*] Server shutting down.")
