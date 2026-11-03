from fastapi import UploadFile

from services.errors import ScanError

UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1MB


async def read_upload_limited(upload: UploadFile, max_bytes: int) -> bytes:
    """Read an upload chunk by chunk, raising 413 as soon as it passes max_bytes"""
    buffer = bytearray()
    while True:
        chunk = await upload.read(UPLOAD_CHUNK_SIZE)
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > max_bytes:
            raise ScanError(413, f"File size exceeds maximum limit of {max_bytes // (1024 * 1024)}MB")
    return bytes(buffer)
