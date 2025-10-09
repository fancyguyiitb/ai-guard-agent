# src/utils/config.py
import os

# Activation phrase variants (lowercase)
ACTIVATION_PHRASES = [
    "guard my room",
    "guard the room",
    "guard this room",
    "start guard",
    "start guarding",
    "guarding my room"
]

# Whisper model to use. 'base.en' improves accuracy over 'tiny.en' with small latency hit.
# Tip: for even better accuracy, consider 'small.en' (heavier) if CPU allows.
WHISPER_MODEL = "base.en"

# How many seconds of audio to record per chunk when listening continuously.
# Longer windows can capture the full phrase but add latency (here 7s per user choice).
PHRASE_TIME_LIMIT = 7

# Seconds to sample for ambient noise adjustment before listening loop.
# Increase in noisy rooms to improve VAD threshold stability.
AMBIENT_ADJUST_SECONDS = 3.0

# Optional: pause after detection (seconds) to avoid immediate re-trigger
POST_DETECTION_PAUSE = 1.0

# ---- Face recognition settings ----
# Where enrollment images are stored
ENROLL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "enrolled_faces")
ENROLL_DIR = os.path.abspath(ENROLL_DIR)

# Where to save embeddings (pickle)
EMBEDDINGS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "embeddings.pkl")
EMBEDDINGS_PATH = os.path.abspath(EMBEDDINGS_PATH)

# Face recognition matching threshold (lower = stricter). 0.45-0.6 typical.
# Higher values allow more matches but increase false positives (0.6 chosen).
FACE_MATCH_THRESHOLD = 0.6

# How many images to capture during enrollment by default
# More diverse samples (angles/lighting/expressions) improve recognition robustness.
DEFAULT_ENROLL_COUNT = 30

# Webcam index for face recognition (0 usually)
WEBCAM_INDEX = 0

# ---- Escalation settings ----
ESCALATION_MAX_LEVEL = 3
ESCALATION_WAIT_AFTER_SPEAK = 3.0  # seconds to wait after speaking before checking for trusted user
ESCALATION_CHECK_FRAMES = 30  # number of frames to check for trusted user after speaking
ESCALATION_CHECK_INTERVAL = 0.1  # seconds between frame checks
ESCALATION_UNKNOWN_COOLDOWN = 5.0  # seconds to wait before allowing another unknown face callback

# ---- Logging and snapshots ----
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "logs")
LOGS_DIR = os.path.abspath(LOGS_DIR)
SNAPSHOT_DIR = os.path.join(LOGS_DIR, "snapshots")
SNAPSHOT_DIR = os.path.abspath(SNAPSHOT_DIR)

# ---- TTS and alarm settings ----
ALARM_SOUND_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "alarm.mp3")
ALARM_SOUND_PATH = os.path.abspath(ALARM_SOUND_PATH)

# ---- OpenAI settings (optional) ----
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # Set via environment variable

# ---- Milestone 3: Interaction settings ----
# Secret passcode required for access (set via env). Empty means no passcode configured.
ROOM_SECRET_PASSCODE = os.getenv("ROOM_SECRET_PASSCODE", "").strip()

# Per-level listen durations (seconds); can be overridden via env
def _get_float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default

LEVEL1_LISTEN_SECONDS = _get_float_env("LEVEL1_LISTEN_SECONDS", 6.0)
LEVEL2_LISTEN_SECONDS = _get_float_env("LEVEL2_LISTEN_SECONDS", 6.0)
LEVEL3_LISTEN_SECONDS = _get_float_env("LEVEL3_LISTEN_SECONDS", 0.0)