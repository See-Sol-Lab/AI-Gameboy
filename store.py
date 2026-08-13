"""SQLite 存取:两张表,一份真相(蓝图 §9)。

只负责连接、建表与行读写;鉴权、revision 校验与规则调用在 game_host。
"""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS session (
    id                TEXT PRIMARY KEY,
    cartridge_id      TEXT NOT NULL,
    cartridge_version TEXT NOT NULL,
    status            TEXT NOT NULL CHECK (status IN ('lobby','playing','finished')),
    revision          INTEGER NOT NULL,
    engine_state_json TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS seat (
    session_id          TEXT NOT NULL,
    seat_id             TEXT NOT NULL,
    participant_type    TEXT NOT NULL,
    display_name        TEXT,
    surface             TEXT,
    public_profile_json TEXT,
    token_hash          TEXT NOT NULL,
    joined_at           TEXT,
    PRIMARY KEY (session_id, seat_id)
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.isolation_level = None  # 事务由调用方显式 BEGIN IMMEDIATE / COMMIT
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA)
    return conn


# ---------- session ----------

def insert_session(conn, sid, cartridge_id, cartridge_version, status,
                   revision, engine_state_json, created_at, updated_at):
    conn.execute(
        "INSERT INTO session (id, cartridge_id, cartridge_version, status, revision,"
        " engine_state_json, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
        (sid, cartridge_id, cartridge_version, status, revision,
         engine_state_json, created_at, updated_at),
    )


def get_session(conn, sid):
    return conn.execute("SELECT * FROM session WHERE id = ?", (sid,)).fetchone()


def update_session(conn, sid, status, revision, engine_state_json, updated_at):
    conn.execute(
        "UPDATE session SET status=?, revision=?, engine_state_json=?, updated_at=?"
        " WHERE id=?",
        (status, revision, engine_state_json, updated_at, sid),
    )


def list_sessions(conn):
    return conn.execute(
        "SELECT id, cartridge_id, cartridge_version, status, revision,"
        " created_at, updated_at FROM session ORDER BY created_at DESC"
    ).fetchall()


# ---------- seat ----------

def insert_seat(conn, session_id, seat_id, participant_type, token_hash, created_at):
    conn.execute(
        "INSERT INTO seat (session_id, seat_id, participant_type, token_hash, joined_at)"
        " VALUES (?,?,?,?,NULL)",
        (session_id, seat_id, participant_type, token_hash),
    )


def get_seats(conn, session_id):
    return conn.execute(
        "SELECT * FROM seat WHERE session_id = ? ORDER BY seat_id", (session_id,)
    ).fetchall()


def get_seat_by_token_hash(conn, session_id, token_hash):
    return conn.execute(
        "SELECT * FROM seat WHERE session_id = ? AND token_hash = ?",
        (session_id, token_hash),
    ).fetchone()


def update_seat_profile(conn, session_id, seat_id, display_name, surface,
                        public_profile_json, joined_at):
    conn.execute(
        "UPDATE seat SET display_name=?, surface=?, public_profile_json=?, joined_at=?"
        " WHERE session_id=? AND seat_id=?",
        (display_name, surface, public_profile_json, joined_at, session_id, seat_id),
    )
