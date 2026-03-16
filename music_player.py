import os
import logging
import threading

import pygame
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

logger = logging.getLogger("music_player")

# Initialize pygame mixer once
try:
    pygame.mixer.init()
except Exception as e:
    logger.error(f"Failed to initialize pygame mixer: {e}")

_current_track = None
_is_playing = False
_lock = threading.Lock()

def get_system_volume():
    """Returns the current system volume as an integer (0-100)."""
    try:
        import comtypes
        comtypes.CoInitialize()
        from pycaw.pycaw import AudioUtilities
        devices = AudioUtilities.GetAllDevices()
        for d in devices:
            if d.state == 1 and hasattr(d, 'EndpointVolume') and d.EndpointVolume:
                current = d.EndpointVolume.GetMasterVolumeLevelScalar()
                return int(round(current * 100))
    except Exception as e:
        logger.error(f"Error getting volume: {e}")
        
    try:
        return int(round(pygame.mixer.music.get_volume() * 100))
    except:
        return 50  # Fallback

def set_system_volume(level: int):
    """Sets the system volume (0-100)."""
    level = max(0, min(100, level))
    
    # 1. Update pygame player volume
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.set_volume(level / 100.0)
    except Exception as e:
        logger.warning(f"Could not set pygame volume: {e}")
        
    # 2. Update windows master volume for all active devices
    try:
        import comtypes
        comtypes.CoInitialize()
        from pycaw.pycaw import AudioUtilities
        devices = AudioUtilities.GetAllDevices()
        changed = False
        for d in devices:
            if d.state == 1 and hasattr(d, 'EndpointVolume') and d.EndpointVolume:
                d.EndpointVolume.SetMasterVolumeLevelScalar(level / 100.0, None)
                changed = True
        
        if changed:
            logger.info(f"System volume set to {level}% on all active devices")
        else:
            logger.warning(f"No active audio devices found. Pygame volume set to {level}%")
        return True
    except Exception as e:
        logger.error(f"Error setting Windows volume: {e}")
        return True # Return true since pygame volume was still updated

def play_track(filepath: str):
    """Plays an audio file using pygame.mixer.music"""
    global _current_track, _is_playing
    
    if not os.path.exists(filepath):
        logger.error(f"Track not found: {filepath}")
        return False

    with _lock:
        try:
            # Stop existing
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
                
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            _current_track = os.path.basename(filepath)
            _is_playing = True
            logger.info(f"Playing track: {_current_track}")
            return True
        except Exception as e:
            logger.error(f"Error playing track: {e}")
            _is_playing = False
            _current_track = None
            return False

def stop_track():
    """Stops the currently playing track."""
    global _current_track, _is_playing
    with _lock:
        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
            _is_playing = False
            _current_track = None
            logger.info("Music playback stopped.")
            return True
        except Exception as e:
            logger.error(f"Error stopping track: {e}")
            return False

def get_status():
    """Returns the current player status including volume."""
    global _current_track, _is_playing
    
    # pygame.mixer.music.get_busy() tells us if it's currently playing
    is_busy = False
    try:
        is_busy = pygame.mixer.music.get_busy()
    except:
        pass

    if _is_playing and not is_busy:
        # Track finished on its own
        with _lock:
            _is_playing = False
            _current_track = None

    return {
        "current_track": _current_track,
        "is_playing": _is_playing,
        "volume": get_system_volume()
    }
