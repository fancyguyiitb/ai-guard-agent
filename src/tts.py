import threading
import pyttsx3


class TTSWrapper:
    """Thin wrapper around pyttsx3 with non-blocking speak() support."""

    def __init__(self):
        self._engine = None
        self._lock = threading.Lock()

    def _ensure_engine(self):
        if self._engine is None:
            with self._lock:
                if self._engine is None:
                    self._engine = pyttsx3.init()

    def speak(self, text: str, async_mode: bool = True):
        self._ensure_engine()
        if async_mode:
            t = threading.Thread(target=self._speak_blocking, args=(text,), daemon=True)
            t.start()
        else:
            self._speak_blocking(text)

    def _speak_blocking(self, text: str):
        try:
            with self._lock:
                self._engine.say(text)
                self._engine.runAndWait()
        except Exception:
            # Keep silent if audio backend isn't available
            pass



