"""Small durable SQLite store. Every operation owns and closes its connection."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

from app.journal_models import SurfSession


def spot_key(lat: float, lon: float) -> str:
    return f"{round(lat, 4) + 0.0:.4f},{round(lon, 4) + 0.0:.4f}"


class JournalStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise RuntimeError("Journal database schema is newer than this application")
            db.execute("""CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, spot TEXT NOT NULL,
                session_at TEXT NOT NULL, body TEXT NOT NULL
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS sessions_spot_time ON sessions(spot, session_at DESC)")
            db.execute("PRAGMA user_version = 1")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, session_id: str) -> SurfSession | None:
        with self.connect() as db:
            row = db.execute("SELECT body FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return SurfSession.model_validate_json(row[0]) if row else None

    def list(self, spot: str | None = None) -> list[SurfSession]:
        with self.connect() as db:
            if spot is None:
                rows = db.execute("SELECT body FROM sessions ORDER BY session_at DESC, id").fetchall()
            else:
                rows = db.execute("SELECT body FROM sessions WHERE spot = ? ORDER BY session_at DESC, id", (spot,)).fetchall()
        return [SurfSession.model_validate_json(row[0]) for row in rows]

    def save(self, session: SurfSession, *, update: bool = False) -> bool:
        args = (spot_key(session.location.latitude, session.location.longitude),
                session.session_at.isoformat(), session.model_dump_json(), session.id)
        with self.connect() as db:
            if update:
                return db.execute("UPDATE sessions SET spot = ?, session_at = ?, body = ? WHERE id = ?", args).rowcount > 0
            db.execute("INSERT INTO sessions (spot, session_at, body, id) VALUES (?, ?, ?, ?)", args)
        return True

    def delete(self, session_id: str) -> bool:
        with self.connect() as db:
            return db.execute("DELETE FROM sessions WHERE id = ?", (session_id,)).rowcount > 0
