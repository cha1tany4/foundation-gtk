# Exports a Course and all its Lessons to a Markdown file.
#
# Called from CourseDetailPage._on_export() when the user picks
# "Export to Markdown" from the course menu.
# A GtkFileDialog is shown so the user can choose where to save the file.

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio, GLib

from foundation.models.course import Course
from foundation.models.lesson import Lesson, TEXT_CONTENT


def _build_markdown(course: Course, lessons: list[Lesson]) -> str:
    """Build the Markdown document string for a course and its lessons."""
    lines = [f"# {course.title}"]

    if course.description:
        lines += ["", course.description]

    if course.completed():
        lines += ["", "**Status:** Completed"]

    for lesson in lessons:
        lines += ["", "---", "", f"## {lesson.title}"]
        lines += [f"**Type:** {lesson.content_type_label()}  "]
        lines += [f"**Status:** {lesson.status_label()}"]

        if lesson.has_url() and lesson.source_url:
            lines += [f"**URL:** {lesson.source_url}"]

        if lesson.content_type == TEXT_CONTENT and lesson.content:
            lines += ["", lesson.content]

        if lesson.feynman_notes:
            lines += ["", "### Feynman Explanation", "", lesson.feynman_notes]

    return "\n".join(lines) + "\n"


def export_course(course: Course, window) -> None:
    """Open a save dialog and write the course to a .md file.

    The dialog is non-blocking. The file is written in the callback
    once the user confirms a save location.
    """
    lessons = Lesson.for_course(course.id)
    md_text = _build_markdown(course, lessons)

    dialog = Gtk.FileDialog.new()
    dialog.set_title("Export Course to Markdown")

    # Pre-fill the filename, replacing path separators that would break the name.
    safe_name = course.title.replace("/", "-").replace("\\", "-")
    dialog.set_initial_name(f"{safe_name}.md")

    # Restrict the file type filter to .md files.
    filters = Gio.ListStore.new(Gtk.FileFilter)
    md_filter = Gtk.FileFilter()
    md_filter.set_name("Markdown files")
    md_filter.add_pattern("*.md")
    filters.append(md_filter)
    dialog.set_filters(filters)

    def on_save(dlg, result):
        # save_finish() raises GLib.Error if the user cancelled.
        try:
            gfile = dlg.save_finish(result)
        except GLib.Error:
            return
        try:
            gfile.replace_contents(
                md_text.encode("utf-8"),
                None,   # etag — not needed here
                False,  # make_backup
                Gio.FileCreateFlags.REPLACE_DESTINATION,
                None,   # cancellable
            )
            window.show_toast(f"Exported to {gfile.get_basename()}")
        except GLib.Error as e:
            window.show_toast(f"Export failed: {e.message}")

    # save() is async — on_save is called when the dialog closes.
    dialog.save(window, None, on_save)
