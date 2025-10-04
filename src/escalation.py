# src/escalation.py
import os
import time
import cv2
import threading
from datetime import datetime
from src.utils.config import (
    ESCALATION_MAX_LEVEL, ESCALATION_WAIT_AFTER_SPEAK, 
    ESCALATION_CHECK_FRAMES, ESCALATION_CHECK_INTERVAL,
    LOGS_DIR, SNAPSHOT_DIR
)
from src.llm_agent import LLMAgent
from src.tts import TTSWrapper

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
        
        self.escalation_thread = threading.Thread(
            target=self._escalation_loop, 
            daemon=True
        )
        self.escalation_thread.start()
    
    def _escalation_loop(self):
        """Main escalation loop that progresses through levels."""
        try:
            while (self.current_level < ESCALATION_MAX_LEVEL and 
                   not self._stop_escalation and 
                   self.state_manager.get_state().value == "GUARD"):
                
                self.current_level += 1
                print(f"🔊 [ESCALATION LEVEL {self.current_level}] Starting escalation level {self.current_level}/3")
                
                try:
                    # Generate and speak response
                    response = self.llm_agent.generate_response(self.current_level)
                    self._log_event(f"Level {self.current_level}: {response}")
                    
                    print(f"🗣️ [TTS] Level {self.current_level}: '{response}'")
                    # Speak the response with explicit error handling
                    try:
                        self.tts.speak(response, blocking=True)
                        print(f"✅ [TTS] Level {self.current_level} speech completed")
                    except Exception as tts_error:
                        print(f"❌ [TTS ERROR] Level {self.current_level}: {tts_error}")
                        # Try a simple fallback
                        try:
                            import subprocess
                            subprocess.run(['powershell', '-Command', f'Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{response}")'], 
                                         check=False, capture_output=True)
                            print(f"✅ [FALLBACK TTS] Level {self.current_level} completed")
                        except Exception as fallback_error:
                            print(f"❌ [FALLBACK TTS ERROR]: {fallback_error}")
                    
                except Exception as e:
                    print(f"[EscalationManager] Error in level {self.current_level}: {e}")
                    self._log_event(f"Error in level {self.current_level}: {e}")
                
                # Wait after speaking to ensure TTS completes
                print(f"⏳ [ESCALATION] Waiting {ESCALATION_WAIT_AFTER_SPEAK} seconds after Level {self.current_level}...")
                time.sleep(ESCALATION_WAIT_AFTER_SPEAK)
                
                # Check if trusted user appeared during wait
                try:
                    if self._check_trusted_user():
                        self._log_event("Trusted user detected, aborting escalation")
                        break
                except Exception as e:
                    print(f"[EscalationManager] Error checking trusted user: {e}")
                
                # If not max level, wait 5 seconds before next escalation
                if self.current_level < ESCALATION_MAX_LEVEL:
                    print(f"⏳ [ESCALATION] Waiting 5 seconds before Level {self.current_level + 1}...")
                    time.sleep(5.0)
            
            # Handle end of escalation
            if self.current_level >= ESCALATION_MAX_LEVEL and not self._stop_escalation:
                try:
                    self._trigger_alarm()
                except Exception as e:
                    print(f"[EscalationManager] Error triggering alarm: {e}")
                    self._log_event(f"Error triggering alarm: {e}")
            else:
                self._log_event("Escalation aborted or completed")
                
        except Exception as e:
            print(f"[EscalationManager] Error in escalation loop: {e}")
            self._log_event(f"Escalation error: {e}")
        finally:
            self.is_escalating = False
            self.current_level = 0
            print("[EscalationManager] Escalation ended")
    
    def _check_trusted_user(self):
        """
        Check if a trusted user appears during escalation.
        Returns True if trusted user detected, False otherwise.
        Note: This is a simplified check - the main face recognition loop
        will handle trusted user detection and abort escalation via callback.
        """
        print("[EscalationManager] Checking for trusted user...")
        
        # Since the main face recognition loop is already running and will
        # call the trusted user callback which stops escalation, we don't
        # need to do additional camera checking here. Just wait a bit.
        time.sleep(1.0)
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
            
            if self.escalation_thread:
                self.escalation_thread.join(timeout=2.0)
    
    def reset(self):
        """Reset escalation manager state."""
        self.stop_escalation()
        self.current_level = 0
        self.is_escalating = False
        self._stop_escalation = False
        print("[EscalationManager] Reset completed")
