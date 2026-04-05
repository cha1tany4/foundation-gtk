# Shared GTK utility functions used across all view modules.
#
# build_nav_header() — builds the root-page header bar with Bookmarks / All Subjects / Study Log
# clear_children()   — removes all children from a widget (replaces manual while-loop)
# make_menu_button() — builds a ⋮ MenuButton with a Popover containing flat buttons
# confirm_destructive() — shows a destructive AlertDialog and calls a callback on confirm

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw


def clear_children(box: Gtk.Widget) -> None:
    """Remove all children from a Gtk.Box (or any widget with first-child/sibling API)."""
    child = box.get_first_child()
    while child:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt


def make_menu_button(
    items: list[tuple[str, object, str | None]],
    *,
    flat: bool = False,
) -> Gtk.MenuButton:
    """Build a ⋮ MenuButton with a Popover containing a column of flat buttons.

    items: list of (label, clicked_callback, extra_css_class_or_None).
           Set extra_css_class to "destructive-action" for destructive items.
    flat:  if True, add "flat" CSS class to the MenuButton itself.
    """
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    for label, callback, extra_css in items:
        btn = Gtk.Button(label=label)
        btn.add_css_class("flat")
        if extra_css:
            btn.add_css_class(extra_css)
        btn.connect("clicked", callback)
        box.append(btn)
    popover = Gtk.Popover()
    popover.set_child(box)
    popover.set_has_arrow(False)
    menu_btn = Gtk.MenuButton()
    menu_btn.set_icon_name("view-more-symbolic")
    menu_btn.set_popover(popover)
    if flat:
        menu_btn.add_css_class("flat")
    return menu_btn


def confirm_destructive(
    heading: str,
    body: str,
    parent,
    on_confirm,
    *,
    confirm_label: str = "Delete",
) -> None:
    """Show a destructive AlertDialog. Calls on_confirm() if the user confirms.

    heading:       Dialog title, e.g. "Delete Course?"
    body:          Explanatory text shown below the heading.
    parent:        Widget to present the dialog over (typically the window).
    on_confirm:    Zero-argument callable invoked when the user confirms.
    confirm_label: Label for the destructive button (default "Delete").
    """
    alert = Adw.AlertDialog(heading=heading, body=body)
    alert.add_response("cancel", "Cancel")
    alert.add_response("delete", confirm_label)
    alert.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
    alert.set_default_response("cancel")
    alert.set_close_response("cancel")

    def _on_response(_alert, response):
        if response == "delete":
            on_confirm()

    alert.connect("response", _on_response)
    alert.present(parent)


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
