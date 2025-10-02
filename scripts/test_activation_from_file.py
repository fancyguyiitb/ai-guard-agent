# scripts/test_activation_from_file.py
# usage: python scripts/test_activation_from_file.py /path/to/file.wav

import sys
import whisper
from src.utils.config import WHISPER_MODEL, ACTIVATION_PHRASES

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_activation_from_file.py /path/to/audio.wav")
        return
    path = sys.argv[1]
    print("[Test] Loading model:", WHISPER_MODEL)
    model = whisper.load_model(WHISPER_MODEL)
    print("[Test] Transcribing", path)
    res = model.transcribe(path, language="en")
    text = res.get("text", "").lower().strip()
    print("[Test] Transcription:", text)
    if any(p in text for p in ACTIVATION_PHRASES):
        print("[Test] Activation phrase DETECTED")
    else:
        print("[Test] Activation phrase NOT found")

if __name__ == "__main__":
    main()
