# Gesture-Controlled Spotify Player

Control Spotify with hand gestures using your webcam! Uses MediaPipe for real-time hand tracking and the Spotify Web API for playback control.

## Features

- **Swipe Left**: Previous track
- **Swipe Right**: Next track  
- **Pinch + Horizontal Movement**: Scrub through track (like a timeline)
- **Closed Fist (0 fingers)**: Play/Pause
- **Peace Sign (2 fingers)**: Volume up
- **3 Fingers**: Volume down

## Setup Instructions

### 1. Activate Virtual Environment

This project uses a virtual environment. Activate it before installing dependencies or running the code:

```bash
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Get Spotify API Credentials

You need to register with Spotify to get API access:

https://developer.spotify.com/dashboard

- **Redirect URI**: `http://127.0.0.1:8888/callback`
After creating, you'll see your **Client ID** and **Client Secret**

### 4. Set Environment Variables


export SPOTIFY_CLIENT_ID='your_client_id_here'
export SPOTIFY_CLIENT_SECRET='your_client_secret_here'

or

$env:SPOTIFY_CLIENT_ID='your_client_id_here'
$env:SPOTIFY_CLIENT_SECRET='your_client_secret_here'



### 5. Run the Application

**hand tracking only** (no Spotify needed):
```bash
python hand_tracker.py
```

**Full gesture controller** (requires Spotify):
```bash
python main.py
```


## How It Works

### Hand Tracking
- MediaPipe Hands provides 21 3D landmarks per hand in real-time
- We track specific landmarks to detect gestures:
  - **Wrist (0)** for swipe detection
  - **Thumb tip (4) + Index tip (8)** for pinch detection
  - **All fingertips vs knuckles** for counting extended fingers

### Gesture Detection Logic

**Swipe**: Tracks wrist movement over last 10 frames. If horizontal displacement > 150 pixels, triggers swipe gesture.

**Pinch w Open Hand**: Calculates Euclidean distance between thumb and index fingertips. Distance < 40 pixels = pinched.

**Finger Counting**: Compares Y-coordinates of fingertips vs PIP joints (fingertips should be above/higher when extended).

### Cooldown System
Prevents gesture spam by requiring 0.5 second cooldown between certain gestures (swipes, play/pause).


## License

MIT - Feel free to use and modify!
