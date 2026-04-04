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

        # Add the local icons directory to GTK's icon theme search path
        # so set_icon_name("foundation") resolves to assets/icons/foundation.svg.
        display = Gdk.Display.get_default()
        if display:
            Gtk.IconTheme.get_for_display(display).add_search_path(_ICONS_DIR)

        win = FoundationWindow(application=self)
        win.present()
