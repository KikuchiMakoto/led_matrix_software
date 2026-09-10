"""AIEmulatorDevice tests (headless, no hardware)."""

import numpy as np

from led_matrix_software.devices import AIEmulatorDevice
from led_matrix_software.matrix import make_grayscale_payload, make_matrix_buffer


def test_write_roundtrip_single_pixel():
    dev = AIEmulatorDevice()
    img = np.zeros((16, 128), dtype=np.uint8)
    img[5, 10] = 255
    img[0, 127] = 255
    dev.write(make_matrix_buffer(img))
    frame = dev.latest_frame
    assert frame.shape == (16, 128) and frame.dtype == np.uint8
    assert frame[5, 10] == 255
    assert frame[0, 127] == 255
    assert frame.sum() == 255 * 2
    assert dev.frame_count == 1


def test_write_grayscale_tone_curve():
    dev = AIEmulatorDevice()
    gray = np.tile((np.arange(128, dtype=np.uint8) * 2), (16, 1))
    dev.write_grayscale(gray, bits=8, gamma=2.2, gain=110 / 255)
    frame = dev.latest_frame
    # monotonic ramp, dimmer than input (gain), nonzero stays lit
    assert frame[:, 0].max() == 0
    assert frame[:, -1].max() > 100
    row = frame[0].astype(int)
    assert all(b >= a for a, b in zip(row, row[1:]))
    assert dev.frame_count == 1


def test_stats_and_history():
    dev = AIEmulatorDevice(history_len=4)
    img = np.zeros((16, 128), dtype=np.uint8)
    for i in range(6):
        img.fill(i)
        dev.write(make_matrix_buffer((img > 127).astype(np.uint8) * 255))
    assert dev.frame_count == 6
    assert len(dev.history) == 4  # bounded
    assert dev.fps() >= 0.0
    assert dev.jitter_ms() >= 0.0
    dev.reset_stats()
    assert dev.frame_count == 0 and len(dev.history) == 0
