# Dialog for creating or editing a Topic (Subject).
#
# Usage:
#   Create: TopicFormDialog(on_success=callback)
#   Edit:   TopicFormDialog(topic=existing_topic, on_success=callback)
#
# on_success is a zero-argument callable invoked after a successful save or delete.
# It is used by the caller to refresh its list.

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from foundation.models.topic import Topic


class TopicFormDialog(Adw.Dialog):
    # __gtype_name__ is required by GTK's type system when subclassing
    # a GObject-based class in Python. It must be unique across the app.
    __gtype_name__ = "TopicFormDialog"

    def __init__(self, topic: Topic | None = None, on_success=None):
        super().__init__()
        self._topic = topic
        self._on_success = on_success
        self._is_edit = topic is not None

        self.set_title("Edit Subject" if self._is_edit else "New Subject")
        self.set_content_width(440)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        self.set_child(toolbar_view)

        header = Adw.HeaderBar()

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: self.close())
        header.pack_start(cancel_btn)

        self._save_btn = Gtk.Button(label="Save")
        self._save_btn.add_css_class("suggested-action")
        self._save_btn.connect("clicked", self._on_save)
        header.pack_end(self._save_btn)

        toolbar_view.add_top_bar(header)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_margin_top(12)
        outer.set_margin_bottom(24)
        outer.set_margin_start(12)
        outer.set_margin_end(12)
        toolbar_view.set_content(outer)

        group = Adw.PreferencesGroup()
        outer.append(group)

        self._title_row = Adw.EntryRow(title="Title")
        group.add(self._title_row)

        self._desc_row = Adw.EntryRow(title="Description (optional)")
        group.add(self._desc_row)

        # Error label — hidden until a validation error occurs.
        self._error_label = Gtk.Label()
        self._error_label.add_css_class("error")
        self._error_label.set_wrap(True)
        self._error_label.set_margin_top(8)
        self._error_label.set_visible(False)
        outer.append(self._error_label)

        # In edit mode, pre-fill fields and show a destructive delete button.
        if self._is_edit:
            self._title_row.set_text(self._topic.title or "")
            self._desc_row.set_text(self._topic.description or "")

            delete_btn = Gtk.Button(label="Delete Subject")
            delete_btn.add_css_class("destructive-action")
            delete_btn.set_margin_top(24)
            delete_btn.connect("clicked", self._on_delete_clicked)
            outer.append(delete_btn)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

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

        self.close()
        if self._on_success:
            self._on_success()

    def _on_delete_clicked(self, _btn):
        # Require a confirmation before destroying the topic and all its data.
        alert = Adw.AlertDialog(
            heading="Delete Subject?",
            body=f'"{self._topic.title}" and all its courses and lessons will be permanently deleted.',
        )
        alert.add_response("cancel", "Cancel")
        alert.add_response("delete", "Delete")
        alert.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        alert.set_default_response("cancel")
        alert.set_close_response("cancel")
        alert.connect("response", self._on_delete_confirmed)
        alert.present(self)

    def _on_delete_confirmed(self, _alert, response: str):
        if response != "delete":
            return
        self._topic.delete()
        self.close()
        if self._on_success:
            self._on_success()

    def _show_errors(self, errors: list[str]):
        self._error_label.set_text(" ".join(errors))
        self._error_label.set_visible(True)
