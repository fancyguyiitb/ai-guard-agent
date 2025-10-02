# src/main.py
import time
import argparse
import cv2

from src.state_manager import StateManager
from src.asr_worker import ASRWorker

def on_state_change(old, new):
    print(f"[Main] state callback: {old.value} -> {new.value}")
    # For Milestone 1 we just log. Later, trigger other actions (TTS/welcome/etc.)

def camera_test():
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

def main(camera_test_only=False):
    sm = StateManager()
    sm.register_callback(on_state_change)

    if camera_test_only:
        camera_test()
        return

    asr = ASRWorker(sm)
    print("[Main] Starting ASR worker in background. Say activation phrase (e.g., 'guard my room').")
    thread = asr.start_in_background()

    try:
        while True:
            time.sleep(0.5)
            # show current state every few seconds (helpful while debugging)
            # print(f"[Main] Current state: {sm.get_state().value}")
    except KeyboardInterrupt:
        print("[Main] KeyboardInterrupt — stopping...")
        asr.stop()
        time.sleep(0.5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera-test", action="store_true", help="Run webcam test and exit")
    args = parser.parse_args()
    main(camera_test_only=args.camera_test)
