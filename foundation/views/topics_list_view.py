# The "All Subjects" root page.
#
# Shows all Topics in a scrollable list. Each row shows the topic title
# and a count of its courses and lessons. Clicking a row pushes TopicDetailPage.
#
# The "New Subject" button and Ctrl+N both open TopicFormDialog.
# trigger_new() is called by the window's Ctrl+N handler.

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from foundation.models.topic import Topic
from foundation.views._utils import build_nav_header, clear_children, make_menu_button


class TopicsListPage(Adw.NavigationPage):
    __gtype_name__ = "TopicsListPage"

    def __init__(self, window):
        super().__init__(title="All Subjects")
        self._window = window
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        self.set_child(toolbar_view)

        header = build_nav_header(self._window, "subjects")

        new_btn = Gtk.Button(label="New Subject")
        new_btn.add_css_class("suggested-action")
        new_btn.connect("clicked", self._on_new_topic)
        header.pack_end(new_btn)

        # Import/Export menu — sits to the left of the "New Subject" button.
        menu_btn = make_menu_button([
            ("Import Subjects (CSV)", self._on_import_subjects, None),
            ("Export Subjects (CSV)", self._on_export_subjects, None),
        ], flat=True)
        header.pack_end(menu_btn)

        toolbar_view.add_top_bar(header)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        toolbar_view.set_content(scrolled)

        self._content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._content_box.set_margin_top(12)
        self._content_box.set_margin_bottom(24)
        self._content_box.set_margin_start(12)
        self._content_box.set_margin_end(12)
        scrolled.set_child(self._content_box)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.add_css_class("boxed-list")

        self._status_page = Adw.StatusPage()
        self._status_page.set_title("No Subjects Yet")
        self._status_page.set_description(
            "Create your first subject to start organising your learning."
        )
        self._status_page.set_icon_name("folder-symbolic")
        self._status_page.set_vexpand(True)

        self.refresh()

    def refresh(self):
        """Reload topics from the database and rebuild the list."""
        clear_children(self._content_box)

        topics = Topic.all()

        if not topics:
            self._content_box.append(self._status_page)
            return

        counts = Topic.get_course_lesson_counts()

        clear_children(self._list_box)

        for topic in topics:
            self._list_box.append(self._build_topic_row(topic, counts))

        self._content_box.append(self._list_box)

    def _build_topic_row(self, topic: Topic, counts: dict) -> Adw.ActionRow:
        nc, nl = counts.get(topic.id, (0, 0))
        subtitle = f"{nc} course{'s' if nc != 1 else ''} · {nl} lesson{'s' if nl != 1 else ''}"

        row = Adw.ActionRow()
        row.set_use_markup(False)  # topic titles may contain & or < characters
        row.set_title(topic.title)
        row.set_subtitle(subtitle)
        row.set_activatable(True)
        row.connect("activated", lambda _r, t=topic: self._open_topic(t))

        chevron = Gtk.Image.new_from_icon_name("go-next-symbolic")
        row.add_suffix(chevron)

        return row

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def trigger_new(self):
        """Called by the window's Ctrl+N handler."""
        self._on_new_topic(None)

    def _on_new_topic(self, _btn):
        from foundation.views.form_dialogs import TopicFormDialog
        dialog = TopicFormDialog(on_success=self.refresh)
        dialog.present(self._window)

    def _on_import_subjects(self, _btn):
        from foundation.utils.csv_io import import_subjects
        import_subjects(self._window, self.refresh)

    def _on_export_subjects(self, _btn):
        from foundation.utils.csv_io import export_subjects
        export_subjects(self._window)

    def _open_topic(self, topic):
        from foundation.views.topic_detail_view import TopicDetailPage
        page = TopicDetailPage(topic, self._window, on_topic_changed=self.refresh)
        self._window.nav_view.push(page)
