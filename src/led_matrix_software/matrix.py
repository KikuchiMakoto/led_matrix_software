"""LED Matrix buffer conversion utilities"""

import numpy as np


def make_matrix_buffer(img: np.ndarray) -> np.ndarray:
    """
    Convert image to LED matrix buffer format.

    Args:
        img: Binary image (16 rows, variable width)

    Returns:
        Matrix buffer as uint16 array [8][16] for 128x16 LED matrix
    """
    matrix_buffer = np.zeros((4 * 2, 16), dtype=np.uint16)

    for x in range(8):
        for y in range(16):
            matrix_buffer[x][y] = 0x0000
            for bit in range(16):
                xindex = x * 16 + bit
                yindex = y
                # out of range check
                if xindex >= img.shape[1]:
                    continue
                if yindex >= img.shape[0]:
                    continue
                if img[yindex, xindex] > 127:
                    matrix_buffer[x][y] |= 1 << (15 - bit)
    return matrix_buffer
