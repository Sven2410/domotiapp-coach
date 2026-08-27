"""Kale websocket-client voor Svens HA (er is hier geen websockets-module).

Alleen lezen: authenticeren en commando's sturen die niets veranderen.
"""
import base64, json, os, socket, struct
import ha


def _frame(payload: bytes, opcode: int = 1) -> bytes:
    mask = os.urandom(4)
    n = len(payload)
    head = bytes([0x80 | opcode])
    if n < 126:
        head += bytes([0x80 | n])
    elif n < 65536:
        head += bytes([0x80 | 126]) + struct.pack(">H", n)
    else:
        head += bytes([0x80 | 127]) + struct.pack(">Q", n)
    return head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))


class WS:
    def __init__(self):
        # ha.host() zoekt zo nodig eerst uit welk adres uit het tokenbestand
        # antwoord geeft: thuis het eigen netwerk, onderweg Nabu Casa.
        host, port = ha.host().rsplit(":", 1)
        self.s = socket.create_connection((host, int(port)), timeout=20)
        if ha.SCHEMA == "https":
            # Een installatie die op naam bereikbaar is draait wel met een
            # certificaat, en dan moet de socket eerst omhoog voor de handshake.
            import ssl

            self.s = ssl.create_default_context().wrap_socket(
                self.s, server_hostname=host
            )
        # De standaardpoort hoort niet in de Host-header: de omgekeerde proxy
        # van Nabu Casa kijkt daarnaar.
        kop = host if port in ("443", "80") else ha.HOST
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall(
            f"GET /api/websocket HTTP/1.1\r\nHost: {kop}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n".encode()
        )
        self.buf = b""
        while b"\r\n\r\n" not in self.buf:
            self.buf += self.s.recv(4096)
        self.buf = self.buf.split(b"\r\n\r\n", 1)[1]
        self.id = 0
        assert self.recv()["type"] == "auth_required"
        self.send({"type": "auth", "access_token": ha.TOKEN})
        assert self.recv()["type"] == "auth_ok"

    def send(self, msg):
        self.s.sendall(_frame(json.dumps(msg).encode()))

    def _read(self, n):
        while len(self.buf) < n:
            deel = self.s.recv(65536)
            if not deel:
                raise ConnectionError("verbinding dicht")
            self.buf += deel
        uit, self.buf = self.buf[:n], self.buf[n:]
        return uit

    def recv(self):
        while True:
            b0, b1 = self._read(2)
            opcode = b0 & 0x0F
            n = b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            data = self._read(n)
            if opcode == 1:
                return json.loads(data.decode())
            if opcode == 9:  # ping van de server, hoort een pong terug
                self.s.sendall(_frame(data, opcode=10))
                continue
            if opcode == 8:
                raise ConnectionError("server sloot de verbinding")

    def vraag(self, type_, **kw):
        self.id += 1
        self.send({"id": self.id, "type": type_, **kw})
        while True:
            m = self.recv()
            if m.get("id") == self.id and m.get("type") == "result":
                if not m.get("success", True):
                    raise RuntimeError(m.get("error"))
                return m.get("result")
