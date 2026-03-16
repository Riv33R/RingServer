import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from config import load_config

cfg = load_config()
DB_PATH = os.path.join(os.path.dirname(__file__), cfg["DATABASE"])


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            color TEXT DEFAULT '#3b82f6',
            is_active INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS bells (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL,
            hour INTEGER NOT NULL,
            minute INTEGER NOT NULL,
            label TEXT DEFAULT '',
            sound_file TEXT DEFAULT '',
            duration INTEGER DEFAULT 5,
            bell_type TEXT DEFAULT 'lesson',
            enabled INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS week_assignments (
            weekday INTEGER PRIMARY KEY,
            profile_id INTEGER,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS ring_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER,
            bell_id INTEGER,
            triggered_at TEXT NOT NULL,
            trigger_type TEXT DEFAULT 'auto',
            success INTEGER DEFAULT 1,
            notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS calendar_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE NOT NULL,
            profile_id INTEGER,
            description TEXT DEFAULT '',
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE SET NULL
        );
    """)

    # Seed default week_assignments rows (0=Mon ... 6=Sun)
    for wd in range(7):
        cur.execute(
            "INSERT OR IGNORE INTO week_assignments (weekday, profile_id) VALUES (?, NULL)",
            (wd,)
        )

    conn.commit()
    conn.close()


def seed_defaults():
    """Create default admin user and sample profiles if DB is empty."""
    conn = get_db()
    cur = conn.cursor()

    # Default admin
    cur.execute("SELECT id FROM users WHERE username = ?", (cfg["ADMIN_USERNAME"],))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)",
            (cfg["ADMIN_USERNAME"], generate_password_hash(cfg["ADMIN_PASSWORD"]))
        )

    # Default profiles
    default_profiles = [
        ("Обычный день",    "Стандартное расписание",          "#3b82f6"),
        ("Сокращённый день","Расписание для коротких дней",    "#f59e0b"),
        ("Суббота",         "Расписание для субботних занятий", "#8b5cf6"),
        ("Карантин/Экзамен","Расписание во время карантина",   "#ef4444"),
    ]
    for name, desc, color in default_profiles:
        cur.execute(
            "INSERT OR IGNORE INTO profiles (name, description, color) VALUES (?, ?, ?)",
            (name, desc, color)
        )

    # Activate 'Обычный день' by default
    cur.execute("UPDATE profiles SET is_active = 1 WHERE name = 'Обычный день'")

    # Assign weekdays 0-4 (Mon-Fri) to first profile
    cur.execute("SELECT id FROM profiles WHERE name = 'Обычный день'")
    row = cur.fetchone()
    if row:
        pid = row["id"]
        for wd in range(5):
            cur.execute(
                "UPDATE week_assignments SET profile_id = ? WHERE weekday = ? AND profile_id IS NULL",
                (pid, wd)
            )

    # Sample bells for 'Обычный день'
    cur.execute("SELECT id FROM profiles WHERE name = 'Обычный день'")
    row = cur.fetchone()
    if row:
        pid = row["id"]
        cur.execute("SELECT COUNT(*) as cnt FROM bells WHERE profile_id = ?", (pid,))
        if cur.fetchone()["cnt"] == 0:
            sample_bells = [
                (pid, 8,  0,  "Звонок на 1 урок",    "lesson"),
                (pid, 8,  45, "Звонок с 1 урока",    "break"),
                (pid, 8,  55, "Звонок на 2 урок",    "lesson"),
                (pid, 9,  40, "Звонок с 2 урока",    "break"),
                (pid, 9,  50, "Звонок на 3 урок",    "lesson"),
                (pid, 10, 35, "Звонок с 3 урока",    "break"),
                (pid, 10, 50, "Звонок на 4 урок",    "lesson"),
                (pid, 11, 35, "Звонок с 4 урока",    "break"),
                (pid, 11, 45, "Звонок на 5 урок",    "lesson"),
                (pid, 12, 30, "Звонок с 5 урока",    "break"),
                (pid, 12, 40, "Звонок на 6 урок",    "lesson"),
                (pid, 13, 25, "Звонок с 6 урока",    "break"),
                (pid, 13, 35, "Звонок на 7 урок",    "lesson"),
                (pid, 14, 20, "Конец уроков",         "end"),
            ]
            cur.executemany(
                "INSERT INTO bells (profile_id, hour, minute, label, bell_type) VALUES (?,?,?,?,?)",
                sample_bells
            )

    conn.commit()
    conn.close()


# --------------- USER CRUD ---------------

def get_user_by_username(username):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(uid):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def verify_password(username, password):
    user = get_user_by_username(username)
    if user and check_password_hash(user["password_hash"], password):
        return user
    return None


def create_user(username, password, is_admin=False):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
            (username, generate_password_hash(password), int(is_admin))
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def update_user_password(uid, new_password):
    conn = get_db()
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(new_password), uid)
    )
    conn.commit()
    conn.close()


def delete_user(uid):
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id = ? AND is_admin = 0", (uid,))
    conn.commit()
    conn.close()


def list_users():
    conn = get_db()
    rows = conn.execute("SELECT id, username, is_admin FROM users ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --------------- PROFILE CRUD ---------------

def list_profiles():
    conn = get_db()
    rows = conn.execute("SELECT * FROM profiles ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_profile(pid):
    conn = get_db()
    row = conn.execute("SELECT * FROM profiles WHERE id = ?", (pid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_profile(name, description="", color="#3b82f6"):
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO profiles (name, description, color) VALUES (?, ?, ?)",
            (name, description, color)
        )
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        return new_id
    except sqlite3.IntegrityError:
        conn.close()
        return None


def update_profile(pid, **kwargs):
    allowed = {"name", "description", "color", "is_active"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn = get_db()
    conn.execute(
        f"UPDATE profiles SET {set_clause} WHERE id = ?",
        (*fields.values(), pid)
    )
    conn.commit()
    conn.close()


def set_active_profile(pid):
    conn = get_db()
    conn.execute("UPDATE profiles SET is_active = 0")
    conn.execute("UPDATE profiles SET is_active = 1 WHERE id = ?", (pid,))
    conn.commit()
    conn.close()


def delete_profile(pid):
    conn = get_db()
    conn.execute("DELETE FROM profiles WHERE id = ?", (pid,))
    conn.commit()
    conn.close()


def get_active_profile():
    conn = get_db()
    row = conn.execute("SELECT * FROM profiles WHERE is_active = 1 LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def get_profile_for_today():
    """Returns the profile assigned to today's weekday, or a calendar override if set. Otherwise the globally active one."""
    import datetime
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    weekday = now.weekday()  # 0=Mon
    
    conn = get_db()
    
    # 1. Check for calendar override
    override = conn.execute("""
        SELECT co.profile_id, p.name, p.color, p.description, p.is_active, co.description as override_msg
        FROM calendar_overrides co
        LEFT JOIN profiles p ON p.id = co.profile_id
        WHERE co.date = ?
    """, (today_str,)).fetchone()
    
    if override is not None:
        conn.close()
        # If profile_id is NULL, it means "No bells today"
        if override["profile_id"] is None:
            return None
        # Otherwise, yield the overridden profile
        profile = dict(override)
        profile["id"] = override["profile_id"]
        return profile

    # 2. Check week assignment
    wa_row = conn.execute("SELECT profile_id FROM week_assignments WHERE weekday = ?", (weekday,)).fetchone()
    if wa_row:
        pid = wa_row["profile_id"]
        if pid is None:
            conn.close()
            return None
        p_row = conn.execute("SELECT * FROM profiles WHERE id = ?", (pid,)).fetchone()
        conn.close()
        return dict(p_row) if p_row else get_active_profile()
        
    conn.close()
    return get_active_profile()

# --------------- CALENDAR OVERRIDES ---------------

def get_calendar_overrides(year, month):
    """Get overrides for a specific month (YYYY-MM)"""
    conn = get_db()
    prefix = f"{year:04d}-{month:02d}-%"
    rows = conn.execute("""
        SELECT co.*, p.name as profile_name, p.color
        FROM calendar_overrides co
        LEFT JOIN profiles p ON p.id = co.profile_id
        WHERE co.date LIKE ?
        ORDER BY co.date
    """, (prefix,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_calendar_override(date_str):
    conn = get_db()
    row = conn.execute("""
        SELECT co.*, p.name as profile_name, p.color 
        FROM calendar_overrides co
        LEFT JOIN profiles p ON p.id = co.profile_id
        WHERE co.date = ?
    """, (date_str,)).fetchone()
    conn.close()
    return dict(row) if row else None


def set_calendar_override(date_str, profile_id, description=""):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO calendar_overrides (date, profile_id, description) VALUES (?, ?, ?)",
        (date_str, profile_id, description)
    )
    conn.commit()
    conn.close()


def delete_calendar_override(date_str):
    conn = get_db()
    conn.execute("DELETE FROM calendar_overrides WHERE date = ?", (date_str,))
    conn.commit()
    conn.close()


# --------------- BELL CRUD ---------------

def list_bells(profile_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM bells WHERE profile_id = ? ORDER BY hour, minute",
        (profile_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_bell(bell_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM bells WHERE id = ?", (bell_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_bell(profile_id, hour, minute, label="", sound_file="", duration=5, bell_type="lesson"):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO bells (profile_id, hour, minute, label, sound_file, duration, bell_type) VALUES (?,?,?,?,?,?,?)",
        (profile_id, hour, minute, label, sound_file, duration, bell_type)
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def update_bell(bell_id, **kwargs):
    allowed = {"hour", "minute", "label", "sound_file", "duration", "bell_type", "enabled"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn = get_db()
    conn.execute(
        f"UPDATE bells SET {set_clause} WHERE id = ?",
        (*fields.values(), bell_id)
    )
    conn.commit()
    conn.close()


def delete_bell(bell_id):
    conn = get_db()
    conn.execute("DELETE FROM bells WHERE id = ?", (bell_id,))
    conn.commit()
    conn.close()


# --------------- WEEK ASSIGNMENTS ---------------

def get_week_assignments():
    conn = get_db()
    rows = conn.execute("""
        SELECT wa.weekday, wa.profile_id, p.name as profile_name, p.color
        FROM week_assignments wa
        LEFT JOIN profiles p ON p.id = wa.profile_id
        ORDER BY wa.weekday
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_week_assignment(weekday, profile_id):
    conn = get_db()
    conn.execute(
        "UPDATE week_assignments SET profile_id = ? WHERE weekday = ?",
        (profile_id, weekday)
    )
    conn.commit()
    conn.close()


# --------------- SETTINGS ---------------

def get_setting(key, default=None):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, str(value))
    )
    conn.commit()
    conn.close()


def get_all_settings():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


# --------------- RING LOG ---------------

def log_ring(profile_id, bell_id, trigger_type="auto", success=True, notes=""):
    import datetime
    conn = get_db()
    conn.execute(
        "INSERT INTO ring_log (profile_id, bell_id, triggered_at, trigger_type, success, notes) VALUES (?,?,?,?,?,?)",
        (profile_id, bell_id, datetime.datetime.now().isoformat(timespec="seconds"),
         trigger_type, int(success), notes)
    )
    conn.commit()
    conn.close()


def get_ring_log(limit=50):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM ring_log ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
