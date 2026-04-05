# Detail page for a single Topic (Subject).
#
# Shows all Courses for the topic, each with a progress bar.
# Provides buttons to add a new course and to edit or delete the topic itself.
# Clicking a course row pushes CourseDetailPage.
#
# on_topic_changed is called when the topic is edited or deleted so the
# parent list (TopicsListPage or DashboardPage) can refresh.

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from foundation.models.topic import Topic
from foundation.models.course import Course
from foundation.views._utils import clear_children, make_menu_button, confirm_destructive


class TopicDetailPage(Adw.NavigationPage):
    __gtype_name__ = "TopicDetailPage"

    def __init__(self, topic: Topic, window, on_topic_changed=None):
        super().__init__(title=topic.title)
        self._topic = topic
        self._window = window
        self._on_topic_changed = on_topic_changed
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        self.set_child(toolbar_view)

        header = Adw.HeaderBar()

        # ⋮ menu — edit or delete the topic
        # Packed first so it appears rightmost (pack_end stacks right-to-left).
        more_btn = make_menu_button([
            ("Edit Subject",   self._on_edit_topic,   None),
            ("Delete Subject", self._on_delete_topic, "destructive-action"),
        ])
        header.pack_end(more_btn)

        # Primary action packed second — appears to the left of ⋮.
        new_course_btn = Gtk.Button(label="New Course")
        new_course_btn.add_css_class("suggested-action")
        new_course_btn.connect("clicked", self._on_new_course)
        header.pack_end(new_course_btn)

        toolbar_view.add_top_bar(header)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        toolbar_view.set_content(scrolled)

        self._content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._content_box.set_margin_top(12)
        self._content_box.set_margin_bottom(24)
        self._content_box.set_margin_start(12)
        self._content_box.set_margin_end(12)
        scrolled.set_child(self._content_box)

        self._populate()

    def _populate(self):
        """Clear and rebuild the course list. Called on first build and after changes."""
        clear_children(self._content_box)

        title_lbl = Gtk.Label(label=self._topic.title)
        title_lbl.add_css_class("title-1")
        title_lbl.set_xalign(0)
        title_lbl.set_margin_start(4)
        title_lbl.set_margin_bottom(4)
        self._content_box.append(title_lbl)

        if self._topic.description:
            desc = Gtk.Label(label=self._topic.description)
            desc.set_wrap(True)
            desc.set_xalign(0)
            desc.add_css_class("dim-label")
            desc.set_margin_start(4)
            self._content_box.append(desc)

        courses = Course.for_topic(self._topic.id)

        if not courses:
            status = Adw.StatusPage()
            status.set_title("No Courses Yet")
            status.set_description("Add your first course to start building this subject.")
            status.set_icon_name("folder-open-symbolic")
            status.set_vexpand(True)
            self._content_box.append(status)
            return

        group = Adw.PreferencesGroup(title="Courses")
        self._content_box.append(group)

        lesson_counts = Course.get_lesson_counts([c.id for c in courses])

        # GtkListBox inside the PreferencesGroup so rows get the boxed-list style.
        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        list_box.add_css_class("boxed-list")
        group.add(list_box)

        for course in courses:
            list_box.append(self._build_course_card(course, lesson_counts))

    def _build_course_card(self, course: Course, lesson_counts: dict) -> Adw.ActionRow:
        total, completed = lesson_counts.get(course.id, (0, 0))

        row = Adw.ActionRow()
        row.set_use_markup(False)  # course titles/descriptions may contain & or < characters
        # Append a checkmark to the title when all lessons are done.
        title_text = course.title + ("  ✓" if course.completed() else "")
        row.set_title(title_text)
        if course.description:
            row.set_subtitle(course.description)
        row.set_activatable(True)
        row.connect("activated", lambda _r, c=course: self._open_course(c))

        # Progress bar and count on the right side of the row.
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        right_box.set_valign(Gtk.Align.CENTER)

        progress_label = Gtk.Label(label=f"{completed}/{total} lessons")
        progress_label.add_css_class("caption")
        progress_label.add_css_class("dim-label")
        right_box.append(progress_label)

        if total > 0:
            bar = Gtk.ProgressBar()
            bar.set_fraction(completed / total)
            bar.set_size_request(100, -1)
            right_box.append(bar)

        row.add_suffix(right_box)
        row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))

        return row

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def trigger_new(self):
        """Called by the window's Ctrl+N handler — opens the new course dialog."""
        self._on_new_course(None)

    def _on_new_course(self, _btn):
        from foundation.views.form_dialogs import CourseFormDialog
        dialog = CourseFormDialog(topic_id=self._topic.id, on_success=self._populate)
        dialog.present(self._window)

    def _on_edit_topic(self, _btn):
        from foundation.views.form_dialogs import TopicFormDialog
        dialog = TopicFormDialog(topic=self._topic, on_success=self._after_topic_edit)
        dialog.present(self._window)

    def _on_delete_topic(self, _btn):
        confirm_destructive(
            "Delete Subject?",
            f'"{self._topic.title}" and all its courses and lessons will be permanently deleted.',
            self._window,
            self._do_delete_topic,
        )

    def _do_delete_topic(self):
        self._topic.delete()
        self._window.show_toast(f'Subject "{self._topic.title}" deleted.')
        self._window.nav_view.pop()
        if self._on_topic_changed:
            self._on_topic_changed()

    def _open_course(self, course):
        from foundation.views.course_detail_view import CourseDetailPage
        page = CourseDetailPage(course, self._window, on_course_changed=self._populate)
        self._window.nav_view.push(page)

    def _after_topic_edit(self):
        # Re-fetch the topic from the DB to pick up the new title/description.
        updated = Topic.find(self._topic.id)
        if updated:
            self._topic = updated
            self.set_title(self._topic.title)
            self._populate()
        if self._on_topic_changed:
            self._on_topic_changed()
