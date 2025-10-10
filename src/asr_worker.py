"""ASR worker thread that continuously listens and looks for activation phrases.

Design notes:
- Uses `speech_recognition` for microphone capture and VAD-like chunking.
- Writes each captured chunk to a temp WAV file; transcribes via Whisper.
- On detecting any configured activation phrase, asks `StateManager` to switch state.

The implementation favors clarity and portability over exotic optimizations.
"""
# src/asr_worker.py
import speech_recognition as sr
import whisper
import tempfile
import os
import time
import threading

from src.utils.config import ACTIVATION_PHRASES, WHISPER_MODEL, PHRASE_TIME_LIMIT, AMBIENT_ADJUST_SECONDS, POST_DETECTION_PAUSE
from difflib import SequenceMatcher

class ASRWorker:
    """Background speech recognizer that triggers state transitions.

    Parameters
    ----------
    state_manager : StateManager
        Object managing global state transitions (e.g., OFF -> GUARD).
    model_name : str
        Whisper model to load lazily (default from config).
    phrase_time_limit : float
        Max seconds to listen per chunk before transcribing.
    ambient_adjust : float
        Seconds used to calibrate ambient noise threshold.
    """
    def __init__(self, state_manager, model_name=WHISPER_MODEL, phrase_time_limit=PHRASE_TIME_LIMIT, ambient_adjust=AMBIENT_ADJUST_SECONDS):
        self.state_manager = state_manager
        self.phrase_time_limit = phrase_time_limit
        self.recognizer = sr.Recognizer()
        self.model_name = model_name
        self.model = None  # lazy load to avoid heavy cost at import time
        self._running = False
        self.ambient_adjust = ambient_adjust
        self._listening_enabled = True

    def _ensure_model(self):
        """Load Whisper model on first use to keep import time fast."""
        if self.model is None:
            print(f"[ASR] Loading Whisper model '{self.model_name}' (this may take a moment)...")
            self.model = whisper.load_model(self.model_name)
            print("[ASR] Whisper model loaded.")

    def start(self):
        """Blocking listening loop.

        Capture microphone audio, transcribe with Whisper, and trigger
        state changes when an activation phrase is detected. Intended
        to be run inside a background thread.
        """
        self._running = True
        self._ensure_model()

        try:
            with sr.Microphone() as source:
                print("[ASR] Adjusting for ambient noise ({}s)...".format(self.ambient_adjust))
                # calibrate energy threshold for ambient noise
                self.recognizer.adjust_for_ambient_noise(source, duration=self.ambient_adjust)

                while self._running:
                    # Only listen if listening is enabled and we're in OFF state
                    if not self._listening_enabled or self.state_manager.get_state().value != "OFF":
                        time.sleep(1.0)  # Check every second
                        continue
                        
                    print("[ASR] Listening (phrase_time_limit={}s) ...".format(self.phrase_time_limit))
                    try:
                        audio = self.recognizer.listen(source, phrase_time_limit=self.phrase_time_limit)
                    except Exception as e:
                        print("[ASR] Microphone listening error:", e)
                        time.sleep(0.2)
                        continue

                    # write audio bytes to temp WAV file
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                        f.write(audio.get_wav_data())
                        tmp_path = f.name

                    try:
                        # Transcribe via Whisper with CPU-friendly settings.
                        # Notes:
                        # - temperature=0.0 nudges decoding towards most likely output
                        # - no_speech/logprob thresholds help filter accidental captures
                        # - condition_on_previous_text=False reduces cascading errors across chunks
                        res = self.model.transcribe(
                            tmp_path,
                            language="en",
                            temperature=0.0,
                            no_speech_threshold=0.6,
                            logprob_threshold=-0.8,
                            condition_on_previous_text=False,
                        )
                        text = res.get("text", "").lower().strip()
                        print(f"[ASR] Transcribed: '{text}'")

                        # Check activation phrases with fuzzy matching for robustness.
                        # We compare n-gram windows to handle small insertions/omissions.
                        def fuzzy_contains(haystack: str, needle: str, cutoff: float = 0.82) -> bool:
                            if needle in haystack:
                                return True
                            # sliding window approximate match
                            words = haystack.split()
                            n = len(needle.split())
                            for i in range(0, max(1, len(words) - n + 1)):
                                window = " ".join(words[i:i+n])
                                if SequenceMatcher(None, window, needle).ratio() >= cutoff:
                                    return True
                            return False

                        if any(fuzzy_contains(text, phrase) for phrase in ACTIVATION_PHRASES):
                            print("[ASR] Activation phrase detected!")
                            self._listening_enabled = False  # Stop listening until reset to OFF
                            self.state_manager.set_state("GUARD")
                            time.sleep(POST_DETECTION_PAUSE)
                    except Exception as e:
                        print("[ASR] Transcription error:", e)
                    finally:
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass
        except KeyboardInterrupt:
            print("[ASR] Stopped by user")
        except Exception as e:
            print("[ASR] Fatal error:", e)

    def stop(self):
        """Signal the background loop to stop at the next opportunity."""
        self._running = False

    def enable_listening(self):
        """Re-enable listening (call when returning to OFF state)."""
        self._listening_enabled = True
        print("[ASR] Listening re-enabled")

    def disable_listening(self):
        """Disable listening (call when leaving OFF state)."""
        self._listening_enabled = False
        print("[ASR] Listening disabled")

    def start_in_background(self):
        """Start the listening loop in a daemon thread and return it."""
        t = threading.Thread(target=self.start, daemon=True)
        t.start()
        return t
