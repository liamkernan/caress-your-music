import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os

class SpotifyController:
    def __init__(self):
        client_id = os.environ.get('SPOTIFY_CLIENT_ID')
        client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            raise ValueError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables must be set")
        
        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri='http://127.0.0.1:8888/callback',
            scope='user-modify-playback-state user-read-playback-state'
        ))

        print("Spotify controller initialized!")

    def next_track(self):
        try:
            self.sp.next_track()
            print("Next track")
        except Exception as e:
            print(f"Error skipping track: {e}")

    def previous_track(self):
        try:
            self.sp.previous_track()
            print("Previous track")
        except Exception as e:
            print(f"Error going to previous track: {e}")

    def play_pause(self):
        try:
            playback = self.sp.current_playback()
            if playback and playback['is_playing']:
                self.sp.pause_playback()
                print("Paused")
            else:
                self.sp.start_playback()
                print("Playing")
        except Exception as e:
            print(f"Error toggling playback: {e}")

    def set_volume(self, volume_percent):
        try:
            volume_percent = max(0, min(100, volume_percent))
            self.sp.volume(volume_percent)
            print(f"Volume: {volume_percent}%")
        except Exception as e:
            print(f"Error setting volume: {e}")

    def adjust_volume(self, delta):
        """Adjust volume by delta amount"""
        try:
            playback = self.sp.current_playback()
            if playback:
                current_volume = playback['device']['volume_percent']
                new_volume = max(0, min(100, current_volume + delta))
                self.set_volume(new_volume)
        except Exception as e:
            print(f"Error adjusting volume: {e}")

    def seek_position(self, position_ms):
        try:
            self.sp.seek_track(position_ms)
            print(f"Seeked to {position_ms // 1000}s")
        except Exception as e:
            print(f"Error seeking: {e}")

    def get_current_track_info(self):
        """Get info about currently playing track"""
        try:
            playback = self.sp.current_playback()
            if playback and playback['item']:
                track = playback['item']
                return {
                    'name': track['name'],
                    'artist': track['artists'][0]['name'],
                    'duration_ms': track['duration_ms'],
                    'progress_ms': playback['progress_ms'],
                    'is_playing': playback['is_playing']
                }
        except Exception as e:
            print(f"Error getting track info: {e}")
        return None


# Test the Spotify controller
if __name__ == "__main__":
    controller = SpotifyController()

    # Get current track info
    info = controller.get_current_track_info()
    if info:
        print(f"Now playing: {info['name']} by {info['artist']}")
        print(f"Progress: {info['progress_ms']//1000}s / {info['duration_ms']//1000}s")