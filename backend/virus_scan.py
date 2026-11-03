"""Malware scanning of uploads with ClamAV.

Talks to a running clamd over its INSTREAM protocol, so no extra Python package is needed.
Enable with CLAMAV_ENABLED=true and point CLAMAV_HOST / CLAMAV_PORT at the daemon.

If the scanner cannot be reached the upload is refused (fail closed). Set
CLAMAV_FAIL_OPEN=true only if you accept unscanned files during an outage.
"""
import asyncio
import logging
import os
import struct
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

CHUNK_SIZE = 64 * 1024


class MalwareDetected(Exception):
    def __init__(self, signature: str):
        super().__init__(f"Malware detected: {signature}")
        self.signature = signature


class ScannerUnavailable(Exception):
    """The scanner could not be reached or gave an unusable answer"""


class VirusScanner(ABC):
    name: str = "base"
    enabled: bool = True

    @abstractmethod
    async def scan(self, data: bytes) -> None:
        """Return normally when clean; raise MalwareDetected or ScannerUnavailable"""

    async def ping(self) -> bool:
        return True


class NoopScanner(VirusScanner):
    name = "disabled"
    enabled = False

    async def scan(self, data: bytes) -> None:
        return None


class ClamAVScanner(VirusScanner):
    name = "clamav"

    def __init__(self, host: str = "localhost", port: int = 3310, timeout: float = 30.0, fail_open: bool = False):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.fail_open = fail_open

    async def _command(self, payload: bytes, stream: bytes = None) -> str:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=self.timeout
            )
        except (OSError, asyncio.TimeoutError) as e:
            raise ScannerUnavailable(f"Cannot reach ClamAV at {self.host}:{self.port}: {e}") from e

        try:
            writer.write(payload)
            if stream is not None:
                for start in range(0, len(stream), CHUNK_SIZE):
                    chunk = stream[start:start + CHUNK_SIZE]
                    writer.write(struct.pack("!I", len(chunk)) + chunk)
                writer.write(struct.pack("!I", 0))  # end of stream
            await asyncio.wait_for(writer.drain(), timeout=self.timeout)
            reply = await asyncio.wait_for(reader.read(), timeout=self.timeout)
            return reply.decode("utf-8", errors="replace").strip("\x00\n ")
        except (OSError, asyncio.TimeoutError) as e:
            raise ScannerUnavailable(f"ClamAV connection failed: {e}") from e
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    async def scan(self, data: bytes) -> None:
        try:
            reply = await self._command(b"zINSTREAM\x00", stream=data)
        except ScannerUnavailable:
            if self.fail_open:
                logger.error("ClamAV unreachable; accepting the file unscanned (CLAMAV_FAIL_OPEN)")
                return
            raise

        if reply.endswith("OK"):
            return
        if reply.endswith("FOUND"):
            signature = reply.split(":", 1)[-1].replace("FOUND", "").strip() or "unknown"
            raise MalwareDetected(signature)
        # e.g. "INSTREAM size limit exceeded. ERROR"
        if self.fail_open:
            logger.error(f"ClamAV returned an error ({reply}); accepting the file unscanned")
            return
        raise ScannerUnavailable(f"ClamAV returned an error: {reply}")

    async def ping(self) -> bool:
        try:
            return (await self._command(b"zPING\x00")) == "PONG"
        except ScannerUnavailable:
            return False


def get_virus_scanner() -> VirusScanner:
    if os.getenv("CLAMAV_ENABLED", "false").lower() != "true":
        logger.warning("Virus scanning is OFF (CLAMAV_ENABLED is not 'true'). Enable it before accepting public uploads.")
        return NoopScanner()
    return ClamAVScanner(
        host=os.getenv("CLAMAV_HOST", "localhost"),
        port=int(os.getenv("CLAMAV_PORT", "3310")),
        timeout=float(os.getenv("CLAMAV_TIMEOUT_SECONDS", "30")),
        fail_open=os.getenv("CLAMAV_FAIL_OPEN", "false").lower() == "true",
    )
