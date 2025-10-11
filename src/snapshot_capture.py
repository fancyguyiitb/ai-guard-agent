"""
AI Room Guard System - Snapshot Capture Module

This module provides functionality for capturing and saving snapshots of intruders
during security escalations. It crops face regions from camera frames and saves
them with timestamped filenames for evidence collection.

Features:
- Face region cropping with padding
- Timestamped filename generation
- Automatic directory creation
- Error handling and logging

"""

import cv2
import os
import time
from datetime import datetime
from pathlib import Path
import logging

class SnapshotCapture:
    """
    Handles capturing and saving snapshots of intruders.
    
    Provides methods for cropping face regions from camera frames and saving
    them as timestamped image files for security evidence.
    """
    
    def __init__(self, snapshots_dir="data/logs/snapshots"):
        self.snapshots_dir = Path(snapshots_dir)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("SnapshotCapture")
        
    def capture_intruder_snapshot(self, frame, face_box=None):
        """
        Capture a snapshot of the intruder.
        
        Args:
            frame: OpenCV frame containing the intruder
            face_box: Tuple of (top, right, bottom, left) face coordinates
            
        Returns:
            str: Path to the saved snapshot file, or None if failed
        """
        try:
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"intruder_{timestamp}.jpg"
            snapshot_path = self.snapshots_dir / filename
            
            # If face box is provided, crop to face area with some padding
            if face_box:
                top, right, bottom, left = face_box
                height, width = frame.shape[:2]
                
                # Add padding around the face (20% on each side)
                padding = 50
                top = max(0, top - padding)
                left = max(0, left - padding)
                bottom = min(height, bottom + padding)
                right = min(width, right + padding)
                
                # Crop the frame to focus on the face area
                cropped_frame = frame[top:bottom, left:right]
                
                # If cropped frame is too small, use full frame
                if cropped_frame.shape[0] < 50 or cropped_frame.shape[1] < 50:
                    self.logger.warning("Cropped frame too small, using full frame")
                    cropped_frame = frame
            else:
                # Use full frame if no face box provided
                cropped_frame = frame
            
            # Save the snapshot
            success = cv2.imwrite(str(snapshot_path), cropped_frame)
            
            if success:
                self.logger.info(f"Snapshot saved: {snapshot_path}")
                return str(snapshot_path)
            else:
                self.logger.error(f"Failed to save snapshot: {snapshot_path}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error capturing snapshot: {e}")
            return None
    
    def capture_full_frame_snapshot(self, frame):
        """
        Capture a full frame snapshot.
        
        Args:
            frame: OpenCV frame
            
        Returns:
            str: Path to the saved snapshot file, or None if failed
        """
        return self.capture_intruder_snapshot(frame, face_box=None)
    
    def get_latest_snapshot(self):
        """
        Get the path to the most recently created snapshot.
        
        Returns:
            str: Path to the latest snapshot, or None if no snapshots exist
        """
        try:
            snapshots = list(self.snapshots_dir.glob("intruder_*.jpg"))
            if snapshots:
                # Sort by modification time and return the most recent
                latest = max(snapshots, key=lambda x: x.stat().st_mtime)
                return str(latest)
            return None
        except Exception as e:
            self.logger.error(f"Error getting latest snapshot: {e}")
            return None

# Global instance for easy access
snapshot_capture = SnapshotCapture()

def capture_intruder_snapshot(frame, face_box=None):
    """Capture intruder snapshot."""
    return snapshot_capture.capture_intruder_snapshot(frame, face_box)

def capture_full_frame_snapshot(frame):
    """Capture full frame snapshot."""
    return snapshot_capture.capture_full_frame_snapshot(frame)

def get_latest_snapshot():
    """Get latest snapshot path."""
    return snapshot_capture.get_latest_snapshot()
