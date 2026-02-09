import socket
import time
import datetime
import random
import json


def send_syslog(host: str, port: int, app: str, msg: str):
    # Simple RFC3164-ish payload. Most syslog servers accept it.
    pri = 13  # user-level notice-ish
    ts = datetime.datetime.utcnow().strftime("%b %d %H:%M:%S")
    hostname = "demo-app"
    payload = f"<{pri}>{ts} {hostname} {app}: {msg}"
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(payload.encode("utf-8"), (host, port))
    sock.close()


def main():
    targets = [
        ("127.0.0.1", 5514, "demo-app-A"),
        ("127.0.0.1", 5515, "demo-app-B"),
    ]

    i = 0
    while True:
        i += 1

        # Different structures to test "raw vs indexed"
        msg_a = {
            "event": "payment_attempt",
            "trace_id": f"tr-{random.randint(1000,9999)}",
            "amount": random.randint(5, 500),
            "currency": "GBP",
            "status": random.choice(["OK", "FAIL"]),
            "ts": datetime.datetime.utcnow().isoformat() + "Z",
        }
        msg_b = f"user_login user={random.choice(['paul','sam','ada'])} result={random.choice(['success','deny'])} i={i}"

        send_syslog(*targets[0], msg=json.dumps(msg_a))
        print(f"sent -> {targets[0][0]}:{targets[0][1]} {targets[0][2]} {msg_a}")
        send_syslog(*targets[1], msg=msg_b)
        print(f"sent -> {targets[1][0]}:{targets[1][1]} {targets[1][2]} {msg_b}")

        time.sleep(1)


if __name__ == "__main__":
    main()
