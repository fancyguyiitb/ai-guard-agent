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

# ---- Logging settings ----
# Directory and file for consolidated logs (console still prints; file stores all events)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".."))
LOG_DIR = os.path.join(BASE_DIR, "data", "logs")
LOG_FILE = os.path.join(LOG_DIR, "events.log")