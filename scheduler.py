"""
scheduler.py — Background scheduler engine using APScheduler.
Checks the active profile every minute and fires the bell if time matches.
"""
import datetime
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import database as db
import audio

logger = logging.getLogger("scheduler")

scheduler = BackgroundScheduler(timezone="Europe/Moscow", daemon=True)

# Shared state for dashboard API
_state = {
    "last_check": None,
    "next_bell": None,       # {"time": "HH:MM", "label": "...", "seconds_left": N}
    "active_profile": None,
}


def get_state() -> dict:
    return dict(_state)


def _check_bells():
    """Called every minute to fire matching bells."""
    now = datetime.datetime.now()
    _state["last_check"] = now.isoformat(timespec="seconds")

    profile = db.get_profile_for_today()
    if not profile:
        logger.warning("No profile assigned for today.")
        _state["active_profile"] = None
        _state["next_bell"] = None
        return

    _state["active_profile"] = {"id": profile["id"], "name": profile["name"], "color": profile["color"]}
    bells = [b for b in db.list_bells(profile["id"]) if b["enabled"]]

    # Fire matching bells (within the same minute)
    fired_any = False
    for bell in bells:
        if bell["hour"] == now.hour and bell["minute"] == now.minute:
            logger.info(f"Firing bell: {bell['label']} at {bell['hour']:02d}:{bell['minute']:02d}")
            db.log_ring(profile["id"], bell["id"], trigger_type="auto", success=True)
            audio.ring_bell(
                sound_file=bell.get("sound_file", ""),
                duration=bell.get("duration", 5)
            )
            fired_any = True

    # Calculate next bell
    _update_next_bell(now, bells)
    if fired_any:
        # Re-calculate next bell after firing (skip current minute)
        pass


def _update_next_bell(now: datetime.datetime, bells: list):
    """Find the next upcoming bell and update shared state."""
    current_minutes = now.hour * 60 + now.minute
    upcoming = []
    for b in bells:
        bell_minutes = b["hour"] * 60 + b["minute"]
        if bell_minutes > current_minutes:
            upcoming.append((bell_minutes, b))

    if upcoming:
        upcoming.sort(key=lambda x: x[0])
        next_minutes, next_bell = upcoming[0]
        diff = next_minutes - current_minutes
        _state["next_bell"] = {
            "time": f"{next_bell['hour']:02d}:{next_bell['minute']:02d}",
            "label": next_bell.get("label", ""),
            "seconds_left": diff * 60,
            "bell_id": next_bell["id"],
        }
    else:
        _state["next_bell"] = None


def start():
    """Start the background scheduler."""
    if scheduler.running:
        return
    # Check every minute at :00 seconds
    scheduler.add_job(
        _check_bells,
        CronTrigger(second=0),
        id="bell_check",
        replace_existing=True,
        misfire_grace_time=30,
    )
    scheduler.start()
    logger.info("Scheduler started.")
    # Do an immediate check to populate state
    _check_bells()


def stop():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")


def refresh():
    """Force a re-check without waiting for the next cron trigger."""
    _check_bells()
