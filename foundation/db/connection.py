# Database connection factory.
#
# Every model calls get_connection() to get a fresh SQLite connection,
# runs its query, then closes the connection. This is intentionally simple:
# no connection pooling, no persistent global connection.
#
# The database file lives at:
#   ~/.local/share/foundation/foundation.db   (or $XDG_DATA_HOME/foundation/)
# This follows the XDG Base Directory standard used by Linux desktop apps.

import os
import sqlite3
from pathlib import Path


def get_db_path() -> Path:
    """Return the path to the SQLite file, creating the directory if needed."""
    # XDG_DATA_HOME defaults to ~/.local/share if not set in the environment.
    xdg_data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    db_dir = xdg_data / "foundation"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "foundation.db"


def get_connection() -> sqlite3.Connection:
    """Open and return a configured SQLite connection.

    Settings applied to every connection:
      WAL mode       — allows reads during a write; safer for desktop apps.
      foreign_keys   — enforces ON DELETE CASCADE rules defined in the schema.
                       SQLite disables this by default; must be set per connection.
      Row factory    — row["column_name"] access instead of row[0] integer indexes.
    """
    conn = sqlite3.connect(str(get_db_path()))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn
