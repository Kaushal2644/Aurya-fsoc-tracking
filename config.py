"""
Central configuration for the FSOC Virtual Camera Tracking System.
All values sourced from SIH26169 'Parameters and Specifications' table.
"""

# ---- Scene ----
SCENE_WIDTH = 2000
SCENE_HEIGHT = 2000

# ---- Camera ----
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FOV_DEG = (4.0, 3.0)       # (horizontal, vertical) degrees
CAMERA_UPDATE_RATE_HZ = 30
CAMERA_INITIAL_POS = "center"      # center of scene

# ---- Target ----
TARGET_SIZE_RANGE = (5, 20)        # px, square default
TARGET_SIZE_DEFAULT = 10
NUM_TARGETS_DEFAULT = 1
TARGET_MOTION_TYPES = ["straight_line", "circular", "figure_8", "random"]
TARGET_MOTION_DEFAULT = "random"
TARGET_INITIAL_LOCATION = "random"  # or (x, y)

# ---- Camera motion constraints ----
MAX_PAN_SPEED_DEG_S = 5.0
MAX_TILT_SPEED_DEG_S = 5.0
CONTROL_UPDATE_RATE_HZ = 20

# ---- Performance targets (for self-evaluation) ----
TARGET_ACQUISITION_TIME_S = 2.0
TARGET_TRACKING_ERROR_PX = 10.0
TARGET_LOSS_RATE_MAX = 0.05
TARGET_REACQUISITION_TIME_S = 1.0
TARGET_PROCESSING_FPS_MIN = 20.0

# ---- Disturbances ----
NOISE_TYPES = ["salt_pepper", "gaussian", "poisson"]
SALT_PEPPER_AMOUNT = 0.10          # 10% of image
GAUSSIAN_NOISE_MAX_STD = 20.0      # pixels intensity std
CAMERA_JITTER_MAX_PX = 20          # per frame
PLATFORM_MOTION_MAX_PX = 20        # per frame
ATMOSPHERIC_PRESETS = ["clear", "haze", "fog", "rain", "low_light"]

# ---- PID gains (tune later) ----
PID_KP = 0.05
PID_KI = 0.001
PID_KD = 0.01