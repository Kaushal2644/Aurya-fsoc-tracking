"""
core/target.py
Defines the moving beacon target(s) within the virtual scene.
Implements required motion models: straight_line, circular, figure_8, random
Optional: spiral, sinusoidal
"""

import numpy as np
import random
import config


class Target:
    """
    Represents a single beacon spot target moving within the scene.
    Ground-truth position is tracked internally and used later
    for computing tracking error against detector output.
    """

    def __init__(
        self,
        scene_width=config.SCENE_WIDTH,
        scene_height=config.SCENE_HEIGHT,
        motion_type=config.TARGET_MOTION_DEFAULT,
        size=config.TARGET_SIZE_DEFAULT,
        shape="square",
        initial_pos=None,
        speed=100.0,
        rng=None,              # NEW: seeded random.Random instance for reproducible spawns
    ):
        self._rng = rng or random.Random()
        self.scene_w = scene_width
        self.scene_h = scene_height
        self.motion_type = motion_type
        self.size = size
        self.shape = shape
        self.speed = speed

        # Time accumulator drives motion equations
        self.t = 0.0

        # Initial position
        # Initial position
        if initial_pos == "random" or initial_pos is None:
            self.x = self._rng.uniform(size, scene_width - size)
            self.y = self._rng.uniform(size, scene_height - size)
        else:
            self.x, self.y = initial_pos

        # Store starting point (used as anchor for parametric motions)
        self.origin_x = self.x
        self.origin_y = self.y

        # Random parameters for 'random' motion mode
        self._rand_target = self._new_random_waypoint()

        # Direction for straight_line motion
        angle = self._rng.uniform(0, 2 * np.pi)
        self.direction = np.array([np.cos(angle), np.sin(angle)])

        # Phase offset for time-parametric motions (circular, figure_8,
        # spiral) — without this, every target on the same motion type
        # would trace an identical path since those formulas depend only
        # on elapsed time, not on the target's own state.
        self._phase_offset = self._rng.uniform(0, 2 * np.pi)

    # ------------------------------------------------------------------
    def _new_random_waypoint(self):
        return np.array([
            self._rng.uniform(self.size, self.scene_w - self.size),
            self._rng.uniform(self.size, self.scene_h - self.size),
        ])

    def _clamp_to_scene(self):
        self.x = np.clip(self.x, self.size, self.scene_w - self.size)
        self.y = np.clip(self.y, self.size, self.scene_h - self.size)

    # ------------------------------------------------------------------
    def update(self, dt):
        """
        Advance target position by dt seconds according to motion_type.
        """
        self.t += dt

        if self.motion_type == "straight_line":
            self._update_straight_line(dt)
        elif self.motion_type == "circular":
            self._update_circular()
        elif self.motion_type == "figure_8":
            self._update_figure_8()
        elif self.motion_type == "random":
            self._update_random(dt)
        elif self.motion_type == "spiral":
            self._update_spiral()
        elif self.motion_type == "sinusoidal":
            self._update_sinusoidal()
        else:
            raise ValueError(f"Unknown motion_type: {self.motion_type}")

        self._clamp_to_scene()
        return self.x, self.y

    # ------------------------------------------------------------------
    def _update_straight_line(self, dt):
        self.x += self.direction[0] * self.speed * dt
        self.y += self.direction[1] * self.speed * dt

        # Bounce off scene edges so target stays in view over time
        if self.x <= self.size or self.x >= self.scene_w - self.size:
            self.direction[0] *= -1
        if self.y <= self.size or self.y >= self.scene_h - self.size:
            self.direction[1] *= -1

    def _update_circular(self, radius=150.0, angular_speed=0.8):
        cx, cy = self.scene_w / 2, self.scene_h / 2
        # phase_offset differentiates multiple targets on the same circular
        # path (otherwise every target converges to an identical position,
        # since this formula is purely a function of time)
        self.x = cx + radius * np.cos(angular_speed * self.t + self._phase_offset)
        self.y = cy + radius * np.sin(angular_speed * self.t + self._phase_offset)

    def _update_figure_8(self, radius=300.0, angular_speed=0.6):
        cx, cy = self.scene_w / 2, self.scene_h / 2
        phase = angular_speed * self.t + self._phase_offset
        self.x = cx + radius * np.sin(phase)
        self.y = cy + radius * np.sin(phase) * np.cos(phase)

    def _update_random(self, dt, waypoint_threshold=5.0):
        """Random walk: move toward a random waypoint, pick new one on arrival."""
        pos = np.array([self.x, self.y])
        direction = self._rand_target - pos
        dist = np.linalg.norm(direction)

        if dist < waypoint_threshold:
            self._rand_target = self._new_random_waypoint()
        else:
            direction = direction / dist
            pos += direction * self.speed * dt
            self.x, self.y = pos[0], pos[1]

    def _update_spiral(self, growth_rate=15.0, angular_speed=1.2):
        cx, cy = self.scene_w / 2, self.scene_h / 2
        radius = growth_rate * self.t
        radius = radius % (min(self.scene_w, self.scene_h) / 2 - self.size)
        phase = angular_speed * self.t + self._phase_offset
        self.x = cx + radius * np.cos(phase)
        self.y = cy + radius * np.sin(phase)

    def _update_sinusoidal(self, amplitude=250.0, freq=0.5):
        self.x = (self.x + self.speed * 0.016) % self.scene_w  # drift rightward, wraps
        self.y = self.origin_y + amplitude * np.sin(freq * self.t)

    # ------------------------------------------------------------------
    def get_position(self):
        return self.x, self.y

    def get_bbox(self):
        """Returns (x1, y1, x2, y2) for rendering/ground-truth comparison."""
        half = self.size / 2
        return (
            int(self.x - half), int(self.y - half),
            int(self.x + half), int(self.y + half),
        )


class MultiTargetManager:
    """
    Manages multiple Target instances (optional feature: 'multiple targets').
    """

    def __init__(self, num_targets=config.NUM_TARGETS_DEFAULT, **target_kwargs):
        base_rng = target_kwargs.pop("rng", None)
        self.targets = []
        for i in range(num_targets):
            kwargs = dict(target_kwargs)
            if base_rng is not None:
                # Derive a distinct but deterministic RNG per target, so
                # multiple targets don't spawn identically on top of each
                # other (same shared RNG = same draws = same position),
                # while the whole multi-target scenario stays reproducible
                # given the same base seed.
                import random as _random_module
                derived_seed = base_rng.randint(0, 2**31 - 1)
                kwargs["rng"] = _random_module.Random(derived_seed)
            self.targets.append(Target(**kwargs))

    def update(self, dt):
        return [t.update(dt) for t in self.targets]

    def get_all_positions(self):
        return [t.get_position() for t in self.targets]

    def get_all_bboxes(self):
        return [t.get_bbox() for t in self.targets]