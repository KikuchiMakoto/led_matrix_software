"""Serial LED device implementation"""

import base64
import numpy as np
import serial

from .base import LEDDevice


class SerialLEDDevice(LEDDevice):
    """LED matrix device connected via serial port"""

    def __init__(self, port: str, baudrate: int = 921600, timeout: int = 1):
        """
        Initialize serial LED device.

        Args:
            port: Serial port name (e.g., 'COM23' or '/dev/ttyUSB0')
            baudrate: Communication speed (default: 921600)
            timeout: Serial timeout in seconds (default: 1)
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        # Set write_timeout=1 to prevent unbounded blocking if UART stalls
        self.serial = serial.Serial(port, baudrate, timeout=timeout, write_timeout=1)
        # Preallocate reusable bytearray: 8x16 uint16 = 256 bytes raw -> 344 bytes base64 + 2 CRLF = 346 bytes
        self._raw_buf = bytearray(256)

    def write(self, matrix_buffer: np.ndarray) -> None:
        """
        Write matrix buffer to serial device without intermediate copies.

        Args:
            matrix_buffer: uint16 array [8][16]
        """
        b64 = base64.b64encode(matrix_buffer.data) + b"\r\n"
        self.serial.write(b64)

    def close(self) -> None:
        """Close serial connection"""
        if self.serial.is_open:
            self.serial.close()
