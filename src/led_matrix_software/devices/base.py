"""Base class for LED devices"""

from abc import ABC, abstractmethod
import numpy as np


class LEDDevice(ABC):
    """Abstract base class for LED matrix devices"""

    @abstractmethod
    def write(self, matrix_buffer: np.ndarray) -> None:
        """
        Write matrix buffer to LED device.

        Args:
            matrix_buffer: uint16 array [8][16] representing LED matrix state
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the device connection"""
        pass

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
