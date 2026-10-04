import sqlite3, os, hashlib

DB_PATH = os.path.join(os.path.dirname(__file__), "evacuai.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hp(p):
    return hashlib.sha256(p.encode()).hexdigest()

def gen_password(sid):
    digits = ''.join(c for c in sid if c.isdigit())
    return 'uc@' + digits[-6:] if len(digits) >= 6 else 'uc@' + digits

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT NOT NULL,
            email          TEXT,
            student_id     TEXT UNIQUE,
            password       TEXT NOT NULL,
            role           TEXT NOT NULL DEFAULT 'student',
            must_change_pw INTEGER NOT NULL DEFAULT 0,
            phone          TEXT
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            type        TEXT NOT NULL DEFAULT 'general',
            user_id     INTEGER,
            message     TEXT NOT NULL,
            sender      TEXT NOT NULL,
            sender_role TEXT NOT NULL DEFAULT 'admin',
            created_at  TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'approved'
        );
        CREATE TABLE IF NOT EXISTS reports (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            location   TEXT NOT NULL,
            detail     TEXT,
            created_at TEXT NOT NULL,
            room_id    TEXT,
            floor      TEXT,
            pos_x      REAL,
            pos_y      REAL,
            confirmed  INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS safety_status (
            user_id    INTEGER PRIMARY KEY,
            is_safe    INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS sos_alerts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            sender       TEXT NOT NULL,
            created_at   TEXT NOT NULL,
            resolved     INTEGER NOT NULL DEFAULT 0,
            responded    INTEGER NOT NULL DEFAULT 0,
            responded_at TEXT,
            cancelled    INTEGER NOT NULL DEFAULT 0,
            notification TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS room_status (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id    TEXT NOT NULL UNIQUE,
            floor      TEXT NOT NULL,
            status     TEXT NOT NULL DEFAULT 'passable',
            set_by     INTEGER,
            updated_at TEXT,
            FOREIGN KEY (set_by) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS evacuation_status (
            user_id       INTEGER PRIMARY KEY,
            room          TEXT,
            floor         TEXT,
            is_evacuating INTEGER NOT NULL DEFAULT 0,
            updated_at    TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS schedules (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT NOT NULL,
            subject     TEXT NOT NULL,
            room        TEXT NOT NULL,
            day         TEXT NOT NULL,
            time_start  TEXT NOT NULL,
            time_end    TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS notifications (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            title      TEXT NOT NULL,
            body       TEXT NOT NULL,
            type       TEXT NOT NULL DEFAULT 'alert',
            created_at TEXT NOT NULL,
            is_read    INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS drill_sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            started_by INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            ended_at   TEXT,
            is_active  INTEGER NOT NULL DEFAULT 1,
            scenario   TEXT NOT NULL DEFAULT 'earthquake',
            notes      TEXT,
            FOREIGN KEY (started_by) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            actor_name TEXT NOT NULL,
            action     TEXT NOT NULL,
            detail     TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    db.commit()
    # Migrations for existing databases
    try:
        db.execute("ALTER TABLE users ADD COLUMN phone TEXT")
        db.commit()
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE drill_sessions ADD COLUMN notes TEXT")
        db.commit()
    except Exception:
        pass
    # Seed default admin
    existing = db.execute("SELECT id FROM users WHERE student_id='ADMIN001'").fetchone()
    if not existing:
        db.execute(
            "INSERT INTO users (name,student_id,password,role,must_change_pw) VALUES (?,?,?,?,0)",
            ('Administrator', 'ADMIN001', hp('admin123'), 'admin')
        )
        db.commit()
    db.close()