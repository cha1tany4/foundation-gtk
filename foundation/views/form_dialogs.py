# Dialogs for creating and editing Topics, Courses, and Bookmarks.
#
# _FormDialog is a non-public base class that handles the shared chrome:
#   - AdwHeaderBar with Cancel (left) and Save (right)
#   - AdwPreferencesGroup (fields added by subclass via _build_fields())
#   - Error label below the group
#   - Destructive delete button in edit mode (label from _delete_label())
#
# Subclasses set their model attribute (e.g. self._topic) BEFORE calling
# super().__init__() so that _build_fields() can access it when called
# from within _build_ui() during base class initialisation.
#
# Usage:
#   Create: TopicFormDialog(on_success=callback)
#   Edit:   TopicFormDialog(topic=existing_topic, on_success=callback)
#   Then:   dialog.present(parent_widget)
#
# on_success is a zero-argument callable invoked after a successful save or delete.

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from foundation.models.topic import Topic
from foundation.models.course import Course
from foundation.models.bookmark import Bookmark


class _FormDialog(Adw.Dialog):
    __gtype_name__ = "_FormDialog"

    def __init__(self, *, is_edit: bool, title: str, width: int = 440, on_success=None):
        super().__init__()
        self._is_edit = is_edit
        self._on_success = on_success
        self.set_title(title)
        self.set_content_width(width)
        self._build_ui()

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        self.set_child(toolbar_view)

        header = Adw.HeaderBar()
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: self.close())
        header.pack_start(cancel_btn)
        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save)
        header.pack_end(save_btn)
        toolbar_view.add_top_bar(header)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_margin_top(12)
        outer.set_margin_bottom(24)
        outer.set_margin_start(12)
        outer.set_margin_end(12)
        toolbar_view.set_content(outer)

        group = Adw.PreferencesGroup()
        outer.append(group)
        self._build_fields(group)

        self._error_label = Gtk.Label()
        self._error_label.add_css_class("error")
        self._error_label.set_wrap(True)
        self._error_label.set_margin_top(8)
        self._error_label.set_visible(False)
        outer.append(self._error_label)

        if self._is_edit:
            delete_btn = Gtk.Button(label=self._delete_label())
            delete_btn.add_css_class("destructive-action")
            delete_btn.set_margin_top(24)
            delete_btn.connect("clicked", self._on_delete_clicked)
            outer.append(delete_btn)

    # ------------------------------------------------------------------
    # Subclass contract — override these
    # ------------------------------------------------------------------

    def _build_fields(self, group: Adw.PreferencesGroup) -> None:
        """Add entry rows to the group and pre-fill them in edit mode."""

    def _delete_label(self) -> str:
        return "Delete"

    def _on_save(self, _btn) -> None:
        """Validate, create or update the model, then call _finish_save()."""

    def _on_delete_clicked(self, _btn) -> None:
        """Call _show_delete_confirm(heading, body)."""

    def _do_delete(self) -> None:
        """Call model.delete()."""

    # ------------------------------------------------------------------
    # Shared implementations
    # ------------------------------------------------------------------

    def _show_delete_confirm(self, heading: str, body: str) -> None:
        alert = Adw.AlertDialog(heading=heading, body=body)
        alert.add_response("cancel", "Cancel")
        alert.add_response("delete", "Delete")
        alert.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        alert.set_default_response("cancel")
        alert.set_close_response("cancel")
        alert.connect("response", self._on_delete_confirmed)
        alert.present(self)

    def _on_delete_confirmed(self, _alert, response: str) -> None:
        if response != "delete":
            return
        self._do_delete()
        self.close()
        if self._on_success:
            self._on_success()

    def _finish_save(self) -> None:
        self.close()
        if self._on_success:
            self._on_success()

    def _show_errors(self, errors: list[str]) -> None:
        self._error_label.set_text(" ".join(errors))
        self._error_label.set_visible(True)


class TopicFormDialog(_FormDialog):
    __gtype_name__ = "TopicFormDialog"

    def __init__(self, topic: Topic | None = None, on_success=None):
        self._topic = topic
        super().__init__(
            is_edit=topic is not None,
            title="Edit Subject" if topic else "New Subject",
            on_success=on_success,
        )

    def _build_fields(self, group):
        self._title_row = Adw.EntryRow(title="Title")
        self._desc_row = Adw.EntryRow(title="Description (optional)")
        group.add(self._title_row)
        group.add(self._desc_row)
        if self._is_edit:
            self._title_row.set_text(self._topic.title or "")
            self._desc_row.set_text(self._topic.description or "")

    def _delete_label(self): return "Delete Subject"

    def _on_save(self, _btn):
        title = self._title_row.get_text().strip()
        desc = self._desc_row.get_text().strip() or None
        errors = Topic.validate(title)
        if errors:
            self._show_errors(errors)
            return
        if self._is_edit:
            self._topic.update(title, desc)
        else:
            Topic.create(title, desc)
        self._finish_save()

    def _on_delete_clicked(self, _btn):
        self._show_delete_confirm(
            "Delete Subject?",
            f'"{self._topic.title}" and all its courses and lessons will be permanently deleted.',
        )

    def _do_delete(self):
        self._topic.delete()


class CourseFormDialog(_FormDialog):
    __gtype_name__ = "CourseFormDialog"

    def __init__(self, topic_id: int | None = None, course: Course | None = None, on_success=None):
        self._topic_id = topic_id
        self._course = course
        super().__init__(
            is_edit=course is not None,
            title="Edit Course" if course else "New Course",
            on_success=on_success,
        )

    def _build_fields(self, group):
        self._title_row = Adw.EntryRow(title="Title")
        self._desc_row = Adw.EntryRow(title="Description (optional)")
        group.add(self._title_row)
        group.add(self._desc_row)
        if self._is_edit:
            self._title_row.set_text(self._course.title or "")
            self._desc_row.set_text(self._course.description or "")

    def _delete_label(self): return "Delete Course"

    def _on_save(self, _btn):
        title = self._title_row.get_text().strip()
        desc = self._desc_row.get_text().strip() or None
        errors = Course.validate(title)
        if errors:
            self._show_errors(errors)
            return
        if self._is_edit:
            self._course.update(title, desc)
        else:
            Course.create(self._topic_id, title, desc)
        self._finish_save()

    def _on_delete_clicked(self, _btn):
        self._show_delete_confirm(
            "Delete Course?",
            f'"{self._course.title}" and all its lessons will be permanently deleted.',
        )

    def _do_delete(self):
        self._course.delete()


class BookmarkFormDialog(_FormDialog):
    # The bookmark cap (MAX_BOOKMARKS) is enforced inside Bookmark.create(), not here.
    # The dashboard checks the cap before opening this dialog to avoid
    # showing the form only to reject it.
    __gtype_name__ = "BookmarkFormDialog"

    def __init__(self, bookmark: Bookmark | None = None, on_success=None):
        self._bookmark = bookmark
        super().__init__(
            is_edit=bookmark is not None,
            title="Edit Bookmark" if bookmark else "New Bookmark",
            width=420,
            on_success=on_success,
        )

    def _build_fields(self, group):
        self._name_row = Adw.EntryRow(title="Name")
        self._url_row = Adw.EntryRow(title="URL (https://…)")
        group.add(self._name_row)
        group.add(self._url_row)
        if self._is_edit:
            self._name_row.set_text(self._bookmark.name or "")
            self._url_row.set_text(self._bookmark.url or "")

    def _delete_label(self): return "Delete Bookmark"

    def _on_save(self, _btn):
        name = self._name_row.get_text().strip()
        url = self._url_row.get_text().strip()
        if self._is_edit:
            errors = self._bookmark.update(name, url)
        else:
            _bm, errors = Bookmark.create(name, url)
        if errors:
            self._show_errors(errors)
            return
        self._finish_save()

    def _on_delete_clicked(self, _btn):
        self._show_delete_confirm(
            "Delete Bookmark?",
            f'"{self._bookmark.name}" will be removed from your dashboard.',
        )

    def _do_delete(self):
        self._bookmark.delete()
