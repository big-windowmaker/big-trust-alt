"""Decompress small in-memory members (bounded output)."""

from __future__ import annotations

import gzip
import io
import lzma

MAX_OUTPUT = 32 << 20


def open_compressed(name: str, raw: bytes) -> bytes:
    if name.endswith(".gz"):
        stream = gzip.GzipFile(fileobj=io.BytesIO(raw))
    elif name.endswith(".xz"):
        stream = lzma.LZMAFile(io.BytesIO(raw))
    elif name.endswith(".zst"):
        from compression import zstd
        stream = zstd.ZstdFile(io.BytesIO(raw))
    elif name.endswith(".tar"):
        return raw
    else:
        raise ValueError(f"unsupported compression in {name}")
    data = stream.read(MAX_OUTPUT + 1)
    if len(data) > MAX_OUTPUT:
        raise ValueError("member expands too much")
    return data
