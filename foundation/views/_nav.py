# Shared navigation header builder for the three root pages.
#
# Each root page (Bookmarks, Topics, Activity) calls build_nav_header()
# to get a pre-built AdwHeaderBar with the Bookmarks / All Subjects / Study Log
# buttons in the title area.
#
# The active button has no extra CSS class (libadwaita gives it a subtle
# filled/elevated appearance). Inactive buttons use the "flat" class
# (transparent background).
#
# Navigation logic (switching pages) stays in FoundationWindow, not here.
# The buttons are connected to the window's on_nav_* methods.

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw


def build_nav_header(window, active: str) -> Adw.HeaderBar:
    """Return an AdwHeaderBar with Bookmarks / All Subjects / Study Log nav buttons.

    Args:
        window: The FoundationWindow instance. Used to connect button signals.
        active: Which button to highlight. One of "bookmarks", "subjects", "log".

    To add a new top-level section:
        1. Add a new Gtk.Button below with its label and signal connection.
        2. Append it to nav_box.
        3. Add "your-key" to the active-check condition.
    """
    header = Adw.HeaderBar()

    btn_home = Gtk.Button(label="Bookmarks")
    btn_subjects = Gtk.Button(label="All Subjects")
    btn_log = Gtk.Button(label="Study Log")

    # Inactive buttons are flat (transparent). The active button keeps the
    # default style, giving it a subtle background to indicate current location.
    if active != "bookmarks":
        btn_home.add_css_class("flat")
    if active != "subjects":
        btn_subjects.add_css_class("flat")
    if active != "log":
        btn_log.add_css_class("flat")

    btn_home.connect("clicked", lambda _: window.on_nav_home())
    btn_subjects.connect("clicked", lambda _: window.on_nav_subjects())
    btn_log.connect("clicked", lambda _: window.on_nav_log())

    nav_box = Gtk.Box(spacing=4)
    nav_box.append(btn_home)
    nav_box.append(btn_subjects)
    nav_box.append(btn_log)

    header.set_title_widget(nav_box)

    # Gear icon button — opens the Settings page.
    # pack_start() places it on the LEFT side — Settings is a global action,
    # not page-specific, so it belongs on the left rather than mixed with
    # page-specific action buttons on the right.
    settings_btn = Gtk.Button()
    settings_btn.set_icon_name("preferences-system-symbolic")
    settings_btn.add_css_class("flat")
    settings_btn.set_tooltip_text("Settings")
    settings_btn.connect("clicked", lambda _: window.on_nav_settings())
    header.pack_start(settings_btn)

    return header
