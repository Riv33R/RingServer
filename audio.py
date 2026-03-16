"""
audio.py — Bell execution engine.
Supports:
  - WAV playback via winsound (Windows built-in, no deps)
  - MP3 playback via playsound3 (pip install playsound3)
  - External script execution (.bat / .py)
  - "log" mode for testing without audio hardware
"""
import os
import threading
import subprocess
import logging
import time
from config import load_config

logger = logging.getLogger("audio")


def _play_wav(filepath: str, duration: int):
    """Play a WAV file using winsound (blocking, repeated for duration seconds)."""
    try:
        import winsound
        # If duration is 0 or less, play once
        if duration <= 0:
            winsound.PlaySound(filepath, winsound.SND_FILENAME | winsound.SND_NODEFAULT)
            return

        end_time = time.time() + duration
        while time.time() < end_time:
            winsound.PlaySound(filepath, winsound.SND_FILENAME | winsound.SND_NODEFAULT)
    except Exception as e:
        logger.error(f"winsound error: {e}")


def _play_mp3(filepath: str, duration: int):
    """Play an MP3 using playsound3 (cross-platform, requires playsound3)."""
    try:
        from playsound3 import playsound
        # If duration is 0 or less, play once
        if duration <= 0:
            playsound(filepath, block=True)
            return

        # playsound3 plays once; loop it for duration
        end_time = time.time() + duration
        while time.time() < end_time:
            playsound(filepath, block=True)
    except ImportError:
        logger.warning("playsound3 not installed. Falling back to winsound (WAV only).")
        _play_wav(filepath, duration)
    except Exception as e:
        logger.error(f"playsound3 error: {e}")


def _run_script(script_path: str, duration: int):
    """Execute an external script for relay control."""
    if not os.path.exists(script_path):
        logger.error(f"Relay script not found: {script_path}")
        return
    try:
        ext = os.path.splitext(script_path)[1].lower()
        if ext == ".bat":
            cmd = ["cmd.exe", "/c", script_path, str(duration)]
        elif ext == ".py":
            import sys
            cmd = [sys.executable, script_path, str(duration)]
        else:
            cmd = [script_path, str(duration)]
        result = subprocess.run(cmd, timeout=duration + 10, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Script exited {result.returncode}: {result.stderr}")
        else:
            logger.info(f"Script completed: {result.stdout.strip()}")
    except subprocess.TimeoutExpired:
        logger.warning("Relay script timed out.")
    except Exception as e:
        logger.error(f"Script execution error: {e}")


def _bell_worker(sound_file: str, duration: int, mode: str, relay_script: str):
    """Worker function run in a daemon thread."""
    logger.info(f"🔔 RING! mode={mode} sound={sound_file!r} duration={duration}s")

    if mode == "log":
        logger.info("Bell triggered (log mode — no audio/relay)")
        return

    if mode in ("audio", "both"):
        if sound_file and os.path.exists(sound_file):
            ext = os.path.splitext(sound_file)[1].lower()
            if ext == ".wav":
                _play_wav(sound_file, duration)
            else:
                _play_mp3(sound_file, duration)
        else:
            # Fallback: system beep
            try:
                import winsound
                for _ in range(max(1, duration // 1)):
                    winsound.Beep(880, 800)
                    time.sleep(0.2)
            except Exception as e:
                logger.warning(f"System beep failed: {e}")

    if mode in ("script", "both"):
        if relay_script:
            _run_script(relay_script, duration)
        else:
            logger.warning("Relay script mode selected but no script path configured.")


def ring_bell(sound_file: str = "", duration: int = None, mode: str = None):
    """
    Trigger the bell asynchronously in a daemon thread.
    Falls back to config defaults if not provided.
    """
    cfg = load_config()
    if duration is None:
        duration = int(cfg.get("BELL_DURATION", 5))
    if mode is None:
        mode = cfg.get("BELL_MODE", "audio")
    relay_script = cfg.get("RELAY_SCRIPT", "")

    # Resolve sound_file: use provided → config default → empty
    if not sound_file:
        sound_file = cfg.get("DEFAULT_SOUND", "")

    t = threading.Thread(
        target=_bell_worker,
        args=(sound_file, duration, mode, relay_script),
        daemon=True,
        name="bell-worker"
    )
    t.start()
    return t
