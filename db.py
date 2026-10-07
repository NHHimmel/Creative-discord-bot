import sqlite3
import os
import threading
import time
from typing import List, Optional, Tuple, Dict, Any

DB_PATH = "data/vault.db"
_local = threading.local()

def get_db():
    if not hasattr(_local, "conn") or _local.conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn

def init_db():
    os.makedirs("data", exist_ok=True)
    conn = get_db()
    with conn:
        # Quotes Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL UNIQUE,
                author_id INTEGER NOT NULL,
                author_name TEXT NOT NULL,
                content TEXT NOT NULL,
                jump_url TEXT NOT NULL,
                captured_by_id INTEGER NOT NULL,
                captured_by_name TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)

        # Guild Flashback Settings Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                flashback_channel_id INTEGER,
                last_flashback_date TEXT
            )
        """)

        # Economy User Balance & Timestamps Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS economy (
                user_id INTEGER,
                guild_id INTEGER,
                points INTEGER DEFAULT 0,
                last_daily REAL DEFAULT 0,
                last_chat_award REAL DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            )
        """)

        # Active Perks (like temporary nicknames or mutes that expire)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS active_perks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                perk_type TEXT NOT NULL,
                original_value TEXT,
                expires_at REAL NOT NULL
            )
        """)

# --- Quote Vault Helpers ---
def add_quote(guild_id: int, channel_id: int, message_id: int,
              author_id: int, author_name: str, content: str,
              jump_url: str, captured_by_id: int, captured_by_name: str) -> Optional[int]:
    conn = get_db()
    try:
        with conn:
            cur = conn.execute("""
                INSERT INTO quotes (
                    guild_id, channel_id, message_id, author_id, author_name,
                    content, jump_url, captured_by_id, captured_by_name, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (guild_id, channel_id, message_id, author_id, author_name,
                  content, jump_url, captured_by_id, captured_by_name, time.time()))
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None # Already archived

def get_random_quote(guild_id: int) -> Optional[sqlite3.Row]:
    conn = get_db()
    cur = conn.execute("""
        SELECT * FROM quotes WHERE guild_id = ? ORDER BY RANDOM() LIMIT 1
    """, (guild_id,))
    return cur.fetchone()

def get_quote_leaderboard(guild_id: int, limit: int = 10) -> List[Tuple[str, int]]:
    conn = get_db()
    cur = conn.execute("""
        SELECT author_name, COUNT(*) as quote_count
        FROM quotes
        WHERE guild_id = ?
        GROUP BY author_id, author_name
        ORDER BY quote_count DESC
        LIMIT ?
    """, (guild_id, limit))
    return [(row["author_name"], row["quote_count"]) for row in cur.fetchall()]

def get_all_quote_authors(guild_id: int) -> List[Tuple[int, str]]:
    conn = get_db()
    cur = conn.execute("""
        SELECT DISTINCT author_id, author_name FROM quotes WHERE guild_id = ?
    """, (guild_id,))
    return [(row["author_id"], row["author_name"]) for row in cur.fetchall()]

def get_total_quotes(guild_id: int) -> int:
    conn = get_db()
    cur = conn.execute("SELECT COUNT(*) FROM quotes WHERE guild_id = ?", (guild_id,))
    return cur.fetchone()[0]

def set_flashback_channel(guild_id: int, channel_id: int):
    conn = get_db()
    with conn:
        conn.execute("""
            INSERT INTO guild_settings (guild_id, flashback_channel_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET flashback_channel_id = excluded.flashback_channel_id
        """, (guild_id, channel_id))

def get_guild_settings(guild_id: int) -> Optional[sqlite3.Row]:
    conn = get_db()
    cur = conn.execute("SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,))
    return cur.fetchone()

def get_all_flashback_guilds() -> List[sqlite3.Row]:
    conn = get_db()
    cur = conn.execute("SELECT * FROM guild_settings WHERE flashback_channel_id IS NOT NULL")
    return cur.fetchall()

def update_flashback_date(guild_id: int, date_str: str):
    conn = get_db()
    with conn:
        conn.execute("UPDATE guild_settings SET last_flashback_date = ? WHERE guild_id = ?", (date_str, guild_id))

# --- Economy Helpers ---
def get_balance(user_id: int, guild_id: int) -> int:
    conn = get_db()
    cur = conn.execute("SELECT points FROM economy WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
    row = cur.fetchone()
    return row["points"] if row else 0

def add_points(user_id: int, guild_id: int, points: int) -> int:
    conn = get_db()
    with conn:
        cur = conn.execute("""
            INSERT INTO economy (user_id, guild_id, points)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, guild_id) DO UPDATE SET points = points + excluded.points
            RETURNING points
        """, (user_id, guild_id, points))
        return cur.fetchone()["points"]

def remove_points(user_id: int, guild_id: int, points: int) -> bool:
    current = get_balance(user_id, guild_id)
    if current < points:
        return False
    conn = get_db()
    with conn:
        conn.execute("UPDATE economy SET points = points - ? WHERE user_id = ? AND guild_id = ?", (points, user_id, guild_id))
    return True

def claim_daily(user_id: int, guild_id: int, reward: int = 250, cooldown_sec: int = 86400) -> Tuple[bool, int, float]:
    conn = get_db()
    now = time.time()
    cur = conn.execute("SELECT points, last_daily FROM economy WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
    row = cur.fetchone()
    last_daily = row["last_daily"] if row else 0
    current_points = row["points"] if row else 0

    if now - last_daily < cooldown_sec:
        remaining = cooldown_sec - (now - last_daily)
        return False, current_points, remaining

    with conn:
        cur = conn.execute("""
            INSERT INTO economy (user_id, guild_id, points, last_daily)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, guild_id) DO UPDATE SET
                points = points + excluded.points,
                last_daily = excluded.last_daily
            RETURNING points
        """, (user_id, guild_id, reward, now))
        new_balance = cur.fetchone()["points"]
        return True, new_balance, 0.0

def award_chat_activity(user_id: int, guild_id: int, points: int = 5, cooldown_sec: int = 60) -> bool:
    conn = get_db()
    now = time.time()
    cur = conn.execute("SELECT last_chat_award FROM economy WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
    row = cur.fetchone()
    last_award = row["last_chat_award"] if row else 0

    if now - last_award < cooldown_sec:
        return False

    with conn:
        conn.execute("""
            INSERT INTO economy (user_id, guild_id, points, last_chat_award)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, guild_id) DO UPDATE SET
                points = points + excluded.points,
                last_chat_award = excluded.last_chat_award
        """, (user_id, guild_id, points, now))
    return True

def get_rich_leaderboard(guild_id: int, limit: int = 10) -> List[Tuple[int, int]]:
    conn = get_db()
    cur = conn.execute("""
        SELECT user_id, points
        FROM economy
        WHERE guild_id = ?
        ORDER BY points DESC
        LIMIT ?
    """, (guild_id, limit))
    return [(row["user_id"], row["points"]) for row in cur.fetchall()]

# --- Active Perks Tracking ---
def add_active_perk(guild_id: int, user_id: int, perk_type: str, original_value: str, duration_sec: float):
    conn = get_db()
    expires_at = time.time() + duration_sec
    with conn:
        conn.execute("""
            INSERT INTO active_perks (guild_id, user_id, perk_type, original_value, expires_at)
            VALUES (?, ?, ?, ?, ?)
        """, (guild_id, user_id, perk_type, original_value, expires_at))

def get_expired_perks() -> List[sqlite3.Row]:
    conn = get_db()
    now = time.time()
    cur = conn.execute("SELECT * FROM active_perks WHERE expires_at <= ?", (now,))
    return cur.fetchall()

def remove_active_perk(perk_id: int):
    conn = get_db()
    with conn:
        conn.execute("DELETE FROM active_perks WHERE id = ?", (perk_id,))

def remove_user_active_perk(guild_id: int, user_id: int, perk_type: str):
    conn = get_db()
    with conn:
        conn.execute("DELETE FROM active_perks WHERE guild_id = ? AND user_id = ? AND perk_type = ?", (guild_id, user_id, perk_type))

def get_user_active_perk(guild_id: int, user_id: int, perk_type: str) -> Optional[sqlite3.Row]:
    conn = get_db()
    cur = conn.execute("SELECT * FROM active_perks WHERE guild_id = ? AND user_id = ? AND perk_type = ? ORDER BY expires_at DESC LIMIT 1", (guild_id, user_id, perk_type))
    return cur.fetchone()
