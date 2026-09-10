"""Binary frame protocol: Fixed 4B header + Raw payload + COBS + 0x00.

Header (little-endian):
  [0] MAGIC = 0x55
  [1] MODE  = bit depth N (0x01..0x08, max 8bit/256 levels)
  [2..3] PAYLOAD_LEN = N * 256 (uint16 LE)

Payload layout (plane-major, LSB first):
  plane[p][8][16] uint16LE, each plane 256B identical to legacy
  matrix_buffer layout. N planes concatenated -> N*256 bytes.

No compression (RLE deliberately omitted: expands video data).
No Base64 legacy.
"""

from __future__ import annotations

from . import cobs

MAGIC: int = 0x55
DELIMITER: int = 0x00
MIN_BITS: int = 1
MAX_BITS: int = 8
CMD_MODE: int = 0x00
CMD_PAYLOAD_LEN: int = 2
CMD_BRIGHTNESS: int = 0x01
PANEL_LINES: int = 8
COLS: int = 16
PLANE_BYTES: int = PANEL_LINES * COLS * 2  # 256
HEADER_SIZE: int = 4


def payload_len(bits: int) -> int:
    if not (MIN_BITS <= bits <= MAX_BITS):
        raise ValueError(f"bits must be {MIN_BITS}..{MAX_BITS}, got {bits}")
    return bits * PLANE_BYTES


def pack(bits: int, payload: bytes | bytearray) -> bytes:
    """Build raw (pre-COBS) packet: header + payload."""
    n = payload_len(bits)
    if len(payload) != n:
        raise ValueError(f"bits={bits} needs {n} payload bytes, got {len(payload)}")
    hdr = bytes((MAGIC, bits, n & 0xFF, (n >> 8) & 0xFF))
    return hdr + bytes(payload)


def encode_frame(bits: int, payload: bytes | bytearray) -> bytes:
    """Build on-wire frame: COBS(header+payload) + 0x00."""
    return cobs.encode(pack(bits, payload)) + b"\x00"


def pack_command(cmd: int, value: int) -> bytes:
    """Build raw (pre-COBS) command packet: header + 2B payload."""
    if not (0 <= cmd <= 0xFF and 0 <= value <= 0xFF):
        raise ValueError("cmd/value must be 0..255")
    hdr = bytes((MAGIC, CMD_MODE, CMD_PAYLOAD_LEN, 0))
    return hdr + bytes((cmd, value))


def encode_command(cmd: int, value: int) -> bytes:
    """Build on-wire command frame: COBS(header+payload) + 0x00."""
    return cobs.encode(pack_command(cmd, value)) + b"\x00"


def decode_packet(raw: bytes | bytearray) -> tuple[int, bytes]:
    """Validate raw (post-COBS) packet. Returns (bits, payload)."""
    if len(raw) < HEADER_SIZE:
        raise ValueError(f"packet too short: {len(raw)}")
    magic, bits = raw[0], raw[1]
    if magic != MAGIC:
        raise ValueError(f"bad magic: {magic:#x}")
    if bits == CMD_MODE:
        length = raw[2] | (raw[3] << 8)
        if length != CMD_PAYLOAD_LEN or len(raw) != HEADER_SIZE + length:
            raise ValueError("bad command length")
        return bits, bytes(raw[HEADER_SIZE:])
    if not (MIN_BITS <= bits <= MAX_BITS):
        raise ValueError(f"bad mode: {bits:#x}")
    length = raw[2] | (raw[3] << 8)
    expect = payload_len(bits)
    if length != expect:
        raise ValueError(f"length mismatch: header={length} expect={expect}")
    if len(raw) != HEADER_SIZE + expect:
        raise ValueError(f"packet size mismatch: {len(raw)} != {HEADER_SIZE + expect}")
    return bits, bytes(raw[HEADER_SIZE:])


def decode_frame(block: bytes | bytearray) -> tuple[int, bytes]:
    """COBS-decode then validate. `block` excludes trailing 0x00."""
    return decode_packet(cobs.decode(block))
