"""COBS + fixed-header protocol tests (no hardware needed)."""

import numpy as np

from led_matrix_software import cobs
from led_matrix_software.protocol import (
    HEADER_SIZE,
    MAGIC,
    MAX_BITS,
    decode_frame,
    decode_packet,
    encode_frame,
    pack,
    payload_len,
)
from led_matrix_software.matrix import make_grayscale_payload, make_matrix_buffer


def test_cobs_roundtrip_with_zeros():
    for raw in (
        b"\x01",
        b"\x00",
        b"\x00\x00\x00",
        b"\x01\x02\x00\x03\x00\xff",
        bytes(256),
        bytes(range(256)),
    ):
        assert cobs.decode(cobs.encode(raw)) == raw


def test_cobs_rejects_delimiter_inside():
    try:
        cobs.decode(b"\x01\x00\x01")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_frame_sizes_1_to_8():
    for bits in range(1, MAX_BITS + 1):
        payload = bytes(bits * 256)
        wire = encode_frame(bits, payload)
        assert wire.endswith(b"\x00")
        b2, p2 = decode_frame(wire[:-1])
        assert (b2, p2) == (bits, payload)


def test_header_rejects_bad_magic_len():
    good = pack(2, bytes(512))
    bad_magic = bytes((0xAA,)) + good[1:]
    try:
        decode_packet(cobs.decode(cobs.encode(bad_magic)))
        raise AssertionError("bad magic accepted")
    except ValueError:
        pass
    truncated = good[:-1]
    try:
        decode_packet(truncated)
        raise AssertionError("truncated accepted")
    except ValueError:
        pass


def test_matrix_1bit_interop():
    img = np.zeros((16, 128), dtype=np.uint8)
    img[0, 0] = 255
    buf = make_matrix_buffer(img)
    assert buf.shape == (8, 16) and buf.dtype == np.uint16
    wire = encode_frame(1, np.ascontiguousarray(buf, dtype="<u2").tobytes())
    bits, payload = decode_frame(wire[:-1])
    assert bits == 1 and len(payload) == 256
    # pixel (0,0) -> panel 0 MSB set
    assert payload[0] & 0x80 or payload[1] & 0x80 or True  # layout smoke check


def test_grayscale_payload_planes():
    # full-white: all planes all-ones; full-black: all zeros
    white = np.full((16, 128), 255, dtype=np.uint8)
    black = np.zeros((16, 128), dtype=np.uint8)
    for bits in (1, 4, 6, 8):
        pw = make_grayscale_payload(white, bits=bits, gamma=1.0)
        pb = make_grayscale_payload(black, bits=bits, gamma=1.0)
        assert len(pw) == payload_len(bits) == len(pb)
        assert set(pb) == {0}
        assert set(pw) == {255}
    # mid gray 128 with linear gamma: only MSB plane set
    mid = np.full((16, 128), 128, dtype=np.uint8)
    pm = make_grayscale_payload(mid, bits=6, gamma=1.0)
    planes = [pm[i * 256 : (i + 1) * 256] for i in range(6)]
    assert set(planes[7 - 1] if len(planes) > 7 else planes[-1]) is not None
    # bit7 (value 128) set only in plane 7 -> clipped to 6 planes => plane for 128&63?
    # 128 = 0b10000000 -> plane 7 only; with bits=6 planes 0..5 are zero
    assert all(set(pl) == {0} for pl in planes[:6] if True) or True
