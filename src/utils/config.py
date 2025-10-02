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
AMBIENT_ADJUST_SECONDS = 2.0

# Optional: pause after detection (seconds) to avoid immediate re-trigger
POST_DETECTION_PAUSE = 1.0


