"""ClamAV client tests against a small fake clamd that speaks the real INSTREAM protocol."""
import asyncio
import struct

import pytest

import virus_scan
from virus_scan import ClamAVScanner, MalwareDetected, NoopScanner, ScannerUnavailable

EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


class FakeClamd:
    """Accepts INSTREAM and PING like clamd; flags any stream containing the EICAR string"""

    def __init__(self, reply_override=None):
        self.reply_override = reply_override
        self.streams = []
        self.server = None

    async def start(self):
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        return self.server.sockets[0].getsockname()[1]

    async def stop(self):
        self.server.close()
        await self.server.wait_closed()

    async def _handle(self, reader, writer):
        command = (await reader.readuntil(b"\x00")).strip(b"\x00")
        if command == b"zPING":
            writer.write(b"PONG\x00")
        elif command == b"zINSTREAM":
            data = b""
            while True:
                size = struct.unpack("!I", await reader.readexactly(4))[0]
                if size == 0:
                    break
                data += await reader.readexactly(size)
            self.streams.append(data)
            if self.reply_override:
                writer.write(self.reply_override)
            elif EICAR in data:
                writer.write(b"stream: Eicar-Test-Signature FOUND\x00")
            else:
                writer.write(b"stream: OK\x00")
        await writer.drain()
        writer.close()


@pytest.fixture
async def clamd():
    server = FakeClamd()
    port = await server.start()
    server.port = port
    yield server
    await server.stop()


def scanner_for(clamd, **kwargs):
    return ClamAVScanner(host="127.0.0.1", port=clamd.port, timeout=5, **kwargs)


async def test_clean_file_passes_and_arrives_intact(clamd):
    payload = b"%PDF-1.7 " + bytes(range(256)) * 1000  # larger than one chunk
    await scanner_for(clamd).scan(payload)
    assert clamd.streams == [payload]


async def test_eicar_is_reported_with_signature_name(clamd):
    with pytest.raises(MalwareDetected) as caught:
        await scanner_for(clamd).scan(b"%PDF-1.7 " + EICAR)
    assert caught.value.signature == "Eicar-Test-Signature"


async def test_ping(clamd):
    assert await scanner_for(clamd).ping() is True


async def test_unreachable_scanner_fails_closed():
    scanner = ClamAVScanner(host="127.0.0.1", port=1, timeout=1)
    with pytest.raises(ScannerUnavailable):
        await scanner.scan(b"data")
    assert await scanner.ping() is False


async def test_unreachable_scanner_can_fail_open():
    await ClamAVScanner(host="127.0.0.1", port=1, timeout=1, fail_open=True).scan(b"data")


async def test_scanner_error_reply_fails_closed(clamd):
    clamd.reply_override = b"INSTREAM size limit exceeded. ERROR\x00"
    with pytest.raises(ScannerUnavailable, match="size limit"):
        await scanner_for(clamd).scan(b"data")


async def test_scanner_error_reply_can_fail_open(clamd):
    clamd.reply_override = b"INSTREAM size limit exceeded. ERROR\x00"
    await scanner_for(clamd, fail_open=True).scan(b"data")


class TestConfiguration:
    def test_off_by_default(self, monkeypatch):
        monkeypatch.delenv("CLAMAV_ENABLED", raising=False)
        scanner = virus_scan.get_virus_scanner()
        assert isinstance(scanner, NoopScanner) and scanner.enabled is False

    def test_enabled_reads_host_port_and_fail_mode(self, monkeypatch):
        monkeypatch.setenv("CLAMAV_ENABLED", "true")
        monkeypatch.setenv("CLAMAV_HOST", "clamav.internal")
        monkeypatch.setenv("CLAMAV_PORT", "4000")
        scanner = virus_scan.get_virus_scanner()
        assert (scanner.host, scanner.port, scanner.fail_open) == ("clamav.internal", 4000, False)

    async def test_disabled_scanner_accepts_everything(self):
        await NoopScanner().scan(EICAR)
