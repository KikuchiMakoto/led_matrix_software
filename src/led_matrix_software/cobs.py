"""COBS (Consistent Overhead Byte Stuffing) pure-python implementation.

No third-party dependency. Framing: COBS encode, delimiter 0x00 appended
by the caller (protocol.encode_frame).
"""

from __future__ import annotations


def encode(data: bytes | bytearray) -> bytes:
    """COBS-encode data (without trailing delimiter)."""
    if not data:
        return b"\x01"
    out = bytearray()
    # Reserve space for first code byte
    code_idx = 0
    out.append(0)
    code = 1
    for b in data:
        if b == 0:
            out[code_idx] = code
            code_idx = len(out)
            out.append(0)
            code = 1
        else:
            out.append(b)
            code += 1
            if code == 0xFF:
                out[code_idx] = code
                code_idx = len(out)
                out.append(0)
                code = 1
    out[code_idx] = code
    return bytes(out)


def decode(data: bytes | bytearray) -> bytes:
    """COBS-decode data (without trailing delimiter). Raises ValueError."""
    if not data:
        raise ValueError("empty COBS block")
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        code = data[i]
        if code == 0:
            raise ValueError("zero byte inside COBS block")
        i += 1
        end = i + code - 1
        if end > n:
            raise ValueError("COBS code overruns block")
        out.extend(data[i:end])
        i = end
        if code < 0xFF and i < n:
            out.append(0)
    return bytes(out)
