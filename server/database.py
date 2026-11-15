"""Small SQLite queue with a temporary delivery lease."""
import sqlite3
import time


def _connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path):
    with _connect(path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                lease_until INTEGER,
                acknowledged_at INTEGER
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_queue ON messages(acknowledged_at, lease_until, id)")


def enqueue_message(path, text):
    with _connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO messages(text, created_at) VALUES(?, ?)",
            (text, int(time.time())),
        )
        return cur.lastrowid


def lease_next_message(path, lease_seconds=120):
    now = int(time.time())
    with _connect(path) as conn:
        row = conn.execute(
            """SELECT id, text, created_at FROM messages
               WHERE acknowledged_at IS NULL AND (lease_until IS NULL OR lease_until < ?)
               ORDER BY id LIMIT 1""",
            (now,),
        ).fetchone()
        if row is None:
            return None
        conn.execute("UPDATE messages SET lease_until=? WHERE id=?",
                     (now + lease_seconds, row["id"]))
        return {"id": row["id"], "text": row["text"], "created_at": row["created_at"]}


def acknowledge_message(path, message_id):
    with _connect(path) as conn:
        cur = conn.execute(
            "UPDATE messages SET acknowledged_at=? WHERE id=? AND acknowledged_at IS NULL",
            (int(time.time()), message_id),
        )
        return cur.rowcount == 1


def list_messages(path, limit=20):
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT id, text, created_at, acknowledged_at FROM messages ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
        return [dict(row) for row in rows]
