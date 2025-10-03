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

# Whisper model to use. 'tiny.en' is small + fast for English-only transcription.
WHISPER_MODEL = "tiny.en"

# How many seconds of audio to record per chunk when listening continuously.
PHRASE_TIME_LIMIT = 4

# Seconds to sample for ambient noise adjustment before listening loop.
AMBIENT_ADJUST_SECONDS = 1.0

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
FACE_MATCH_THRESHOLD = 0.50

# How many images to capture during enrollment by default
DEFAULT_ENROLL_COUNT = 8

# Webcam index for face recognition (0 usually)
WEBCAM_INDEX = 0
