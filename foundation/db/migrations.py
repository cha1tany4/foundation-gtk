# Database schema migrations.
#
# A migration is a numbered SQL statement that creates or alters a table.
# run_migrations() applies each one exactly once, in order, and records
# which versions have been applied in the schema_version table.
#
# HOW TO ADD A NEW MIGRATION:
#   1. Append a new tuple to the MIGRATIONS list below: (next_number, "SQL").
#   2. Never modify or remove an existing migration — that would break
#      databases that already ran it. Always add forward-only changes.
#
# Example — adding a column to lessons:
#   (13, "ALTER TABLE lessons ADD COLUMN my_field TEXT")

from foundation.db.connection import get_connection

MIGRATIONS = [
    (1, """
        CREATE TABLE IF NOT EXISTS topics (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            description TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """),
    (2, """
        CREATE TABLE IF NOT EXISTS courses (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id     INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            title        TEXT NOT NULL,
            description  TEXT,
            completed_at TEXT,
            created_at   TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """),
    (3, "CREATE INDEX IF NOT EXISTS idx_courses_topic_id ON courses(topic_id)"),
    (4, """
        CREATE TABLE IF NOT EXISTS lessons (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id     INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
            title         TEXT NOT NULL,
            content_type  INTEGER NOT NULL DEFAULT 0,
            source_url    TEXT,
            content       TEXT,
            feynman_notes TEXT,
            started_at    TEXT,
            completed_at  TEXT,
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """),
    # content_type values: 0=text, 1=video, 2=pdf, 3=external_link
    # These constants are defined in foundation/models/lesson.py.
    (5, "CREATE INDEX IF NOT EXISTS idx_lessons_course_id ON lessons(course_id)"),
    (6, "CREATE INDEX IF NOT EXISTS idx_lessons_completed_at ON lessons(completed_at)"),
    (7, """
        CREATE TABLE IF NOT EXISTS activities (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id  INTEGER REFERENCES lessons(id) ON DELETE SET NULL,
            action     TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """),
    # Activities are INSERT-only. They are never updated or deleted by the app.
    # lesson_id uses SET NULL (not CASCADE) so the log survives lesson deletion.
    (8, "CREATE INDEX IF NOT EXISTS idx_activities_created_at ON activities(created_at)"),
    (9, "CREATE INDEX IF NOT EXISTS idx_activities_lesson_id ON activities(lesson_id)"),
    (10, """
        CREATE TABLE IF NOT EXISTS bookmarks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            url        TEXT NOT NULL,
            position   INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """),
    (11, "CREATE INDEX IF NOT EXISTS idx_bookmarks_position ON bookmarks(position)"),
    (12, "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"),
    (13, """
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """),
]


def run_migrations() -> None:
    """Apply any unapplied migrations in order. Called once at app startup."""
    conn = get_connection()

    # Create schema_version first so we can safely query it below,
    # even on a brand-new database where it doesn't exist yet.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
    )
    conn.commit()

    # Load the set of already-applied version numbers.
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_version")}

    for version, sql in MIGRATIONS:
        if version in applied:
            continue
        conn.execute(sql)
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
        conn.commit()

    conn.close()
