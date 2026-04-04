# The top-level GTK application object.
#
# Responsibilities:
#   - Create the main window on launch.
#   - Run the database migrations so the schema is always up to date.
#   - Register the app icon and keyboard shortcuts.
#
# You should not need to modify this file unless you are adding a new
# application-wide keyboard shortcut or changing the app ID.

import os
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, Gdk

from foundation.db import run_migrations
from foundation.window import FoundationWindow


def _preload_modules() -> None:
    """Import all view and utility modules that are otherwise loaded lazily
    inside handler functions.

    In the Flatpak sandbox every module import involves filesystem operations
    through bwrap. Front-loading them here means the work happens once while
    the window is being set up rather than causing a freeze on the first click
    of each button or navigation action.
    """
    import foundation.views.bookmark_form_view  # noqa: F401
    import foundation.views.topic_form_view     # noqa: F401
    import foundation.views.course_form_view    # noqa: F401
    import foundation.views.lesson_form_view    # noqa: F401
    import foundation.views.topic_detail_view   # noqa: F401
    import foundation.views.course_detail_view  # noqa: F401
    import foundation.views.lesson_view         # noqa: F401
    import foundation.views.settings_view       # noqa: F401
    import foundation.utils.csv_io              # noqa: F401
    import foundation.utils.export              # noqa: F401

# Absolute path to the directory containing foundation.svg.
# GTK's icon theme searches this directory so the name "foundation"
# resolves to our local SVG without a system-wide install.
_ICONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons")


class FoundationApp(Adw.Application):
    def __init__(self):
        # application_id must be unique (reverse-DNS style).
        # It appears in window titles and is used by the desktop environment.
        super().__init__(application_id="io.github.cha1tany4.foundation")
        self.connect("activate", self._on_activate)

        # Register Ctrl+N as the accelerator for the "win.new-item" action.
        # "win." means the action lives on the window, not the app.
        # The action itself is defined in FoundationWindow.__init__.
        # To add more shortcuts: self.set_accels_for_action("win.action-name", ["<Control>key"])
        self.set_accels_for_action("win.new-item", ["<Control>n"])

    def _on_activate(self, _app):
        # Run DB migrations before the window opens so the schema always
        # matches what the models expect. Safe to call every launch —
        # already-applied migrations are skipped.
        run_migrations()

        # Pre-load all lazily-imported modules so first-click lag is avoided.
        _preload_modules()

        # Add the local icons directory to GTK's icon theme search path
        # so set_icon_name("foundation") resolves to assets/icons/foundation.svg.
        display = Gdk.Display.get_default()
        if display:
            Gtk.IconTheme.get_for_display(display).add_search_path(_ICONS_DIR)

        win = FoundationWindow(application=self)
        win.present()
