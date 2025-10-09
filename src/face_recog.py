# src/face_recog.py
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
    def __init__(self, embeddings_path=EMBEDDINGS_PATH, enroll_dir=ENROLL_DIR, match_threshold=FACE_MATCH_THRESHOLD, webcam_index=WEBCAM_INDEX):
        self.embeddings_path = embeddings_path
        self.enroll_dir = enroll_dir
        self.match_threshold = match_threshold
        self.webcam_index = webcam_index
        self.logger = get_face_logger()

        # dict: name -> list of 128-d numpy arrays
        self.known_embeddings = {}
        self._load_embeddings()

        # recognition thread control
        self._running = False
        self._thread = None

        # callback when a trusted person recognized: fn(name, distance)
        self.on_recognized_callback = None

    def _load_embeddings(self):
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
        os.makedirs(os.path.dirname(self.embeddings_path), exist_ok=True)
        with open(self.embeddings_path, "wb") as f:
            pickle.dump(self.known_embeddings, f)
        self.logger.info("Saved embeddings (%d people) to %s", len(self.known_embeddings), self.embeddings_path)

    def add_embeddings_for(self, name, encodings):
        """
        encodings: list of 1D numpy arrays (face encodings)
        """
        if name in self.known_embeddings:
            self.known_embeddings[name].extend([e.tolist() for e in encodings])
        else:
            self.known_embeddings[name] = [e.tolist() for e in encodings]
        # normalize back to numpy lists on save/load; we store lists to be pickle-safe
        self.save_embeddings()

    def get_known_encodings(self):
        # return dict name -> list of numpy arrays
        return {name: [np.array(e) for e in lst] for name, lst in self.known_embeddings.items()}

    def recognize_frame(self, frame_bgr):
        """
        frame_bgr: OpenCV BGR frame
        returns: list of dicts for each detected face:
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
        Starts thread that reads webcam frames and calls on_recognized(name, distance)
        for recognized trusted persons (first detection per person will call callback).
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
        try:
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.05)
                    continue

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
                    else:
                        self.logger.info(
                            "Detected face: %s (dist=%s, box=(%d,%d,%d,%d))",
                            name, dist_str, top, right, bottom, left
                        )

                    if name != "unknown":
                        if name not in seen_this_session:
                            seen_this_session.add(name)
                            self.logger.info("Recognized %s (dist=%.3f)", name, dist)
                            if self.on_recognized_callback:
                                try:
                                    self.on_recognized_callback(name, dist)
                                except Exception as e:
                                    self.logger.error("on_recognized_callback error: %s", e, exc_info=True)
                    else:
                        if self.on_unknown_callback:
                            try:
                                # Pass a copy of the current frame for snapshot/escalation
                                self.on_unknown_callback(frame.copy(), r)
                            except Exception as e:
                                self.logger.error("on_unknown_callback error: %s", e, exc_info=True)
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

    def stop_recognition(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)


