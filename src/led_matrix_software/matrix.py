"""LED Matrix buffer conversion utilities"""

import numpy as np

# Bit weights preallocated for vectorization: bit 0 is MSB (1 << 15)
_POWERS_OF_TWO = (1 << np.arange(15, -1, -1, dtype=np.uint16))

# Gamma LUT cache: gamma -> uint8[256]
_GAMMA_LUTS: dict[float, np.ndarray] = {}


def gamma_lut(gamma: float = 2.2) -> np.ndarray:
    """Return uint8 gamma correction LUT (cached per gamma value)."""
    if gamma not in _GAMMA_LUTS:
        x = np.arange(256, dtype=np.float64) / 255.0
        _GAMMA_LUTS[gamma] = np.round(255.0 * np.power(x, gamma)).astype(np.uint8)
    return _GAMMA_LUTS[gamma]


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


def _binary_to_matrix_buffer(binary: np.ndarray) -> np.ndarray:
    """Convert 16x128 binary (0/1) uint image to [8][16] uint16 buffer."""
    return np.dot(binary.reshape(16, 8, 16).swapaxes(0, 1), _POWERS_OF_TWO)


def matrix_buffer_to_image(matrix_buffer: np.ndarray) -> np.ndarray:
    """Convert [8][16] uint16 buffer to 16x128 uint8 image (0/255)."""
    buf = np.ascontiguousarray(matrix_buffer, dtype="<u2").reshape(8, 16)
    img = np.zeros((16, 128), dtype=np.uint8)
    shifts = np.arange(15, -1, -1, dtype=np.uint16)
    for g in range(8):
        bits = ((buf[g][:, None] >> shifts) & 1).astype(np.uint8)
        img[:, g * 16 : (g + 1) * 16] = bits * 255
    return img


def make_grayscale_payload(
    gray: np.ndarray, bits: int = 8, gamma: float = 2.2, gain: float = 1.0
) -> bytes:
    """Convert 16x128 grayscale uint8 image to plane-major payload bytes.

    All tonal adjustment lives here (firmware stays at full brightness).

    Args:
        gray: uint8 array (16, 128), values 0..255.
        bits: bit depth 1..8 (LSB-first planes).
        gamma: gamma correction exponent (2.2 default, 1.0 = linear).
        gain: digital gain 0..1 (1.0 default). E.g. 110/255 reproduces
            the reference look previously made with firmware brightness.

    Returns:
        bytes of length bits*256, plane-major, each plane [8][16] uint16LE.
    """
    from .protocol import MAX_BITS, MIN_BITS

    if not (MIN_BITS <= bits <= MAX_BITS):
        raise ValueError(f"bits must be {MIN_BITS}..{MAX_BITS}, got {bits}")
    h, w = gray.shape[:2]
    target = np.zeros((16, 128), dtype=np.uint8)
    vh, vw = min(h, 16), min(w, 128)
    if vh > 0 and vw > 0:
        g = gray[:vh, :vw]
        if g.dtype != np.uint8:
            g = np.clip(g, 0, 255).astype(np.uint8)
        target[:vh, :vw] = g
    corrected = gamma_lut(gamma)[target].astype(np.float32) * gain
    corrected = np.clip(corrected, 0, 255).astype(np.uint8)
    # Lift: gamma crushes small inputs to 0, which would stay fully dark
    # (LED Vf threshold). Guarantee LSB so nonzero inputs glow faintly.
    corrected = np.where((target > 0) & (corrected == 0), 1, corrected)
    # planes: (bits, 16, 128) binary
    shifts = np.arange(bits, dtype=np.uint8)[:, None, None]
    planes_bin = ((corrected[None, :, :] >> shifts) & 1).astype(np.uint16)
    out = bytearray()
    for p in range(bits):
        buf = _binary_to_matrix_buffer(planes_bin[p])
        out.extend(buf.astype("<u2", copy=False).tobytes())
    return bytes(out)

