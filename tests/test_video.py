"""Video mode tests (synthetic clip, headless emulator + image devices)."""

import cv2
import numpy as np

from led_matrix_software.devices import AIEmulatorDevice, ImageSimulator
from led_matrix_software.video import VideoPlayer, frame_to_gray


def _make_clip(path: str, n: int = 10, w: int = 96, h: int = 48) -> None:
    out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 30, (w, h))
    for i in range(n):
        img = np.zeros((h, w, 3), dtype=np.uint8)
        img[:, (i * 8) % w : ((i * 8) % w) + 8] = 255
        out.write(img)
    out.release()


def test_frame_to_gray_geometry():
    # 4:3 source -> center crop keeps aspect (no vertical squash)
    img = np.zeros((360, 480), dtype=np.uint8)
    img[150:210, :] = 200
    g = frame_to_gray(img)
    assert g.shape == (16, 128)
    assert abs(float(g.mean()) - 200) < 1.0
    s = frame_to_gray(img, aspect="stretch")
    assert abs(float(s.mean()) - 200 * 60 / 360) < 2.0


def test_video_player_emulator(tmp_path):
    clip = str(tmp_path / "clip.mp4")
    _make_clip(clip)
    dev = AIEmulatorDevice()
    player = VideoPlayer(dev, clip, fps=60, bits=8)
    n = player.run()
    assert n == 10
    assert dev.frame_count == 10
    assert dev.latest_frame.shape == (16, 128)
    assert dev.latest_frame.max() > 0


def test_video_player_image(tmp_path):
    clip = str(tmp_path / "clip.mp4")
    _make_clip(clip)
    dev = ImageSimulator(output_dir=str(tmp_path / "out"))
    player = VideoPlayer(dev, clip, fps=60, bits=4)
    assert player.run() == 10
    assert len(dev.frames) == 10
    dev.close()
    assert (tmp_path / "out" / "animation.mp4").exists()
