# Dialog for creating or editing a Bookmark.
#
# Usage:
#   Create: BookmarkFormDialog(on_success=callback)
#   Edit:   BookmarkFormDialog(bookmark=existing, on_success=callback)
#
# The bookmark cap (MAX_BOOKMARKS) is enforced inside Bookmark.create(), not here.
# The dashboard checks the cap before opening this dialog to avoid
# showing the form only to reject it.

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from foundation.models.bookmark import Bookmark


class BookmarkFormDialog(Adw.Dialog):
    __gtype_name__ = "BookmarkFormDialog"

    def __init__(self, bookmark: Bookmark | None = None, on_success=None):
        super().__init__()
        self._bookmark = bookmark
        self._on_success = on_success
        self._is_edit = bookmark is not None

        self.set_title("Edit Bookmark" if self._is_edit else "New Bookmark")
        self.set_content_width(420)
        self._build_ui()

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

        self._name_row = Adw.EntryRow(title="Name")
        group.add(self._name_row)

        self._url_row = Adw.EntryRow(title="URL (https://…)")
        group.add(self._url_row)

        self._error_label = Gtk.Label()
        self._error_label.add_css_class("error")
        self._error_label.set_wrap(True)
        self._error_label.set_margin_top(8)
        self._error_label.set_visible(False)
        outer.append(self._error_label)

        if self._is_edit:
            self._name_row.set_text(self._bookmark.name or "")
            self._url_row.set_text(self._bookmark.url or "")

            delete_btn = Gtk.Button(label="Delete Bookmark")
            delete_btn.add_css_class("destructive-action")
            delete_btn.set_margin_top(24)
            delete_btn.connect("clicked", self._on_delete_clicked)
            outer.append(delete_btn)

    def _on_save(self, _btn):
        name = self._name_row.get_text().strip()
        url = self._url_row.get_text().strip()

        if self._is_edit:
            errors = self._bookmark.update(name, url)
            if errors:
                self._show_errors(errors)
                return
        else:
            _bm, errors = Bookmark.create(name, url)
            if errors:
                self._show_errors(errors)
                return

        self.close()
        if self._on_success:
            self._on_success()

    def _on_delete_clicked(self, _btn):
        alert = Adw.AlertDialog(
            heading="Delete Bookmark?",
            body=f'"{self._bookmark.name}" will be removed from your dashboard.',
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
        self._bookmark.delete()
        self.close()
        if self._on_success:
            self._on_success()

    def _show_errors(self, errors: list[str]):
        self._error_label.set_text(" ".join(errors))
        self._error_label.set_visible(True)
