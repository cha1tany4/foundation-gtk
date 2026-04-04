# Bookmark model — quick-access links shown on the Dashboard.
#
# Bookmarks are displayed as a drag-reorderable grid (max 4 per row).
# There is a hard cap of 36 bookmarks enforced in create().
# Order is stored in the position column and updated by reorder().

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from foundation.db.connection import get_connection

MAX_BOOKMARKS = 36


@dataclass
class Bookmark:
    """Represents one row in the bookmarks table."""
    id: Optional[int]
    name: str
    url: str
    position: int   # Lower number = shown first. Managed by reorder().
    created_at: str
    updated_at: str

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @classmethod
    def all(cls) -> list[Bookmark]:
        """Return all bookmarks sorted by position (the display order)."""
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM bookmarks ORDER BY position ASC"
        ).fetchall()
        conn.close()
        return [cls._from_row(r) for r in rows]

    @classmethod
    def count(cls) -> int:
        conn = get_connection()
        n = conn.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0]
        conn.close()
        return n

    @classmethod
    def find(cls, bookmark_id: int) -> Optional[Bookmark]:
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM bookmarks WHERE id = ?", (bookmark_id,)
        ).fetchone()
        conn.close()
        return cls._from_row(row) if row else None

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    @classmethod
    def create(cls, name: str, url: str) -> tuple[Optional[Bookmark], list[str]]:
        """Insert a new bookmark.

        Returns (bookmark, []) on success, or (None, [error, ...]) on failure.
        The cap check happens here so the dashboard never needs to re-check.
        """
        errors = cls.validate(name, url)
        if errors:
            return None, errors

        if cls.count() >= MAX_BOOKMARKS:
            return None, [f"Dashboard is full. Maximum of {MAX_BOOKMARKS} bookmarks allowed."]

        conn = get_connection()
        # Place the new bookmark at the end by assigning max(position) + 1.
        max_pos = conn.execute(
            "SELECT COALESCE(MAX(position), 0) FROM bookmarks"
        ).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO bookmarks (name, url, position) VALUES (?, ?, ?)",
            (name, url, max_pos + 1),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM bookmarks WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        conn.close()
        return cls._from_row(row), []

    def update(self, name: str, url: str) -> list[str]:
        """Update name and URL. Returns validation errors, or [] on success."""
        errors = self.validate(name, url)
        if errors:
            return errors

        conn = get_connection()
        conn.execute(
            "UPDATE bookmarks SET name=?, url=?, updated_at=datetime('now') WHERE id=?",
            (name, url, self.id),
        )
        conn.commit()
        conn.close()
        self.name = name
        self.url = url
        return []

    def delete(self) -> None:
        conn = get_connection()
        conn.execute("DELETE FROM bookmarks WHERE id = ?", (self.id,))
        conn.commit()
        conn.close()

    @classmethod
    def reorder(cls, ordered_ids: list[int]) -> None:
        """Persist a new display order from a list of bookmark IDs.

        The list must contain every existing bookmark ID.
        Position values are set to 1, 2, 3, ... matching the list order.
        Called by the dashboard after a drag-and-drop reorder.
        """
        conn = get_connection()
        conn.executemany(
            "UPDATE bookmarks SET position=?, updated_at=datetime('now') WHERE id=?",
            [(pos + 1, bid) for pos, bid in enumerate(ordered_ids)],
        )
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate(name: str, url: str) -> list[str]:
        errors = []
        if not name or not name.strip():
            errors.append("Name can't be blank.")
        if not url or not url.strip():
            errors.append("URL can't be blank.")
        elif not (url.startswith("http://") or url.startswith("https://")):
            errors.append("URL must start with http:// or https://")
        return errors

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    @classmethod
    def _from_row(cls, row) -> Bookmark:
        return cls(
            id=row["id"],
            name=row["name"],
            url=row["url"],
            position=row["position"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
