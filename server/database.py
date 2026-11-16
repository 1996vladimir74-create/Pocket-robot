"""SQLite queues for direct robot delivery and iPhone BLE relay."""
import sqlite3
import time

ROBOT_ONLINE_SECONDS = 45


def _connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path):
    with _connect(path) as conn:
        for table in ("messages", "phone_messages"):
            conn.execute("""CREATE TABLE IF NOT EXISTS %s (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                lease_until INTEGER,
                acknowledged_at INTEGER
            )""" % table)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_%s_queue ON %s(acknowledged_at, lease_until, id)"
                % (table, table)
            )
        conn.execute("""CREATE TABLE IF NOT EXISTS device_presence (
            device_id TEXT PRIMARY KEY,
            last_seen INTEGER NOT NULL
        )""")


def touch_robot(path):
    now = int(time.time())
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO device_presence(device_id,last_seen) VALUES('robot',?) "
            "ON CONFLICT(device_id) DO UPDATE SET last_seen=excluded.last_seen",
            (now,),
        )


def robot_is_online(path, online_seconds=ROBOT_ONLINE_SECONDS):
    now = int(time.time())
    with _connect(path) as conn:
        row = conn.execute(
            "SELECT last_seen FROM device_presence WHERE device_id='robot'"
        ).fetchone()
    return bool(row and now - int(row["last_seen"]) <= online_seconds)


def enqueue_message(path, text):
    """Create independent delivery records; clients select the active route."""
    now = int(time.time())
    with _connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO messages(text,created_at) VALUES(?,?)", (text, now)
        )
        conn.execute(
            "INSERT INTO phone_messages(text,created_at) VALUES(?,?)", (text, now)
        )
        return cur.lastrowid


def _lease(path, table, lease_seconds=120):
    now = int(time.time())
    with _connect(path) as conn:
        row = conn.execute(
            "SELECT id,text,created_at FROM " + table +
            " WHERE acknowledged_at IS NULL AND (lease_until IS NULL OR lease_until < ?)"
            " ORDER BY id LIMIT 1",
            (now,),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE " + table + " SET lease_until=? WHERE id=?",
            (now + lease_seconds, row["id"]),
        )
        return dict(row)


def lease_next_message(path, lease_seconds=120):
    return _lease(path, "messages", lease_seconds)


def lease_next_phone_message(path, lease_seconds=120):
    return _lease(path, "phone_messages", lease_seconds)


def _ack(path, table, message_id):
    with _connect(path) as conn:
        cur = conn.execute(
            "UPDATE " + table +
            " SET acknowledged_at=? WHERE id=? AND acknowledged_at IS NULL",
            (int(time.time()), message_id),
        )
        return cur.rowcount == 1


def acknowledge_message(path, message_id):
    # Both queue rows represent the same logical event and share the same ID.
    robot_ok = _ack(path, "messages", message_id)
    _ack(path, "phone_messages", message_id)
    return robot_ok


def acknowledge_phone_message(path, message_id):
    # A successful BLE relay must also retire the direct-Wi-Fi copy.
    phone_ok = _ack(path, "phone_messages", message_id)
    _ack(path, "messages", message_id)
    return phone_ok

def list_messages(path, limit=20):
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT id,text,created_at,acknowledged_at FROM messages ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
        return [dict(row) for row in rows]
