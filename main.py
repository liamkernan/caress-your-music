import cv2
from hand_tracker import HandTracker
from spotify_controller import SpotifyController
import time

class GestureSpotifyController:
    def __init__(self):
        self.tracker = HandTracker()
        try:
            self.spotify = SpotifyController()
            self.spotify_enabled = True
        except Exception as e:
            print(f"could not connect to Spotify: {e}")
            print("running without Spotify control")
            self.spotify_enabled = False
        
        # Scrubbing state
        self.scrubbing_active = False
        self.scrub_start_x = None
        self.scrub_start_progress = None
        self.last_scrub_time = 0
        self.scrub_end_time = 0
        self.post_scrub_cooldown = 2.0
        
        # Volume control state
        self.last_volume_gesture = None
        self.last_volume_time = 0
        self.volume_gesture_armed = True
        
        # Play/pause control state
        self.last_play_pause_time = 0
        self.play_pause_armed = True
        
        # Swipe control state
        self.last_swipe_time = 0
        self.last_swipe_direction = None
        self.swipe_same_direction_cooldown = 0.8
        self.swipe_opposite_direction_cooldown = 3.0
        self.swipe_to_other_action_cooldown = 1.0
        
        # Gesture stability tracking
        self.stable_finger_count = None
        self.finger_count_start_time = 0
        self.stability_threshold = 0.3
        
        # Hand appearance cooldown
        self.hand_first_seen_time = 0
        self.hand_appearance_cooldown = 0.6
        self.hand_was_visible = False
        
        # Track info cache
        self.cached_track_info = None
        self.last_track_fetch_time = 0
        self.track_fetch_interval = 2.0
        
    def get_stable_finger_count(self, finger_count):
        current_time = time.time()
        
        if finger_count != self.stable_finger_count:
            self.stable_finger_count = finger_count
            self.finger_count_start_time = current_time
            return None
        
        if (current_time - self.finger_count_start_time) >= self.stability_threshold:
            return finger_count
        
        return None
    
    def handle_gestures(self, gesture, landmarks, finger_count):
        if not self.spotify_enabled:
            return
        
        stable_count = self.get_stable_finger_count(finger_count)
        current_time = time.time()
        time_since_swipe = current_time - self.last_swipe_time
        
        if gesture == "swipe_left":
            if self.last_swipe_direction == "left":
                cooldown = self.swipe_same_direction_cooldown
            elif self.last_swipe_direction == "right":
                cooldown = self.swipe_opposite_direction_cooldown
            else:
                cooldown = 0
            
            if time_since_swipe > cooldown:
                self.spotify.previous_track()
                self.last_swipe_time = current_time
                self.last_swipe_direction = "left"
                print("Swipe Left - Previous Track")
        
        elif gesture == "swipe_right":
            if self.last_swipe_direction == "right":
                cooldown = self.swipe_same_direction_cooldown
            elif self.last_swipe_direction == "left":
                cooldown = self.swipe_opposite_direction_cooldown
            else:
                cooldown = 0
            
            if time_since_swipe > cooldown:
                self.spotify.next_track()
                self.last_swipe_time = current_time
                self.last_swipe_direction = "right"
                print("Swipe Right - Next Track")
        
        play_pause_cooldown = 1.5
        play_pause_in_cooldown = (current_time - self.last_play_pause_time) < play_pause_cooldown
        after_swipe_cooldown = (current_time - self.last_swipe_time) < self.swipe_to_other_action_cooldown
        
        if stable_count == 1:
            if self.play_pause_armed and not play_pause_in_cooldown and not after_swipe_cooldown:
                self.spotify.play_pause()
                self.last_play_pause_time = current_time
                self.play_pause_armed = False
        elif stable_count is not None and stable_count != 1:
            if not play_pause_in_cooldown:
                self.play_pause_armed = True
        
        volume_cooldown = 1.0
        volume_in_cooldown = (current_time - self.last_volume_time) < volume_cooldown
        
        if stable_count is None:
            pass
        elif stable_count not in [2, 3]:
            if not volume_in_cooldown:
                self.volume_gesture_armed = True
                self.last_volume_gesture = None
        elif volume_in_cooldown or after_swipe_cooldown:
            pass
        elif not self.volume_gesture_armed:
            pass
        elif stable_count == 2 and self.last_volume_gesture != "up":
            self.spotify.adjust_volume(10)
            self.last_volume_gesture = "up"
            self.last_volume_time = current_time
            self.volume_gesture_armed = False
        elif stable_count == 3 and self.last_volume_gesture != "down":
            self.spotify.adjust_volume(-10)
            self.last_volume_gesture = "down"
            self.last_volume_time = current_time
            self.volume_gesture_armed = False
    
    def get_track_info_cached(self):
        current_time = time.time()
        if current_time - self.last_track_fetch_time > self.track_fetch_interval:
            self.cached_track_info = self.spotify.get_current_track_info()
            self.last_track_fetch_time = current_time
        return self.cached_track_info
    
    def run(self):
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        print("controls:")
        print("Swipe Left: Previous track")
        print("Swipe Right: Next track")
        print("Two hands (4+ fingers + pinch): Scrub track")
        print("1 finger: Play/Pause")
        print("2 fingers: Volume up")
        print("3 fingers: Volume down")
        print("Press 'q' to quit\n")
        
        frame_count = 0
        process_every_n_frames = 2
        prev_time = time.time()
        last_hand_landmarks = None
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            frame = cv2.flip(frame, 1)
            frame_count += 1
            current_time = time.time()
            
            if frame_count % process_every_n_frames == 0:
                hand_landmarks = self.tracker.get_hand_landmarks(frame)
                if hand_landmarks:
                    last_hand_landmarks = hand_landmarks
                else:
                    last_hand_landmarks = None
            else:
                hand_landmarks = last_hand_landmarks
            
            if self.tracker.last_landmarks:
                self.tracker.draw_landmarks(frame, self.tracker.last_landmarks)
            
            swipe_zone_y = int(frame.shape[0] * 0.85)
            cv2.line(frame, (0, swipe_zone_y), (frame.shape[1], swipe_zone_y), (100, 100, 100), 1)
            cv2.putText(frame, "Swipe zone above", (10, swipe_zone_y - 5),
                      cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1)
            
            if self.spotify_enabled:
                track_info = self.get_track_info_cached()
                if track_info:
                    status = ">" if track_info['is_playing'] else "||"
                    text = f"{status} {track_info['name'][:30]} - {track_info['artist'][:20]}"
                    cv2.putText(frame, text, (10, frame.shape[0] - 20),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            fps = 1 / (current_time - prev_time) if (current_time - prev_time) > 0 else 0
            prev_time = current_time
            cv2.putText(frame, f"FPS: {int(fps)}", (frame.shape[1] - 100, 30),
                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            
            if hand_landmarks and len(hand_landmarks) > 0:
                # Track hand appearance for cooldown
                if not self.hand_was_visible:
                    self.hand_first_seen_time = current_time
                    self.hand_was_visible = True
                    # Clear position history to prevent false swipe detection when hand first appears
                    self.tracker.position_history.clear()
                
                in_hand_appearance_cooldown = (current_time - self.hand_first_seen_time) < self.hand_appearance_cooldown
                
                all_hands_data = []
                for hand_lms in hand_landmarks:
                    landmarks = self.tracker.get_landmark_coords(hand_lms, frame.shape)
                    finger_count = self.tracker.count_extended_fingers(landmarks)
                    is_pinching = self.tracker.detect_pinch(landmarks)
                    all_hands_data.append({
                        'landmarks': landmarks,
                        'finger_count': finger_count,
                        'is_pinching': is_pinching,
                        'wrist_x': landmarks[0][0],
                        'wrist_y': landmarks[0][1]
                    })
                
                scrub_trigger_hand = None
                scrub_control_hand = None
                
                if len(all_hands_data) == 2:
                    hand1, hand2 = all_hands_data
                    if hand1['finger_count'] >= 4 and hand2['is_pinching']:
                        scrub_trigger_hand = hand1
                        scrub_control_hand = hand2
                    elif hand2['finger_count'] >= 4 and hand1['is_pinching']:
                        scrub_trigger_hand = hand2
                        scrub_control_hand = hand1
                
                if scrub_trigger_hand and scrub_control_hand:
                    pinch_x = scrub_control_hand['wrist_x']
                    
                    if not self.scrubbing_active:
                        self.scrubbing_active = True
                        self.scrub_start_x = pinch_x
                        track_info = self.get_track_info_cached()
                        if track_info:
                            self.scrub_start_progress = track_info['progress_ms']
                        print("Scrubbing started")
                    else:
                        if self.scrub_start_x is not None and self.scrub_start_progress is not None:
                            delta_x = pinch_x - self.scrub_start_x
                            scrub_ms = int(delta_x * 250)
                            
                            if abs(scrub_ms) > 500 and (current_time - self.last_scrub_time) > 0.2:
                                track_info = self.get_track_info_cached()
                                if track_info:
                                    new_position = max(0, min(
                                        self.scrub_start_progress + scrub_ms,
                                        track_info['duration_ms'] - 1000
                                    ))
                                    self.spotify.seek_position(int(new_position))
                                    self.last_scrub_time = current_time
                    
                    cv2.putText(frame, "SCRUBBING", (10, 110),
                              cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                else:
                    if self.scrubbing_active:
                        print("Scrubbing ended")
                        self.scrub_end_time = current_time
                    self.scrubbing_active = False
                    self.scrub_start_x = None
                    self.scrub_start_progress = None
                    
                    # If 2 hands visible but not scrubbing, block all single-hand gestures
                    two_hands_visible = len(all_hands_data) == 2
                    
                    if two_hands_visible:
                        cv2.putText(frame, "Two hands - scrub only", (10, 110),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.6, (128, 128, 128), 2)
                        self.handle_gestures(None, None, 0)
                        finger_count = all_hands_data[0]['finger_count']
                        cv2.putText(frame, f"Fingers: {finger_count}", (10, 70),
                                  cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
                    else:
                        in_post_scrub_cooldown = (current_time - self.scrub_end_time) < self.post_scrub_cooldown
                        in_any_cooldown = in_post_scrub_cooldown or in_hand_appearance_cooldown
                        
                        if in_any_cooldown:
                            cv2.putText(frame, "Cooldown...", (10, 110),
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, (128, 128, 128), 2)
                        
                        hand_data = all_hands_data[0]
                        landmarks = hand_data['landmarks']
                        finger_count = hand_data['finger_count']
                        
                        self.tracker.position_history.append(landmarks)
                        
                        gesture = None
                        frame_height = frame.shape[0]
                        wrist_y = landmarks[0][1]
                        hand_in_swipe_zone = wrist_y < (frame_height * 0.85)
                        
                        swipe = self.tracker.detect_swipe(landmarks)
                        if swipe and self.tracker.can_trigger_gesture() and hand_in_swipe_zone and not in_any_cooldown:
                            gesture = swipe
                            self.tracker.mark_gesture_triggered()
                        
                        if hand_data['is_pinching'] and not in_any_cooldown:
                            gesture = "pinch"
                        
                        if not in_any_cooldown:
                            self.handle_gestures(gesture, landmarks, finger_count)
                        else:
                            self.handle_gestures(None, landmarks, 0)
                        
                        if gesture and not in_any_cooldown:
                            cv2.putText(frame, f"Gesture: {gesture}", (10, 30),
                                      cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                        
                        cv2.putText(frame, f"Fingers: {finger_count}", (10, 70),
                                  cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
            else:
                self.hand_was_visible = False
                self.scrubbing_active = False
                self.scrub_start_x = None
                self.scrub_start_progress = None
                self.handle_gestures(None, None, 0)
                cv2.putText(frame, "Fingers: 0", (10, 70),
                          cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
            
            cv2.imshow('Gesture Spotify Controller', frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    controller = GestureSpotifyController()
    controller.run()
