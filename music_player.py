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
_current_track_path = None  # full path for repeat support
_is_playing = False
_lock = threading.Lock()
_queue = []  # list of file paths
_repeat = False  # repeat current track
_track_start_time = None  # when current track started (for timer)
_sleep_timer = None        # threading.Timer object
_sleep_timer_end = None    # epoch time when the timer fires

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
    global _current_track, _current_track_path, _is_playing, _track_start_time
    
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
            _current_track_path = filepath
            _is_playing = True
            _track_start_time = __import__('time').time()
            logger.info(f"Playing track: {_current_track}")
            return True
        except Exception as e:
            logger.error(f"Error playing track: {e}")
            _is_playing = False
            _current_track = None
            _current_track_path = None
            _track_start_time = None
            return False

def stop_track():
    """Stops the currently playing track."""
    global _current_track, _current_track_path, _is_playing, _track_start_time
    with _lock:
        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
            _is_playing = False
            _current_track = None
            _current_track_path = None
            _track_start_time = None
            logger.info("Music playback stopped.")
            return True
        except Exception as e:
            logger.error(f"Error stopping track: {e}")
            return False

def set_repeat(enabled: bool):
    """Enable or disable track repeat."""
    global _repeat
    _repeat = enabled
    logger.info(f"Repeat mode {'on' if enabled else 'off'}")

# ---- Sleep Timer ----

def _sleep_timer_fire():
    """Called by the threading.Timer when time is up."""
    global _sleep_timer, _sleep_timer_end
    logger.info("Sleep timer fired — stopping music.")
    stop_track()
    _sleep_timer = None
    _sleep_timer_end = None

def set_sleep_timer(seconds: int):
    """Start (or restart) the sleep timer."""
    import time
    global _sleep_timer, _sleep_timer_end
    # Cancel any existing timer
    if _sleep_timer is not None:
        _sleep_timer.cancel()
    if seconds <= 0:
        _sleep_timer = None
        _sleep_timer_end = None
        logger.info("Sleep timer cancelled.")
        return
    _sleep_timer = threading.Timer(seconds, _sleep_timer_fire)
    _sleep_timer.daemon = True
    _sleep_timer.start()
    _sleep_timer_end = time.time() + seconds
    logger.info(f"Sleep timer set for {seconds}s.")

def cancel_sleep_timer():
    """Cancel the active sleep timer."""
    global _sleep_timer, _sleep_timer_end
    if _sleep_timer is not None:
        _sleep_timer.cancel()
        _sleep_timer = None
        _sleep_timer_end = None
        logger.info("Sleep timer cancelled.")

def get_sleep_timer_remaining() -> int:
    """Returns seconds remaining on the sleep timer, or 0 if not active."""
    import time
    if _sleep_timer_end is None:
        return 0
    remaining = int(_sleep_timer_end - time.time())
    return max(0, remaining)
# ---- Queue Management ----

def add_to_queue(filepath: str):
    """Adds a track to the end of the playback queue."""
    if not os.path.exists(filepath):
        logger.error(f"Cannot queue — file not found: {filepath}")
        return False
    _queue.append(filepath)
    logger.info(f"Queued: {os.path.basename(filepath)} (queue size: {len(_queue)})")
    return True

def remove_from_queue(index: int):
    """Removes a track from the queue by index."""
    if 0 <= index < len(_queue):
        removed = _queue.pop(index)
        logger.info(f"Removed from queue: {os.path.basename(removed)}")
        return True
    return False

def get_queue():
    """Returns the current queue as a list of filenames."""
    return [os.path.basename(f) for f in _queue]

def clear_queue():
    """Clears the entire playback queue."""
    _queue.clear()
    logger.info("Queue cleared.")

def _play_next_from_queue():
    """Plays the next track from the queue, or repeats current if repeat is on."""
    global _current_track, _current_track_path, _is_playing, _track_start_time
    import time
    # Repeat current track
    if _repeat and _current_track_path and os.path.exists(_current_track_path):
        try:
            pygame.mixer.music.load(_current_track_path)
            pygame.mixer.music.play()
            _track_start_time = time.time()
            _is_playing = True
            logger.info(f"Repeating: {_current_track}")
            return
        except Exception as e:
            logger.error(f"Error repeating track: {e}")
    # Advance queue
    if _queue:
        next_path = _queue.pop(0)
        if os.path.exists(next_path):
            try:
                pygame.mixer.music.load(next_path)
                pygame.mixer.music.play()
                _current_track = os.path.basename(next_path)
                _current_track_path = next_path
                _is_playing = True
                _track_start_time = time.time()
                logger.info(f"Auto-playing next in queue: {_current_track}")
                return
            except Exception as e:
                logger.error(f"Error auto-playing next track: {e}")
    # Nothing left
    _is_playing = False
    _current_track = None
    _current_track_path = None
    _track_start_time = None

def get_status():
    """Returns the current player status including volume, queue, repeat and elapsed time."""
    global _current_track, _is_playing
    import time
    
    # pygame.mixer.music.get_busy() tells us if it's currently playing
    is_busy = False
    try:
        is_busy = pygame.mixer.music.get_busy()
    except:
        pass

    if _is_playing and not is_busy:
        # Track finished on its own — try to repeat or play next from queue
        with _lock:
            _play_next_from_queue()

    # Calculate elapsed seconds
    elapsed = 0
    if _track_start_time and _is_playing:
        elapsed = int(time.time() - _track_start_time)

    return {
        "current_track": _current_track,
        "is_playing": _is_playing,
        "volume": get_system_volume(),
        "queue": get_queue(),
        "repeat": _repeat,
        "elapsed": elapsed,
        "sleep_timer": get_sleep_timer_remaining(),
    }

