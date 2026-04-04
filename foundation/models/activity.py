# Activity model — append-only study log.
#
# Activities are created automatically when a lesson is completed
# (see Lesson.mark_as_done). They are never edited or deleted by the app.
# If a lesson is deleted, its activities remain but lesson_id is set to NULL.
#
# The all() query joins lessons and courses so the Study Log view can display
# full context (course name, lesson title, source URL) without extra queries.

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from foundation.db.connection import get_connection


@dataclass
class Activity:
    """Represents one row in the activities table."""
    id: Optional[int]
    lesson_id: Optional[int]   # NULL if the lesson was deleted after completion
    action: str                # Human-readable description, e.g. 'Completed "Intro to Git"'
    created_at: str
    updated_at: str

    # These fields are NOT columns in the activities table.
    # They are populated by the JOIN query in all() for display purposes only.
    lesson_title: Optional[str] = field(default=None)
    lesson_source_url: Optional[str] = field(default=None)
    course_title: Optional[str] = field(default=None)
    course_id: Optional[int] = field(default=None)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @classmethod
    def all(cls) -> list[Activity]:
        """Return all activities newest-first, with lesson and course info joined in."""
        conn = get_connection()
        rows = conn.execute(
            """
            SELECT
                a.id, a.lesson_id, a.action, a.created_at, a.updated_at,
                l.title      AS lesson_title,
                l.source_url AS lesson_source_url,
                c.title      AS course_title,
                c.id         AS course_id
            FROM activities a
            LEFT JOIN lessons l  ON a.lesson_id = l.id
            LEFT JOIN courses c  ON l.course_id = c.id
            ORDER BY a.created_at DESC
            """
        ).fetchall()
        conn.close()
        return [cls._from_join_row(r) for r in rows]

    # ------------------------------------------------------------------
    # Mutations — INSERT only
    # ------------------------------------------------------------------

    @classmethod
    def create(cls, lesson_id: Optional[int], action: str) -> Activity:
        """Insert a new activity record and return it.

        Called from Lesson.mark_as_done() — not intended to be called directly.
        """
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO activities (lesson_id, action) VALUES (?, ?)",
            (lesson_id, action),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM activities WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        conn.close()
        # Use the simple row builder — joined fields are not needed after INSERT.
        return cls._from_row(row)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @classmethod
    def _from_row(cls, row) -> Activity:
        """Build from a plain activities row (no joined columns)."""
        return cls(
            id=row["id"],
            lesson_id=row["lesson_id"],
            action=row["action"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @classmethod
    def _from_join_row(cls, row) -> Activity:
        """Build from the joined query row used by all()."""
        return cls(
            id=row["id"],
            lesson_id=row["lesson_id"],
            action=row["action"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            lesson_title=row["lesson_title"],
            lesson_source_url=row["lesson_source_url"],
            course_title=row["course_title"],
            course_id=row["course_id"],
        )
