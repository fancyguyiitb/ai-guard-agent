# src/tts.py
import os
import threading
import time
import pyttsx3
from src.utils.config import ALARM_SOUND_PATH

class TTSWrapper:
    """
    Text-to-speech wrapper with alarm functionality.
    Uses pyttsx3 for speech synthesis and playsound for alarm sounds.
    """
    
    _instance = None
    _engine = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one TTS engine."""
        if cls._instance is None:
            cls._instance = super(TTSWrapper, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize TTS engine."""
        if not hasattr(self, 'initialized'):
            self.engine = None
            self._initialize_engine()
            self.initialized = True
    
    def _initialize_engine(self):
        """Initialize the pyttsx3 engine with optimal settings."""
        try:
            self.engine = pyttsx3.init()
            
            # Configure voice properties
            voices = self.engine.getProperty('voices')
            if voices:
                # Try to use a female voice if available (often clearer for security)
                for voice in voices:
                    if 'female' in voice.name.lower() or 'zira' in voice.name.lower():
                        self.engine.setProperty('voice', voice.id)
                        break
                else:
                    # Fallback to first available voice
                    self.engine.setProperty('voice', voices[0].id)
            
            # Set speech rate (words per minute)
            self.engine.setProperty('rate', 180)
            
            # Set volume (0.0 to 1.0)
            self.engine.setProperty('volume', 0.9)
            
            print("[TTS] Engine initialized successfully")
            
        except Exception as e:
            print(f"[TTS] Failed to initialize engine: {e}")
            self.engine = None
    
    def speak(self, text, blocking=True):
        """
        Speak the given text.
        
        Args:
            text (str): Text to speak
            blocking (bool): If True, wait for speech to complete before returning
        """
        def _speak_worker():
            try:
                print(f"[TTS] Attempting to speak: '{text}'")
                
                # Use a completely fresh engine instance
                import pyttsx3
                engine = pyttsx3.init()
                
                # Set properties
                engine.setProperty('rate', 180)
                engine.setProperty('volume', 0.9)
                
                # Configure voice
                voices = engine.getProperty('voices')
                if voices:
                    # Try to use a female voice if available
                    for voice in voices:
                        if 'female' in voice.name.lower() or 'zira' in voice.name.lower():
                            engine.setProperty('voice', voice.id)
                            break
                    else:
                        # Fallback to first available voice
                        engine.setProperty('voice', voices[0].id)
                
                # Stop any existing speech
                try:
                    engine.stop()
                except:
                    pass
                
                # Speak the text
                engine.say(text)
                engine.runAndWait()
                
                print(f"[TTS] Successfully spoke: '{text}'")
                
            except Exception as e:
                print(f"[TTS] Error in speak worker: {e}")
                # Try alternative TTS method
                try:
                    import subprocess
                    # Use Windows built-in TTS as fallback
                    subprocess.run(['powershell', '-Command', f'Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{text}")'], 
                                 check=False, capture_output=True)
                    print(f"[TTS] Fallback TTS completed: '{text}'")
                except Exception as e2:
                    print(f"[TTS] Fallback TTS also failed: {e2}")
        
        try:
            if blocking:
                _speak_worker()
            else:
                # Run in separate thread for non-blocking speech
                thread = threading.Thread(target=_speak_worker, daemon=True)
                thread.start()
                
        except Exception as e:
            print(f"[TTS] Error speaking: {e}")
    
    def play_alarm(self):
        """
        Play alarm sound. Tries to play MP3 file first, falls back to TTS alarm.
        """
        # Try to play alarm sound file first
        if os.path.exists(ALARM_SOUND_PATH):
            try:
                import playsound
                playsound.playsound(ALARM_SOUND_PATH, block=False)
                print("[TTS] Playing alarm sound file")
                return
            except ImportError:
                print("[TTS] playsound not available, falling back to TTS alarm")
            except Exception as e:
                print(f"[TTS] Error playing alarm file: {e}, falling back to TTS alarm")
        
        # Fallback to TTS alarm
        print("[TTS] Playing TTS alarm")
        alarm_texts = [
            "ALARM! ALARM! INTRUDER DETECTED!",
            "SECURITY BREACH! SECURITY BREACH!",
            "EMERGENCY! UNAUTHORIZED ACCESS!",
            "ALERT! ALERT! CALLING SECURITY!"
        ]
        
        import random
        alarm_text = random.choice(alarm_texts)
        
        # Play alarm multiple times
        for i in range(3):
            self.speak(alarm_text, blocking=True)
            if i < 2:  # Don't wait after the last one
                time.sleep(0.5)
    
    def stop(self):
        """Stop any ongoing speech."""
        if self.engine:
            try:
                self.engine.stop()
            except Exception as e:
                print(f"[TTS] Error stopping engine: {e}")