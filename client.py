import socket
import ssl
import time
import random
import sys
import argparse
import protocol

# Defaults (overridable via CLI arguments)
DEFAULT_SERVER_IP = '127.0.0.1'
DEFAULT_PORT      = 8888
SEND_RATE         = 0.1   # seconds between packets  →  ~10 packets/sec
MAX_RETRIES       = 3



# Secure SSL/TLS Handshake (TCP)
def secure_handshake(client_id, server_ip, port):
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    context.check_hostname = False       # self-signed cert used in lab
    context.verify_mode   = ssl.CERT_NONE

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"[*] Client {client_id}: SSL/TLS handshake attempt {attempt}/{MAX_RETRIES} → {server_ip}:{port}")

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)

        try:
            secure_sock = context.wrap_socket(sock, server_hostname=server_ip)
            secure_sock.connect((server_ip, port))
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
            print(f"[!] Connection refused — is the server running on {server_ip}:{port}?")
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



# UDP Telemetry Stream
def start_telemetry(client_id, server_ip, port, loss_rate):
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    seq_num  = 0

    print(f"[*] Client {client_id}: Starting UDP telemetry → {server_ip}:{port}  "
          f"(rate ~{int(1/SEND_RATE)} pps, simulated loss {loss_rate*100:.0f}%)")

    try:
        while True:
            data   = {"cpu": random.randint(10, 90), "temp": random.randint(40, 80)}
            packet = protocol.create_packet(client_id, seq_num, data)

            if random.random() >= loss_rate:
                try:
                    udp_sock.sendto(packet, (server_ip, port))
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




if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Telemetry client — authenticates via SSL/TLS then streams UDP data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("client_id",
                        type=int,
                        help="Unique integer client ID (e.g. 101)")
    parser.add_argument("--server",
                        type=str,
                        default=DEFAULT_SERVER_IP,
                        metavar="IP",
                        help="IP address of the server. "
                             "When running on a separate machine over a shared hotspot, "
                             "pass the server machine's LAN IP here "
                             "(find it with: ip addr  /  ifconfig  /  ipconfig).")
    parser.add_argument("--port",
                        type=int,
                        default=DEFAULT_PORT,
                        help="Server port number.")
    parser.add_argument("--loss",
                        type=float,
                        default=0.0,
                        metavar="RATE",
                        help="Fraction of packets to drop locally, 0.0–1.0.")
    args = parser.parse_args()

    if not (0.0 <= args.loss <= 1.0):
        print("[!] --loss must be between 0.0 and 1.0")
        sys.exit(1)

    print(f"[*] Server target : {args.server}:{args.port}")
    print(f"[*] Client ID     : {args.client_id}")
    print(f"[*] Simulated loss: {args.loss*100:.0f}%")
    print("-" * 50)

    if secure_handshake(args.client_id, args.server, args.port):
        start_telemetry(args.client_id, args.server, args.port, args.loss)
    else:
        sys.exit(1)
