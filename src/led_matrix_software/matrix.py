"""LED Matrix buffer conversion utilities"""

import numpy as np

# Bit weights preallocated for vectorization: bit 0 is MSB (1 << 15)
_POWERS_OF_TWO = (1 << np.arange(15, -1, -1, dtype=np.uint16))


def make_matrix_buffer(img: np.ndarray) -> np.ndarray:
    """
    Convert image to LED matrix buffer format using vectorized NumPy operations.

    Args:
        img: Binary image (16 rows, variable width)

    Returns:
        Matrix buffer as uint16 array [8][16] for 128x16 LED matrix
    """
    h, w = img.shape[:2]
    # Fast path: standard 16x128 binary image
    if h == 16 and w >= 128:
        sub = (img[:16, :128] > 127).astype(np.uint16)
        return np.dot(sub.reshape(16, 8, 16).swapaxes(0, 1), _POWERS_OF_TWO)

    # Fallback for images of arbitrary width / height (<128 cols or <16 rows)
    target = np.zeros((16, 128), dtype=np.uint16)
    valid_h = min(h, 16)
    valid_w = min(w, 128)
    if valid_h > 0 and valid_w > 0:
        target[:valid_h, :valid_w] = (img[:valid_h, :valid_w] > 127).astype(np.uint16)

    return np.dot(target.reshape(16, 8, 16).swapaxes(0, 1), _POWERS_OF_TWO)

