import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("DATABASE_PATH", "bot_data.db")

# Columns that may be changed through set_user_value (whitelist for safety).
USER_COLUMNS = {
    "alarm_time", "pending_prompt", "sleep_date", "sleep_response",
    "lunch_date", "summary", "model", "search_enabled",
    "lat", "lon", "place",
}


@contextmanager
def connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                slept INTEGER DEFAULT 0,
                last_alarm TEXT DEFAULT '06:00'
            )
        """)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        additions = {
            "alarm_time": "TEXT DEFAULT '06:00'",
            "pending_prompt": "TEXT",
            "sleep_date": "TEXT",
            "sleep_response": "TEXT",
            "lunch_date": "TEXT",
            "summary": "TEXT",            # rolling summary of older conversation
            "model": "TEXT",              # per-user model override (NULL = default)
            "search_enabled": "INTEGER",  # NULL = default
            "lat": "REAL",
            "lon": "REAL",
            "place": "TEXT",
        }
        for name, definition in additions.items():
            if name not in columns:
                conn.execute(f"ALTER TABLE users ADD COLUMN {name} {definition}")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS alarms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                alarm_time TEXT NOT NULL,
                due_at REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                stopped_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alarms_user_status ON alarms(user_id, status)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id, id)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                memory TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)


# -------------------- Users --------------------

def register_user(user_id):
    with connection() as conn:
        conn.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))


def get_user(user_id):
    with connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_all_users():
    with connection() as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM users").fetchall()]


def set_user_value(user_id, column, value):
    if column not in USER_COLUMNS:
        raise ValueError(f"Column not allowed: {column}")
    with connection() as conn:
        conn.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))
        conn.execute(f"UPDATE users SET {column}=? WHERE user_id=?", (value, user_id))


def set_user_alarm_time(user_id, value):
    with connection() as conn:
        conn.execute("UPDATE users SET alarm_time=?, last_alarm=? WHERE user_id=?", (value, value, user_id))


def set_pending_prompt(user_id, value):
    set_user_value(user_id, "pending_prompt", value)


def set_sleep_state(user_id, date_text, response):
    with connection() as conn:
        conn.execute("UPDATE users SET sleep_date=?, sleep_response=? WHERE user_id=?", (date_text, response, user_id))


def set_lunch_date(user_id, date_text):
    set_user_value(user_id, "lunch_date", date_text)


# -------------------- Alarms --------------------

def create_alarm(user_id, alarm_time, due_at):
    with connection() as conn:
        conn.execute(
            "UPDATE alarms SET status='stopped', stopped_at=CURRENT_TIMESTAMP "
            "WHERE user_id=? AND status IN ('pending','ringing')", (user_id,)
        )
        cur = conn.execute(
            "INSERT INTO alarms(user_id,alarm_time,due_at,status) VALUES(?,?,?,'pending')",
            (user_id, alarm_time, due_at)
        )
        return cur.lastrowid


def get_alarm(alarm_id):
    with connection() as conn:
        row = conn.execute("SELECT * FROM alarms WHERE id=?", (alarm_id,)).fetchone()
        return dict(row) if row else None


def get_active_alarm(user_id):
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM alarms WHERE user_id=? AND status IN ('pending','ringing') ORDER BY id DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        return dict(row) if row else None


def get_unfinished_alarms():
    with connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM alarms WHERE status IN ('pending','ringing')").fetchall()]


def set_alarm_status(alarm_id, status):
    if status not in {"pending", "ringing", "stopped"}:
        raise ValueError("Invalid alarm status")
    with connection() as conn:
        if status == "stopped":
            conn.execute("UPDATE alarms SET status=?, stopped_at=CURRENT_TIMESTAMP WHERE id=?", (status, alarm_id))
        else:
            conn.execute("UPDATE alarms SET status=? WHERE id=?", (status, alarm_id))


# -------------------- Conversation history --------------------

def add_message(user_id, role, content):
    with connection() as conn:
        conn.execute("INSERT INTO messages(user_id,role,content) VALUES(?,?,?)", (user_id, role, content))
        # Hard safety cap; normal trimming is done by summarisation.
        conn.execute("""
            DELETE FROM messages WHERE user_id=? AND id NOT IN
            (SELECT id FROM messages WHERE user_id=? ORDER BY id DESC LIMIT 400)
        """, (user_id, user_id))


def get_recent_messages(user_id, limit=24):
    with connection() as conn:
        rows = conn.execute(
            "SELECT role,content FROM messages WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]


def count_messages(user_id):
    with connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM messages WHERE user_id=?", (user_id,)).fetchone()[0]


def get_oldest_messages(user_id, limit):
    with connection() as conn:
        rows = conn.execute(
            "SELECT id,role,content FROM messages WHERE user_id=? ORDER BY id ASC LIMIT ?",
            (user_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]


def delete_messages_through(user_id, max_id):
    with connection() as conn:
        conn.execute("DELETE FROM messages WHERE user_id=? AND id<=?", (user_id, max_id))


def peek_last_user_message(user_id):
    with connection() as conn:
        row = conn.execute(
            "SELECT id,content FROM messages WHERE user_id=? AND role='user' ORDER BY id DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        return dict(row) if row else None


def delete_messages_from(user_id, min_id):
    with connection() as conn:
        conn.execute("DELETE FROM messages WHERE user_id=? AND id>=?", (user_id, min_id))


def clear_messages(user_id):
    with connection() as conn:
        conn.execute("DELETE FROM messages WHERE user_id=?", (user_id,))
        conn.execute("UPDATE users SET summary=NULL WHERE user_id=?", (user_id,))


# -------------------- Memories --------------------

def add_memory(user_id, memory):
    with connection() as conn:
        conn.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))
        conn.execute("INSERT INTO memories(user_id,memory) VALUES(?,?)", (user_id, memory[:500]))


def get_memories(user_id):
    with connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT id,memory FROM memories WHERE user_id=? ORDER BY id", (user_id,)
        ).fetchall()]


def delete_memory(user_id, number):
    memories = get_memories(user_id)
    if number < 1 or number > len(memories):
        return False
    memory_id = memories[number - 1]["id"]
    with connection() as conn:
        conn.execute("DELETE FROM memories WHERE id=? AND user_id=?", (memory_id, user_id))
    return True