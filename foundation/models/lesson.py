# Lesson model — a single study unit inside a Course.
#
# A lesson moves through three mutually exclusive states:
#   pending   → started_at is NULL
#   started   → started_at is set, completed_at is NULL
#   completed → both started_at and completed_at are set
#
# The Feynman gate (mark_as_done) requires at least 50 characters of
# explanation before the lesson can be marked complete.
#
# HOW TO ADD A NEW CONTENT TYPE:
#   1. Add a constant below (e.g. AUDIO = 4).
#   2. Add its label to CONTENT_TYPE_LABELS.
#   3. Add it to _CONTENT_TYPE_ORDER in foundation/views/lesson_form_view.py.
#   4. Handle rendering in foundation/views/lesson_view.py if needed.

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from foundation.db.connection import get_connection
from foundation.db.settings import Settings

# Content type constants — stored as integers in the database.
TEXT_CONTENT  = 0   # Markdown text stored in the content column
VIDEO         = 1   # External URL; app opens it in the system browser
PDF           = 2   # External URL; app opens it in the system browser
EXTERNAL_LINK = 3   # External URL; app opens it in the system browser

CONTENT_TYPE_LABELS = {
    TEXT_CONTENT:  "Text",
    VIDEO:         "Video",
    PDF:           "PDF",
    EXTERNAL_LINK: "External Link",
}

# Minimum character count for a valid Feynman explanation.
FEYNMAN_MIN_CHARS = 50


@dataclass
class Lesson:
    """Represents one row in the lessons table."""
    id: Optional[int]
    course_id: int
    title: str
    content_type: int
    source_url: Optional[str]   # set for VIDEO, PDF, EXTERNAL_LINK; NULL for TEXT
    content: Optional[str]      # Markdown text; set for TEXT_CONTENT; NULL otherwise
    feynman_notes: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    created_at: str
    updated_at: str

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def completed(self) -> bool:
        return self.completed_at is not None

    def started(self) -> bool:
        # Returns True only for the in-progress state (started but not done).
        return self.started_at is not None and not self.completed()

    def pending(self) -> bool:
        return self.started_at is None

    def status_label(self) -> str:
        if self.completed():
            return "Completed"
        if self.started():
            return "In Progress"
        return "Pending"

    def content_type_label(self) -> str:
        return CONTENT_TYPE_LABELS.get(self.content_type, "Text")

    def has_url(self) -> bool:
        """True for content types that store a URL rather than inline text."""
        return self.content_type in (VIDEO, PDF, EXTERNAL_LINK)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @classmethod
    def for_course(cls, course_id: int) -> list[Lesson]:
        """Return all lessons for a course, ordered by creation date."""
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM lessons WHERE course_id = ? ORDER BY created_at ASC",
            (course_id,),
        ).fetchall()
        conn.close()
        return [cls._from_row(r) for r in rows]

    @classmethod
    def find(cls, lesson_id: int) -> Optional[Lesson]:
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM lessons WHERE id = ?", (lesson_id,)
        ).fetchone()
        conn.close()
        return cls._from_row(row) if row else None

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        course_id: int,
        title: str,
        content_type: int = TEXT_CONTENT,
        source_url: Optional[str] = None,
        content: Optional[str] = None,
    ) -> Lesson:
        conn = get_connection()
        cur = conn.execute(
            """INSERT INTO lessons (course_id, title, content_type, source_url, content)
               VALUES (?, ?, ?, ?, ?)""",
            (course_id, title, content_type, source_url, content),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM lessons WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        conn.close()
        return cls._from_row(row)

    def update(
        self,
        title: str,
        content_type: int = TEXT_CONTENT,
        source_url: Optional[str] = None,
        content: Optional[str] = None,
    ) -> None:
        conn = get_connection()
        conn.execute(
            """UPDATE lessons SET title=?, content_type=?, source_url=?, content=?,
               updated_at=datetime('now') WHERE id=?""",
            (title, content_type, source_url, content, self.id),
        )
        conn.commit()
        conn.close()
        self.title = title
        self.content_type = content_type
        self.source_url = source_url
        self.content = content

    def delete(self) -> None:
        conn = get_connection()
        conn.execute("DELETE FROM lessons WHERE id = ?", (self.id,))
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Stamp started_at. Idempotent — safe to call more than once."""
        if self.started_at is not None:
            return
        conn = get_connection()
        conn.execute(
            "UPDATE lessons SET started_at=datetime('now'), updated_at=datetime('now') WHERE id=?",
            (self.id,),
        )
        conn.commit()
        row = conn.execute(
            "SELECT started_at FROM lessons WHERE id=?", (self.id,)
        ).fetchone()
        self.started_at = row["started_at"]
        conn.close()

    def mark_as_done(self, feynman_notes: str) -> list[str]:
        """Complete the lesson with the provided Feynman notes.

        Returns a list of validation error strings.
        Empty list means success — the lesson is now complete and an
        Activity record has been created.
        """
        errors = self.validate_for_completion(feynman_notes)
        if errors:
            return errors

        # Imported here to avoid a circular import (Activity → Lesson → Activity).
        from foundation.models.activity import Activity
        from foundation.models.course import Course

        conn = get_connection()
        conn.execute(
            """UPDATE lessons SET feynman_notes=?, completed_at=datetime('now'),
               updated_at=datetime('now') WHERE id=?""",
            (feynman_notes.strip(), self.id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT feynman_notes, completed_at FROM lessons WHERE id=?", (self.id,)
        ).fetchone()
        self.feynman_notes = row["feynman_notes"]
        self.completed_at = row["completed_at"]
        conn.close()

        # Log the completion and check whether the parent course is now done.
        Activity.create(lesson_id=self.id, action=f'Completed "{self.title}"')
        course = Course.find(self.course_id)
        if course:
            course.check_completion()

        return []

    def update_notes(self, feynman_notes: str) -> list[str]:
        """Replace feynman_notes on an already-completed lesson.

        Returns validation errors, or an empty list on success.
        """
        errors = self.validate_for_completion(feynman_notes)
        if errors:
            return errors

        conn = get_connection()
        conn.execute(
            "UPDATE lessons SET feynman_notes=?, updated_at=datetime('now') WHERE id=?",
            (feynman_notes.strip(), self.id),
        )
        conn.commit()
        conn.close()
        self.feynman_notes = feynman_notes.strip()
        return []

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate_for_completion(feynman_notes: str) -> list[str]:
        """Check that the Feynman notes meet the minimum length requirement.

        The minimum is read from Settings each time so changes in the settings
        page take effect immediately without restarting the app.
        """
        min_chars = Settings.get_int("feynman_min_chars", FEYNMAN_MIN_CHARS)
        errors = []
        if not feynman_notes or len(feynman_notes.strip()) < min_chars:
            errors.append(
                f"Feynman notes must be at least {min_chars} characters. "
                f"Write a proper explanation!"
            )
        return errors

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
    def _from_row(cls, row) -> Lesson:
        return cls(
            id=row["id"],
            course_id=row["course_id"],
            title=row["title"],
            content_type=row["content_type"],
            source_url=row["source_url"],
            content=row["content"],
            feynman_notes=row["feynman_notes"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
