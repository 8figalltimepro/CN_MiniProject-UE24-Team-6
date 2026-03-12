"""
client.py — Telemetry Client
==============================
1. Performs an SSL/TLS handshake over TCP to authenticate with the server.
2. Streams UDP telemetry packets at ~10 packets/second after authentication.

Usage:
    python3 client.py <client_id> [--loss 0.0-1.0]

Example:
    python3 client.py 101              # No simulated packet loss
    python3 client.py 202 --loss 0.2   # 20% simulated packet loss
"""

import socket
import ssl
import time
import random
import sys
import argparse
import protocol

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SERVER_IP   = '127.0.0.1'
PORT        = 8888
SEND_RATE   = 0.1   # seconds between packets (10 pps)
MAX_RETRIES = 3     # SSL handshake retry attempts


# ---------------------------------------------------------------------------
# Step 1 — Secure SSL/TLS Handshake (TCP)
# ---------------------------------------------------------------------------
def secure_handshake(client_id):
    """
    Opens a TCP connection to the server, wraps it in SSL/TLS,
    and performs a simple challenge-response authentication.

    Note on SSL verification:
        CERT_NONE and check_hostname=False are used intentionally
        because the server uses a self-signed certificate for this demo.
        In production, load the CA cert and set verify_mode=CERT_REQUIRED.

    Returns:
        bool: True if authentication succeeded, False otherwise.
    """
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    context.check_hostname = False      # Self-signed cert — no hostname in SAN
    context.verify_mode   = ssl.CERT_NONE  # Accept self-signed for demo

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"[*] Client {client_id}: SSL/TLS handshake attempt {attempt}/{MAX_RETRIES}...")

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)

        try:
            secure_sock = context.wrap_socket(sock, server_hostname=SERVER_IP)
            secure_sock.connect((SERVER_IP, PORT))
            secure_sock.send(f"HELLO:{client_id}".encode())

            response = secure_sock.recv(1024).decode('utf-8', errors='ignore').strip()

            if response == "AUTH_OK":
                print(f"[+] Client {client_id}: SSL/TLS Handshake Successful. Authorised.")
                secure_sock.close()
                return True
            else:
                print(f"[!] Client {client_id}: Server rejected authentication ({response}).")
                secure_sock.close()
                return False

        except ssl.SSLError as e:
            print(f"[!] SSL error on attempt {attempt}: {e}")
        except ConnectionRefusedError:
            print(f"[!] Connection refused — is the server running on {SERVER_IP}:{PORT}?")
        except socket.timeout:
            print(f"[!] Connection timed out on attempt {attempt}.")
        except Exception as e:
            print(f"[!] Unexpected error on attempt {attempt}: {e}")
        finally:
            sock.close()

        if attempt < MAX_RETRIES:
            time.sleep(1)

    print(f"[!] Client {client_id}: All handshake attempts failed. Exiting.")
    return False


# ---------------------------------------------------------------------------
# Step 2 — UDP Telemetry Stream
# ---------------------------------------------------------------------------
def start_telemetry(client_id, loss_rate):
    """
    Continuously sends binary telemetry packets over UDP.

    Simulated telemetry payload:
        cpu  (int): Simulated CPU usage percentage (10–90).
        temp (int): Simulated core temperature in Celsius (40–80).

    Packet loss simulation:
        With probability `loss_rate`, the packet is deliberately not sent.
        This lets the server's sequence-gap detection be demonstrated live.

    Args:
        client_id (int): Identifies this client in every packet header.
        loss_rate (float): Fraction of packets to drop locally (0.0–1.0).
    """
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    seq_num  = 0

    print(f"[*] Client {client_id}: Starting UDP telemetry  "
          f"(rate ~{int(1/SEND_RATE)} pps, simulated loss {loss_rate*100:.0f}%)")

    try:
        while True:
            data   = {"cpu": random.randint(10, 90), "temp": random.randint(40, 80)}
            packet = protocol.create_packet(client_id, seq_num, data)

            if random.random() >= loss_rate:
                try:
                    udp_sock.sendto(packet, (SERVER_IP, PORT))
                except OSError as e:
                    print(f"[!] UDP send error (seq {seq_num}): {e}")
            else:
                print(f"[~] Client {client_id}: Simulated drop — seq {seq_num}")

            seq_num += 1
            time.sleep(SEND_RATE)

    except KeyboardInterrupt:
        print(f"\n[*] Client {client_id}: Stopping telemetry stream.")
    finally:
        udp_sock.close()


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Telemetry client — authenticates via SSL/TLS then streams UDP data."
    )
    parser.add_argument("client_id", type=int,   help="Unique integer client ID (e.g. 101)")
    parser.add_argument("--loss",    type=float, default=0.0,
                        help="Fraction of packets to drop locally, 0.0–1.0 (default: 0.0)")
    args = parser.parse_args()

    if not (0.0 <= args.loss <= 1.0):
        print("[!] --loss must be between 0.0 and 1.0")
        sys.exit(1)

    if secure_handshake(args.client_id):
        start_telemetry(args.client_id, args.loss)
    else:
        sys.exit(1)
