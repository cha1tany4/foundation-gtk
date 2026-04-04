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
from foundation.models.course import Course
from foundation.models.lesson import Lesson
from foundation.views._nav import build_nav_header


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
        # To add more CSV actions, append another Gtk.Button to menu_box here.
        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        import_btn = Gtk.Button(label="Import Subjects (CSV)")
        import_btn.add_css_class("flat")
        import_btn.connect("clicked", self._on_import_subjects)
        menu_box.append(import_btn)

        export_btn = Gtk.Button(label="Export Subjects (CSV)")
        export_btn.add_css_class("flat")
        export_btn.connect("clicked", self._on_export_subjects)
        menu_box.append(export_btn)

        popover = Gtk.Popover()
        popover.set_child(menu_box)
        popover.set_has_arrow(False)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("view-more-symbolic")
        menu_btn.set_popover(popover)
        menu_btn.add_css_class("flat")
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
        self._list_box.connect("row-activated", self._on_topic_activated)

        self._status_page = Adw.StatusPage()
        self._status_page.set_title("No Subjects Yet")
        self._status_page.set_description(
            "Create your first subject to start organising your learning."
        )
        self._status_page.set_icon_name("folder-symbolic")

        self.refresh()

    def refresh(self):
        """Reload topics from the database and rebuild the list."""
        # Remove all current children from the content box.
        child = self._content_box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self._content_box.remove(child)
            child = nxt

        topics = Topic.all()

        if not topics:
            self._content_box.append(self._status_page)
            return

        # Remove all current rows from the list box before repopulating.
        row = self._list_box.get_first_child()
        while row:
            nxt = row.get_next_sibling()
            self._list_box.remove(row)
            row = nxt

        for topic in topics:
            self._list_box.append(self._build_topic_row(topic))

        self._content_box.append(self._list_box)

    def _build_topic_row(self, topic: Topic) -> Adw.ActionRow:
        # Fetch courses and lesson counts for the subtitle.
        # This is N+1 queries but acceptable for a personal app with small data.
        courses = Course.for_topic(topic.id)
        total_lessons = sum(len(Lesson.for_course(c.id)) for c in courses)

        nc = len(courses)
        nl = total_lessons
        subtitle = f"{nc} course{'s' if nc != 1 else ''} · {nl} lesson{'s' if nl != 1 else ''}"

        row = Adw.ActionRow()
        row.set_use_markup(False)  # topic titles may contain & or < characters
        row.set_title(topic.title)
        row.set_subtitle(subtitle)
        row.set_activatable(True)
        # Store the topic on the row so _on_topic_activated can retrieve it.
        row._topic = topic

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
        from foundation.views.topic_form_view import TopicFormDialog
        dialog = TopicFormDialog(on_success=self.refresh)
        dialog.present(self._window)

    def _on_import_subjects(self, _btn):
        from foundation.utils.csv_io import import_subjects
        import_subjects(self._window, self.refresh)

    def _on_export_subjects(self, _btn):
        from foundation.utils.csv_io import export_subjects
        export_subjects(self._window)

    def _on_topic_activated(self, _list_box, row):
        topic = row._topic
        from foundation.views.topic_detail_view import TopicDetailPage
        page = TopicDetailPage(topic, self._window, on_topic_changed=self.refresh)
        self._window.nav_view.push(page)
