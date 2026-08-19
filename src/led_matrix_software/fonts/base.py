"""Base class for font renderers"""

from abc import ABC, abstractmethod
import numpy as np


class FontRenderer(ABC):
    """Abstract base class for font renderers"""

    @abstractmethod
    def render_string(self, text: str) -> np.ndarray:
        """
        Render text string to binary image.

        Args:
            text: Text to render

        Returns:
            Binary image (height=16, variable width)
        """
        pass

    @abstractmethod
    def get_char_image(self, char: str) -> np.ndarray:
        """
        Get image for a single character.

        Args:
            char: Single character

        Returns:
            Character image or None if not found
        """
        pass
