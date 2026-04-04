# Database connection factory.
#
# get_connection() returns a persistent singleton connection that lives for the
# entire process lifetime. Opening a new SQLite connection for every query is
# noticeably slow inside a Flatpak sandbox because each open/close goes through
# bubblewrap's namespace isolation and seccomp filter evaluation. A persistent
# connection eliminates that overhead while remaining safe — the app is
# single-threaded (GTK main loop) so there are no concurrency concerns.
#
# The _Connection wrapper makes close() a no-op so all callers can keep their
# existing conn.close() calls without accidentally closing the shared connection.
#
# The database file lives at:
#   ~/.local/share/foundation/foundation.db   (or $XDG_DATA_HOME/foundation/)
# This follows the XDG Base Directory standard used by Linux desktop apps.

import os
import sqlite3
from pathlib import Path


_db_path: Path | None = None
_connection: "sqlite3.Connection | None" = None


class _Connection:
    """Thin wrapper that delegates everything to the real sqlite3.Connection
    but turns close() into a no-op so the singleton is never accidentally closed."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def close(self):
        pass  # intentional no-op: the connection is reused across queries

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_db_path() -> Path:
    """Return the path to the SQLite file, creating the directory if needed."""
    global _db_path
    if _db_path is None:
        # XDG_DATA_HOME defaults to ~/.local/share if not set in the environment.
        xdg_data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        db_dir = xdg_data / "foundation"
        db_dir.mkdir(parents=True, exist_ok=True)
        _db_path = db_dir / "foundation.db"
    return _db_path


def get_connection() -> _Connection:
    """Return the shared database connection, creating it on the first call.

    Settings applied once at connection creation:
      WAL mode       — allows reads during a write; safer for desktop apps.
                       Persists in the DB file, so only needs to be set once.
      foreign_keys   — enforces ON DELETE CASCADE rules defined in the schema.
      Row factory    — row["column_name"] access instead of row[0] integer indexes.
    """
    global _connection
    if _connection is None:
        raw = sqlite3.connect(str(get_db_path()))
        raw.execute("PRAGMA journal_mode=WAL")
        raw.execute("PRAGMA foreign_keys=ON")
        raw.row_factory = sqlite3.Row
        _connection = _Connection(raw)
    return _connection
