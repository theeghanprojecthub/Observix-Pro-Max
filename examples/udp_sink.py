import socket

HOST = "127.0.0.1"
PORT = 5514

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((HOST, PORT))
print(f"listening on udp://{HOST}:{PORT}")

while True:
    data, addr = sock.recvfrom(65535)
    print(f"{addr} -> {data.decode('utf-8', errors='ignore')}")
