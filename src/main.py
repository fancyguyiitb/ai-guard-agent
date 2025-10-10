# src/main.py
import time
import argparse
import cv2
import threading
from collections import deque

from src.state_manager import StateManager, State
from src.asr_worker import ASRWorker
from src.face_recog import FaceRecognizer

def main(camera_test_only=False, direct_guard=False):
    sm = StateManager()
    fr = FaceRecognizer()
    asr = ASRWorker(sm)

    # Escalation tracking
    unknown_detections = deque()  # Store timestamps of unknown face detections
    
    # Use nonlocal to allow modification in nested functions
    escalation_active = False
    escalation_thread = None

    def on_face_recognized(name, distance):
        # called when fr detects a trusted person (first time in session)
        print(f"[Main] Trusted person detected: {name} (dist={distance:.3f})")
        
        # If escalation is active, terminate it
        nonlocal escalation_active
        if escalation_active:
            print("[Main] ESCALATION TERMINATED - Trusted person detected")
            escalation_active = False
            fr.enable_recognition()  # Re-enable face recognition
            # Don't change state here - let the escalation thread handle it

    def on_unknown_face_detected():
        """Called when unknown face is detected - track for escalation trigger"""
        nonlocal escalation_active
        current_time = time.time()
        unknown_detections.append(current_time)
        
        # Remove detections older than 4 seconds
        while unknown_detections and current_time - unknown_detections[0] > 4.0:
            unknown_detections.popleft()
        
        print(f"[Main] Unknown face detected ({len(unknown_detections)} detections in last 4s)")
        
        # If we have 2+ detections in 4 seconds, start escalation
        if len(unknown_detections) >= 2 and not escalation_active:
            print("[Main] ESCALATION TRIGGERED - Unknown person confirmed")
            start_escalation()

    def start_escalation():
        """Start the 3-stage escalation process"""
        nonlocal escalation_active, escalation_thread
        escalation_active = True
        fr.disable_recognition()  # Disable face recognition during escalation
        escalation_thread = threading.Thread(target=run_escalation, daemon=True)
        escalation_thread.start()

    def run_escalation():
        """Run the 3-stage escalation with 7-second delays"""
        nonlocal escalation_active
        escalation_messages = [
            "Stage 1: Excuse me, I don't recognize you. Please identify yourself.",
            "Stage 2: You are not authorized to be here. Please leave immediately.", 
            "Stage 3: ALERT. Intruder detected. Security and the room owner have been notified."
        ]
        
        for stage, message in enumerate(escalation_messages, 1):
            if not escalation_active:
                return  # Escalation was terminated
            
            print(f"[Main] ESCALATION STAGE {stage}: {message}")
            
            # Re-enable face recognition during 7-second wait (except after final stage)
            if stage < 3:
                fr.enable_recognition()
                print("[Main] Face recognition re-enabled during escalation wait")
                
                # Wait 7 seconds, checking for termination
                for _ in range(7):  # 7 seconds * 1 check per second
                    if not escalation_active:
                        print("[Main] Escalation terminated during wait - returning to GUARD")
                        # Return to GUARD state when escalation is terminated by trusted face
                        sm.set_state(State.GUARD)
                        return
                    time.sleep(1.0)
                
                fr.disable_recognition()  # Disable again for next stage
                print("[Main] Face recognition disabled for next escalation stage")
        
        # Escalation completed - go to OFF state
        print("[Main] ESCALATION COMPLETED - Returning to OFF state")
        escalation_active = False
        sm.set_state(State.OFF)

    # state-change callback
    def on_state_change(old, new):
        print(f"[Main] state callback: {old.value} -> {new.value}")
        if new == State.GUARD:
            print("[Main] Entered GUARD: starting face recognition loop.")
            fr.start_recognition_loop(on_recognized=on_face_recognized, on_unknown=on_unknown_face_detected, show_preview=True)
        elif new == State.OFF:
            # Stop face recognition when returning to OFF state
            print("[Main] Entered OFF: stopping face recognition loop.")
            fr.stop_recognition()
            # Re-enable ASR listening when returning to OFF state
            asr.enable_listening()
        else:
            # Disable ASR listening for all other states (GUARD, INTERACT, ALARM)
            asr.disable_listening()

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

    if direct_guard:
        # Skip ASR and directly enter GUARD mode
        print("[Main] Direct GUARD mode - bypassing ASR activation.")
        sm.set_state(State.GUARD)
    else:
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
    parser.add_argument("--direct-guard", action="store_true", help="Skip ASR and directly enter GUARD mode")
    args = parser.parse_args()
    main(camera_test_only=args.camera_test, direct_guard=args.direct_guard)
