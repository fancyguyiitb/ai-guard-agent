"""
AI Room Guard System - Face Recognition Module

This module handles face detection and recognition using the face_recognition library.
It provides continuous face monitoring, known face identification, and unknown face detection
with proper logging and state management.

Features:
- Continuous face detection and recognition
- Known face identification with confidence thresholds
- Unknown face detection and logging
- Configurable recognition enable/disable
- Frame and face box storage for snapshot capture
- Thread-safe operation

"""

import os
import cv2
import pickle
import threading
import time
import numpy as np

try:
    import face_recognition
except Exception as e:
    raise ImportError(
        "face_recognition (dlib) is required for face recognition. "
        "See README for install instructions. Error: " + str(e)
    )

from src.utils.config import EMBEDDINGS_PATH, ENROLL_DIR, FACE_MATCH_THRESHOLD, WEBCAM_INDEX
from src.utils.logger import get_face_logger

class FaceRecognizer:
    """
    Face recognition system that detects and identifies faces from a webcam feed.
    
    This class provides continuous face monitoring with the ability to:
    - Detect faces in real-time video streams
    - Identify known faces using pre-computed embeddings
    - Log unknown faces for security monitoring
    - Enable/disable recognition dynamically
    - Store frames and face boxes for snapshot capture
    """
    
    def __init__(self, embeddings_path=EMBEDDINGS_PATH, enroll_dir=ENROLL_DIR, 
                 match_threshold=FACE_MATCH_THRESHOLD, webcam_index=WEBCAM_INDEX):
        """
        Initialize the face recognizer.
        
        Args:
            embeddings_path (str): Path to the face embeddings pickle file
            enroll_dir (str): Directory containing enrolled face images
            match_threshold (float): Distance threshold for face matching (lower = stricter)
            webcam_index (int): Camera device index for OpenCV
        """
        self.embeddings_path = embeddings_path
        self.enroll_dir = enroll_dir
        self.match_threshold = match_threshold
        self.webcam_index = webcam_index
        self.logger = get_face_logger()

        # Known face embeddings: dict mapping name -> list of 128-d numpy arrays
        self.known_embeddings = {}
        self._load_embeddings()

        # Threading control
        self._running = False
        self._thread = None
        self._recognition_enabled = True  # Flag to control face processing

        # Callback functions
        self.on_recognized_callback = None  # Called when trusted person recognized: fn(name, distance)
        self.on_unknown_callback = None     # Called when unknown face detected: fn()
        
        # Snapshot capture support
        self._current_frame = None
        self._last_unknown_face_box = None

    def _load_embeddings(self):
        """
        Load pre-computed face embeddings from the pickle file.
        
        The embeddings file contains a dictionary mapping person names to lists of 
        128-dimensional face encoding vectors.
        """
        if os.path.exists(self.embeddings_path):
            try:
                with open(self.embeddings_path, "rb") as f:
                    self.known_embeddings = pickle.load(f)
                self.logger.info("Loaded embeddings for %d people.", len(self.known_embeddings))
            except Exception as e:
                self.logger.error("Failed to load embeddings: %s", e)
                self.known_embeddings = {}
        else:
            self.known_embeddings = {}

    def save_embeddings(self):
        """
        Save the current known face embeddings to the pickle file.
        
        Creates the directory if it doesn't exist and writes the embeddings dictionary.
        """
        os.makedirs(os.path.dirname(self.embeddings_path), exist_ok=True)
        with open(self.embeddings_path, "wb") as f:
            pickle.dump(self.known_embeddings, f)
        self.logger.info("Saved embeddings (%d people) to %s", len(self.known_embeddings), self.embeddings_path)

    def add_embeddings_for(self, name, encodings):
        """
        Add face embeddings for a specific person.
        
        Args:
            name (str): Name of the person
            encodings (list): List of 1D numpy arrays containing face encodings
        """
        if name in self.known_embeddings:
            self.known_embeddings[name].extend([e.tolist() for e in encodings])
        else:
            self.known_embeddings[name] = [e.tolist() for e in encodings]
        # Convert to lists for pickle safety, normalize back to numpy on load
        self.save_embeddings()

    def get_known_encodings(self):
        """
        Get all known face encodings as numpy arrays.
        
        Returns:
            dict: Dictionary mapping person names to lists of numpy arrays (face encodings)
        """
        return {name: [np.array(e) for e in lst] for name, lst in self.known_embeddings.items()}

    def recognize_frame(self, frame_bgr):
        """
        Recognize faces in a single frame.
        
        Args:
            frame_bgr: OpenCV BGR frame to analyze
            
        Returns:
            list: List of dictionaries for each detected face:
                  [{"name": "Alice" or "unknown", "distance": 0.42, "location": (top,right,bottom,left)} ...]
        """
        results = []
        # Ensure RGB image is contiguous uint8 for dlib/face_recognition bindings
        rgb = np.ascontiguousarray(frame_bgr[:, :, ::-1], dtype=np.uint8)
        face_locations = face_recognition.face_locations(rgb)
        if not face_locations:
            return results

        encodings = face_recognition.face_encodings(rgb, face_locations)
        known = self.get_known_encodings()

        for loc, enc in zip(face_locations, encodings):
            best_name = "unknown"
            best_dist = None

            for name, enc_list in known.items():
                if len(enc_list) == 0:
                    continue
                dists = face_recognition.face_distance(enc_list, enc)
                min_idx = np.argmin(dists)
                min_dist = float(dists[min_idx])
                if best_dist is None or min_dist < best_dist:
                    best_dist = min_dist
                    candidate = name

            if best_dist is not None and best_dist <= self.match_threshold:
                best_name = candidate

            results.append({
                "name": best_name,
                "distance": best_dist if best_dist is not None else None,
                "location": loc
            })
        return results

    # ---- Webcam-based continuous recognition ----
    def start_recognition_loop(self, on_recognized=None, on_unknown=None, show_preview=False, preview_window_name="FaceRecog"):
        """
        Start continuous face recognition loop in a separate thread.
        
        Args:
            on_recognized (callable): Callback function called when a trusted person is detected
                                    Signature: on_recognized(name, distance)
            on_unknown (callable): Callback function called when an unknown face is detected
                                 Signature: on_unknown()
            show_preview (bool): Whether to display the camera feed with face boxes
            preview_window_name (str): Name of the preview window
        """
        if self._running:
            return
        self._running = True
        self.on_recognized_callback = on_recognized
        self.on_unknown_callback = on_unknown
        self._thread = threading.Thread(target=self._run_loop, args=(show_preview, preview_window_name), daemon=True)
        self._thread.start()

    def _run_loop(self, show_preview, preview_window_name):
        cap = cv2.VideoCapture(self.webcam_index)
        if not cap.isOpened():
            self.logger.error("Cannot open webcam for recognition.")
            self._running = False
            return

        seen_this_session = set()  # to avoid repeated callbacks for same person
        last_check_time = 0
        try:
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.05)
                    continue

                # Store current frame for snapshot capture
                self._current_frame = frame.copy()
                current_time = time.time()
                
                # Only process faces if recognition is enabled and 1 second has passed
                if self._recognition_enabled and (current_time - last_check_time) >= 1.0:
                    results = self.recognize_frame(frame)
                    for r in results:
                        name = r["name"]
                        dist = r["distance"]
                        top, right, bottom, left = r["location"]

                        # Uniform logging for every detected face (console colored by level)
                        dist_str = f"{dist:.3f}" if isinstance(dist, (int, float)) else "n/a"
                        if name == "unknown":
                            self.logger.warning(
                                "Detected face: UNKNOWN (dist=%s, box=(%d,%d,%d,%d))",
                                dist_str, top, right, bottom, left
                            )
                            # Store face box for snapshot capture
                            self._last_unknown_face_box = (top, right, bottom, left)
                            # Call unknown callback
                            if self.on_unknown_callback:
                                try:
                                    self.on_unknown_callback()
                                except Exception as e:
                                    self.logger.error("on_unknown_callback error: %s", e, exc_info=True)
                        else:
                            self.logger.info(
                                "Detected face: %s (dist=%s, box=(%d,%d,%d,%d))",
                                name, dist_str, top, right, bottom, left
                            )

                        if name != "unknown":
                            if name not in seen_this_session:
                                seen_this_session.add(name)
                                self.logger.info("Recognized %s (dist=%.3f)", name, dist)
                            # Always call the callback for trusted faces (not just first time)
                            if self.on_recognized_callback:
                                try:
                                    self.on_recognized_callback(name, dist)
                                except Exception as e:
                                    self.logger.error("on_recognized_callback error: %s", e, exc_info=True)
                    last_check_time = current_time  # Update last check time
                else:
                    # Recognition disabled - just show camera feed without processing
                    results = []
                    
                if show_preview:
                    # draw boxes
                    for r in results:
                        top, right, bottom, left = r["location"]
                        label = r["name"]
                        cv2.rectangle(frame, (left, top), (right, bottom), (0,255,0), 2)
                        cv2.putText(frame, label, (left, top-8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)
                    cv2.imshow(preview_window_name, frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        self._running = False
                        break
                else:
                    time.sleep(0.05)
        finally:
            cap.release()
            if show_preview:
                cv2.destroyWindow(preview_window_name)
            self._running = False
            self.logger.info("Recognition loop stopped.")

    def enable_recognition(self):
        """
        Enable face recognition processing.
        
        This allows the recognition loop to process faces and trigger callbacks.
        The camera feed continues running regardless of this setting.
        """
        self._recognition_enabled = True
        self.logger.info("Face recognition enabled")

    def disable_recognition(self):
        """
        Disable face recognition processing.
        
        This stops face processing and callback triggers while keeping the camera feed running.
        Useful during escalation periods or when you want to pause recognition.
        """
        self._recognition_enabled = False
        self.logger.info("Face recognition disabled")

    def stop_recognition(self):
        """
        Stop the recognition loop and clean up resources.
        
        This completely stops the background thread and releases the camera.
        """
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
    
    def get_current_frame_and_face_box(self):
        """
        Get the current frame and last unknown face box for snapshot capture.
        
        Returns:
            tuple: (frame, face_box) where face_box is (top, right, bottom, left)
        """
        return self._current_frame, self._last_unknown_face_box


