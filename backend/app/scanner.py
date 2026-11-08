"""Malware scanning before a document is stored.

- `ClamdScanner`: talks to a ClamAV daemon over TCP with the INSTREAM command (docker-compose service `clamav`).
- `DevStubScanner`: dev only, clearly labelled. It flags the EICAR test string and passes everything else, so the
  infected path can be exercised without ClamAV. It refuses to load outside TL_ENV=dev.
"""
from __future__ import annotations

import socket
import struct
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Protocol

from .config import get_settings

EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


@dataclass
class ScanResult:
    clean: bool
    engine: str          # e.g. "ClamAV 1.4.2" or "DEV STUB (not a malware scanner)"
    signature: str | None
    scanned_at: str


class Scanner(Protocol):
    def scan(self, data: bytes) -> ScanResult: ...


class ScannerUnavailable(Exception):
    """The scanner could not be reached. Uploads are refused rather than stored unscanned."""


class ClamdScanner:
    def __init__(self, host: str, port: int, timeout: float = 30.0):
        self.host, self.port, self.timeout = host, port, timeout

    def _cmd(self, payload: bytes, data: bytes | None = None) -> bytes:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
                s.sendall(payload)
                if data is not None:
                    for i in range(0, len(data), 64 * 1024):
                        chunk = data[i:i + 64 * 1024]
                        s.sendall(struct.pack(">I", len(chunk)) + chunk)
                    s.sendall(struct.pack(">I", 0))
                out = b""
                while not out.endswith(b"\0"):
                    part = s.recv(4096)
                    if not part:
                        break
                    out += part
                return out.rstrip(b"\0")
        except OSError as e:
            raise ScannerUnavailable(f"ClamAV at {self.host}:{self.port}: {e}") from e

    def version(self) -> str:
        return self._cmd(b"zVERSION\0").decode(errors="replace")

    def scan(self, data: bytes) -> ScanResult:
        reply = self._cmd(b"zINSTREAM\0", data).decode(errors="replace")   # "stream: OK" | "stream: Eicar-Signature FOUND"
        now = datetime.now().isoformat(timespec="seconds")
        engine = self.version().split("/")[0]
        if reply.endswith("OK"):
            return ScanResult(True, engine, None, now)
        if reply.endswith("FOUND"):
            return ScanResult(False, engine, reply.split(":", 1)[1].rsplit(" ", 1)[0].strip(), now)
        raise ScannerUnavailable(f"unexpected ClamAV reply: {reply}")


class DevStubScanner:
    ENGINE = "DEV STUB (not a malware scanner)"

    def __init__(self) -> None:
        if not get_settings().is_dev:
            raise RuntimeError("the dev stub scanner is not allowed outside TL_ENV=dev; set TL_SCANNER=clamd")

    def scan(self, data: bytes) -> ScanResult:
        now = datetime.now().isoformat(timespec="seconds")
        if EICAR in data:
            return ScanResult(False, self.ENGINE, "EICAR-Test-File (stub match)", now)
        return ScanResult(True, self.ENGINE, None, now)


@lru_cache
def scanner() -> Scanner:
    s = get_settings()
    if s.scanner == "clamd":
        return ClamdScanner(s.clamd_host, s.clamd_port)
    return DevStubScanner()
