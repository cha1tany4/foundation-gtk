# CSV import and export for subjects (topics/courses/lessons) and bookmarks.
#
# HOW IT WORKS
# ------------
# Each public function opens a GTK file dialog (non-blocking/async), then runs
# the actual import or export inside the callback once the user picks a file or folder.
# This is the same pattern used in export.py for Markdown export.
#
# IMPORT FORMAT
# -------------
# Import accepts the exact CSV format exported by the Rails app, as well as
# CSVs produced by this module's export functions.  Column lookup is by name
# (via csv.DictReader), so extra or missing columns are handled gracefully.
#
# DUPLICATE WARNING
# -----------------
# Import always appends — it does not check for existing records with the same
# title. Running import twice will create duplicate topics/courses/lessons.
# To add deduplication later: before each INSERT, run a SELECT to check whether
# a row with the same title (and parent ID) already exists, and skip it if found.
#
# ADDING A NEW ENTITY TYPE
# -------------------------
# 1. Add export_<entity> and import_<entity> functions following the patterns below.
# 2. Wire them up to a menu button in the relevant view file.

import csv
import io
import os

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio, GLib

from foundation.db.connection import get_connection
from foundation.models.bookmark import MAX_BOOKMARKS


# ---------------------------------------------------------------------------
# Subjects: Topics + Courses + Lessons
# ---------------------------------------------------------------------------

def import_subjects(window, refresh) -> None:
    """Open a folder picker; read topics.csv, courses.csv, lessons.csv from it.

    The three files must all be present in the selected folder.
    IDs from the CSV are used only to resolve foreign keys (topic_id, course_id)
    — they are never written to the database. SQLite assigns its own IDs.

    Args:
        window:  The main application window (used to anchor the dialog and show toasts).
        refresh: A callable with no arguments — called after import so the UI redraws.
    """
    dialog = Gtk.FileDialog.new()
    dialog.set_title("Select folder containing topics.csv, courses.csv, lessons.csv")

    def on_folder_selected(dlg, result):
        try:
            gfolder = dlg.select_folder_finish(result)
        except GLib.Error:
            # User cancelled — do nothing.
            return

        folder_path = gfolder.get_path()
        try:
            counts = _do_import_subjects(folder_path)
            window.show_toast(
                f"Imported {counts['topics']} topics, "
                f"{counts['courses']} courses, "
                f"{counts['lessons']} lessons."
            )
            refresh()
        except FileNotFoundError as e:
            window.show_toast(str(e))
        except Exception as e:
            window.show_toast(f"Import failed: {e}")

    dialog.select_folder(window, None, on_folder_selected)


def _do_import_subjects(folder_path: str) -> dict:
    """Read the three CSV files and insert rows into the database.

    Returns a dict with keys 'topics', 'courses', 'lessons' showing how many
    rows were inserted.

    Raises FileNotFoundError if any of the three required files are missing.
    """
    # Verify all three files exist before starting — avoids a partial import.
    for name in ("topics.csv", "courses.csv", "lessons.csv"):
        path = os.path.join(folder_path, name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"{name} not found in selected folder.")

    conn = get_connection()
    topic_id_map = {}   # {old_csv_id: new_sqlite_id}
    course_id_map = {}  # {old_csv_id: new_sqlite_id}
    counts = {"topics": 0, "courses": 0, "lessons": 0}

    # --- Topics ---
    with open(os.path.join(folder_path, "topics.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            old_id = row.get("id", "").strip()
            title = row.get("title", "").strip()
            description = row.get("description", "").strip() or None

            if not title:
                continue  # Skip rows with no title.

            cur = conn.execute(
                "INSERT INTO topics (title, description) VALUES (?, ?)",
                (title, description),
            )
            if old_id:
                topic_id_map[old_id] = cur.lastrowid
            counts["topics"] += 1

    conn.commit()

    # --- Courses ---
    with open(os.path.join(folder_path, "courses.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            old_id = row.get("id", "").strip()
            old_topic_id = row.get("topic_id", "").strip()
            title = row.get("title", "").strip()
            description = row.get("description", "").strip() or None
            completed_at = row.get("completed_at", "").strip() or None

            if not title:
                continue

            # Map the old topic ID to the new SQLite topic ID.
            # If not found, skip this course — its parent topic wasn't imported.
            new_topic_id = topic_id_map.get(old_topic_id)
            if new_topic_id is None:
                continue

            cur = conn.execute(
                "INSERT INTO courses (topic_id, title, description, completed_at) VALUES (?, ?, ?, ?)",
                (new_topic_id, title, description, completed_at),
            )
            if old_id:
                course_id_map[old_id] = cur.lastrowid
            counts["courses"] += 1

    conn.commit()

    # --- Lessons ---
    with open(os.path.join(folder_path, "lessons.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            old_course_id = row.get("course_id", "").strip()
            title = row.get("title", "").strip()

            if not title:
                continue

            new_course_id = course_id_map.get(old_course_id)
            if new_course_id is None:
                continue

            # content_type is stored as an integer (0=text, 1=video, 2=pdf, 3=link).
            # Default to 0 (text) if the value is missing or not a number.
            raw_ct = row.get("content_type", "0").strip()
            try:
                content_type = int(raw_ct)
            except ValueError:
                content_type = 0

            source_url   = row.get("source_url",    "").strip() or None
            content      = row.get("content",        "").strip() or None
            feynman_notes = row.get("feynman_notes", "").strip() or None
            started_at   = row.get("started_at",     "").strip() or None
            completed_at = row.get("completed_at",   "").strip() or None

            conn.execute(
                """INSERT INTO lessons
                   (course_id, title, content_type, source_url, content,
                    feynman_notes, started_at, completed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (new_course_id, title, content_type, source_url, content,
                 feynman_notes, started_at, completed_at),
            )
            counts["lessons"] += 1

    conn.commit()
    conn.close()
    return counts


def export_subjects(window) -> None:
    """Open a folder picker; write topics.csv, courses.csv, lessons.csv into it.

    Args:
        window: The main application window (used to anchor the dialog and show toasts).
    """
    dialog = Gtk.FileDialog.new()
    dialog.set_title("Select folder to export subjects into")

    def on_folder_selected(dlg, result):
        try:
            gfolder = dlg.select_folder_finish(result)
        except GLib.Error:
            return

        folder_path = gfolder.get_path()
        try:
            counts = _do_export_subjects(folder_path)
            window.show_toast(
                f"Exported {counts['topics']} topics, "
                f"{counts['courses']} courses, "
                f"{counts['lessons']} lessons to {folder_path}"
            )
        except Exception as e:
            window.show_toast(f"Export failed: {e}")

    dialog.select_folder(window, None, on_folder_selected)


def _do_export_subjects(folder_path: str) -> dict:
    """Query the database and write three CSV files.

    CSV columns written:
      topics.csv   — id, title, description
      courses.csv  — id, title, description, topic_id, completed_at
      lessons.csv  — id, title, course_id, content_type, source_url,
                     content, feynman_notes, started_at, completed_at

    Returns a dict with row counts.
    """
    conn = get_connection()
    counts = {}

    # --- Topics ---
    rows = conn.execute(
        "SELECT id, title, description FROM topics ORDER BY id ASC"
    ).fetchall()
    _write_csv(
        os.path.join(folder_path, "topics.csv"),
        ["id", "title", "description"],
        rows,
    )
    counts["topics"] = len(rows)

    # --- Courses ---
    rows = conn.execute(
        "SELECT id, title, description, topic_id, completed_at "
        "FROM courses ORDER BY topic_id ASC, id ASC"
    ).fetchall()
    _write_csv(
        os.path.join(folder_path, "courses.csv"),
        ["id", "title", "description", "topic_id", "completed_at"],
        rows,
    )
    counts["courses"] = len(rows)

    # --- Lessons ---
    rows = conn.execute(
        "SELECT id, title, course_id, content_type, source_url, content, "
        "feynman_notes, started_at, completed_at "
        "FROM lessons ORDER BY course_id ASC, id ASC"
    ).fetchall()
    _write_csv(
        os.path.join(folder_path, "lessons.csv"),
        ["id", "title", "course_id", "content_type", "source_url",
         "content", "feynman_notes", "started_at", "completed_at"],
        rows,
    )
    counts["lessons"] = len(rows)

    conn.close()
    return counts


# ---------------------------------------------------------------------------
# Bookmarks
# ---------------------------------------------------------------------------

def import_bookmarks(window, refresh) -> None:
    """Open a file picker for bookmarks.csv and insert the rows.

    Respects the 16-bookmark cap — rows beyond the cap are skipped and a warning
    is included in the toast.

    Args:
        window:  The main application window.
        refresh: Called with no arguments after import so the dashboard redraws.
    """
    dialog = Gtk.FileDialog.new()
    dialog.set_title("Select bookmarks.csv to import")

    # Restrict the picker to CSV files so the user doesn't pick the wrong thing.
    filters = Gio.ListStore.new(Gtk.FileFilter)
    csv_filter = Gtk.FileFilter()
    csv_filter.set_name("CSV files")
    csv_filter.add_pattern("*.csv")
    filters.append(csv_filter)
    dialog.set_filters(filters)

    def on_file_selected(dlg, result):
        try:
            gfile = dlg.open_finish(result)
        except GLib.Error:
            return

        file_path = gfile.get_path()
        try:
            imported, skipped = _do_import_bookmarks(file_path)
            if skipped > 0:
                window.show_toast(
                    f"Imported {imported} bookmarks. "
                    f"{skipped} skipped ({MAX_BOOKMARKS}-bookmark cap reached)."
                )
            else:
                window.show_toast(f"Imported {imported} bookmarks.")
            refresh()
        except Exception as e:
            window.show_toast(f"Import failed: {e}")

    dialog.open(window, None, on_file_selected)


def _do_import_bookmarks(file_path: str) -> tuple[int, int]:
    """Read bookmarks.csv and insert rows up to the bookmark cap.

    Returns (imported_count, skipped_count).
    """
    conn = get_connection()

    current_count = conn.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0]
    slots_available = MAX_BOOKMARKS - current_count

    if slots_available <= 0:
        conn.close()
        return 0, 0

    imported = 0
    skipped = 0

    with open(file_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row.get("name", "").strip()
            url  = row.get("url",  "").strip()

            if not name or not url:
                continue  # Skip incomplete rows.

            if imported >= slots_available:
                skipped += 1
                continue

            # Position: use the CSV value if present, otherwise append at the end.
            raw_pos = row.get("position", "").strip()
            try:
                position = int(raw_pos)
            except ValueError:
                position = current_count + imported + 1

            conn.execute(
                "INSERT INTO bookmarks (name, url, position) VALUES (?, ?, ?)",
                (name, url, position),
            )
            imported += 1

    conn.commit()
    conn.close()
    return imported, skipped


def export_bookmarks(window) -> None:
    """Open a save dialog and write bookmarks.csv.

    Args:
        window: The main application window.
    """
    dialog = Gtk.FileDialog.new()
    dialog.set_title("Export Bookmarks to CSV")
    dialog.set_initial_name("bookmarks.csv")

    filters = Gio.ListStore.new(Gtk.FileFilter)
    csv_filter = Gtk.FileFilter()
    csv_filter.set_name("CSV files")
    csv_filter.add_pattern("*.csv")
    filters.append(csv_filter)
    dialog.set_filters(filters)

    def on_save(dlg, result):
        try:
            gfile = dlg.save_finish(result)
        except GLib.Error:
            return

        try:
            conn = get_connection()
            rows = conn.execute(
                "SELECT id, name, url, position FROM bookmarks ORDER BY position ASC"
            ).fetchall()
            conn.close()

            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["id", "name", "url", "position"])
            for r in rows:
                writer.writerow([r["id"], r["name"], r["url"], r["position"]])

            gfile.replace_contents(
                buf.getvalue().encode("utf-8"),
                None,
                False,
                Gio.FileCreateFlags.REPLACE_DESTINATION,
                None,
            )
            window.show_toast(f"Exported {len(rows)} bookmarks to {gfile.get_basename()}")
        except Exception as e:
            window.show_toast(f"Export failed: {e}")

    dialog.save(window, None, on_save)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _write_csv(file_path: str, headers: list[str], rows) -> None:
    """Write a CSV file with the given headers and sqlite3.Row rows.

    Each row is accessed by column name, so only columns listed in `headers`
    that actually exist on the row are written. Missing columns become empty strings.
    """
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            # sqlite3.Row supports key access; convert to a plain list in header order.
            writer.writerow([row[col] if col in row.keys() else "" for col in headers])
