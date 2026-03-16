"""
app.py — Main Flask application entry point.
"""
import os
import csv
import io
import datetime
import logging
import zipfile
import shutil
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session, g, make_response
import re

def make_safe_filename(filename):
    filename = os.path.basename(filename)
    # Allow cyrillic, alphanumeric, space, dot, and dash
    filename = re.sub(r'[^\w\s\.\-а-яА-ЯёЁ]', '_', filename)
    filename = re.sub(r'\s+', '_', filename)
    return filename.strip('._')

import database as db
import audio
import scheduler as sched
import music_player
from auth import auth_bp, login_required, admin_required
from config import load_config, save_config
import bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("ringscheduler.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("app")

ALLOWED_EXTENSIONS = {"mp3", "wav", "ogg"}


def create_app():
    cfg = load_config()
    app = Flask(__name__)
    app.secret_key = cfg["SECRET_KEY"]
    app.permanent_session_lifetime = datetime.timedelta(days=30)

    # Ensure upload directory exists
    os.makedirs(cfg["UPLOAD_FOLDER"], exist_ok=True)

    # Initialize DB
    db.init_db()
    db.seed_defaults()

    # Register auth blueprint
    app.register_blueprint(auth_bp)

    # Start background scheduler
    sched.start()
    
    # Start Telegram Bot
    bot.start_bot()

    def allowed_file(filename):
        return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

    # ------------------------------------------------------------------ #
    #  CONTEXT PROCESSOR — inject current user into all templates
    # ------------------------------------------------------------------ #
    @app.context_processor
    def inject_user():
        user = None
        if "user_id" in session:
            user = db.get_user_by_id(session["user_id"])
        return {"current_user": user}

    # ================================================================== #
    #  MAIN PAGES
    # ================================================================== #

    @app.route("/")
    @login_required
    def dashboard():
        state = sched.get_state()
        profile = db.get_profile_for_today()
        bells = db.list_bells(profile["id"]) if profile else []
        log = db.get_ring_log(20)
        return render_template(
            "dashboard.html",
            state=state,
            profile=profile,
            bells=bells,
            ring_log=log,
        )

    @app.route("/schedule")
    @login_required
    def schedule():
        profiles = db.list_profiles()
        selected_id = request.args.get("profile_id", type=int)
        if not selected_id and profiles:
            selected_id = profiles[0]["id"]
        bells = db.list_bells(selected_id) if selected_id else []
        
        cfg = load_config()
        upload_folder = cfg["UPLOAD_FOLDER"]
        audio_files = []
        if os.path.isdir(upload_folder):
            audio_files = [
                f for f in os.listdir(upload_folder)
                if os.path.splitext(f)[1].lower() in (".mp3", ".wav", ".ogg")
            ]
            
        return render_template(
            "schedule.html",
            profiles=profiles,
            selected_id=selected_id,
            bells=bells,
            audio_files=audio_files,
        )

    @app.route("/profiles")
    @login_required
    def profiles():
        all_profiles = db.list_profiles()
        assignments = db.get_week_assignments()
        return render_template(
            "profiles.html",
            profiles=all_profiles,
            assignments=assignments,
        )

    @app.route("/settings")
    @admin_required
    def settings():
        cfg = load_config()
        users = db.list_users()
        upload_folder = cfg["UPLOAD_FOLDER"]
        audio_files = []
        if os.path.isdir(upload_folder):
            audio_files = [
                f for f in os.listdir(upload_folder)
                if os.path.splitext(f)[1].lower() in (".mp3", ".wav", ".ogg")
            ]
        return render_template(
            "settings.html",
            cfg=cfg,
            users=users,
            audio_files=audio_files,
        )

    @app.route("/log")
    @login_required
    def log_view():
        ring_log = db.get_ring_log(100)
        return render_template("log.html", ring_log=ring_log)

    @app.route("/calendar")
    @login_required
    def calendar():
        profiles = db.list_profiles()
        return render_template("calendar.html", profiles=profiles)

    @app.route("/music")
    @login_required
    def music():
        cfg = load_config()
        upload_folder = cfg["UPLOAD_FOLDER"]
        audio_files = []
        if os.path.isdir(upload_folder):
            audio_files = [
                {"name": f, "size": os.path.getsize(os.path.join(upload_folder, f))}
                for f in os.listdir(upload_folder)
                if os.path.splitext(f)[1].lower() in (".mp3", ".wav", ".ogg")
            ]
        status = music_player.get_status()
        return render_template("music.html", audio_files=audio_files, status=status)

    # ================================================================== #
    #  PROFILE API
    # ================================================================== #

    @app.route("/api/profiles", methods=["GET"])
    @login_required
    def api_list_profiles():
        return jsonify(db.list_profiles())

    @app.route("/api/profiles", methods=["POST"])
    @login_required
    def api_create_profile():
        data = request.json or {}
        name = data.get("name", "").strip()
        if not name:
            return jsonify({"error": "Название профиля обязательно"}), 400
        pid = db.create_profile(name, data.get("description", ""), data.get("color", "#3b82f6"))
        if pid is None:
            return jsonify({"error": "Профиль с таким именем уже существует"}), 409
        return jsonify(db.get_profile(pid)), 201

    @app.route("/api/profiles/<int:pid>", methods=["PUT"])
    @login_required
    def api_update_profile(pid):
        data = request.json or {}
        db.update_profile(pid, **data)
        sched.refresh()
        return jsonify(db.get_profile(pid))

    @app.route("/api/profiles/<int:pid>/activate", methods=["POST"])
    @login_required
    def api_activate_profile(pid):
        db.set_active_profile(pid)
        sched.refresh()
        return jsonify({"ok": True})

    @app.route("/api/profiles/<int:pid>", methods=["DELETE"])
    @login_required
    def api_delete_profile(pid):
        db.delete_profile(pid)
        sched.refresh()
        return jsonify({"ok": True})

    # ================================================================== #
    #  BELL API
    # ================================================================== #

    @app.route("/api/profiles/<int:pid>/bells", methods=["GET"])
    @login_required
    def api_list_bells(pid):
        return jsonify(db.list_bells(pid))

    @app.route("/api/profiles/<int:pid>/bells", methods=["POST"])
    @login_required
    def api_create_bell(pid):
        data = request.json or {}
        try:
            hour = int(data["hour"])
            minute = int(data["minute"])
        except (KeyError, ValueError):
            return jsonify({"error": "Нужно указать hour и minute"}), 400
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return jsonify({"error": "Некорректное время"}), 400
        bid = db.create_bell(
            pid, hour, minute,
            label=data.get("label", ""),
            sound_file=data.get("sound_file", ""),
            duration=int(data.get("duration", 5)),
            bell_type=data.get("bell_type", "lesson"),
        )
        sched.refresh()
        return jsonify(db.get_bell(bid)), 201

    @app.route("/api/bells/<int:bid>", methods=["PUT"])
    @login_required
    def api_update_bell(bid):
        data = request.json or {}
        db.update_bell(bid, **data)
        sched.refresh()
        return jsonify(db.get_bell(bid))

    @app.route("/api/bells/<int:bid>", methods=["DELETE"])
    @login_required
    def api_delete_bell(bid):
        db.delete_bell(bid)
        sched.refresh()
        return jsonify({"ok": True})

    @app.route("/api/profiles/<int:pid>/export", methods=["GET"])
    @login_required
    def api_export_schedule(pid):
        bells = db.list_bells(pid)
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(["hour", "minute", "label", "sound_file", "duration", "bell_type", "enabled"])
        for b in bells:
            cw.writerow([
                b["hour"], b["minute"], b.get("label", ""), b.get("sound_file", ""),
                b.get("duration", 5), b.get("bell_type", "lesson"), b.get("enabled", 1)
            ])
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = f"attachment; filename=schedule_profile_{pid}.csv"
        output.headers["Content-type"] = "text/csv; charset=utf-8"
        return output

    @app.route("/api/profiles/<int:pid>/import", methods=["POST"])
    @login_required
    def api_import_schedule(pid):
        if "file" not in request.files:
            return jsonify({"error": "No file part"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No selected file"}), 400
            
        try:
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_input = csv.DictReader(stream)
            
            # Simple validation to ensure it's the right format
            if not csv_input.fieldnames or "hour" not in csv_input.fieldnames or "minute" not in csv_input.fieldnames:
                return jsonify({"error": "Invalid CSV format. Missing 'hour' or 'minute' columns"}), 400
                
            imported_count = 0
            for row in csv_input:
                try:
                    h = int(row["hour"])
                    m = int(row["minute"])
                    if 0 <= h <= 23 and 0 <= m <= 59:
                        db.create_bell(
                            pid, h, m,
                            label=row.get("label", ""),
                            sound_file=row.get("sound_file", ""),
                            duration=int(row.get("duration", 5) or 5),
                            bell_type=row.get("bell_type", "lesson")
                        )
                        imported_count += 1
                except ValueError:
                    continue # skip invalid rows
                    
            sched.refresh()
            return jsonify({"ok": True, "count": imported_count})
        except Exception as e:
            return jsonify({"error": f"Error parsing CSV: {str(e)}"}), 400

    # ================================================================== #
    #  WEEK ASSIGNMENT API
    # ================================================================== #

    @app.route("/api/week-assignments", methods=["GET"])
    @login_required
    def api_week_assignments():
        return jsonify(db.get_week_assignments())

    @app.route("/api/week-assignments", methods=["POST"])
    @login_required
    def api_set_week_assignment():
        data = request.json or {}
        weekday = data.get("weekday")
        profile_id = data.get("profile_id")  # None = unassign
        if weekday is None or weekday not in range(7):
            return jsonify({"error": "weekday must be 0-6"}), 400
        db.set_week_assignment(weekday, profile_id)
        sched.refresh()
        return jsonify({"ok": True})

    # ================================================================== #
    #  CALENDAR API
    # ================================================================== #

    @app.route("/api/calendar/<int:year>/<int:month>", methods=["GET"])
    @login_required
    def api_get_calendar(year, month):
        overrides = db.get_calendar_overrides(year, month)
        return jsonify(overrides)

    @app.route("/api/calendar", methods=["POST"])
    @login_required
    def api_set_calendar_override():
        data = request.json or {}
        date_str = data.get("date")
        if not date_str:
            return jsonify({"error": "date is required"}), 400
        profile_id = data.get("profile_id") # None = no bells
        if profile_id == "":
            profile_id = None
        desc = data.get("description", "")
        db.set_calendar_override(date_str, profile_id, desc)
        sched.refresh()
        return jsonify({"ok": True})

    @app.route("/api/calendar/<date_str>", methods=["DELETE"])
    @login_required
    def api_delete_calendar_override(date_str):
        db.delete_calendar_override(date_str)
        sched.refresh()
        return jsonify({"ok": True})

    # ================================================================== #
    #  SETTINGS API
    # ================================================================== #

    @app.route("/api/settings", methods=["POST"])
    @admin_required
    def api_save_settings():
        data = request.json or {}
        allowed_keys = {
            "BELL_MODE", "RELAY_SCRIPT", "DEFAULT_SOUND", "BELL_DURATION",
            "EMERGENCY_FIRE_SOUND", "EMERGENCY_DRILL_SOUND", "EMERGENCY_LOCKDOWN_SOUND",
            "TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_PASSWORD"
        }
        filtered = {k: v for k, v in data.items() if k in allowed_keys}
        save_config(filtered)
        
        # Restart bot if token changed
        if "TELEGRAM_BOT_TOKEN" in filtered:
            bot.restart_bot()
            
        return jsonify({"ok": True})

    @app.route("/api/upload-audio", methods=["POST"])
    @login_required # Changed from admin_required for operator access
    def api_upload_audio():
        cfg = load_config()
        if "file" not in request.files:
            return jsonify({"error": "No file"}), 400
        f = request.files["file"]
        if not f.filename or not allowed_file(f.filename):
            return jsonify({"error": "Invalid file type. Allowed: mp3, wav, ogg"}), 400
        filename = make_safe_filename(f.filename)
        dest = os.path.join(cfg["UPLOAD_FOLDER"], filename)
        f.save(dest)
        return jsonify({"ok": True, "filename": filename, "path": os.path.abspath(dest)})

    @app.route("/api/upload-audio/<path:filename>", methods=["DELETE"])
    @login_required # Changed from admin_required for operator access
    def api_delete_audio(filename):
        cfg = load_config()
        # Prevent directory traversal
        filename = make_safe_filename(filename)
        dest = os.path.join(cfg["UPLOAD_FOLDER"], filename)
        if os.path.exists(dest):
            try:
                os.remove(dest)
                return jsonify({"ok": True})
            except Exception as e:
                return jsonify({"error": f"Ошибка удаления: {str(e)}"}), 500
        return jsonify({"error": "Файл не найден"}), 404

    @app.route("/api/music/play", methods=["POST"])
    @login_required
    def api_music_play():
        data = request.json or {}
        filename = data.get("filename")
        if not filename:
             return jsonify({"error": "Трек не выбран"}), 400
             
        cfg = load_config()
        safe_name = make_safe_filename(filename)
        filepath = os.path.join(cfg["UPLOAD_FOLDER"], safe_name)
        
        if music_player.play_track(filepath):
            return jsonify({"ok": True, "status": music_player.get_status()})
        return jsonify({"error": "Ошибка воспроизведения"}), 500

    @app.route("/api/music/stop", methods=["POST"])
    @login_required
    def api_music_stop():
        if music_player.stop_track():
            return jsonify({"ok": True, "status": music_player.get_status()})
        return jsonify({"error": "Ошибка остановки"}), 500

    @app.route("/api/music/volume", methods=["POST"])
    @login_required
    def api_music_volume():
        data = request.json or {}
        try:
            level = int(data.get("volume", 50))
        except ValueError:
             return jsonify({"error": "Некорректная громкость"}), 400
             
        if music_player.set_system_volume(level):
            return jsonify({"ok": True, "status": music_player.get_status()})
        return jsonify({"error": "Ошибка изменения громкости"}), 500

    @app.route("/api/music/status", methods=["GET"])
    @login_required
    def api_music_status():
        return jsonify(music_player.get_status())

    @app.route("/api/change-password", methods=["POST"])
    @login_required
    def api_change_password():
        data = request.json or {}
        uid = session.get("user_id")
        old_pw = data.get("old_password", "")
        new_pw = data.get("new_password", "")
        if not new_pw or len(new_pw) < 4:
            return jsonify({"error": "Новый пароль слишком короткий (мин. 4 символа)"}), 400
        user = db.get_user_by_id(uid)
        from werkzeug.security import check_password_hash
        if not check_password_hash(user["password_hash"], old_pw):
            return jsonify({"error": "Неверный текущий пароль"}), 403
        db.update_user_password(uid, new_pw)
        return jsonify({"ok": True})

    @app.route("/api/users", methods=["POST"])
    @admin_required
    def api_create_user():
        data = request.json or {}
        username = data.get("username", "").strip()
        password = data.get("password", "")
        is_admin = bool(data.get("is_admin", False))
        if not username or not password:
            return jsonify({"error": "Логин и пароль обязательны"}), 400
        if db.create_user(username, password, is_admin):
            return jsonify({"ok": True}), 201
        return jsonify({"error": "Пользователь уже существует"}), 409

    @app.route("/api/users/<int:uid>", methods=["DELETE"])
    @admin_required
    def api_delete_user(uid):
        if uid == session.get("user_id"):
            return jsonify({"error": "Нельзя удалить себя"}), 400
        db.delete_user(uid)
        return jsonify({"ok": True})

    # ================================================================== #
    #  STATUS + MANUAL RING
    # ================================================================== #

    @app.route("/api/status")
    @login_required
    def api_status():
        state = sched.get_state()
        now = datetime.datetime.now()
        return jsonify({
            "server_time": now.strftime("%H:%M:%S"),
            "server_date": now.strftime("%A, %d %B %Y"),
            "weekday": now.weekday(),
            "next_bell": state.get("next_bell"),
            "active_profile": state.get("active_profile"),
        })

    @app.route("/api/ring-now", methods=["POST"])
    @login_required
    def api_ring_now():
        cfg = load_config()
        sound = request.json.get("sound_file", "") if request.json else ""
        audio.ring_bell(sound_file=sound or cfg.get("DEFAULT_SOUND", ""))
        profile = db.get_profile_for_today()
        db.log_ring(
            profile["id"] if profile else None,
            None,
            trigger_type="manual",
            success=True,
            notes=f"Manual ring by user {session.get('user_id')}"
        )
        return jsonify({"ok": True, "message": "Звонок подан!"})

    @app.route("/api/emergency/<path:type>", methods=["POST"])
    @login_required
    def api_emergency_alert(type):
        """Trigger an emergency alert of a specific type."""
        cfg = load_config()
        sound = ""
        label = "Экстренная тревога"
        
        if type == "fire":
            sound = cfg.get("EMERGENCY_FIRE_SOUND", "")
            label = "Пожарная тревога"
        elif type == "drill":
            sound = cfg.get("EMERGENCY_DRILL_SOUND", "")
            label = "Учебная тревога"
        elif type == "lockdown":
            sound = cfg.get("EMERGENCY_LOCKDOWN_SOUND", "")
            label = "Блокировка"
        else:
            return jsonify({"error": "Unknown emergency type"}), 400

        audio.ring_bell(sound_file=sound, duration=60) # Emergency plays longer
        
        profile = db.get_profile_for_today()
        db.log_ring(
            profile["id"] if profile else None,
            None,
            trigger_type="emergency",
            success=True,
            notes=f"Emergency ({type}) by user {session.get('user_id')}"
        )
        return jsonify({"ok": True, "message": f"{label} запущена!"})

    @app.route("/api/test-bell", methods=["POST"])
    @admin_required
    def api_test_bell():
        """Test bell without logging."""
        cfg = load_config()
        audio.ring_bell(sound_file=cfg.get("DEFAULT_SOUND", ""), duration=2)
        return jsonify({"ok": True})

    return app


if __name__ == "__main__":
    cfg = load_config()
    app = create_app()
    app.run(
        host=cfg.get("HOST", "0.0.0.0"),
        port=int(cfg.get("PORT", 5000)),
        debug=cfg.get("DEBUG", False),
        use_reloader=False,  # Reloader breaks APScheduler
    )
