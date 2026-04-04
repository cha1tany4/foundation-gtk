# Settings helper — simple key-value store backed by the SQLite settings table.
#
# Usage:
#   Settings.get("color_scheme", "0")          → str
#   Settings.get_int("feynman_min_chars", 50)  → int
#   Settings.set("feynman_min_chars", 75)
#
# The settings table is created by migration 13 in foundation/db/migrations.py.
# Keys are plain snake_case strings. Values are stored as TEXT and converted on read.
#
# ADDING A NEW SETTING:
#   1. Choose a key name (e.g. "my_setting").
#   2. Call Settings.get("my_setting", "default") wherever you need it.
#   3. Call Settings.set("my_setting", new_value) wherever you save it.
#   No schema changes needed — the table accepts any key.
#
# CURRENT SETTINGS KEYS:
#   color_scheme        — "0" Follow System, "1" Light, "2" Dark
#   feynman_min_chars   — integer string, default "50"

from foundation.db.connection import get_connection


class Settings:

    @staticmethod
    def get(key: str, default: str = "") -> str:
        """Return the stored string value for key, or default if not set."""
        conn = get_connection()
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        conn.close()
        return row["value"] if row else default

    @staticmethod
    def get_int(key: str, default: int = 0) -> int:
        """Return the stored value converted to int, or default if missing or invalid."""
        raw = Settings.get(key, str(default))
        try:
            return int(raw)
        except ValueError:
            return default

    @staticmethod
    def set(key: str, value) -> None:
        """Store value under key. Creates the row if it doesn't exist, updates if it does."""
        conn = get_connection()
        conn.execute(
            # INSERT OR REPLACE is equivalent to upsert for a PRIMARY KEY column.
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, str(value)),
        )
        conn.commit()
        conn.close()
