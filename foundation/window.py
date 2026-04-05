# The main application window.
#
# Layout (outermost → innermost):
#   AdwApplicationWindow
#     AdwToastOverlay        ← lets any view show a brief notification
#       AdwNavigationView    ← single-pane stack; pages are pushed/popped as the
#                               user drills into topics → courses → lessons
#
# Each root page (Dashboard, Topics, Activity) owns its own AdwHeaderBar,
# which includes the Home / All Subjects / Study Log nav buttons via
# the build_nav_header() helper in foundation/views/_utils.py.
#
# Drill-down pages (topic detail, course detail, lesson view) each have their
# own AdwHeaderBar with a back button auto-provided by AdwNavigationView.
#
# To add a new top-level section:
#   1. Create a new page class in foundation/views/.
#   2. Instantiate it here (like self._activity_page).
#   3. Add on_nav_<name>() and a _switch_root call.
#   4. Add the button in foundation/views/_nav.py.

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio

from foundation.db.settings import Settings
from foundation.views.dashboard_view import DashboardPage
from foundation.views.topics_list_view import TopicsListPage
from foundation.views.activity_view import ActivityLogPage


class FoundationWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Foundation")
        self.set_default_size(1000, 700)
        self.set_icon_name("foundation")

        # Apply the saved color scheme before any widgets are created.
        _scheme_map = [Adw.ColorScheme.DEFAULT, Adw.ColorScheme.PREFER_LIGHT, Adw.ColorScheme.PREFER_DARK]
        Adw.StyleManager.get_default().set_color_scheme(
            _scheme_map[Settings.get_int("color_scheme", 0)]
        )

        # ToastOverlay wraps the navigation view so any page can call
        # window.show_toast("message") to display a brief notification.
        self._toast_overlay = Adw.ToastOverlay()
        self.set_content(self._toast_overlay)

        # AdwNavigationView is the direct child — no outer toolbar or header bar.
        # Each page supplies its own header bar, which AdwNavigationView surfaces.
        self._nav_view = Adw.NavigationView()
        self._toast_overlay.set_child(self._nav_view)

        # Root pages are created once and reused.
        # Pages that implement refresh() are refreshed each time you switch to them.
        self._dashboard_page = DashboardPage(self)
        self._topics_page = TopicsListPage(self)
        self._activity_page = ActivityLogPage(self)

        self._nav_view.add(self._dashboard_page)
        self._current_root = "bookmarks"

        # "win.new-item" action: triggered by Ctrl+N (registered in app.py).
        # Delegates to trigger_new() on the currently visible page.
        new_action = Gio.SimpleAction.new("new-item", None)
        new_action.connect("activate", self._on_new_item)
        self.add_action(new_action)

    # ------------------------------------------------------------------
    # Navigation — called by _nav.py button connections
    # ------------------------------------------------------------------

    def on_nav_home(self):
        self._switch_root(self._dashboard_page, "bookmarks")

    def on_nav_subjects(self):
        self._switch_root(self._topics_page, "subjects")

    def on_nav_log(self):
        self._switch_root(self._activity_page, "log")

    def on_nav_settings(self):
        from foundation.views.settings_view import SettingsPage
        self._nav_view.push(SettingsPage(self))

    def _switch_root(self, page: Adw.NavigationPage, name: str) -> None:
        # If already on this root, pop any drill-down pages to return to the top,
        # then refresh so settings changes (e.g. bookmark columns) take effect.
        if self._current_root == name:
            self._nav_view.pop_to_page(page)
            if hasattr(page, "refresh"):
                page.refresh()
            return
        self._current_root = name
        # replace() discards the entire stack and sets this as the only page.
        self._nav_view.replace([page])
        # Re-load data so the page reflects any changes made while away.
        if hasattr(page, "refresh"):
            page.refresh()

    # ------------------------------------------------------------------
    # Ctrl+N handler
    # ------------------------------------------------------------------

    def _on_new_item(self, _action, _param):
        page = self._nav_view.get_visible_page()
        if page and hasattr(page, "trigger_new"):
            page.trigger_new()

    # ------------------------------------------------------------------
    # Public helpers used by views
    # ------------------------------------------------------------------

    def show_toast(self, message: str) -> None:
        """Display a brief notification bar at the bottom of the window."""
        toast = Adw.Toast.new(message)
        self._toast_overlay.add_toast(toast)

    @property
    def nav_view(self) -> Adw.NavigationView:
        """Direct access to the navigation view for push/pop from within pages."""
        return self._nav_view
