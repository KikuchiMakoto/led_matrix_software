"""Serial LED device implementation (COBS binary protocol, no Base64)."""

import numpy as np
import serial

from ..protocol import CMD_BRIGHTNESS, encode_command, encode_frame
from ..matrix import make_grayscale_payload
from .base import LEDDevice


class SerialLEDDevice(LEDDevice):
    """LED matrix device connected via serial port (USB CDC-ACM)."""

    def __init__(self, port: str, baudrate: int = 921600, timeout: int = 1):
        """
        Initialize serial LED device.

        Args:
            port: Serial port name (e.g., '/dev/ttyACM0')
            baudrate: Ignored by USB CDC except 1200bps touch (UF2).
            timeout: Serial timeout in seconds (default: 1)
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        # Set write_timeout=1 to prevent unbounded blocking if USB stalls
        self.serial = serial.Serial(port, baudrate, timeout=timeout, write_timeout=1)

    def write(self, matrix_buffer: np.ndarray) -> None:
        """
        Write 1-bit matrix buffer as MODE=0x01 COBS frame.

        Args:
            matrix_buffer: uint16 array [8][16]
        """
        raw = np.ascontiguousarray(matrix_buffer, dtype="<u2").tobytes()
        if len(raw) != 256:
            raise ValueError(f"matrix_buffer must be 256 bytes, got {len(raw)}")
        self.serial.write(encode_frame(1, raw))

    def write_grayscale(
        self, gray: np.ndarray, bits: int = 8, gamma: float = 2.2, gain: float = 1.0
    ) -> None:
        """
        Write grayscale image as MODE=N COBS frame.

        Args:
            gray: uint8 array (16, 128), values 0..255
            bits: bit depth 1..8
            gamma: gamma exponent
            gain: digital gain 0..1 (software-side brightness)
        """
        payload = make_grayscale_payload(gray, bits=bits, gamma=gamma, gain=gain)
        self.serial.write(encode_frame(bits, payload))

    def set_brightness(self, value: int) -> None:
        """
        Set global display brightness (0..255, default 255).

        Args:
            value: brightness level, scaled on firmware BAM on-times
        """
        if not (0 <= value <= 255):
            raise ValueError("brightness must be 0..255")
        self.serial.write(encode_command(CMD_BRIGHTNESS, value))

    def close(self) -> None:
        """Close serial connection"""
        if self.serial.is_open:
            self.serial.close()
