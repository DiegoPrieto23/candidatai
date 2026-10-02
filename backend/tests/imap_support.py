"""Servidor IMAP falso y estricto para los tests: solo admite lecturas.

Responde a `CAPABILITY`, `LOGIN`, `EXAMINE`, `UID SEARCH`, `UID FETCH` con `BODY.PEEK[…]`, `NOOP`
y `LOGOUT`. Cualquier otra orden (`SELECT`, `STORE`, `COPY`, `MOVE`, `EXPUNGE`, `APPEND`, `DELETE`,
`CLOSE`…) o un `FETCH` sin `PEEK` (que marcaría el correo como leído) queda en `violations` y
recibe `BAD`. Escucha en 127.0.0.1, sin TLS.
"""

import re
import socketserver
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

USER, PASSWORD, FOLDER = "candidata@demo.invalid", "secreto-demo", "Alertas empleo"
_ALLOWED = {"CAPABILITY", "LOGIN", "EXAMINE", "NOOP", "LOGOUT"}
_PEEK = re.compile(r"\(BODY\.PEEK\[(HEADER\.FIELDS \(MESSAGE-ID\))?\]\)", re.IGNORECASE)


@dataclass
class FakeImap:
    messages: dict[int, bytes]  # UID -> correo completo
    violations: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    port: int = 0


def _header_id(raw: bytes) -> bytes:
    for line in raw.split(b"\n"):
        if line.lower().startswith(b"message-id:"):
            return line.rstrip(b"\r") + b"\r\n\r\n"
    return b"\r\n"


class _Handler(socketserver.StreamRequestHandler):
    server: "_Server"

    def _send(self, data: bytes) -> None:
        self.wfile.write(data)

    def handle(self) -> None:
        state = self.server.state
        self._send(b"* OK Servidor IMAP falso listo\r\n")
        while line := self.rfile.readline():
            text = line.decode("utf-8", "replace").rstrip("\r\n")
            tag, _, rest = text.partition(" ")
            command, _, args = rest.partition(" ")
            command = command.upper()
            state.commands.append(command if command != "UID" else f"UID {args.split()[0]}")
            if command == "UID":
                sub, _, args = args.partition(" ")
                self._uid(tag, sub.upper(), args)
                continue
            if command not in _ALLOWED:
                state.violations.append(text)
                self._send(f"{tag} BAD orden no permitida\r\n".encode())
                continue
            if command == "CAPABILITY":
                self._send(f"* CAPABILITY IMAP4rev1\r\n{tag} OK hecho\r\n".encode())
            elif command == "LOGIN":
                # imaplib entrecomilla la contraseña y deja el usuario tal cual.
                ok = [part.strip('"') for part in args.split(" ", 1)] == [USER, PASSWORD]
                self._send(f"{tag} {'OK' if ok else 'NO'} login\r\n".encode())
            elif command == "EXAMINE":
                if args.strip('"') != FOLDER:
                    self._send(f"{tag} NO carpeta inexistente\r\n".encode())
                    continue
                self._send(
                    f"* {len(state.messages)} EXISTS\r\n* OK [UIDVALIDITY 1]\r\n"
                    f"{tag} OK [READ-ONLY] EXAMINE hecho\r\n".encode()
                )
            elif command == "NOOP":
                self._send(f"{tag} OK\r\n".encode())
            elif command == "LOGOUT":
                self._send(f"* BYE\r\n{tag} OK adiós\r\n".encode())
                return

    def _uid(self, tag: str, sub: str, args: str) -> None:
        state = self.server.state
        if sub == "SEARCH":
            uids = " ".join(str(u) for u in sorted(state.messages))
            self._send(f"* SEARCH {uids}\r\n{tag} OK hecho\r\n".encode())
            return
        if sub != "FETCH":
            state.violations.append(f"UID {sub} {args}")
            self._send(f"{tag} BAD orden no permitida\r\n".encode())
            return
        uid_set, _, items = args.partition(" ")
        match = _PEEK.fullmatch(items.strip())
        if match is None:
            state.violations.append(f"UID FETCH {args}")
            self._send(f"{tag} BAD solo BODY.PEEK\r\n".encode())
            return
        header_only = match.group(1) is not None
        for seq, uid in enumerate(int(u) for u in uid_set.split(",")):
            raw = state.messages.get(uid)
            if raw is None:
                continue
            data = _header_id(raw) if header_only else raw
            section = "BODY[HEADER.FIELDS (MESSAGE-ID)]" if header_only else "BODY[]"
            self._send(f"* {seq + 1} FETCH (UID {uid} {section} {{{len(data)}}}\r\n".encode())
            self._send(data + b")\r\n")
        self._send(f"{tag} OK hecho\r\n".encode())


class _Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, state: FakeImap) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.state = state


@contextmanager
def fake_imap(messages: dict[int, bytes]) -> Iterator[FakeImap]:
    state = FakeImap(messages=messages)
    server = _Server(state)
    state.port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
