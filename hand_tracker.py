import cv2
import numpy as np
from collections import deque
import time
import os
import tempfile
import urllib.request

# New MediaPipe API imports
from mediapipe.tasks.python.vision import HandLandmarker, HandLandmarkerOptions
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision.core import image as mp_image_module


class HandTracker:
    def __init__(self):
        # Download model if needed
        model_url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
        model_path = os.path.join(tempfile.gettempdir(), "hand_landmarker.task")
        
        if not os.path.exists(model_path):
            print(f"Downloading hand landmarker model to {model_path}...")
            urllib.request.urlretrieve(model_url, model_path)
            print("downloaded")

        base_options = BaseOptions(model_asset_path=model_path)
        options = HandLandmarkerOptions(
            base_options=base_options,
            num_hands=2,
            min_hand_detection_confidence=0.4,
            min_hand_presence_confidence=0.4,
            min_tracking_confidence=0.4
        )
        self.hand_landmarker = HandLandmarker.create_from_options(options)

        # Store recent hand positions for gesture detection
        self.position_history = deque(maxlen=10)

        # Gesture cooldown to prevent spam
        self.last_gesture_time = 0
        self.cooldown_seconds = 0.5

        # Cache last landmarks to display even when skipping frames
        self.last_landmarks = None
        self.last_landmark_list = None  # Store the list format for drawing

    def get_hand_landmarks(self, frame):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp_image_module.Image(image_format=mp_image_module.ImageFormat.SRGB, data=rgb_frame)
        
        detection_result = self.hand_landmarker.detect(mp_image)
        
        if detection_result.hand_landmarks:
            self.last_landmark_list = detection_result.hand_landmarks
            self.last_landmarks = list(detection_result.hand_landmarks)
            return self.last_landmarks
        else:
            return None

    def draw_landmarks(self, frame, hand_landmarks):
        """Draw hand landmarks on frame"""
        if hand_landmarks is None or len(hand_landmarks) == 0:
            return
            
        # Draw each hand's landmarks
        for hand_landmark_list in hand_landmarks:
            # Draw connections
            connections = [
                # Thumb
                (0, 1), (1, 2), (2, 3), (3, 4),
                # Index finger
                (0, 5), (5, 6), (6, 7), (7, 8),
                # Middle finger
                (5, 9), (9, 10), (10, 11), (11, 12),
                # Ring finger
                (9, 13), (13, 14), (14, 15), (15, 16),
                # Pinky
                (13, 17), (17, 18), (18, 19), (19, 20),
                # Wrist connections
                (0, 17)
            ]
            
            h, w = frame.shape[:2]
            
            # Draw connections
            for connection in connections:
                start_idx, end_idx = connection
                if start_idx < len(hand_landmark_list) and end_idx < len(hand_landmark_list):
                    start = hand_landmark_list[start_idx]
                    end = hand_landmark_list[end_idx]
                    
                    start_x = int(start.x * w)
                    start_y = int(start.y * h)
                    end_x = int(end.x * w)
                    end_y = int(end.y * h)
                    
                    cv2.line(frame, (start_x, start_y), (end_x, end_y), (0, 255, 0), 2)
            
            # Draw landmarks
            for landmark in hand_landmark_list:
                x = int(landmark.x * w)
                y = int(landmark.y * h)
                cv2.circle(frame, (x, y), 5, (0, 0, 255), -1)

    def get_landmark_coords(self, hand_landmarks, frame_shape):
        """Convert normalized landmarks to pixel coordinates"""
        h, w, _ = frame_shape
        landmarks = []

        for lm in hand_landmarks:
            # Convert normalized coordinates to pixels
            x = int(lm.x * w)
            y = int(lm.y * h)
            landmarks.append((x, y))

        return landmarks

    def detect_swipe(self, landmarks):
        if len(self.position_history) < 8:
            return None

        wrist_positions = [pos[0] for pos in self.position_history]
        
        start_x = wrist_positions[0][0]
        end_x = wrist_positions[-1][0]
        start_y = wrist_positions[0][1]
        end_y = wrist_positions[-1][1]
        
        horizontal_distance = end_x - start_x
        vertical_distance = abs(end_y - start_y)

        horizontal_threshold = 120
        vertical_threshold = 80
        
        if abs(horizontal_distance) > horizontal_threshold and vertical_distance < vertical_threshold:
            if abs(horizontal_distance) > vertical_distance * 1.5:
                self.position_history.clear()
                
                if horizontal_distance > 0:
                    return "swipe_right"
                else:
                    return "swipe_left"

        return None

    def calculate_distance(self, point1, point2):
        """Calculate Euclidean distance between two points"""
        return np.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2)

    def detect_pinch(self, landmarks):
        """Detect pinch gesture (thumb tip + index tip)"""
        # Thumb tip = landmark 4, Index tip = landmark 8
        thumb_tip = landmarks[4]
        index_tip = landmarks[8]

        distance = self.calculate_distance(thumb_tip, index_tip)

        # Pinch detected when distance is small
        if distance < 40:  # pixels, tune this threshold
            return True
        return False

    def count_extended_fingers(self, landmarks):
        """Count how many fingers are extended"""
        # Finger tip and PIP joint landmark indices
        # Thumb: 4, 3
        # Index: 8, 6
        # Middle: 12, 10
        # Ring: 16, 14
        # Pinky: 20, 18

        finger_tips = [4, 8, 12, 16, 20]
        finger_pips = [3, 6, 10, 14, 18]

        extended_count = 0

        for i in range(5):
            tip = landmarks[finger_tips[i]]
            pip = landmarks[finger_pips[i]]

            # For most fingers, tip should be above PIP when extended
            # (lower y value since origin is top-left)
            if i == 0:  # Thumb is special
                # Check horizontal distance for thumb
                if abs(tip[0] - pip[0]) > 30:
                    extended_count += 1
            else:
                if tip[1] < pip[1] - 10:  # Tip above PIP
                    extended_count += 1

        return extended_count

    def can_trigger_gesture(self):
        """Check if enough time has passed since last gesture"""
        current_time = time.time()
        if current_time - self.last_gesture_time > self.cooldown_seconds:
            return True
        return False

    def mark_gesture_triggered(self):
        """Mark that a gesture was just triggered"""
        self.last_gesture_time = time.time()

    def __del__(self):
        """Cleanup when object is destroyed"""
        if hasattr(self, 'hand_landmarker'):
            self.hand_landmarker.close()


def main():
    # Initialize webcam with lower resolution for better performance
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)  # Reduced from 640
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)  # Reduced from 480
    cap.set(cv2.CAP_PROP_FPS, 30)

    tracker = HandTracker()

    # FPS tracking
    prev_time = time.time()
    frame_count = 0

    # Lower = more responsive but slower FPS
    # Higher = faster FPS but less responsive
    process_every_n_frames = 3  # Increased from 2 for M2 Pro

    print("Optimized hand tracking started. Press 'q' to quit.")
    print(f"Camera FPS: {cap.get(cv2.CAP_PROP_FPS)}")
    print(f"Processing every {process_every_n_frames} frames")

    # Store last detected values to display between frames
    last_gesture = None
    last_finger_count = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Flip frame horizontally for mirror effect
        frame = cv2.flip(frame, 1)

        frame_count += 1

        # Only process hand detection every N frames for performance
        if frame_count % process_every_n_frames == 0:
            hand_landmarks = tracker.get_hand_landmarks(frame)

            # Process gestures if hands detected
            if hand_landmarks:
                for hand_lms in hand_landmarks:
                    # Get pixel coordinates
                    landmarks = tracker.get_landmark_coords(hand_lms, frame.shape)

                    # Store position history
                    tracker.position_history.append(landmarks)

                    # Detect gestures
                    gesture = None

                    # Check swipe
                    swipe = tracker.detect_swipe(landmarks)
                    if swipe and tracker.can_trigger_gesture():
                        gesture = swipe
                        tracker.mark_gesture_triggered()
                        last_gesture = gesture

                    # Check pinch
                    if tracker.detect_pinch(landmarks):
                        gesture = "pinch"
                        last_gesture = gesture

                    # Count fingers
                    last_finger_count = tracker.count_extended_fingers(landmarks)

        # Always draw landmarks (even on skipped frames, use cached)
        if tracker.last_landmarks:
            tracker.draw_landmarks(frame, tracker.last_landmarks)

        # Display last detected values
        if last_gesture:
            cv2.putText(frame, f"Gesture: {last_gesture}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.putText(frame, f"Fingers: {last_finger_count}", (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

        # Calculate and display FPS
        current_time = time.time()
        fps = 1 / (current_time - prev_time)
        prev_time = current_time
        cv2.putText(frame, f"FPS: {int(fps)}", (10, frame.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        # Show frame
        cv2.imshow('Gesture Controller (Optimized)', frame)

        # Quit on 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
