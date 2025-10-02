"""Simple thread-safe state manager with callback hooks.

States represent high-level modes of the agent. Callbacks are invoked
on each transition, enabling modules like UI, TTS, or logging to react.
"""
# src/state_manager.py
import threading
import time
from enum import Enum

class State(Enum):
    """Top-level agent states."""
    OFF = "OFF"
    GUARD = "GUARD"
    INTERACT = "INTERACT"
    ALARM = "ALARM"

class StateManager:
    """Owns the current state and notifies registered listeners on changes."""
    def __init__(self, initial=State.OFF):
        self._state = initial
        self._lock = threading.Lock()
        self._callbacks = []

    def get_state(self):
        """Return the current state (thread-safe)."""
        with self._lock:
            return self._state

    def set_state(self, new_state):
        """Update the state and notify callbacks.

        Accepts either a `State` enum or a string (e.g., 'GUARD').
        Falls back to `State.OFF` if parsing fails.
        """
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
        """Register a listener of signature: fn(old_state, new_state)."""
        self._callbacks.append(fn)
