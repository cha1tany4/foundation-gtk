# Full-page form for creating or editing a Lesson.
#
# This is a navigation page (not a dialog) so the Markdown editor gets full
# screen space. AdwNavigationView provides the back button automatically.
# The Save button lives in the header bar.
#
# Usage:
#   Create: LessonFormPage(course_id=id, window=window, on_success=callback)
#   Edit:   LessonFormPage(lesson=existing_lesson, window=window, on_success=callback)
#   Then:   window.nav_view.push(page)
#
# HOW TO ADD A NEW CONTENT TYPE:
#   1. Add the constant and label to foundation/models/lesson.py.
#   2. Add it to _CONTENT_TYPE_ORDER below.
#   3. If it needs different input (not URL and not text), add a new stack
#      page and update _sync_stack().

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

from foundation.models.lesson import (
    Lesson, TEXT_CONTENT, VIDEO, PDF, EXTERNAL_LINK,
    CONTENT_TYPE_LABELS,
)

# The order in this list determines the order in the dropdown.
# Must include every content type defined in lesson.py.
_CONTENT_TYPE_ORDER = [TEXT_CONTENT, VIDEO, PDF, EXTERNAL_LINK]


class LessonFormPage(Adw.NavigationPage):
    __gtype_name__ = "LessonFormPage"

    def __init__(self, course_id: int | None = None, lesson: Lesson | None = None,
                 window=None, on_success=None):
        super().__init__()
        self._course_id = course_id
        self._lesson = lesson
        self._window = window
        self._on_success = on_success
        self._is_edit = lesson is not None

        self.set_title("Edit Lesson" if self._is_edit else "New Lesson")
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        self.set_child(toolbar_view)

        header = Adw.HeaderBar()

        self._save_btn = Gtk.Button(label="Save")
        self._save_btn.add_css_class("suggested-action")
        self._save_btn.connect("clicked", self._on_save)
        header.pack_end(self._save_btn)

        toolbar_view.add_top_bar(header)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        toolbar_view.set_content(scrolled)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.set_margin_top(12)
        outer.set_margin_bottom(24)
        outer.set_margin_start(12)
        outer.set_margin_end(12)
        scrolled.set_child(outer)

        # Title and content-type fields
        basic_group = Adw.PreferencesGroup()
        outer.append(basic_group)

        self._title_row = Adw.EntryRow(title="Title")
        basic_group.add(self._title_row)

        # GtkDropDown populated from _CONTENT_TYPE_ORDER labels.
        # When the selection changes, _on_type_changed switches the stack below.
        type_labels = [CONTENT_TYPE_LABELS[ct] for ct in _CONTENT_TYPE_ORDER]
        string_list = Gtk.StringList.new(type_labels)
        self._type_dropdown = Gtk.DropDown.new(string_list, None)
        self._type_dropdown.set_valign(Gtk.Align.CENTER)
        self._type_dropdown.connect("notify::selected", self._on_type_changed)

        type_row = Adw.ActionRow(title="Content Type")
        type_row.add_suffix(self._type_dropdown)
        basic_group.add(type_row)

        # GtkStack with two pages:
        #   "url"  — shown for Video, PDF, External Link
        #   "text" — shown for Text content
        self._content_stack = Gtk.Stack()
        outer.append(self._content_stack)

        url_group = Adw.PreferencesGroup()
        self._url_row = Adw.EntryRow(title="URL / File Path")

        # Browse button — shown as a suffix icon on the URL entry, visible only
        # when PDF type is selected. Clicking opens a file picker and fills the field.
        # To show it for other types too, remove the set_visible(False) call in _sync_stack().
        self._browse_btn = Gtk.Button()
        self._browse_btn.set_icon_name("folder-open-symbolic")
        self._browse_btn.add_css_class("flat")
        self._browse_btn.set_valign(Gtk.Align.CENTER)
        self._browse_btn.set_tooltip_text("Browse for PDF file")
        self._browse_btn.connect("clicked", self._on_browse_pdf)
        self._url_row.add_suffix(self._browse_btn)

        url_group.add(self._url_row)
        self._content_stack.add_named(url_group, "url")

        text_group = Adw.PreferencesGroup(title="Content (Markdown)")
        text_scroll = Gtk.ScrolledWindow()
        text_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        # Full page means the editor can expand freely — no fixed min height needed.
        text_scroll.set_vexpand(True)
        self._content_view = Gtk.TextView()
        self._content_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._content_view.set_top_margin(8)
        self._content_view.set_bottom_margin(8)
        self._content_view.set_left_margin(8)
        self._content_view.set_right_margin(8)
        self._content_view.add_css_class("card")
        text_scroll.set_child(self._content_view)
        text_group.add(text_scroll)
        self._content_stack.add_named(text_group, "text")

        self._error_label = Gtk.Label()
        self._error_label.add_css_class("error")
        self._error_label.set_wrap(True)
        self._error_label.set_visible(False)
        outer.append(self._error_label)

        # Pre-fill fields in edit mode, then sync the stack to show the right panel.
        if self._is_edit:
            self._title_row.set_text(self._lesson.title or "")
            idx = _CONTENT_TYPE_ORDER.index(self._lesson.content_type)
            self._type_dropdown.set_selected(idx)
            if self._lesson.has_url():
                self._url_row.set_text(self._lesson.source_url or "")
            else:
                self._content_view.get_buffer().set_text(self._lesson.content or "")
        else:
            self._type_dropdown.set_selected(0)

        # Always sync the stack last — set_selected() fires notify::selected,
        # but _sync_stack() is cheap so the double call here is harmless.
        self._sync_stack()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _selected_content_type(self) -> int:
        """Return the content type constant for the current dropdown selection."""
        idx = self._type_dropdown.get_selected()
        return _CONTENT_TYPE_ORDER[idx]

    def _sync_stack(self):
        """Show the URL entry or text editor depending on selected content type."""
        ct = self._selected_content_type()
        if ct == TEXT_CONTENT:
            self._content_stack.set_visible_child_name("text")
        else:
            self._content_stack.set_visible_child_name("url")
        # Show the browse button only for PDF — other URL types expect a web address.
        self._browse_btn.set_visible(ct == PDF)

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _on_browse_pdf(self, _btn):
        """Open a file picker and write the selected path as a file:// URI into the URL field."""
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Select PDF File")

        filters = Gio.ListStore.new(Gtk.FileFilter)
        pdf_filter = Gtk.FileFilter()
        pdf_filter.set_name("PDF files")
        pdf_filter.add_mime_type("application/pdf")
        pdf_filter.add_pattern("*.pdf")
        filters.append(pdf_filter)
        dialog.set_filters(filters)

        def on_file_selected(dlg, result):
            try:
                gfile = dlg.open_finish(result)
            except GLib.Error:
                return  # User cancelled.
            # Convert the system path to a file:// URI so launch_default_for_uri works.
            self._url_row.set_text(gfile.get_uri())

        # get_root() returns the top-level AdwApplicationWindow from any widget.
        dialog.open(self.get_root(), None, on_file_selected)

    def _on_type_changed(self, _dropdown, _pspec):
        self._sync_stack()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_save(self, _btn):
        title = self._title_row.get_text().strip()
        errors = Lesson.validate(title)
        if errors:
            self._show_errors(errors)
            return

        ct = self._selected_content_type()
        if ct == TEXT_CONTENT:
            buf = self._content_view.get_buffer()
            content = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False).strip() or None
            source_url = None
        else:
            source_url = self._url_row.get_text().strip() or None
            content = None

        if self._is_edit:
            self._lesson.update(title, ct, source_url, content)
        else:
            Lesson.create(self._course_id, title, ct, source_url, content)

        # Call on_success before popping so the previous page refreshes
        # before it becomes visible again.
        if self._on_success:
            self._on_success()
        self._window.nav_view.pop()

    def _show_errors(self, errors: list[str]):
        self._error_label.set_text(" ".join(errors))
        self._error_label.set_visible(True)
