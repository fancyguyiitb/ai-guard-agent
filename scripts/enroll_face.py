# scripts/enroll_face.py
import os
import sys
import argparse
import cv2
import time
import face_recognition
import numpy as np

# Ensure project root is on sys.path so `src` imports work when running this script directly
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.face_recog import FaceRecognizer
from src.utils.config import ENROLL_DIR, DEFAULT_ENROLL_COUNT, WEBCAM_INDEX

def capture_images(name, count=DEFAULT_ENROLL_COUNT, save_dir=ENROLL_DIR, webcam_index=WEBCAM_INDEX):
    person_dir = os.path.join(save_dir, name)
    os.makedirs(person_dir, exist_ok=True)

    cap = cv2.VideoCapture(webcam_index)
    if not cap.isOpened():
        print("❌ Cannot open webcam. Check webcam_index or device.")
        return []

    print(f"[Enroll] Capturing {count} images for '{name}'. Press 'c' to capture, 'q' to quit early.")
    captured = 0
    images = []
    try:
        while captured < count:
            ret, frame = cap.read()
            if not ret:
                continue
            display = frame.copy()
            cv2.putText(display, f"Captures: {captured}/{count} - press 'c' to capture", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
            cv2.imshow("Enroll - press c to capture, q to quit", display)
            k = cv2.waitKey(1) & 0xFF
            if k == ord('c'):
                # save frame
                fname = os.path.join(person_dir, f"{name}_{int(time.time())}_{captured}.jpg")
                cv2.imwrite(fname, frame)
                images.append(fname)
                captured += 1
                print(f"[Enroll] Saved {fname} ({captured}/{count})")
                time.sleep(0.4)  # brief pause
            elif k == ord('q'):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
    return images

def compute_encodings(image_paths):
    encs = []
    for p in image_paths:
        img = face_recognition.load_image_file(p)
        boxes = face_recognition.face_locations(img)
        if len(boxes) == 0:
            print(f"[Enroll] No face found in {p}, skipping.")
            continue
        enc = face_recognition.face_encodings(img, boxes)[0]
        encs.append(enc)
    return encs

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Name for enrollment (e.g., 'Sarthak')")
    parser.add_argument("--count", type=int, default=DEFAULT_ENROLL_COUNT, help="Number of images to capture")
    parser.add_argument("--auto", action="store_true", help="Auto-capture images every second (no 'c' press)")
    args = parser.parse_args()

    if args.auto:
        print("[Enroll] Auto-capture mode: capturing every 1s")
        # simple auto-capture loop
        cap = cv2.VideoCapture(WEBCAM_INDEX)
        person_dir = os.path.join(ENROLL_DIR, args.name)
        os.makedirs(person_dir, exist_ok=True)
        captured = 0
        try:
            while captured < args.count:
                ret, frame = cap.read()
                if not ret:
                    continue
                fname = os.path.join(person_dir, f"{args.name}_{int(time.time())}_{captured}.jpg")
                cv2.imwrite(fname, frame)
                print(f"[Enroll] Saved {fname}")
                captured += 1
                time.sleep(1.0)
        finally:
            cap.release()
        images = [os.path.join(person_dir, f) for f in os.listdir(person_dir) if f.startswith(args.name)]
    else:
        images = capture_images(args.name, count=args.count)

    if not images:
        print("[Enroll] No images captured, aborting.")
        return

    encs = compute_encodings(images)
    if not encs:
        print("[Enroll] No valid face encodings found in captured images.")
        return

    fr = FaceRecognizer()
    fr.add_embeddings_for(args.name, encs)
    print(f"[Enroll] Enrollment complete for {args.name} with {len(encs)} encodings.")

if __name__ == "__main__":
    main()


