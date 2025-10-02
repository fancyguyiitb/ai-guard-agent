# src/state_manager.py
import threading
import time
from enum import Enum

class State(Enum):
    OFF = "OFF"
    GUARD = "GUARD"
    INTERACT = "INTERACT"
    ALARM = "ALARM"

class StateManager:
    def __init__(self, initial=State.OFF):
        self._state = initial
        self._lock = threading.Lock()
        self._callbacks = []

    def get_state(self):
        with self._lock:
            return self._state

    def set_state(self, new_state):
        """Accepts either State enum or string like 'GUARD'."""
        if isinstance(new_state, str):
            try:
                new_state = State[new_state]
            except Exception:
                # try match by value (e.g., "GUARD")
                try:
                    new_state = State(new_state)
                except Exception:
                    new_state = State.OFF

        with self._lock:
            old = self._state
            self._state = new_state

        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[StateManager] {ts} - {old.value} -> {new_state.value}")
        for cb in self._callbacks:
            try:
                cb(old, new_state)
            except Exception as e:
                print("[StateManager] callback error:", e)

    def register_callback(self, fn):
        """fn(old_state, new_state)"""
        self._callbacks.append(fn)
