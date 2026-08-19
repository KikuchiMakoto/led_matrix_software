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
        self.serial = serial.Serial(port, baudrate, timeout=timeout)

    def write(self, matrix_buffer: np.ndarray) -> None:
        """
        Write matrix buffer to serial device.

        The buffer is converted to bytes, base64 encoded, and sent with CRLF.

        Args:
            matrix_buffer: uint16 array [8][16]
        """
        barray = matrix_buffer.tobytes()
        b64 = base64.b64encode(barray) + b"\r\n"
        self.serial.write(b64)

    def close(self) -> None:
        """Close serial connection"""
        if self.serial.is_open:
            self.serial.close()
