# src/escalation.py
import os
import time
import cv2
import threading
import tempfile
from datetime import datetime
import speech_recognition as sr
import whisper
from src.utils.config import (
    ESCALATION_MAX_LEVEL, ESCALATION_WAIT_AFTER_SPEAK, 
    ESCALATION_CHECK_FRAMES, ESCALATION_CHECK_INTERVAL,
    LOGS_DIR, SNAPSHOT_DIR,
    ROOM_SECRET_PASSCODE, LEVEL1_LISTEN_SECONDS, LEVEL2_LISTEN_SECONDS, LEVEL3_LISTEN_SECONDS,
    WHISPER_MODEL
)
from src.llm_agent import LLMAgent
from src.tts import TTSWrapper
from src.utils.audio_gate import AudioGate

class EscalationManager:
    """
    Manages escalation levels when unknown persons are detected.
    Handles dialogue, logging, snapshots, and state transitions.
    """
    
    def __init__(self, state_manager, face_recognizer, llm_mode="rule"):
        """
        Initialize escalation manager.
        
        Args:
            state_manager: StateManager instance for state transitions
            face_recognizer: FaceRecognizer instance for monitoring trusted users
            llm_mode: "rule" or "openai" for response generation
        """
        self.state_manager = state_manager
        self.face_recognizer = face_recognizer
        self.llm_agent = LLMAgent(mode=llm_mode)
        self.tts = TTSWrapper()
        self._sr_recognizer = sr.Recognizer()
        self._whisper_model = None  # lazy load
        
        # Escalation state
        self.current_level = 0
        self.is_escalating = False
        self.escalation_thread = None
        self._stop_escalation = False
        
        # Ensure directories exist
        os.makedirs(LOGS_DIR, exist_ok=True)
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        
        # Log file path
        self.log_file = os.path.join(LOGS_DIR, "events.log")
        
        print("[EscalationManager] Initialized")
    
    def start_escalation(self, face_crop, location):
        """
        Start escalation process for unknown person.
        
        Args:
            face_crop: OpenCV image of the unknown face
            location: (top, right, bottom, left) face location
        """
        if self.is_escalating:
            print("⚠️ [ESCALATION] Already escalating, ignoring new unknown")
            return
        
        # Save snapshot
        self._save_snapshot(face_crop, location)
        
        # Log event
        self._log_event(f"Unknown person detected at {location}, starting escalation")
        
        print("🚨 [ESCALATION] Starting 3-level escalation sequence")
        print("📸 [SNAPSHOT] Unknown face saved to logs")
        
        # Start escalation in separate thread
        self.is_escalating = True
        self.current_level = 0
        self._stop_escalation = False
        # Enter INTERACT state
        try:
            self.state_manager.set_state("INTERACT")
        except Exception:
            pass
        
        self.escalation_thread = threading.Thread(
            target=self._escalation_loop, 
            daemon=True
        )
        self.escalation_thread.start()
    
    def _escalation_loop(self):
        """Main escalation loop implementing Level 1 → Level 2 → Level 3."""
        try:
            if self._stop_escalation:
                return

            # Level 1
            self.current_level = 1
            if self._handle_level(
                level=1,
                prompt=self.llm_agent.generate_response(1, {"instruction": "Ask for name and passcode. Tell user to speak after the beep."}) or "Please state your name and passcode. Speak after the beep.",
                listen_seconds=LEVEL1_LISTEN_SECONDS,
            ):
                return

            if self._stop_escalation:
                return

            # Small wait before next level
            time.sleep(1.0)

            # Level 2 (re-check face before escalating)
            self.current_level = 2
            try:
                if self._check_trusted_user():
                    self._log_event("Trusted user recognized before Level 2, aborting")
                    self.state_manager.set_state("GUARD")
                    return
            except Exception:
                pass
            if self._handle_level(
                level=2,
                prompt=(self.llm_agent.generate_response(2, {"instruction": "Request name, purpose of visit, and passcode. Warn and tell to speak after the beep."}) 
                        or "State your name, purpose of visit, and passcode. If you don't respond, action will be taken. Speak after the beep."),
                listen_seconds=LEVEL2_LISTEN_SECONDS,
            ):
                return

            if self._stop_escalation:
                return

            # Level 3 (re-check face before alarming)
            self.current_level = 3
            try:
                if self._check_trusted_user():
                    self._log_event("Trusted user recognized before Level 3, aborting")
                    self.state_manager.set_state("GUARD")
                    return
            except Exception:
                pass
            self._log_event("Level 3: Alarm will be triggered")
            try:
                # Speak explicit Level 3 message before alarm
                self.tts.speak(
                    "ALARM. You have been captured. Security and the room owner have been notified.",
                    blocking=True,
                )
            except Exception as e:
                print(f"[EscalationManager] TTS error at Level 3: {e}")
            self._trigger_alarm()
                
        except Exception as e:
            print(f"[EscalationManager] Error in escalation loop: {e}")
            self._log_event(f"Escalation error: {e}")
        finally:
            self.is_escalating = False
            self.current_level = 0
            print("[EscalationManager] Escalation ended")

    def _ensure_whisper(self):
        if self._whisper_model is None:
            print(f"[Escalation] Loading Whisper model '{WHISPER_MODEL}'...")
            self._whisper_model = whisper.load_model(WHISPER_MODEL)
            print("[Escalation] Whisper model loaded")

    def _listen_and_transcribe(self, seconds: float) -> str:
        """Record up to `seconds` of audio and return Whisper transcript (lowercased).
        Includes a lightweight retry to improve robustness.
        """
        if seconds <= 0:
            return ""
        self._ensure_whisper()

        try:
            with sr.Microphone() as source:
                # quick ambient adjust for stability
                try:
                    self._sr_recognizer.adjust_for_ambient_noise(source, duration=0.8)
                except Exception:
                    pass
                audio = self._sr_recognizer.listen(source, phrase_time_limit=seconds)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio.get_wav_data())
                tmp_path = f.name

            try:
                res = self._whisper_model.transcribe(
                    tmp_path,
                    language="en",
                    temperature=0.0,
                    no_speech_threshold=0.6,
                    logprob_threshold=-0.8,
                    condition_on_previous_text=False,
                )
                text = (res.get("text", "") or "").lower().strip()
                if text:
                    return text
                # Retry once with slightly different params if first is empty
                res = self._whisper_model.transcribe(
                    tmp_path,
                    language="en",
                    temperature=0.2,
                    no_speech_threshold=0.5,
                    logprob_threshold=-1.0,
                    condition_on_previous_text=False,
                )
                return (res.get("text", "") or "").lower().strip()
            finally:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
        except Exception as e:
            print(f"[Escalation] ASR error: {e}")
            return ""

    def _handle_level(self, level: int, prompt: str, listen_seconds: float) -> bool:
        """
        Handle a single interaction level.

        Returns True if user was trusted and escalation should stop.
        """
        if self._stop_escalation:
            return False

        print(f"🔊 [ESCALATION LEVEL {level}] {prompt}")
        self._log_event(f"Level {level}: prompt='{prompt}'")

        # Speak prompt (audio gate mutes mic inside speak)
        try:
            self.tts.speak(prompt, blocking=True)
        except Exception as e:
            print(f"[EscalationManager] TTS error at Level {level}: {e}")

        # Give a short pause to avoid recording TTS tail
        time.sleep(0.9)

        # Beep to signal start of listening
        try:
            self.tts.beep()
        except Exception:
            pass

        # Listen under mic session to avoid overlap
        gate = AudioGate()
        with gate.mic_session():
            transcript = self._listen_and_transcribe(listen_seconds)
        print(f"[Escalation] Captured transcript (L{level}): '{transcript}'")
        self._log_event(f"Level {level}: transcript='{transcript}'")

        if not transcript:
            self._log_event(f"Level {level}: no response detected → escalate")
            return False

        # Parse identity
        parsed = self.llm_agent.parse_identity(transcript, return_raw=True)
        name = parsed.get("name", "")
        passcode = parsed.get("passcode", "")
        purpose = parsed.get("purpose", "")
        raw = parsed.get("_raw", "")
        self._log_event(
            f"Level {level}: parsed name='{name}', passcode='{passcode}', purpose='{purpose}'"
        )
        print(f"[Escalation] GPT parsed (L{level}): name='{name}', passcode='{passcode}', purpose='{purpose}' | raw={raw}")

        # Decision
        secret = (ROOM_SECRET_PASSCODE or "").strip()
        # Normalize and allow simple synonyms like 'passcode is orange' -> 'orange'
        normalized_a = (passcode or "").strip().lower()
        normalized_b = secret.strip().lower()
        if secret and normalized_a and normalized_a == normalized_b:
            # Trusted
            self._log_event(f"Level {level}: passcode correct → TRUSTED")
            try:
                self.tts.speak("Access granted. You may proceed.", blocking=True)
            except Exception:
                pass
            try:
                self.state_manager.set_state("GUARD")
            except Exception:
                pass
            return True
        else:
            self._log_event(f"Level {level}: passcode incorrect or missing → escalate")
            return False
    
    def _check_trusted_user(self):
        """
        Check if a trusted user appears during escalation.
        Returns True if trusted user detected, False otherwise.
        Performs a one-shot recognition using the webcam.
        """
        print("[EscalationManager] Checking for trusted user...")
        try:
            cap = cv2.VideoCapture(self.face_recognizer.webcam_index)
            if not cap.isOpened():
                return False
            # Grab a couple of frames to allow exposure/AF to settle
            ret, frame = cap.read()
            if not ret:
                cap.release()
                return False
            # Optional small delay and second frame
            time.sleep(0.05)
            ret2, frame2 = cap.read()
            cap.release()
            frame_to_use = frame2 if ret2 else frame
            results = self.face_recognizer.recognize_frame(frame_to_use)
            for r in results:
                name = r.get("name")
                if name and name != "unknown":
                    print(f"[EscalationManager] Trusted user now recognized: {name}")
                    return True
            return False
        except Exception as e:
            print(f"[EscalationManager] Quick recognition check failed: {e}")
            return False
    
    def _trigger_alarm(self):
        """Trigger alarm and transition to ALARM state."""
        print("🚨 [ALARM TRIGGERED] Maximum escalation reached!")
        print("🔊 [ALARM] Playing alarm sound and transitioning to ALARM state")
        self._log_event("Maximum escalation reached, triggering alarm")
        
        # Transition to ALARM state
        self.state_manager.set_state("ALARM")
        
        # Play alarm sound
        self.tts.play_alarm()
    
    def _save_snapshot(self, face_crop, location):
        """Save snapshot of unknown face."""
        try:
            timestamp = int(time.time())
            filename = f"unknown_{timestamp}_{location[0]}_{location[1]}_{location[2]}_{location[3]}.jpg"
            filepath = os.path.join(SNAPSHOT_DIR, filename)
            
            cv2.imwrite(filepath, face_crop)
            print(f"[EscalationManager] Saved snapshot: {filename}")
            
        except Exception as e:
            print(f"[EscalationManager] Error saving snapshot: {e}")
    
    def _log_event(self, message):
        """Log event to file with timestamp."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] {message}\n"
            
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
                
        except Exception as e:
            print(f"[EscalationManager] Error logging event: {e}")
    
    def stop_escalation(self):
        """Stop current escalation process."""
        if self.is_escalating:
            print("🛑 [ESCALATION STOPPED] Trusted user detected, aborting escalation")
            self._stop_escalation = True
            self._log_event("Escalation stopped by trusted user")
            
            # Avoid joining if we're currently in the escalation thread
            if self.escalation_thread and threading.current_thread() is not self.escalation_thread:
                self.escalation_thread.join(timeout=2.0)
    
    def reset(self):
        """Reset escalation manager state."""
        self.stop_escalation()
        self.current_level = 0
        self.is_escalating = False
        self._stop_escalation = False
        print("[EscalationManager] Reset completed")
