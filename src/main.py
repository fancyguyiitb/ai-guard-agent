# src/main.py
import time
import argparse
import cv2
import threading
from collections import deque

from src.state_manager import StateManager, State
from src.asr_worker import ASRWorker
from src.face_recog import FaceRecognizer
from src.tts import speak
from src.email_notifier import send_escalation_alert
from src.snapshot_capture import capture_intruder_snapshot

def main(camera_test_only=False, direct_guard=False):
    sm = StateManager()
    fr = FaceRecognizer()
    asr = ASRWorker(sm)

    # Escalation tracking
    unknown_detections = deque()  # Store timestamps of unknown face detections
    
    # Simple escalation state
    escalation_stage = 0  # 0 = no escalation, 1-3 = escalation stages
    escalation_start_time = 0
    last_greeting_time = 0  # Track last greeting to prevent spam
    restart_needed = False  # Flag to request system restart
    escalation_message_spoken = False  # Prevent duplicate TTS messages

    def on_face_recognized(name, distance):
        # called when fr detects a trusted person (first time in session)
        print(f"[Main] Trusted person detected: {name} (dist={distance:.3f})")
        
        nonlocal escalation_stage, last_greeting_time, restart_needed
        current_time = time.time()
        
        if escalation_stage > 0:
            print("[Main] ESCALATION TERMINATED - Trusted person detected")
            escalation_stage = 0  # Reset escalation
            # Set flag to request restart first
            restart_needed = True
            print("[Main] Restart flag set - waiting for main loop to handle restart")
            # Speak termination message asynchronously
            speak(f"Hello {name}! Escalation has been terminated. Welcome back.", async_mode=True)
            last_greeting_time = current_time
        elif sm.get_state() == State.OFF:
            # Only greet when in OFF state (initial greeting)
            if current_time - last_greeting_time > 10.0:  # 10 second cooldown
                speak(f"Hello {name}! Welcome. The room is now under guard.")
                last_greeting_time = current_time
        # No greeting for normal GUARD mode detections - just log them

    def on_unknown_face_detected():
        """Called when unknown face is detected - track for escalation trigger"""
        nonlocal escalation_stage, escalation_start_time
        current_time = time.time()
        
        # Only process if not already in escalation
        if escalation_stage > 0:
            return
            
        unknown_detections.append(current_time)
        
        # Remove detections older than 4 seconds
        while unknown_detections and current_time - unknown_detections[0] > 4.0:
            unknown_detections.popleft()
        
        print(f"[Main] Unknown face detected ({len(unknown_detections)} detections in last 4s)")
        
        # If we have 2+ detections in 4 seconds, start escalation
        if len(unknown_detections) >= 2:
            print("[Main] ESCALATION TRIGGERED - Unknown person confirmed")
            escalation_stage = 1
            escalation_start_time = current_time
            escalation_message_spoken = False
            fr.disable_recognition()


    # state-change callback
    def on_state_change(old, new):
        print(f"[Main] state callback: {old.value} -> {new.value}")
        if new == State.GUARD:
            # Always start face recognition when entering GUARD state
            print("[Main] Entered GUARD: starting face recognition loop.")
            fr.start_recognition_loop(on_recognized=on_face_recognized, on_unknown=on_unknown_face_detected, show_preview=True)
        elif new == State.OFF:
            # Stop face recognition when returning to OFF state
            print("[Main] Entered OFF: stopping face recognition loop.")
            fr.stop_recognition()
            # Clear any escalation state
            escalation_stage = 0
            escalation_message_spoken = False
            # Re-enable ASR listening when returning to OFF state (unless direct-guard mode)
            if not direct_guard:
                asr.enable_listening()
            else:
                # In direct-guard mode, automatically return to GUARD state
                print("[Main] Direct-guard mode: automatically returning to GUARD state")
                time.sleep(1.0)  # Small delay before restart
                sm.set_state(State.GUARD)
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
            time.sleep(0.5)  # Back to reasonable main loop speed
            # main loop idle; state callbacks manage recognition
            
            # Check for restart request first
            if restart_needed:
                print("[Main] Restart requested - restarting system")
                restart_needed = False
                escalation_stage = 0
                escalation_message_spoken = False
                # Reset TTS engine to prevent "run loop already started" errors
                try:
                    # Import TTS manager from the correct module
                    import src.tts as tts_module
                    if hasattr(tts_module, 'tts_manager'):
                        tts_manager = tts_module.tts_manager
                        if tts_manager.engine:
                            if hasattr(tts_manager.engine, '_inLoop') and tts_manager.engine._inLoop:
                                tts_manager.engine.stop()
                            # Force reinitialize TTS engine
                            tts_manager.engine = None
                            tts_manager._initialized = False
                            print("[Main] TTS engine reset for restart")
                    else:
                        print("[Main] TTS manager not found in module")
                except Exception as e:
                    print(f"[Main] TTS reset error: {e}")
                print("[Main] Setting state to OFF")
                sm.set_state(State.OFF)
                print("[Main] State change initiated, continuing main loop")
                continue
            
            # Handle escalation logic with simple timer-based approach
            if escalation_stage > 0:
                current_time = time.time()
                time_since_escalation = current_time - escalation_start_time
                
                # Escalation messages and timing
                escalation_messages = [
                    "Stage 1: Excuse me, I don't recognize you. Please identify yourself.",
                    "Stage 2: You are not authorized to be here. Please leave immediately.", 
                    "Stage 3: ALERT. Intruder detected. Security and the room owner have been notified."
                ]
                
                # Determine current stage based on time
                if escalation_stage == 1:
                    if time_since_escalation < 1.0 and not escalation_message_spoken:  # First second - speak stage 1
                        print(f"[Main] ESCALATION STAGE {escalation_stage}: {escalation_messages[0]}")
                        speak(escalation_messages[0], async_mode=False)
                        escalation_message_spoken = True
                    elif time_since_escalation >= 8.0:  # After 8 seconds - move to stage 2
                        escalation_stage = 2
                        escalation_start_time = current_time
                        escalation_message_spoken = False
                        
                elif escalation_stage == 2:
                    if time_since_escalation < 1.0 and not escalation_message_spoken:  # First second - speak stage 2
                        print(f"[Main] ESCALATION STAGE {escalation_stage}: {escalation_messages[1]}")
                        speak(escalation_messages[1], async_mode=False)
                        escalation_message_spoken = True
                    elif time_since_escalation >= 8.0:  # After 8 seconds - move to stage 3
                        escalation_stage = 3
                        escalation_start_time = current_time
                        escalation_message_spoken = False
                        
                elif escalation_stage == 3:
                    if time_since_escalation < 1.0 and not escalation_message_spoken:  # First second - speak stage 3
                        print(f"[Main] ESCALATION STAGE {escalation_stage}: {escalation_messages[2]}")
                        speak(escalation_messages[2], async_mode=False)
                        escalation_message_spoken = True
                        
                        # Capture snapshot of intruder
                        print("[Main] Capturing intruder snapshot...")
                        frame, face_box = fr.get_current_frame_and_face_box()
                        snapshot_path = None
                        if frame is not None:
                            snapshot_path = capture_intruder_snapshot(frame, face_box)
                            if snapshot_path:
                                print(f"[Main] Snapshot captured: {snapshot_path}")
                            else:
                                print("[Main] Failed to capture snapshot")
                        else:
                            print("[Main] No frame available for snapshot")
                        
                        # Send email alert for Level 3 escalation with snapshot
                        print("[Main] Sending email alert for Level 3 escalation...")
                        email_sent = send_escalation_alert({
                            'stage': 3,
                            'timestamp': current_time,
                            'message': escalation_messages[2]
                        }, snapshot_path)
                        if email_sent:
                            print("[Main] Email alert sent successfully")
                        else:
                            print("[Main] Failed to send email alert")
                    elif time_since_escalation >= 8.0:  # After 8 seconds - complete escalation
                        print("[Main] ESCALATION COMPLETED - Restarting system")
                        escalation_stage = 0
                        escalation_message_spoken = False
                        # Reset TTS engine to prevent "run loop already started" errors
                        try:
                            # Import TTS manager from the correct module
                            import src.tts as tts_module
                            if hasattr(tts_module, 'tts_manager'):
                                tts_manager = tts_module.tts_manager
                                if tts_manager.engine:
                                    if hasattr(tts_manager.engine, '_inLoop') and tts_manager.engine._inLoop:
                                        tts_manager.engine.stop()
                                    # Force reinitialize TTS engine
                                    tts_manager.engine = None
                                    tts_manager._initialized = False
                                    print("[Main] TTS engine reset for escalation completion")
                            else:
                                print("[Main] TTS manager not found in module")
                        except Exception as e:
                            print(f"[Main] TTS reset error: {e}")
                        sm.set_state(State.OFF)
                        
                # Enable face recognition during wait periods (between stages)
                if escalation_stage > 0 and 2.0 <= time_since_escalation <= 7.0:
                    fr.enable_recognition()
                elif escalation_stage > 0:
                    fr.disable_recognition()
                # If escalation_stage == 0, don't touch face recognition (let state callback handle it)
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
