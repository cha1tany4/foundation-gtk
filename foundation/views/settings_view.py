# Settings page — user preferences and data management.
#
# Opened by the gear icon button in the navigation header (_nav.py).
# The page is an AdwNavigationPage pushed onto the navigation stack;
# AdwNavigationView provides the back button automatically.
#
# ADDING A NEW SETTING:
#   1. Add a row to the appropriate AdwPreferencesGroup in _build_ui().
#   2. Connect a handler that calls Settings.set("your_key", value).
#   3. Read it wherever needed with Settings.get_int("your_key", default).
#
# SETTINGS KEYS:
#   color_scheme        "0"=Follow System, "1"=Light, "2"=Dark
#   feynman_min_chars   integer string, default "50"

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from foundation.db.settings import Settings
from foundation.db.connection import get_connection, get_db_path


# Maps dropdown index → libadwaita color scheme constant.
_SCHEME_OPTIONS = ["Follow System", "Light", "Dark"]
_SCHEME_MAP = [
    Adw.ColorScheme.DEFAULT,
    Adw.ColorScheme.PREFER_LIGHT,
    Adw.ColorScheme.PREFER_DARK,
]


class SettingsPage(Adw.NavigationPage):
    __gtype_name__ = "SettingsPage"

    def __init__(self, window):
        super().__init__(title="Settings")
        self._window = window
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        self.set_child(toolbar_view)

        toolbar_view.add_top_bar(Adw.HeaderBar())

        # AdwPreferencesPage gives a scrollable, grouped layout — the standard
        # GNOME pattern for settings screens.
        prefs_page = Adw.PreferencesPage()
        toolbar_view.set_content(prefs_page)

        prefs_page.add(self._build_appearance_group())
        prefs_page.add(self._build_learning_group())
        prefs_page.add(self._build_data_group())

    def _build_appearance_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(title="Appearance")

        row = Adw.ComboRow(title="Color Scheme")
        row.set_subtitle("Follow the system setting, or force light or dark mode")
        row.set_model(Gtk.StringList.new(_SCHEME_OPTIONS))
        row.set_selected(Settings.get_int("color_scheme", 0))
        row.connect("notify::selected", self._on_scheme_changed)
        group.add(row)

        return group

    def _build_learning_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(title="Learning")

        adj = Gtk.Adjustment(
            value=Settings.get_int("feynman_min_chars", 50),
            lower=10, upper=200,
            step_increment=10, page_increment=50, page_size=0,
        )
        row = Adw.SpinRow(
            title="Feynman Minimum Characters",
            adjustment=adj,
            digits=0,
        )
        row.set_subtitle("Characters required in your explanation before marking a lesson done")
        row.connect("notify::value", self._on_feynman_min_changed)
        group.add(row)

        return group

    def _build_data_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(title="Data")

        # Read-only row showing where the database file lives.
        db_row = Adw.ActionRow(title="Database Location")
        db_row.set_subtitle(str(get_db_path()))
        db_row.set_use_markup(False)
        group.add(db_row)

        # Destructive action row — red button as a suffix.
        delete_row = Adw.ActionRow(title="Delete All Data")
        delete_row.set_subtitle(
            "Permanently removes all subjects, lessons, bookmarks, and activity history"
        )
        delete_btn = Gtk.Button(label="Delete All")
        delete_btn.add_css_class("destructive-action")
        delete_btn.set_valign(Gtk.Align.CENTER)
        delete_btn.connect("clicked", self._on_delete_all)
        delete_row.add_suffix(delete_btn)
        group.add(delete_row)

        return group

    # ------------------------------------------------------------------
    # Signal handlers — settings apply immediately on change
    # ------------------------------------------------------------------

    def _on_scheme_changed(self, row, _pspec):
        idx = row.get_selected()
        Settings.set("color_scheme", idx)
        # Apply immediately — no restart needed.
        Adw.StyleManager.get_default().set_color_scheme(_SCHEME_MAP[idx])

    def _on_feynman_min_changed(self, row, _pspec):
        Settings.set("feynman_min_chars", int(row.get_value()))

    def _on_delete_all(self, _btn):
        alert = Adw.AlertDialog(
            heading="Delete all data?",
            body=(
                "This will permanently remove all subjects, courses, lessons, "
                "bookmarks, and activity history. This cannot be undone."
            ),
        )
        alert.add_response("cancel", "Cancel")
        alert.add_response("delete", "Delete Everything")
        alert.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        alert.set_default_response("cancel")
        alert.set_close_response("cancel")
        alert.connect("response", self._on_delete_confirmed)
        alert.present(self._window)

    def _on_delete_confirmed(self, _alert, response: str):
        if response != "delete":
            return

        conn = get_connection()
        # Delete child tables before parents to respect foreign key constraints,
        # even though CASCADE handles it. Being explicit keeps the intent clear.
        for table in ("activities", "lessons", "courses", "topics", "bookmarks", "settings"):
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
        conn.close()

        # Navigate home so the user sees the now-empty dashboard.
        self._window.on_nav_home()
        self._window.show_toast("All data deleted.")
