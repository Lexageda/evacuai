import sqlite3, os, hashlib

DB_PATH = os.path.join(os.path.dirname(__file__), "evacuai.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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
            must_change_pw INTEGER NOT NULL DEFAULT 0
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
    """)
    db.commit()
    # Seed default admin
    hp = lambda p: hashlib.sha256(p.encode()).hexdigest()
    existing = db.execute("SELECT id FROM users WHERE student_id='ADMIN001'").fetchone()
    if not existing:
        db.execute("INSERT INTO users (name,student_id,password,role) VALUES (?,?,?,?)",
                   ('Administrator','ADMIN001', hp('admin123'), 'admin'))
        db.commit()
    db.close()
