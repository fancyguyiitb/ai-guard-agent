# src/tts.py
import pyttsx3
import threading
import time

class TTSManager:
    def __init__(self):
        self.engine = None
        self._initialized = False
        self._speaking = False
        
    def _initialize(self):
        """Initialize the TTS engine if not already done"""
        if self._initialized:
            return
            
        try:
            self.engine = pyttsx3.init()
            # Configure voice settings
            voices = self.engine.getProperty('voices')
            if voices:
                # Try to use a female voice if available, otherwise use default
                for voice in voices:
                    if 'female' in voice.name.lower() or 'zira' in voice.name.lower():
                        self.engine.setProperty('voice', voice.id)
                        break
            
            # Set speech rate (words per minute)
            self.engine.setProperty('rate', 180)
            # Set volume (0.0 to 1.0)
            self.engine.setProperty('volume', 0.8)
            
            self._initialized = True
            print("[TTS] TTS engine initialized successfully")
            
        except Exception as e:
            print(f"[TTS] Error initializing TTS engine: {e}")
            self._initialized = False
    
    def speak(self, text, async_mode=False):
        """Speak the given text
        
        Args:
            text (str): Text to speak
            async_mode (bool): If True, speak asynchronously. If False, block until speech completes.
        """
        if not text.strip():
            return
            
        self._initialize()
        
        if not self._initialized:
            print(f"[TTS] Cannot speak - TTS engine not initialized: {text}")
            return
        
        try:
            print(f"[TTS] Speaking: {text}")
            
            if async_mode:
                # Speak asynchronously in a separate thread
                def speak_async():
                    self._speaking = True
                    self.engine.say(text)
                    self.engine.runAndWait()
                    self._speaking = False
                
                thread = threading.Thread(target=speak_async, daemon=True)
                thread.start()
            else:
                # Speak synchronously (blocking)
                self._speaking = True
                self.engine.say(text)
                self.engine.runAndWait()
                self._speaking = False
                
        except Exception as e:
            print(f"[TTS] Error speaking text '{text}': {e}")
            self._speaking = False
    
    def stop(self):
        """Stop any ongoing speech"""
        if self.engine and self._speaking:
            try:
                self.engine.stop()
                self._speaking = False
                print("[TTS] Speech stopped")
            except Exception as e:
                print(f"[TTS] Error stopping speech: {e}")
    
    def is_speaking(self):
        """Check if currently speaking"""
        return self._speaking

# Global TTS instance
_tts_instance = None

def get_tts():
    """Get the global TTS instance"""
    global _tts_instance
    if _tts_instance is None:
        _tts_instance = TTSManager()
    return _tts_instance

def speak(text, async_mode=False):
    """Convenience function to speak text using the global TTS instance"""
    get_tts().speak(text, async_mode)
