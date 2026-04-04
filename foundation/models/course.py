# Course model — a collection of lessons within a Topic.
#
# A Course is considered complete when every one of its lessons has been
# completed. This is managed automatically by check_completion(), which is
# called from Lesson.mark_as_done().
#
# To add a field: see topic.py for the three-step process.

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from foundation.db.connection import get_connection


@dataclass
class Course:
    """Represents one row in the courses table."""
    id: Optional[int]
    topic_id: int
    title: str
    description: Optional[str]
    completed_at: Optional[str]   # NULL until all lessons are done
    created_at: str
    updated_at: str

    def completed(self) -> bool:
        """True if all lessons have been completed (completed_at is set)."""
        return self.completed_at is not None

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @classmethod
    def for_topic(cls, topic_id: int) -> list[Course]:
        """Return all courses for a topic, ordered by creation date."""
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM courses WHERE topic_id = ? ORDER BY created_at ASC",
            (topic_id,),
        ).fetchall()
        conn.close()
        return [cls._from_row(r) for r in rows]

    @classmethod
    def find(cls, course_id: int) -> Optional[Course]:
        """Return a single course by ID, or None if not found."""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM courses WHERE id = ?", (course_id,)
        ).fetchone()
        conn.close()
        return cls._from_row(row) if row else None

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    @classmethod
    def create(cls, topic_id: int, title: str, description: Optional[str] = None) -> Course:
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO courses (topic_id, title, description) VALUES (?, ?, ?)",
            (topic_id, title, description),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM courses WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        conn.close()
        return cls._from_row(row)

    def update(self, title: str, description: Optional[str] = None) -> None:
        conn = get_connection()
        conn.execute(
            "UPDATE courses SET title=?, description=?, updated_at=datetime('now') WHERE id=?",
            (title, description, self.id),
        )
        conn.commit()
        conn.close()
        self.title = title
        self.description = description

    def delete(self) -> None:
        """Delete this course. Lessons cascade-delete automatically."""
        conn = get_connection()
        conn.execute("DELETE FROM courses WHERE id = ?", (self.id,))
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Business logic
    # ------------------------------------------------------------------

    def check_completion(self) -> None:
        """Stamp or clear completed_at based on whether all lessons are done.

        Call this after any lesson state change (start or complete).
        Does nothing if the course has no lessons.
        """
        conn = get_connection()
        row = conn.execute(
            "SELECT COUNT(*) AS total, SUM(completed_at IS NOT NULL) AS done "
            "FROM lessons WHERE course_id = ?",
            (self.id,),
        ).fetchone()
        total, done = row["total"], row["done"]

        if total == 0:
            conn.close()
            return

        all_done = (done == total)

        if all_done and not self.completed():
            # All lessons just became complete — stamp the course.
            conn.execute(
                "UPDATE courses SET completed_at=datetime('now'), updated_at=datetime('now') WHERE id=?",
                (self.id,),
            )
            conn.commit()
            row = conn.execute(
                "SELECT completed_at FROM courses WHERE id=?", (self.id,)
            ).fetchone()
            self.completed_at = row["completed_at"]

        elif not all_done and self.completed():
            # A lesson was un-completed — clear the course completion.
            conn.execute(
                "UPDATE courses SET completed_at=NULL, updated_at=datetime('now') WHERE id=?",
                (self.id,),
            )
            conn.commit()
            self.completed_at = None

        conn.close()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate(title: str) -> list[str]:
        errors = []
        if not title or not title.strip():
            errors.append("Title can't be blank.")
        return errors

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    @classmethod
    def _from_row(cls, row) -> Course:
        return cls(
            id=row["id"],
            topic_id=row["topic_id"],
            title=row["title"],
            description=row["description"],
            completed_at=row["completed_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
