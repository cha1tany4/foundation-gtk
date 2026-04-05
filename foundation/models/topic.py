# Topic model — the top-level organisational unit ("Subject").
#
# A Topic contains one or more Courses.
# Deleting a Topic cascades to its Courses and their Lessons (via SQLite ON DELETE CASCADE).
#
# To add a field:
#   1. Add a migration in foundation/db/migrations.py (ALTER TABLE topics ADD COLUMN ...).
#   2. Add the field to the dataclass below.
#   3. Update create(), update(), and _from_row() to include it.

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from foundation.db.connection import get_connection


@dataclass
class Topic:
    """Represents one row in the topics table."""
    id: Optional[int]      # None before the record is saved to the database
    title: str
    description: Optional[str]
    created_at: str        # SQLite datetime string, e.g. "2024-01-15 10:30:00"
    updated_at: str

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @classmethod
    def all(cls) -> list[Topic]:
        """Return all topics ordered by creation date (oldest first)."""
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM topics ORDER BY created_at ASC"
        ).fetchall()
        conn.close()
        return [cls._from_row(r) for r in rows]

    @classmethod
    def find(cls, topic_id: int) -> Optional[Topic]:
        """Return a single topic by ID, or None if not found."""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM topics WHERE id = ?", (topic_id,)
        ).fetchone()
        conn.close()
        return cls._from_row(row) if row else None

    @classmethod
    def get_course_lesson_counts(cls) -> dict[int, tuple[int, int]]:
        """Return {topic_id: (course_count, lesson_count)} for all topics in one query."""
        conn = get_connection()
        rows = conn.execute("""
            SELECT t.id AS topic_id,
                   COUNT(DISTINCT c.id) AS course_count,
                   COUNT(l.id)          AS lesson_count
            FROM topics t
            LEFT JOIN courses c ON c.topic_id = t.id
            LEFT JOIN lessons l ON l.course_id = c.id
            GROUP BY t.id
        """).fetchall()
        conn.close()
        return {r["topic_id"]: (r["course_count"], r["lesson_count"]) for r in rows}

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    @classmethod
    def create(cls, title: str, description: Optional[str] = None) -> Topic:
        """Insert a new topic and return it with its assigned id."""
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO topics (title, description) VALUES (?, ?)",
            (title, description),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM topics WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        conn.close()
        return cls._from_row(row)

    def update(self, title: str, description: Optional[str] = None) -> None:
        """Update this topic's fields in the database and on the object."""
        conn = get_connection()
        conn.execute(
            "UPDATE topics SET title=?, description=?, updated_at=datetime('now') WHERE id=?",
            (title, description, self.id),
        )
        conn.commit()
        conn.close()
        self.title = title
        self.description = description

    def delete(self) -> None:
        """Delete this topic. Courses and lessons cascade-delete automatically."""
        conn = get_connection()
        conn.execute("DELETE FROM topics WHERE id = ?", (self.id,))
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Validation — called by the form dialog before saving
    # ------------------------------------------------------------------

    @staticmethod
    def validate(title: str) -> list[str]:
        """Return a list of error strings. Empty list means the data is valid."""
        errors = []
        if not title or not title.strip():
            errors.append("Title can't be blank.")
        return errors

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    @classmethod
    def _from_row(cls, row) -> Topic:
        """Build a Topic from a sqlite3.Row (supports row["column"] access)."""
        return cls(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
