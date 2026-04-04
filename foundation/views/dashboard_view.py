# The "Bookmarks" root page — Dashboard.
#
# Shows a drag-reorderable grid of bookmarks (cap set by MAX_BOOKMARKS in bookmark.py).
#
# Drag-and-drop reordering uses GtkDragSource (start drag) and GtkDropTarget
# (accept drop) on each bookmark card. When a card is dropped onto another card,
# Bookmark.reorder() is called with the new ID order and the grid refreshes.
#
# To change the bookmark card layout, edit _build_bookmark_card().

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GObject, Gdk, Pango

from foundation.models.bookmark import Bookmark, MAX_BOOKMARKS
from foundation.db.settings import Settings
from foundation.views._nav import build_nav_header


class DashboardPage(Adw.NavigationPage):
    __gtype_name__ = "DashboardPage"

    def __init__(self, window):
        super().__init__(title="Bookmarks")
        self._window = window
        self._bookmarks: list[Bookmark] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        self.set_child(toolbar_view)

        header = build_nav_header(self._window, "bookmarks")

        # "New Bookmark" button — checks the bookmark cap (MAX_BOOKMARKS) before opening the form.
        add_btn = Gtk.Button(label="New Bookmark")
        add_btn.add_css_class("suggested-action")
        add_btn.connect("clicked", self._on_add_bookmark)
        header.pack_end(add_btn)

        # Import/Export menu for bookmarks — sits to the left of the "+" button.
        # To add more bookmark actions, append another Gtk.Button to menu_box here.
        bm_menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        bm_import_btn = Gtk.Button(label="Import Bookmarks (CSV)")
        bm_import_btn.add_css_class("flat")
        bm_import_btn.connect("clicked", self._on_import_bookmarks)
        bm_menu_box.append(bm_import_btn)

        bm_export_btn = Gtk.Button(label="Export Bookmarks (CSV)")
        bm_export_btn.add_css_class("flat")
        bm_export_btn.connect("clicked", self._on_export_bookmarks)
        bm_menu_box.append(bm_export_btn)

        bm_popover = Gtk.Popover()
        bm_popover.set_child(bm_menu_box)
        bm_popover.set_has_arrow(False)

        bm_menu_btn = Gtk.MenuButton()
        bm_menu_btn.set_icon_name("view-more-symbolic")
        bm_menu_btn.set_popover(bm_popover)
        bm_menu_btn.add_css_class("flat")
        header.pack_end(bm_menu_btn)

        toolbar_view.add_top_bar(header)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        toolbar_view.set_content(scrolled)

        self._page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._page_box.set_margin_top(16)
        self._page_box.set_margin_bottom(24)
        self._page_box.set_margin_start(12)
        self._page_box.set_margin_end(12)
        scrolled.set_child(self._page_box)

        self.refresh()

    def refresh(self):
        """Reload bookmarks from the database and rebuild the grid."""
        child = self._page_box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self._page_box.remove(child)
            child = nxt

        self._bookmarks = Bookmark.all()
        self._build_bookmarks_section()

    # ------------------------------------------------------------------
    # Bookmarks section
    # ------------------------------------------------------------------

    def _build_bookmarks_section(self):
        if not self._bookmarks:
            status = Adw.StatusPage()
            status.set_title("No Bookmarks Yet")
            status.set_description('Press "New Bookmark" to add a quick-access link.')
            status.set_icon_name("starred-symbolic")
            self._page_box.append(status)
            return

        # GtkFlowBox arranges cards in a wrapping grid.
        # Column count is set by the user in Settings (default 4).
        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_max_children_per_line(Settings.get_int("bookmark_columns", 4))
        flow.set_min_children_per_line(1)
        flow.set_row_spacing(8)
        flow.set_column_spacing(8)
        flow.set_homogeneous(True)
        self._page_box.append(flow)

        for bm in self._bookmarks:
            flow.append(self._build_bookmark_card(bm))

    def _build_bookmark_card(self, bm: Bookmark) -> Gtk.FlowBoxChild:
        """Build one bookmark card with open/edit/delete buttons and D&D support."""
        child = Gtk.FlowBoxChild()
        child.set_focusable(False)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.add_css_class("card")
        outer.set_size_request(160, -1)
        child.set_child(outer)

        # Top row: bookmark name + open-in-browser button
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        top_row.set_margin_top(10)
        top_row.set_margin_start(10)
        top_row.set_margin_end(6)

        name_lbl = Gtk.Label(label=bm.name)
        name_lbl.add_css_class("heading")
        name_lbl.set_hexpand(True)
        name_lbl.set_xalign(0)
        name_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        name_lbl.set_tooltip_text(bm.name)
        top_row.append(name_lbl)

        open_btn = Gtk.Button()
        open_btn.set_icon_name("web-browser-symbolic")
        open_btn.add_css_class("flat")
        open_btn.set_valign(Gtk.Align.CENTER)
        open_btn.set_size_request(36, 36)
        open_btn.set_tooltip_text("Open")
        open_btn.connect("clicked", self._on_open_bookmark, bm.url)
        top_row.append(open_btn)

        outer.append(top_row)

        # Domain label (e.g. "github.com") below the name.
        domain_lbl = Gtk.Label(label=self._short_url(bm.url))
        domain_lbl.add_css_class("dim-label")
        domain_lbl.add_css_class("caption")
        domain_lbl.set_margin_start(10)
        domain_lbl.set_margin_bottom(6)
        domain_lbl.set_xalign(0)
        domain_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        outer.append(domain_lbl)

        # Edit and delete icon buttons at the bottom of the card.
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        btn_row.set_margin_start(4)
        btn_row.set_margin_end(4)
        btn_row.set_margin_bottom(4)

        edit_btn = Gtk.Button()
        edit_btn.set_icon_name("document-edit-symbolic")
        edit_btn.add_css_class("flat")
        edit_btn.set_tooltip_text("Edit")
        edit_btn.connect("clicked", self._on_edit_bookmark, bm)
        btn_row.append(edit_btn)

        del_btn = Gtk.Button()
        del_btn.set_icon_name("user-trash-symbolic")
        del_btn.add_css_class("flat")
        del_btn.add_css_class("destructive-action")
        del_btn.set_tooltip_text("Delete")
        del_btn.connect("clicked", self._on_delete_bookmark, bm)
        btn_row.append(del_btn)

        outer.append(btn_row)

        # Attach drag-and-drop controllers so cards can be reordered.
        self._attach_dnd(outer, bm)

        return child

    def _attach_dnd(self, widget: Gtk.Widget, bm: Bookmark):
        """Add GtkDragSource and GtkDropTarget to a bookmark card widget.

        The bookmark ID is passed as a string during the drag.
        On drop, the IDs are reordered and the grid refreshes.
        """
        # DragSource: initiates the drag when the user presses and holds.
        drag_source = Gtk.DragSource.new()
        drag_source.set_actions(Gdk.DragAction.MOVE)
        drag_source.connect("prepare", self._on_drag_prepare, bm.id)
        drag_source.connect("drag-begin", self._on_drag_begin, widget)
        drag_source.connect("drag-end", self._on_drag_end, widget)
        widget.add_controller(drag_source)

        # DropTarget: accepts a string (the dragged bookmark ID) when hovering.
        drop_target = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
        drop_target.connect("drop", self._on_drop, bm.id)
        drop_target.connect("enter", self._on_drop_enter, widget)
        drop_target.connect("leave", self._on_drop_leave, widget)
        widget.add_controller(drop_target)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _short_url(url: str) -> str:
        """Strip the scheme and path, returning just the domain name."""
        url = url.removeprefix("https://").removeprefix("http://").removeprefix("www.")
        return url.split("/")[0]

    # ------------------------------------------------------------------
    # Signal handlers — bookmarks
    # ------------------------------------------------------------------

    def trigger_new(self):
        """Called by the window's Ctrl+N handler — opens the add bookmark dialog."""
        self._on_add_bookmark(None)

    def _on_open_bookmark(self, _btn, url: str):
        try:
            Gio.AppInfo.launch_default_for_uri(url, None)
        except Exception:
            self._window.show_toast("Could not open URL.")

    def _on_import_bookmarks(self, _btn):
        from foundation.utils.csv_io import import_bookmarks
        import_bookmarks(self._window, self.refresh)

    def _on_export_bookmarks(self, _btn):
        from foundation.utils.csv_io import export_bookmarks
        export_bookmarks(self._window)

    def _on_add_bookmark(self, _btn):
        if Bookmark.count() >= MAX_BOOKMARKS:
            self._window.show_toast(f"Dashboard full — maximum {MAX_BOOKMARKS} bookmarks.")
            return
        from foundation.views.bookmark_form_view import BookmarkFormDialog
        dialog = BookmarkFormDialog(on_success=self.refresh)
        dialog.present(self._window)

    def _on_edit_bookmark(self, _btn, bm: Bookmark):
        from foundation.views.bookmark_form_view import BookmarkFormDialog
        dialog = BookmarkFormDialog(bookmark=bm, on_success=self.refresh)
        dialog.present(self._window)

    def _on_delete_bookmark(self, _btn, bm: Bookmark):
        alert = Adw.AlertDialog(
            heading="Delete Bookmark?",
            body=f'"{bm.name}" will be removed from your dashboard.',
        )
        alert.add_response("cancel", "Cancel")
        alert.add_response("delete", "Delete")
        alert.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        alert.set_default_response("cancel")
        alert.set_close_response("cancel")
        alert.connect("response", self._on_delete_confirmed, bm)
        alert.present(self._window)

    def _on_delete_confirmed(self, _alert, response: str, bm: Bookmark):
        if response != "delete":
            return
        bm.delete()
        self._window.show_toast(f'"{bm.name}" removed.')
        self.refresh()

    # ------------------------------------------------------------------
    # Drag-and-drop handlers
    # ------------------------------------------------------------------

    def _on_drag_prepare(self, _source, _x, _y, bm_id: int):
        """Package the bookmark ID as a string for transfer during drag."""
        val = GObject.Value()
        val.init(GObject.TYPE_STRING)
        val.set_string(str(bm_id))
        return Gdk.ContentProvider.new_for_value(val)

    def _on_drag_begin(self, _source, _drag, widget: Gtk.Widget):
        widget.add_css_class("drag-source")

    def _on_drag_end(self, _source, _drag, _delete, widget: Gtk.Widget):
        widget.remove_css_class("drag-source")

    def _on_drop_enter(self, _target, _x, _y, widget: Gtk.Widget):
        """Signal to GTK that this target accepts the drop, and add a visual hint."""
        widget.add_css_class("drop-target")
        return Gdk.DragAction.MOVE

    def _on_drop_leave(self, _target, widget: Gtk.Widget):
        widget.remove_css_class("drop-target")

    def _on_drop(self, _target, value, _x, _y, target_id: int) -> bool:
        """Reorder bookmarks when a card is dropped onto another card.

        value is the string ID of the dragged bookmark (set in _on_drag_prepare).
        target_id is the ID of the card being dropped onto.
        Returns True to confirm the drop was handled.
        """
        src_id = int(value)
        if src_id == target_id:
            return False
        ids = [b.id for b in self._bookmarks]
        if src_id not in ids or target_id not in ids:
            return False
        # Move src_id to just before target_id in the list.
        ids.remove(src_id)
        ids.insert(ids.index(target_id), src_id)
        Bookmark.reorder(ids)
        self.refresh()
        return True
