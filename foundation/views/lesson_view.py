# The lesson reading/completion page.
#
# Layout:
#   Top:    lesson content (WebView for text, status page + link for URLs)
#   Bottom: action area that switches based on lesson state:
#             pending   — "Start Lesson" button
#             started   — Feynman notes text input + character count + submit button
#             completed — notes display (WebView) with an optional edit mode
#
# WebKit2 is used for rendering Markdown. If it is not installed, a plain
# text fallback is shown instead. Install with: sudo apt install gir1.2-webkit2-4.1
#
# State constants (used as GtkStack page names):
_PENDING   = "pending"
_ACTIVE    = "active"
_COMPLETED = "completed"

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio

try:
    gi.require_version("WebKit2", "4.1")
    from gi.repository import WebKit2
    HAS_WEBKIT = True
except (ValueError, ImportError):
    HAS_WEBKIT = False

from foundation.models.lesson import Lesson, TEXT_CONTENT, FEYNMAN_MIN_CHARS
from foundation.db.settings import Settings
from foundation.utils.markdown_renderer import render


class LessonViewPage(Adw.NavigationPage):
    __gtype_name__ = "LessonViewPage"

    def __init__(self, lesson: Lesson, window, on_lesson_changed=None):
        super().__init__(title=lesson.title)
        self._lesson = lesson
        self._window = window
        # on_lesson_changed(lesson) is called after the lesson is completed,
        # its notes updated, edited, or deleted. Pass None on deletion.
        self._on_lesson_changed = on_lesson_changed
        self._notes_edit_mode = False
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        self.set_child(toolbar_view)

        self._header = Adw.HeaderBar()

        # ⋮ menu — edit or delete the lesson
        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        edit_btn = Gtk.Button(label="Edit Lesson")
        edit_btn.add_css_class("flat")
        edit_btn.connect("clicked", self._on_edit)
        menu_box.append(edit_btn)

        delete_btn = Gtk.Button(label="Delete Lesson")
        delete_btn.add_css_class("flat")
        delete_btn.add_css_class("destructive-action")
        delete_btn.connect("clicked", self._on_delete)
        menu_box.append(delete_btn)

        popover = Gtk.Popover()
        popover.set_child(menu_box)
        popover.set_has_arrow(False)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("view-more-symbolic")
        menu_btn.set_popover(popover)
        self._header.pack_end(menu_btn)

        # "Update Explanation" button — only visible when the lesson is completed.
        # Toggles the notes area between display and edit mode.
        self._toggle_notes_btn = Gtk.Button(label="Update Explanation")
        self._toggle_notes_btn.add_css_class("flat")
        self._toggle_notes_btn.connect("clicked", self._on_toggle_notes_edit)
        self._toggle_notes_btn.set_visible(self._lesson.completed())
        self._header.pack_end(self._toggle_notes_btn)

        toolbar_view.add_top_bar(self._header)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        toolbar_view.set_content(scrolled)

        self._page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scrolled.set_child(self._page_box)

        self._build_content_section()
        self._build_action_section()

    def _build_content_section(self):
        """Build the top area that shows the lesson material."""
        if self._lesson.content_type == TEXT_CONTENT:
            if HAS_WEBKIT:
                self._content_webview = WebKit2.WebView()
                self._content_webview.set_size_request(-1, 320)
                self._content_webview.load_html(render(self._lesson.content or ""), None)
                self._page_box.append(self._content_webview)
            else:
                # Fallback when WebKit2 is not installed.
                frame = Gtk.Frame()
                frame.set_margin_top(12)
                frame.set_margin_start(12)
                frame.set_margin_end(12)
                tv = Gtk.TextView()
                tv.set_editable(False)
                tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
                tv.set_size_request(-1, 280)
                tv.get_buffer().set_text(self._lesson.content or "(no content)")
                frame.set_child(tv)
                self._page_box.append(frame)
        else:
            # URL-based lesson — show the link; content is opened in system browser.
            type_label = self._lesson.content_type_label()
            status = Adw.StatusPage()
            status.set_title(self._lesson.title)
            status.set_description(f"This lesson is a {type_label}.")
            status.set_icon_name("applications-internet-symbolic")

            if self._lesson.source_url:
                link_btn = Gtk.LinkButton.new_with_label(
                    self._lesson.source_url, f"Open {type_label}"
                )
                link_btn.set_halign(Gtk.Align.CENTER)
                status.set_child(link_btn)

            self._page_box.append(status)

    def _build_action_section(self):
        """Build the bottom area; three panels managed by a GtkStack."""
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(8)
        self._page_box.append(sep)

        self._action_stack = Gtk.Stack()
        self._action_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._page_box.append(self._action_stack)

        self._action_stack.add_named(self._build_pending_panel(), _PENDING)
        self._action_stack.add_named(self._build_active_panel(), _ACTIVE)
        self._action_stack.add_named(self._build_completed_panel(), _COMPLETED)

        self._sync_action_state()

    def _build_pending_panel(self) -> Gtk.Widget:
        """Panel shown before the lesson is started."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_halign(Gtk.Align.CENTER)
        box.set_margin_top(24)
        box.set_margin_bottom(24)

        lbl = Gtk.Label(label="Start the lesson, then write your Feynman explanation.")
        lbl.add_css_class("dim-label")
        box.append(lbl)

        start_btn = Gtk.Button(label="Start Lesson")
        start_btn.add_css_class("suggested-action")
        start_btn.add_css_class("pill")
        start_btn.set_halign(Gtk.Align.CENTER)
        start_btn.connect("clicked", self._on_start)
        box.append(start_btn)

        return box

    def _build_active_panel(self) -> Gtk.Widget:
        """Panel shown while the lesson is in progress — Feynman notes input."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(12)
        box.set_margin_end(12)

        title_lbl = Gtk.Label(label="Your Feynman Explanation")
        title_lbl.add_css_class("heading")
        title_lbl.set_xalign(0)
        box.append(title_lbl)

        hint_lbl = Gtk.Label(label="Explain what you learned in your own words, as if teaching someone else.")
        hint_lbl.add_css_class("dim-label")
        hint_lbl.set_wrap(True)
        hint_lbl.set_xalign(0)
        box.append(hint_lbl)

        tv_frame = Gtk.Frame()
        tv_scroll = Gtk.ScrolledWindow()
        tv_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        tv_scroll.set_min_content_height(140)
        self._feynman_view = Gtk.TextView()
        self._feynman_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._feynman_view.set_top_margin(8)
        self._feynman_view.set_bottom_margin(8)
        self._feynman_view.set_left_margin(8)
        self._feynman_view.set_right_margin(8)
        tv_scroll.set_child(self._feynman_view)
        tv_frame.set_child(tv_scroll)
        box.append(tv_frame)

        # Character count label and submit button in a row at the bottom.
        bottom_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bottom_row.set_margin_top(4)

        self._char_count_label = Gtk.Label(label=f"0 / {Settings.get_int('feynman_min_chars', FEYNMAN_MIN_CHARS)} characters minimum")
        self._char_count_label.add_css_class("dim-label")
        self._char_count_label.set_hexpand(True)
        self._char_count_label.set_xalign(0)
        bottom_row.append(self._char_count_label)

        self._submit_btn = Gtk.Button(label="Mark as Done")
        self._submit_btn.add_css_class("suggested-action")
        self._submit_btn.set_sensitive(False)   # enabled only when char count >= minimum
        self._submit_btn.connect("clicked", self._on_submit)
        bottom_row.append(self._submit_btn)

        box.append(bottom_row)

        # Update the char count label every time the text buffer changes.
        self._feynman_view.get_buffer().connect("changed", self._on_feynman_text_changed)

        return box

    def _build_completed_panel(self) -> Gtk.Widget:
        """Panel shown after the lesson is completed — notes display with edit mode."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(12)
        box.set_margin_end(12)

        title_lbl = Gtk.Label(label="Your Feynman Explanation")
        title_lbl.add_css_class("heading")
        title_lbl.set_xalign(0)
        box.append(title_lbl)

        # Inner stack switches between "display" (read) and "edit" (write) modes.
        self._notes_stack = Gtk.Stack()
        self._notes_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        box.append(self._notes_stack)

        # Display page: rendered WebView (or plain text fallback).
        if HAS_WEBKIT:
            self._notes_display_webview = WebKit2.WebView()
            self._notes_display_webview.set_size_request(-1, 200)
            self._notes_stack.add_named(self._notes_display_webview, "display")
        else:
            notes_tv = Gtk.TextView()
            notes_tv.set_editable(False)
            notes_tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            notes_tv.set_size_request(-1, 200)
            self._notes_display_fallback = notes_tv
            self._notes_stack.add_named(notes_tv, "display")

        # Edit page: text input with save/cancel buttons.
        edit_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        edit_scroll = Gtk.ScrolledWindow()
        edit_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        edit_scroll.set_min_content_height(180)
        self._notes_edit_view = Gtk.TextView()
        self._notes_edit_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._notes_edit_view.set_top_margin(8)
        self._notes_edit_view.set_bottom_margin(8)
        self._notes_edit_view.set_left_margin(8)
        self._notes_edit_view.set_right_margin(8)
        edit_scroll.set_child(self._notes_edit_view)

        edit_frame = Gtk.Frame()
        edit_frame.set_child(edit_scroll)
        edit_box.append(edit_frame)

        self._notes_char_label = Gtk.Label(label=f"0 / {Settings.get_int('feynman_min_chars', FEYNMAN_MIN_CHARS)} characters minimum")
        self._notes_char_label.add_css_class("dim-label")
        self._notes_char_label.set_xalign(0)
        edit_box.append(self._notes_char_label)

        save_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        save_row.set_halign(Gtk.Align.END)

        cancel_edit_btn = Gtk.Button(label="Cancel")
        cancel_edit_btn.connect("clicked", self._on_cancel_notes_edit)
        save_row.append(cancel_edit_btn)

        self._save_notes_btn = Gtk.Button(label="Save Explanation")
        self._save_notes_btn.add_css_class("suggested-action")
        self._save_notes_btn.set_sensitive(False)
        self._save_notes_btn.connect("clicked", self._on_save_notes)
        save_row.append(self._save_notes_btn)

        edit_box.append(save_row)
        self._notes_stack.add_named(edit_box, "edit")

        self._notes_edit_view.get_buffer().connect("changed", self._on_notes_text_changed)

        return box

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def _sync_action_state(self):
        """Switch the action stack to the panel matching the lesson's current state."""
        if self._lesson.completed():
            self._action_stack.set_visible_child_name(_COMPLETED)
            self._refresh_notes_display()
        elif self._lesson.started():
            self._action_stack.set_visible_child_name(_ACTIVE)
        else:
            self._action_stack.set_visible_child_name(_PENDING)

        self._toggle_notes_btn.set_visible(self._lesson.completed())

    def _refresh_notes_display(self):
        """Load the saved notes into the display widget and switch to display mode."""
        notes = self._lesson.feynman_notes or ""
        if HAS_WEBKIT and hasattr(self, "_notes_display_webview"):
            self._notes_display_webview.load_html(render(notes, notes=True), None)
        elif hasattr(self, "_notes_display_fallback"):
            self._notes_display_fallback.get_buffer().set_text(notes)
        self._notes_stack.set_visible_child_name("display")
        self._notes_edit_mode = False
        self._toggle_notes_btn.set_label("Update Explanation")

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_feynman_text_changed(self, buf):
        min_chars = Settings.get_int("feynman_min_chars", FEYNMAN_MIN_CHARS)
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        n = len(text.strip())
        self._char_count_label.set_text(f"{n} / {min_chars} characters minimum")
        self._submit_btn.set_sensitive(n >= min_chars)

    def _on_notes_text_changed(self, buf):
        min_chars = Settings.get_int("feynman_min_chars", FEYNMAN_MIN_CHARS)
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        n = len(text.strip())
        self._notes_char_label.set_text(f"{n} / {min_chars} characters minimum")
        self._save_notes_btn.set_sensitive(n >= min_chars)

    def _on_toggle_notes_edit(self, _btn):
        """Toggle between display and edit mode for the Feynman notes."""
        if not self._notes_edit_mode:
            self._notes_edit_view.get_buffer().set_text(self._lesson.feynman_notes or "")
            self._notes_stack.set_visible_child_name("edit")
            self._notes_edit_mode = True
            self._toggle_notes_btn.set_label("Cancel")
        else:
            self._refresh_notes_display()

    def _on_cancel_notes_edit(self, _btn):
        self._refresh_notes_display()

    def _on_start(self, _btn):
        """Stamp started_at and open the external resource if applicable."""
        self._lesson.start()
        if self._lesson.has_url() and self._lesson.source_url:
            try:
                url = self._lesson.source_url
                # Bare file paths (e.g. from the Rails import) have no scheme.
                # launch_default_for_uri requires a URI, so prepend file:// for those.
                if "://" not in url:
                    url = "file://" + url
                Gio.AppInfo.launch_default_for_uri(url, None)
            except Exception:
                pass
        self._sync_action_state()

    def _on_submit(self, _btn):
        """Attempt to complete the lesson with the typed Feynman notes."""
        buf = self._feynman_view.get_buffer()
        notes = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        errors = self._lesson.mark_as_done(notes)
        if errors:
            self._window.show_toast(errors[0])
            return
        self._sync_action_state()
        self._window.show_toast("Lesson completed!")
        if self._on_lesson_changed:
            self._on_lesson_changed(self._lesson)

    def _on_save_notes(self, _btn):
        buf = self._notes_edit_view.get_buffer()
        notes = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        errors = self._lesson.update_notes(notes)
        if errors:
            self._window.show_toast(errors[0])
            return
        self._refresh_notes_display()
        self._window.show_toast("Explanation updated.")

    # ------------------------------------------------------------------
    # Edit / Delete
    # ------------------------------------------------------------------

    def _on_edit(self, _btn):
        from foundation.views.lesson_form_view import LessonFormPage
        page = LessonFormPage(lesson=self._lesson, window=self._window, on_success=self._after_edit)
        self._window.nav_view.push(page)

    def _after_edit(self):
        # Re-fetch from DB to pick up any changes made in the form.
        updated = Lesson.find(self._lesson.id)
        if updated:
            self._lesson = updated
            self.set_title(self._lesson.title)
        if self._on_lesson_changed:
            self._on_lesson_changed(self._lesson)

    def _on_delete(self, _btn):
        alert = Adw.AlertDialog(
            heading="Delete Lesson?",
            body=f'"{self._lesson.title}" will be permanently deleted.',
        )
        alert.add_response("cancel", "Cancel")
        alert.add_response("delete", "Delete")
        alert.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        alert.set_default_response("cancel")
        alert.set_close_response("cancel")
        alert.connect("response", self._on_delete_confirmed)
        alert.present(self._window)

    def _on_delete_confirmed(self, _alert, response: str):
        if response != "delete":
            return
        self._lesson.delete()
        self._window.show_toast(f'Lesson "{self._lesson.title}" deleted.')
        self._window.nav_view.pop()
        if self._on_lesson_changed:
            self._on_lesson_changed(None)
