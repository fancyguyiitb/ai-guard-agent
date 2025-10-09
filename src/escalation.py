import os
import time
import threading
import cv2
from typing import Optional

from src.state_manager import StateManager, State
from src.tts import TTSWrapper
from src.utils.config import ESCALATION_MAX_LEVEL, ESCALATION_WAIT_BETWEEN_LEVELS, ESCALATION_ALARM_DURATION_SECONDS, SNAPSHOT_DIR
from src.utils.logger import get_logger


class EscalationManager:
    """Simplified hard-coded escalation flow for unknown faces.

    Public API:
      - start(face_frame_bgr): begins escalation in a background thread
      - reset(): stops any alarm/escalation and returns to GUARD state
    """

    def __init__(self, state_manager: StateManager, tts: Optional[TTSWrapper] = None, alarm_sound_path: str = None):
        self.state_manager = state_manager
        self.tts = tts or TTSWrapper()
        self.alarm_sound_path = alarm_sound_path or os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "alarm.mp3")
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._logger = get_logger("Escalation")
        self._current_level = 0

        os.makedirs(SNAPSHOT_DIR, exist_ok=True)

    def start(self, face_frame_bgr):
        if self._running:
            return
        self._running = True
        self._current_level = 0
        # take a snapshot immediately for auditing
        try:
            ts = int(time.time())
            snap_path = os.path.join(SNAPSHOT_DIR, f"unknown_{ts}.jpg")
            cv2.imwrite(snap_path, face_frame_bgr)
            self._logger.warning("Snapshot saved: %s", snap_path)
        except Exception as e:
            self._logger.error("Failed to save snapshot: %s", e)

        self._thread = threading.Thread(target=self._run_escalation, daemon=True)
        self._thread.start()

    def is_running(self) -> bool:
        return self._running

    def _run_escalation(self):
        try:
            for level in range(1, ESCALATION_MAX_LEVEL + 1):
                if not self._running:
                    return
                self._current_level = level
                if level == 1:
                    msg = "Excuse me, I don’t recognize you. Please identify yourself."
                    self._logger.warning("Escalation Level 1: %s", msg)
                    # Speak synchronously to ensure it is heard before delay
                    self.tts.speak(msg, async_mode=False)
                elif level == 2:
                    msg = "You are not authorized to be here. Please leave immediately."
                    self._logger.warning("Escalation Level 2: %s", msg)
                    self.tts.speak(msg, async_mode=False)
                else:
                    msg = "ALERT. Intruder detected. Security and the room owner have been notified."
                    self._logger.error("Escalation Level 3: %s", msg)
                    self.tts.speak(msg, async_mode=False)
                    # Raise alarm state and play alarm sound
                    self.state_manager.set_state(State.ALARM)
                    self._play_alarm()

                # wait before next level unless already at max
                if level < ESCALATION_MAX_LEVEL:
                    # Fixed delay between levels with deadline loop
                    self._logger.debug("Waiting %ds before next escalation level...", ESCALATION_WAIT_BETWEEN_LEVELS)
                    deadline = time.time() + ESCALATION_WAIT_BETWEEN_LEVELS
                    while self._running and time.time() < deadline:
                        time.sleep(0.2)
                    if not self._running:
                        return
                    self._logger.debug("Proceeding to next escalation level")
            # After escalation finishes, wait here until a trusted face resets or
            # an activation phrase transitions us back to GUARD.
            while self._running and self.state_manager.get_state() != State.GUARD:
                time.sleep(0.5)
        except Exception as e:
            self._logger.error("Escalation thread error at level %d: %s", self._current_level, e, exc_info=True)
        finally:
            # If we reached here without reset, remain in current state (ALARM or GUARD if reset changed it)
            self._running = False

    def _play_alarm(self):
        """Emit an annoying beep on Windows; fallback to ASCII bell elsewhere.

        Continues for up to ~15s or until reset/state change from ALARM.
        """
        try:
            start = time.time()
            try:
                import winsound  # Windows standard lib
                while self._running and self.state_manager.get_state() == State.ALARM and (time.time() - start) < ESCALATION_ALARM_DURATION_SECONDS:
                    winsound.Beep(1000, 300)  # 1000 Hz for 300 ms
                    time.sleep(0.2)
            except Exception:
                # Fallback: ASCII bell
                while self._running and self.state_manager.get_state() == State.ALARM and (time.time() - start) < ESCALATION_ALARM_DURATION_SECONDS:
                    try:
                        print('\a', end='', flush=True)
                    except Exception:
                        pass
                    time.sleep(0.5)
        except Exception as e:
            self._logger.error("Failed to play alarm: %s", e)

    def reset(self):
        """Stop escalation/alarm and return to GUARD."""
        self._running = False
        self.state_manager.set_state(State.GUARD)
        self._logger.info("Escalation reset -> GUARD")


