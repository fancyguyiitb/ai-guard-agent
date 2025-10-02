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
                        # transcribe via whisper
                        res = self.model.transcribe(tmp_path, language="en")
                        text = res.get("text", "").lower().strip()
                        print(f"[ASR] Transcribed: '{text}'")

                        # check activation phrases
                        if any(phrase in text for phrase in ACTIVATION_PHRASES):
                            print("[ASR] Activation phrase detected!")
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

    def start_in_background(self):
        """Start the listening loop in a daemon thread and return it."""
        t = threading.Thread(target=self.start, daemon=True)
        t.start()
        return t
