"""
AI Room Guard System - Main Entry Point

This module orchestrates the entire AI Room Guard System, including:
- Face recognition and escalation management
- ASR (Automatic Speech Recognition) for activation phrases
- TTS (Text-to-Speech) for voice alerts
- Email notifications with intruder snapshots
- State management and system restart cycles

"""

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
    """
    Main entry point for the AI Room Guard System.
    
    Args:
        camera_test_only (bool): If True, only test camera and exit
        direct_guard (bool): If True, bypass ASR and directly enter GUARD mode
        
    Returns:
        None
    """
    # Initialize core system components
    sm = StateManager()
    fr = FaceRecognizer()
    asr = ASRWorker(sm)

    # Escalation tracking system
    unknown_detections = deque(maxlen=10)  # Store timestamps of unknown face detections (rolling window)
    
    # Escalation state management
    escalation_stage = 0  # 0 = no escalation, 1-3 = escalation stages
    escalation_start_time = 0  # Timestamp when current escalation stage started
    last_greeting_time = 0  # Track last greeting to prevent spam
    restart_needed = False  # Flag to request system restart from main loop
    escalation_message_spoken = False  # Prevent duplicate TTS messages during escalation

    def on_face_recognized(name, distance):
        """
        Callback function triggered when a trusted person is detected.
        
        Handles two scenarios:
        1. During escalation: Terminates escalation and requests system restart
        2. During normal operation: Optionally greets trusted person (OFF state only)
        
        Args:
            name (str): Name of the recognized trusted person
            distance (float): Confidence distance from face recognition
        """
        print(f"[Main] Trusted person detected: {name} (dist={distance:.3f})")
        
        nonlocal escalation_stage, last_greeting_time, restart_needed
        current_time = time.time()
        
        if escalation_stage > 0:
            # Scenario 1: Trusted person detected during active escalation
            print("[Main] ESCALATION TERMINATED - Trusted person detected")
            escalation_stage = 0  # Reset escalation state
            
            # Set flag to request restart first (before any blocking operations)
            restart_needed = True
            print("[Main] Restart flag set - waiting for main loop to handle restart")
            
            # Speak termination message asynchronously to avoid blocking main loop
            speak(f"Hello {name}! Escalation has been terminated. Welcome back.", async_mode=True)
            last_greeting_time = current_time
            
        elif sm.get_state() == State.OFF:
            # Scenario 2: Initial greeting when system is in OFF state
            if current_time - last_greeting_time > 10.0:  # 10 second cooldown to prevent spam
                speak(f"Hello {name}! Welcome. The room is now under guard.")
                last_greeting_time = current_time
        # Note: No greeting for normal GUARD mode detections - just log them

    def on_unknown_face_detected():
        """
        Callback function triggered when an unknown face is detected.
        
        Implements escalation trigger logic:
        - Tracks unknown face detections in a rolling 4-second window
        - Triggers escalation if 2+ detections occur within 4 seconds
        - Prevents multiple escalation triggers
        
        Returns:
            None
        """
        nonlocal escalation_stage, escalation_start_time
        current_time = time.time()
        
        # Only process if not already in escalation (prevent multiple triggers)
        if escalation_stage > 0:
            return
            
        # Add current detection timestamp to rolling window
        unknown_detections.append(current_time)
        
        # Remove detections older than 4 seconds (rolling window)
        while unknown_detections and current_time - unknown_detections[0] > 4.0:
            unknown_detections.popleft()
        
        print(f"[Main] Unknown face detected ({len(unknown_detections)} detections in last 4s)")
        
        # Escalation trigger: 2+ detections within 4 seconds
        if len(unknown_detections) >= 2:
            print("[Main] ESCALATION TRIGGERED - Unknown person confirmed")
            escalation_stage = 1  # Begin escalation sequence
            escalation_start_time = current_time
            escalation_message_spoken = False  # Reset TTS message flag
            fr.disable_recognition()  # Disable face recognition during escalation


    def on_state_change(old, new):
        """
        State change callback function that manages system behavior during state transitions.
        
        Handles the following state transitions:
        - GUARD: Start face recognition loop
        - OFF: Stop face recognition, clear escalation state, manage ASR
        - Other states: Disable ASR listening
        
        Args:
            old (State): Previous system state
            new (State): New system state
        """
        print(f"[Main] state callback: {old.value} -> {new.value}")
        
        if new == State.GUARD:
            # Entering GUARD state: Start face recognition loop
            print("[Main] Entered GUARD: starting face recognition loop.")
            fr.start_recognition_loop(
                on_recognized=on_face_recognized, 
                on_unknown=on_unknown_face_detected, 
                show_preview=True
            )
            
        elif new == State.OFF:
            # Entering OFF state: Clean up and prepare for restart
            print("[Main] Entered OFF: stopping face recognition loop.")
            fr.stop_recognition()

            # Clear escalation state for clean restart
            escalation_stage = 0
            escalation_message_spoken = False
            
            # Manage ASR based on startup mode
            if not direct_guard:
                # Normal mode: Re-enable ASR for activation phrase detection
                asr.enable_listening()
            else:
                # Direct-guard mode: Automatically return to GUARD state
                print("[Main] Direct-guard mode: automatically returning to GUARD state")
                time.sleep(1.0)  # Small delay before restart
                sm.set_state(State.GUARD)
        else:
            # All other states (INTERACT, ALARM): Disable ASR listening
            asr.disable_listening()

    # Register state change callback with the state manager
    sm.register_callback(on_state_change)

    # Startup mode handling
    if camera_test_only:
        # Camera test mode: Simple webcam preview for hardware verification
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
        # Direct guard mode: Bypass ASR and immediately enter GUARD state
        print("[Main] Direct GUARD mode - bypassing ASR activation.")
        sm.set_state(State.GUARD)
    else:
        # Normal mode: Start ASR worker for activation phrase detection
        print("[Main] Starting ASR worker in background. Say activation phrase (e.g., 'guard my room').")
        asr_thread = asr.start_in_background()

    try:
        # Main execution loop - handles escalation logic and system restarts
        while True:
            time.sleep(0.5)  # Main loop sleep interval for reasonable CPU usage
            # Main loop handles escalation timing and restart logic
            # State callbacks manage face recognition and ASR
            
            # Handle system restart requests (triggered by trusted person during escalation)
            if restart_needed:
                print("[Main] Restart requested - restarting system")
                restart_needed = False
                escalation_stage = 0
                escalation_message_spoken = False
                
                # Reset TTS engine to prevent "run loop already started" errors
                try:
                    import src.tts as tts_module
                    if hasattr(tts_module, 'tts_manager'):
                        tts_manager = tts_module.tts_manager
                        if tts_manager.engine:
                            if hasattr(tts_manager.engine, '_inLoop') and tts_manager.engine._inLoop:
                                tts_manager.engine.stop()
                            # Force reinitialize TTS engine for clean restart
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
            
            # Handle escalation logic with timer-based approach
            if escalation_stage > 0:
                current_time = time.time()
                time_since_escalation = current_time - escalation_start_time
                
                # Pre-defined escalation messages for each stage
                escalation_messages = [
                    "Stage 1: Excuse me, I don't recognize you. Please identify yourself.",
                    "Stage 2: You are not authorized to be here. Please leave immediately.", 
                    "Stage 3: ALERT. Intruder detected. Security and the room owner have been notified."
                ]
                
                # Escalation stage management based on timing
                if escalation_stage == 1:
                    # Stage 1: Initial warning (first 1 second)
                    if time_since_escalation < 1.0 and not escalation_message_spoken:
                        print(f"[Main] ESCALATION STAGE {escalation_stage}: {escalation_messages[0]}")
                        speak(escalation_messages[0], async_mode=False)
                        escalation_message_spoken = True
                    # Stage 1 to Stage 2 transition (after 8 seconds)
                    elif time_since_escalation >= 8.0:
                        escalation_stage = 2
                        escalation_start_time = current_time
                        escalation_message_spoken = False
                        
                elif escalation_stage == 2:
                    # Stage 2: Second warning (first 1 second)
                    if time_since_escalation < 1.0 and not escalation_message_spoken:
                        print(f"[Main] ESCALATION STAGE {escalation_stage}: {escalation_messages[1]}")
                        speak(escalation_messages[1], async_mode=False)
                        escalation_message_spoken = True
                    # Stage 2 to Stage 3 transition (after 8 seconds)
                    elif time_since_escalation >= 8.0:
                        escalation_stage = 3
                        escalation_start_time = current_time
                        escalation_message_spoken = False
                        
                elif escalation_stage == 3:
                    # Stage 3: Final alert with snapshot capture and email notification
                    if time_since_escalation < 1.0 and not escalation_message_spoken:
                        print(f"[Main] ESCALATION STAGE {escalation_stage}: {escalation_messages[2]}")
                        speak(escalation_messages[2], async_mode=False)
                        escalation_message_spoken = True
                        
                        # Capture snapshot of intruder for evidence
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
                        
                        # Send email alert with intruder snapshot attachment
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
                            
                    # Escalation completion and system restart (after 8 seconds)
                    elif time_since_escalation >= 8.0:
                        print("[Main] ESCALATION COMPLETED - Restarting system")
                        escalation_stage = 0
                        escalation_message_spoken = False
                        
                        # Reset TTS engine to prevent "run loop already started" errors
                        try:
                            import src.tts as tts_module
                            if hasattr(tts_module, 'tts_manager'):
                                tts_manager = tts_module.tts_manager
                                if tts_manager.engine:
                                    if hasattr(tts_manager.engine, '_inLoop') and tts_manager.engine._inLoop:
                                        tts_manager.engine.stop()
                                    # Force reinitialize TTS engine for clean restart
                                    tts_manager.engine = None
                                    tts_manager._initialized = False
                                    print("[Main] TTS engine reset for escalation completion")
                            else:
                                print("[Main] TTS manager not found in module")
                        except Exception as e:
                            print(f"[Main] TTS reset error: {e}")
                            
                        # Return to OFF state to restart the system
                        sm.set_state(State.OFF)
                        
                # Manage face recognition during escalation
                if escalation_stage > 0 and 2.0 <= time_since_escalation <= 7.0:
                    # Enable face recognition during wait periods (2-7 seconds) to allow trusted person detection
                    fr.enable_recognition()
                elif escalation_stage > 0:
                    # Disable face recognition during message delivery periods
                    fr.disable_recognition()
                # Note: If escalation_stage == 0, face recognition is managed by state callbacks
    except KeyboardInterrupt:
        # Graceful shutdown on Ctrl+C
        print("[Main] KeyboardInterrupt — stopping...")
        asr.stop()
        fr.stop_recognition()
        time.sleep(0.5)  # Allow threads to clean up

if __name__ == "__main__":
    # Command line argument parsing
    parser = argparse.ArgumentParser(description="AI Room Guard System - Security monitoring with face recognition and escalation")
    parser.add_argument("--camera-test", action="store_true", help="Run webcam test and exit")
    parser.add_argument("--direct-guard", action="store_true", help="Skip ASR and directly enter GUARD mode")
    
    args = parser.parse_args()
    main(camera_test_only=args.camera_test, direct_guard=args.direct_guard)
