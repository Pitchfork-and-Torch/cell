"""Local sqlite: inbound cache + rate counters."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from cell.models import Message


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            sid TEXT PRIMARY KEY,
            direction TEXT,
            from_n TEXT,
            to_n TEXT,
            body TEXT,
            status TEXT,
            created TEXT,
            error TEXT,
            source TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS usage (
            day TEXT,
            kind TEXT,
            count INTEGER,
            PRIMARY KEY (day, kind)
        )
        """
    )
    con.commit()
    return con


def upsert_message(con: sqlite3.Connection, msg: Message, source: str = "provider") -> None:
    con.execute(
        """
        INSERT INTO messages (sid, direction, from_n, to_n, body, status, created, error, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(sid) DO UPDATE SET
            direction=excluded.direction,
            from_n=excluded.from_n,
            to_n=excluded.to_n,
            body=excluded.body,
            status=excluded.status,
            created=excluded.created,
            error=excluded.error
        """,
        (
            msg.sid,
            msg.direction,
            msg.from_n,
            msg.to,
            msg.body,
            msg.status,
            msg.created,
            msg.error,
            source,
        ),
    )
    con.commit()


def list_local(con: sqlite3.Connection, limit: int = 20, with_n: str | None = None) -> list[Message]:
    if with_n:
        rows = con.execute(
            """
            SELECT * FROM messages
            WHERE from_n = ? OR to_n = ?
            ORDER BY created DESC, sid DESC
            LIMIT ?
            """,
            (with_n, with_n, limit),
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT * FROM messages ORDER BY created DESC, sid DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        Message(
            sid=r["sid"],
            direction=r["direction"] or "",
            from_n=r["from_n"] or "",
            to=r["to_n"] or "",
            body=r["body"] or "",
            status=r["status"] or "",
            created=r["created"] or "",
            error=r["error"] or "",
        )
        for r in rows
    ]


def known_sids(con: sqlite3.Connection) -> set[str]:
    return {r[0] for r in con.execute("SELECT sid FROM messages")}


def bump_usage(con: sqlite3.Connection, kind: str) -> int:
    day = date.today().isoformat()
    con.execute(
        "INSERT INTO usage (day, kind, count) VALUES (?, ?, 1) ON CONFLICT(day, kind) DO UPDATE SET count = count + 1",
        (day, kind),
    )
    con.commit()
    row = con.execute("SELECT count FROM usage WHERE day = ? AND kind = ?", (day, kind)).fetchone()
    return int(row[0]) if row else 1


def usage_today(con: sqlite3.Connection, kind: str) -> int:
    day = date.today().isoformat()
    row = con.execute("SELECT count FROM usage WHERE day = ? AND kind = ?", (day, kind)).fetchone()
    return int(row[0]) if row else 0
