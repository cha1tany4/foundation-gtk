# The lesson reading/completion page.
#
# Layout:
#   Gtk.Paned (VERTICAL, ~50/50)
#   ├── top:    lesson content
#   │     TEXT    → ScrolledWindow → WebView (or styled TextView fallback)
#   │     URL     → centred box with type icon + LinkButton (no scroll)
#   └── bottom: action area switching on lesson state:
#                 pending   — "Start Lesson" button
#                 started   — Feynman notes input + char count + submit
#                 completed — notes display (WebView/TextView) + optional edit
#
# WebKit2 4.1 is used for rendering Markdown when available (e.g. local run).
# In environments where it is absent (Flatpak), render_to_buffer() applies
# TextTags directly so headings, bold, italic, and code are still formatted.
#
# State constants (used as GtkStack page names):
_PENDING   = "pending"
_ACTIVE    = "active"
_COMPLETED = "completed"

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

try:
    gi.require_version("WebKit2", "4.1")
    from gi.repository import WebKit2
    HAS_WEBKIT = True
except (ValueError, ImportError):
    HAS_WEBKIT = False

from foundation.models.lesson import (
    Lesson, TEXT_CONTENT, VIDEO, PDF, EXTERNAL_LINK, FEYNMAN_MIN_CHARS
)
from foundation.db.settings import Settings
from foundation.utils.markdown_renderer import render, render_to_buffer

# Per-type icons used in the top pane for URL-based lessons.
_TYPE_ICON = {
    VIDEO:         "media-playback-start-symbolic",
    PDF:           "document-open-symbolic",
    EXTERNAL_LINK: "web-browser-symbolic",
}


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
        self._toggle_notes_btn = Gtk.Button(label="Update Explanation")
        self._toggle_notes_btn.add_css_class("flat")
        self._toggle_notes_btn.connect("clicked", self._on_toggle_notes_edit)
        self._toggle_notes_btn.set_visible(self._lesson.completed())
        self._header.pack_end(self._toggle_notes_btn)

        toolbar_view.add_top_bar(self._header)

        # Split the page into top (content) and bottom (Feynman/action) halves.
        paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        paned.set_vexpand(True)
        paned.set_wide_handle(False)
        paned.set_shrink_start_child(False)
        paned.set_shrink_end_child(False)
        toolbar_view.set_content(paned)

        paned.set_start_child(self._build_content_section())
        paned.set_end_child(self._build_action_section())

        # Set the divider to 50 % of the available height once the widget is
        # on screen. GLib.idle_add defers until after the first allocation.
        def _set_pos(p):
            h = p.get_height()
            if h > 0:
                p.set_position(h // 2)
            return False
        paned.connect("realize", lambda p: GLib.idle_add(_set_pos, p))

    def _build_content_section(self) -> Gtk.Widget:
        """Build the top pane that shows the lesson material."""
        if self._lesson.content_type == TEXT_CONTENT:
            if HAS_WEBKIT:
                scrolled = Gtk.ScrolledWindow()
                scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
                scrolled.set_vexpand(True)
                self._content_webview = WebKit2.WebView()
                self._content_webview.set_vexpand(True)
                self._content_webview.load_html(render(self._lesson.content or ""), None)
                scrolled.set_child(self._content_webview)
                return scrolled
            else:
                scrolled = Gtk.ScrolledWindow()
                scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
                scrolled.set_vexpand(True)
                tv = Gtk.TextView()
                tv.set_editable(False)
                tv.set_cursor_visible(False)
                tv.set_cursor(None)
                tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
                tv.set_top_margin(12)
                tv.set_bottom_margin(12)
                tv.set_left_margin(16)
                tv.set_right_margin(16)
                tv.set_vexpand(True)
                render_to_buffer(self._lesson.content or "", tv.get_buffer())
                scrolled.set_child(tv)
                return scrolled
        else:
            # URL-based lesson — show a centred icon + link; no scroll needed.
            type_label = self._lesson.content_type_label()
            icon_name = _TYPE_ICON.get(self._lesson.content_type, "web-browser-symbolic")

            outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            outer.set_vexpand(True)
            outer.set_valign(Gtk.Align.CENTER)
            outer.set_halign(Gtk.Align.CENTER)
            outer.set_margin_top(24)
            outer.set_margin_bottom(24)
            outer.set_margin_start(24)
            outer.set_margin_end(24)

            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(64)
            icon.add_css_class("dim-label")
            outer.append(icon)

            title_lbl = Gtk.Label(label=self._lesson.title)
            title_lbl.add_css_class("title-2")
            title_lbl.set_wrap(True)
            title_lbl.set_justify(Gtk.Justification.CENTER)
            outer.append(title_lbl)

            type_lbl = Gtk.Label(label=type_label)
            type_lbl.add_css_class("dim-label")
            outer.append(type_lbl)

            if self._lesson.source_url:
                open_btn = Gtk.Button(label=f"Open {type_label}")
                open_btn.add_css_class("suggested-action")
                open_btn.add_css_class("pill")
                open_btn.set_halign(Gtk.Align.CENTER)
                open_btn.connect("clicked", self._on_open_url, self._lesson.source_url)
                outer.append(open_btn)

            return outer

    def _build_action_section(self) -> Gtk.Widget:
        """Build the bottom pane; three panels managed by a GtkStack."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_vexpand(True)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.append(sep)

        self._action_stack = Gtk.Stack()
        self._action_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._action_stack.set_vexpand(True)
        box.append(self._action_stack)

        self._action_stack.add_named(self._build_pending_panel(), _PENDING)
        self._action_stack.add_named(self._build_active_panel(), _ACTIVE)
        self._action_stack.add_named(self._build_completed_panel(), _COMPLETED)

        self._sync_action_state()
        return box

    def _build_pending_panel(self) -> Gtk.Widget:
        """Panel shown before the lesson is started."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.set_vexpand(True)
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
        box.set_vexpand(True)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
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
        tv_frame.set_vexpand(True)
        tv_scroll = Gtk.ScrolledWindow()
        tv_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        tv_scroll.set_vexpand(True)
        self._feynman_view = Gtk.TextView()
        self._feynman_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._feynman_view.set_top_margin(8)
        self._feynman_view.set_bottom_margin(8)
        self._feynman_view.set_left_margin(8)
        self._feynman_view.set_right_margin(8)
        tv_scroll.set_child(self._feynman_view)
        tv_frame.set_child(tv_scroll)
        box.append(tv_frame)

        # Character count label and submit button.
        bottom_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bottom_row.set_margin_top(4)

        self._char_count_label = Gtk.Label(
            label=f"0 / {Settings.get_int('feynman_min_chars', FEYNMAN_MIN_CHARS)} characters minimum"
        )
        self._char_count_label.add_css_class("dim-label")
        self._char_count_label.set_hexpand(True)
        self._char_count_label.set_xalign(0)
        bottom_row.append(self._char_count_label)

        self._submit_btn = Gtk.Button(label="Mark as Done")
        self._submit_btn.add_css_class("suggested-action")
        self._submit_btn.set_sensitive(False)
        self._submit_btn.connect("clicked", self._on_submit)
        bottom_row.append(self._submit_btn)

        box.append(bottom_row)

        self._feynman_view.get_buffer().connect("changed", self._on_feynman_text_changed)

        return box

    def _build_completed_panel(self) -> Gtk.Widget:
        """Panel shown after the lesson is completed — notes display with edit mode."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_vexpand(True)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)

        title_lbl = Gtk.Label(label="Your Feynman Explanation")
        title_lbl.add_css_class("heading")
        title_lbl.set_xalign(0)
        box.append(title_lbl)

        # Inner stack switches between "display" (read) and "edit" (write) modes.
        self._notes_stack = Gtk.Stack()
        self._notes_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._notes_stack.set_vexpand(True)
        box.append(self._notes_stack)

        # Display page: rendered WebView (or styled TextView fallback).
        if HAS_WEBKIT:
            self._notes_display_webview = WebKit2.WebView()
            self._notes_display_webview.set_vexpand(True)
            self._notes_stack.add_named(self._notes_display_webview, "display")
        else:
            disp_scroll = Gtk.ScrolledWindow()
            disp_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            disp_scroll.set_vexpand(True)
            notes_tv = Gtk.TextView()
            notes_tv.set_editable(False)
            notes_tv.set_cursor_visible(False)
            notes_tv.set_cursor(None)
            notes_tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            notes_tv.set_top_margin(8)
            notes_tv.set_bottom_margin(8)
            notes_tv.set_left_margin(8)
            notes_tv.set_right_margin(8)
            notes_tv.set_vexpand(True)
            self._notes_display_fallback = notes_tv
            disp_scroll.set_child(notes_tv)
            self._notes_stack.add_named(disp_scroll, "display")

        # Edit page: text input with char count and save/cancel buttons.
        edit_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        edit_box.set_vexpand(True)

        edit_scroll = Gtk.ScrolledWindow()
        edit_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        edit_scroll.set_vexpand(True)
        self._notes_edit_view = Gtk.TextView()
        self._notes_edit_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._notes_edit_view.set_top_margin(8)
        self._notes_edit_view.set_bottom_margin(8)
        self._notes_edit_view.set_left_margin(8)
        self._notes_edit_view.set_right_margin(8)
        edit_scroll.set_child(self._notes_edit_view)

        edit_frame = Gtk.Frame()
        edit_frame.set_vexpand(True)
        edit_frame.set_child(edit_scroll)
        edit_box.append(edit_frame)

        self._notes_char_label = Gtk.Label(
            label=f"0 / {Settings.get_int('feynman_min_chars', FEYNMAN_MIN_CHARS)} characters minimum"
        )
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
            render_to_buffer(notes, self._notes_display_fallback.get_buffer(), notes=True)
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

    def _on_open_url(self, _btn, url: str):
        """Open the lesson's source URL in the system default application."""
        try:
            if "://" not in url:
                url = "file://" + url
            Gio.AppInfo.launch_default_for_uri(url, None)
        except Exception:
            self._window.show_toast("Could not open the resource.")

    def _on_start(self, _btn):
        """Stamp started_at and open the external resource if applicable."""
        self._lesson.start()
        if self._lesson.has_url() and self._lesson.source_url:
            try:
                url = self._lesson.source_url
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
