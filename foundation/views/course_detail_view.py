# Detail page for a single Course.
#
# Shows a progress bar and the list of lessons with their status icons.
# The ⋮ menu provides Export, Edit, and Delete for the course.
# Clicking a lesson pushes LessonViewPage.
# The "Add Lesson" button and Ctrl+N push LessonFormPage onto the nav stack.
#
# on_course_changed is called when the course is edited or deleted so the
# parent TopicDetailPage can refresh.

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from foundation.models.course import Course
from foundation.models.lesson import Lesson
from foundation.views._utils import clear_children, make_menu_button, confirm_destructive


class CourseDetailPage(Adw.NavigationPage):
    __gtype_name__ = "CourseDetailPage"

    def __init__(self, course: Course, window, on_course_changed=None):
        super().__init__(title=course.title)
        self._course = course
        self._window = window
        self._on_course_changed = on_course_changed
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        self.set_child(toolbar_view)

        header = Adw.HeaderBar()

        # ⋮ menu — export, edit, or delete the course
        # Packed first so it appears rightmost (pack_end stacks right-to-left).
        menu_btn = make_menu_button([
            ("Export to Markdown", self._on_export, None),
            ("Edit Course",        self._on_edit,   None),
            ("Delete Course",      self._on_delete, "destructive-action"),
        ])
        header.pack_end(menu_btn)

        # Primary action packed second — appears to the left of ⋮.
        add_lesson_btn = Gtk.Button(label="Add Lesson")
        add_lesson_btn.add_css_class("suggested-action")
        add_lesson_btn.connect("clicked", self._on_add_lesson)
        header.pack_end(add_lesson_btn)

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
        """Clear and rebuild the lesson list. Called on first build and after changes."""
        clear_children(self._content_box)

        title_lbl = Gtk.Label(label=self._course.title)
        title_lbl.add_css_class("title-1")
        title_lbl.set_xalign(0)
        title_lbl.set_margin_start(4)
        title_lbl.set_margin_bottom(4)
        self._content_box.append(title_lbl)

        if self._course.description:
            desc_label = Gtk.Label(label=self._course.description)
            desc_label.set_wrap(True)
            desc_label.set_xalign(0)
            desc_label.add_css_class("dim-label")
            desc_label.set_margin_start(4)
            self._content_box.append(desc_label)

        if self._course.completed():
            badge = Gtk.Label(label="Course Completed")
            badge.add_css_class("success")
            badge.set_xalign(0)
            badge.set_margin_start(4)
            self._content_box.append(badge)

        lessons = Lesson.for_course(self._course.id)

        if not lessons:
            status = Adw.StatusPage()
            status.set_title("No Lessons Yet")
            status.set_description("Add your first lesson to get started.")
            status.set_icon_name("document-edit-symbolic")
            status.set_vexpand(True)
            self._content_box.append(status)
            return

        # Progress bar: fraction of lessons completed.
        done = sum(1 for l in lessons if l.completed())
        progress_bar = Gtk.ProgressBar()
        progress_bar.set_fraction(done / len(lessons))
        progress_bar.set_show_text(True)
        progress_bar.set_text(f"{done} / {len(lessons)} completed")
        progress_bar.set_margin_start(4)
        progress_bar.set_margin_end(4)
        self._content_box.append(progress_bar)

        lessons_group = Adw.PreferencesGroup(title="Lessons")
        self._content_box.append(lessons_group)

        for lesson in lessons:
            lessons_group.add(self._make_lesson_row(lesson))

    def _make_lesson_row(self, lesson) -> Adw.ActionRow:
        row = Adw.ActionRow()
        row.set_use_markup(False)  # lesson titles may contain & or < characters
        row.set_title(lesson.title)
        row.set_subtitle(lesson.content_type_label())
        row.set_activatable(True)
        row.connect("activated", self._on_lesson_activated, lesson)

        # Status icon: green check = completed, blue play = started, grey = pending
        if lesson.completed():
            icon_name, css = "object-select-symbolic", "success"
        elif lesson.started():
            icon_name, css = "media-playback-start-symbolic", "accent"
        else:
            icon_name, css = "content-loading-symbolic", "dim-label"

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.add_css_class(css)
        row.add_prefix(icon)

        status_lbl = Gtk.Label(label=lesson.status_label())
        status_lbl.add_css_class("dim-label")
        row.add_suffix(status_lbl)

        row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))

        return row

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def trigger_new(self):
        """Called by the window's Ctrl+N handler — opens the add lesson dialog."""
        self._on_add_lesson(None)

    def _on_export(self, _btn):
        from foundation.utils.export import export_course
        export_course(self._course, self._window)

    def _on_add_lesson(self, _btn):
        from foundation.views.lesson_form_view import LessonFormPage
        page = LessonFormPage(course_id=self._course.id, window=self._window, on_success=self._populate)
        self._window.nav_view.push(page)

    def _on_lesson_activated(self, _row, lesson):
        from foundation.views.lesson_view import LessonViewPage
        page = LessonViewPage(lesson, self._window, on_lesson_changed=self._on_lesson_changed)
        self._window.nav_view.push(page)

    def _on_lesson_changed(self, _lesson):
        # A lesson was completed, edited, or deleted — refresh this page.
        self._populate()

    def _on_edit(self, _btn):
        from foundation.views.form_dialogs import CourseFormDialog
        dialog = CourseFormDialog(course=self._course, on_success=self._after_change)
        dialog.present(self._window)

    def _on_delete(self, _btn):
        confirm_destructive(
            "Delete Course?",
            f'"{self._course.title}" and all its lessons will be permanently deleted.',
            self._window,
            self._do_delete_course,
        )

    def _do_delete_course(self):
        self._course.delete()
        self._window.show_toast(f'Course "{self._course.title}" deleted.')
        self._window.nav_view.pop()
        if self._on_course_changed:
            self._on_course_changed()

    def _after_change(self):
        # Re-fetch the course from the DB to pick up any title/description changes.
        updated = Course.find(self._course.id)
        if updated:
            self._course = updated
            self.set_title(self._course.title)
            self._populate()
        if self._on_course_changed:
            self._on_course_changed()
