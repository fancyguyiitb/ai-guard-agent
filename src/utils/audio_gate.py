import threading
from contextlib import contextmanager
import time


class AudioGate:
    """
    Coordinates full-duplex audio to prevent feedback loops and device contention.

    - When TTS is speaking, the gate is muted, so mic users should pause.
    - Mic sessions are serialized via a lock to avoid multiple listeners.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_once()
        return cls._instance

    def _init_once(self):
        self._muted = threading.Event()
        self._mic_lock = threading.Lock()

    def is_muted(self) -> bool:
        return self._muted.is_set()

    def mute_on(self):
        self._muted.set()

    def mute_off(self):
        self._muted.clear()

    @contextmanager
    def tts_speaking(self):
        """Context during which the mic should be muted."""
        self.mute_on()
        try:
            # brief delay to allow any active listeners to yield
            time.sleep(0.05)
            yield
        finally:
            # small tail to avoid recording TTS end
            time.sleep(0.30)
            self.mute_off()

    @contextmanager
    def mic_session(self, wait_while_muted: bool = True, poll_interval: float = 0.05):
        """
        Acquire exclusive access to the microphone. Optionally wait until not muted.
        """
        if wait_while_muted:
            while self.is_muted():
                time.sleep(poll_interval)
        self._mic_lock.acquire()
        try:
            yield
        finally:
            self._mic_lock.release()


