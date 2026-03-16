import json
import os
import secrets

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

DEFAULTS = {
    "SECRET_KEY": secrets.token_hex(32),
    "PORT": 5000,
    "HOST": "0.0.0.0",
    "DATABASE": "ringscheduler.db",
    "UPLOAD_FOLDER": "uploads",
    "BELL_MODE": "audio",        # "audio" | "script" | "both" | "log"
    "RELAY_SCRIPT": "",           # Path to .bat or .py script
    "DEFAULT_SOUND": "",          # Default audio file path
    "BELL_DURATION": 5,           # Seconds to ring (for audio mode)
    "DEBUG": False,
    "ADMIN_USERNAME": "admin",
    "ADMIN_PASSWORD": "admin",
}


def load_config():
    config = dict(DEFAULTS)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            config.update(saved)
        except Exception:
            pass
    return config


def save_config(data: dict):
    current = load_config()
    current.update(data)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)


# Ensure secret key is persisted across restarts
_cfg = load_config()
if not os.path.exists(CONFIG_FILE):
    save_config(_cfg)
elif "SECRET_KEY" not in json.load(open(CONFIG_FILE)):
    save_config({"SECRET_KEY": _cfg["SECRET_KEY"]})
