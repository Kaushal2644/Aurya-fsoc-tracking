"""
core/scene.py
Renders the full virtual scene: background + target(s).
This is the 'ground truth' world. The virtual camera (camera.py)
will later crop a small FOV window out of this large canvas.
"""

import numpy as np
import cv2
import config


class Scene:
    """
    Represents the full 2000x2000 (default) virtual world.
    Monochrome by default (per spec), optional colour.
    """

    def __init__(
        self,
        width=config.SCENE_WIDTH,
        height=config.SCENE_HEIGHT,
        colour=False,
        background_level=20,   # dark background (space-like), 0-255
    ):
        self.width = width
        self.height = height
        self.colour = colour
        self.background_level = background_level

    # ------------------------------------------------------------------
    def _blank_canvas(self):
        if self.colour:
            canvas = np.full((self.height, self.width, 3), self.background_level, dtype=np.uint8)
        else:
            canvas = np.full((self.height, self.width), self.background_level, dtype=np.uint8)
        return canvas

    # ------------------------------------------------------------------
    def render(self, target_manager, intensity=255, shape="square"):
        """
        Draws all targets from a MultiTargetManager onto a fresh canvas.
        Returns the full scene frame (numpy array).
        """
        canvas = self._blank_canvas()

        for target in target_manager.targets:
            x1, y1, x2, y2 = target.get_bbox()

            # Clip bbox to canvas bounds (safety)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(self.width, x2), min(self.height, y2)

            colour_val = (intensity, intensity, intensity) if self.colour else intensity

            if target.shape == "square":
                cv2.rectangle(canvas, (x1, y1), (x2, y2), colour_val, thickness=-1)
            elif target.shape == "circle":
                cx, cy = int(target.x), int(target.y)
                radius = int(target.size / 2)
                cv2.circle(canvas, (cx, cy), radius, colour_val, thickness=-1)
            else:
                # default fallback: square
                cv2.rectangle(canvas, (x1, y1), (x2, y2), colour_val, thickness=-1)

        return canvas

    # ------------------------------------------------------------------
    def add_star_background(self, canvas, num_stars=150, seed=None):
        """
        Optional cosmetic: scatter faint 'stars' in background for realism
        and to give the detector some clutter to be robust against.
        """
        rng = np.random.default_rng(seed)
        for _ in range(num_stars):
            x = rng.integers(0, self.width)
            y = rng.integers(0, self.height)
            brightness = int(rng.integers(40, 120))  # dim, below target intensity
            val = (brightness, brightness, brightness) if self.colour else brightness
            cv2.circle(canvas, (x, y), 1, val, thickness=-1)
        return canvas