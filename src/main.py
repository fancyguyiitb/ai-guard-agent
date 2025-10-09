# src/main.py
import time
import argparse
import cv2
import threading
import pyttsx3

from src.state_manager import StateManager, State
from src.asr_worker import ASRWorker
from src.face_recog import FaceRecognizer
from src.escalation import EscalationManager
from src.tts import TTSWrapper

def speak_with_wrapper(tts, text):
    try:
        tts.speak(text, async_mode=True)
    except Exception as e:
        print("[TTS] Error:", e)

def main(camera_test_only=False):
    sm = StateManager()
    fr = FaceRecognizer()
    asr = ASRWorker(sm)
    tts = TTSWrapper()
    escalation = EscalationManager(sm, tts)

    # face-recognizer callback
    def on_face_recognized(name, distance):
        # called when fr detects a trusted person (first time in session)
        print(f"[Main] on_face_recognized callback -> {name} (dist={distance})")
        try:
            # greet using shared TTS engine (non-blocking)
            greeting = f"Welcome, {name}. "
            if escalation.is_running():
                greeting += "Escalation has been terminated."
            t = threading.Thread(target=speak_with_wrapper, args=(tts, greeting), daemon=True)
            t.start()
        except Exception as e:
            print("[Main] TTS error:", e)
        # If alarm was active, reset back to GUARD
        try:
            escalation.reset()
        except Exception:
            pass

    def on_unknown_face(frame_bgr, face_result):
        # Only start escalation when in GUARD
        if sm.get_state() == State.GUARD:
            escalation.start(frame_bgr)

    # state-change callback
    def on_state_change(old, new):
        print(f"[Main] state callback: {old.value} -> {new.value}")
        if new == State.GUARD:
            print("[Main] Entered GUARD: starting face recognition loop.")
            fr.start_recognition_loop(on_recognized=on_face_recognized, on_unknown=on_unknown_face, show_preview=True)
        # Keep recognition running even during ALARM per requirement

    sm.register_callback(on_state_change)

    if camera_test_only:
        # simple camera test
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("❌ Cannot open webcam (index 0). Check device or change index.")
            return False
        print("✅ Webcam opened. Press 'q' in the camera window to exit.")
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Failed to grab frame")
                break
            cv2.imshow("Camera Test - press q to quit", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        cap.release()
        cv2.destroyAllWindows()
        return True

    # start ASR worker in background
    print("[Main] Starting ASR worker in background. Say activation phrase (e.g., 'guard my room').")
    asr_thread = asr.start_in_background()

    try:
        while True:
            time.sleep(0.5)
            # main loop idle; state callbacks manage recognition
    except KeyboardInterrupt:
        print("[Main] KeyboardInterrupt — stopping...")
        asr.stop()
        fr.stop_recognition()
        time.sleep(0.5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera-test", action="store_true", help="Run webcam test and exit")
    args = parser.parse_args()
    main(camera_test_only=args.camera_test)
