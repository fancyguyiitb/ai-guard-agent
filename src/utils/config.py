"""Centralized configuration for ASR behavior and activation phrases.

This module groups constants used by the ASR loop and tests. Adjust
values here to tweak responsiveness and phrasing without touching logic.
"""
# src/utils/config.py
import os

# Activation phrase variants (lowercase). Keep short and distinctive
# to reduce false-positives from background speech.
ACTIVATION_PHRASES = [
    "guard my room",
    "guard the room",
    "guard this room",
    "start guard",
    "start guarding",
    "guarding my room"
]

# Whisper model to use. 'tiny.en' is small + fast for English-only transcription.
# Larger models improve accuracy at the cost of latency and RAM.
WHISPER_MODEL = "tiny.en"

# How many seconds of audio to record per chunk when listening continuously.
PHRASE_TIME_LIMIT = 4

# Seconds to sample for ambient noise adjustment before listening loop.
# Increase in noisy environments to stabilize the energy threshold.
AMBIENT_ADJUST_SECONDS = 2.0

# Optional: pause after detection (seconds) to avoid immediate re-trigger.
# Helps prevent rapid oscillations if the phrase appears repeatedly.
POST_DETECTION_PAUSE = 1.0


