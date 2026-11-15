"""Minimal HTTP client for the Pocket Robot message API (MicroPython)."""
import json
import socket


class ServerClient:
    def __init__(self, host, port, token, timeout=2):
        self.host = host
        self.port = int(port)
        self.token = token
        self.timeout = timeout

    def _request(self, method, path, payload=None):
        body = b"" if payload is None else json.dumps(payload).encode()
        addr = socket.getaddrinfo(self.host, self.port)[0][-1]
        sock = socket.socket()
        try:
            sock.settimeout(self.timeout)
            sock.connect(addr)
            sock.sendall((("{} {} HTTP/1.1\r\nHost: {}:{}\r\nAuthorization: Bearer {}\r\nConnection: close\r\n".format(
                method, path, self.host, self.port, self.token)) +
                (("Content-Type: application/json\r\nContent-Length: {}\r\n".format(len(body)))
                 if payload is not None else "") + "\r\n").encode() + body)
            chunks = []
            while True:
                part = sock.recv(512)
                if not part:
                    break
                chunks.append(part)
            raw = b"".join(chunks)
        finally:
            sock.close()
        split = raw.find(b"\r\n\r\n")
        if split < 0:
            raise OSError("Invalid HTTP response")
        status_line = raw[:split].split(b"\r\n", 1)[0]
        status = int(status_line.split()[1])
        if status < 200 or status >= 300:
            raise OSError("HTTP {}".format(status))
        body = raw[split + 4:]
        return json.loads(body.decode()) if body else {}

    def poll(self):
        return self._request("GET", "/api/robot/messages/next").get("message")

    def acknowledge(self, message_id):
        self._request("POST", "/api/robot/messages/{}/ack".format(int(message_id)),
                      {"received": True})
        return True
