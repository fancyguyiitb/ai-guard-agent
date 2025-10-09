# src/main.py
import time
import argparse
import cv2
import threading
import os

from src.state_manager import StateManager, State
from src.asr_worker import ASRWorker
from src.face_recog import FaceRecognizer
from src.escalation import EscalationManager
from src.tts import TTSWrapper

# Global TTS instance
tts = TTSWrapper()

def main(camera_test_only=False, llm_mode="rule"):
    sm = StateManager()
    fr = FaceRecognizer()
    asr = ASRWorker(sm)
    escalation_manager = EscalationManager(sm, fr, llm_mode)

    # face-recognizer callbacks
    def on_face_recognized(name, distance):
        # called when fr detects a trusted person (first time in session)
        print(f"✅ [TRUSTED USER DETECTED] {name} (confidence: {1-distance:.3f})")
        
        # Stop any ongoing escalation if trusted user appears
        if escalation_manager.is_escalating:
            print(f"🛑 [ESCALATION STOPPED] Trusted user {name} detected during escalation")
            escalation_manager.stop_escalation()
            # Audible notification that we're standing down
            try:
                print("🔊 [TTS] Speaking: 'Trusted user detected. Standing down.'")
                t = threading.Thread(target=tts.speak, args=("Trusted user detected. Standing down.",), daemon=True)
                t.start()
            except Exception as e:
                print(f"❌ [TTS ERROR]: {e}")
        
        try:
            # greet using TTS (non-blocking)
            print(f"🔊 [TTS] Speaking: 'Welcome, {name}'")
            t = threading.Thread(target=tts.speak, args=(f"Welcome, {name}",), daemon=True)
            t.start()
        except Exception as e:
            print(f"❌ [TTS ERROR]: {e}")
    
    def on_unknown_face(face_crop, location):
        # called when fr detects an unknown person
        print(f"⚠️ [UNKNOWN PERSON DETECTED] at location {location}")
        
        # Only start escalation if we're in GUARD state and not already escalating
        if sm.get_state() == State.GUARD and not escalation_manager.is_escalating:
            print("🚨 [ESCALATION STARTING] Unknown person detected, beginning escalation sequence")
            escalation_manager.start_escalation(face_crop, location)
        else:
            print("⏸️ [IGNORING] Unknown face - not in GUARD state or already escalating")

    # state-change callback
    def on_state_change(old, new):
        print(f"[Main] state callback: {old.value} -> {new.value}")
        if new == State.GUARD:
            print("[Main] Entered GUARD: starting face recognition loop.")
            fr.start_recognition_loop(
                on_recognized=on_face_recognized, 
                on_unknown=on_unknown_face,
                show_preview=True
            )
        elif new == State.INTERACT:
            # Pause face recognition during interaction to avoid contention and false unknowns
            print("[Main] Entered INTERACT: pausing face recognition during dialogue.")
            fr.stop_recognition()
        elif old == State.GUARD and new in (State.ALARM, State.OFF):
            print("[Main] Leaving GUARD to critical state: stopping face recognition.")
            fr.stop_recognition()
        elif new == State.ALARM:
            print("[Main] ALARM state activated - system is in maximum security mode")
            # Alarm is already handled by escalation manager

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
            # main loop idle; state callbacks manage recognition and escalation
    except KeyboardInterrupt:
        print("[Main] KeyboardInterrupt — stopping...")
        asr.stop()
        fr.stop_recognition()
        escalation_manager.stop_escalation()
        time.sleep(0.5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera-test", action="store_true", help="Run webcam test and exit")
    parser.add_argument("--llm-mode", choices=["rule", "openai"], default="rule", 
                       help="LLM mode: 'rule' for templates, 'openai' for API (requires OPENAI_API_KEY)")
    args = parser.parse_args()
    main(camera_test_only=args.camera_test, llm_mode=args.llm_mode)
