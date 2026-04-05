# The "Study Log" root page.
#
# Displays all completed lessons in a GtkColumnView (a spreadsheet-style table).
#
# GtkColumnView requires items to be GObject subclasses stored in a Gio.ListStore.
# ActivityItem is that wrapper — it holds an Activity and nothing else.
# GtkSignalListItemFactory creates and populates one widget per visible cell.
#
# Columns: Date/Time | Course | Milestone | Review
#
# To add a column:
#   1. Define a factory function (_make_label_factory or a custom one).
#   2. Create a Gtk.ColumnViewColumn with that factory.
#   3. Call self._col_view.append_column(col) in _build_ui.

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GObject, Pango

from foundation.models.activity import Activity
from foundation.views._utils import build_nav_header, clear_children


class ActivityItem(GObject.Object):
    """Wraps an Activity so it can be stored in a Gio.ListStore.

    GObject.Object is the base class required by GTK's list model system.
    A plain Python dataclass cannot be used directly in Gio.ListStore.
    """
    __gtype_name__ = "ActivityItem"

    def __init__(self, activity: Activity):
        super().__init__()
        self.activity = activity


def _fmt_date(sqlite_dt: str) -> str:
    """Format a SQLite datetime string for display.

    Input:  '2024-01-15 10:30:00'
    Output: '15 Jan 2024, 10:30'
    Returns the raw string unchanged if parsing fails.
    """
    try:
        date_part, time_part = sqlite_dt.split(" ")
        year, month_num, day = date_part.split("-")
        hour, minute, _ = time_part.split(":")
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        return f"{int(day)} {months[int(month_num) - 1]} {year}, {hour}:{minute}"
    except (ValueError, AttributeError):
        return sqlite_dt


def _make_label_factory(get_text) -> Gtk.SignalListItemFactory:
    """Create a column factory that shows a plain text label.

    get_text is a function that takes an Activity and returns a string.
    Example: _make_label_factory(lambda a: a.course_title or "—")

    How GtkSignalListItemFactory works:
      "setup" — called once per visible row to create the widget.
      "bind"  — called when a row scrolls into view; populate the widget with data.
    """
    factory = Gtk.SignalListItemFactory()

    def setup(_f, item):
        lbl = Gtk.Label()
        lbl.set_xalign(0)
        lbl.set_margin_start(8)
        lbl.set_margin_end(8)
        lbl.set_margin_top(6)
        lbl.set_margin_bottom(6)
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
        item.set_child(lbl)

    def bind(_f, item):
        item.get_child().set_text(get_text(item.get_item().activity))

    factory.connect("setup", setup)
    factory.connect("bind", bind)
    return factory


def _make_review_factory() -> Gtk.SignalListItemFactory:
    """Create a column factory for the Review column.

    Shows a GtkLinkButton if the lesson has a source URL (video/pdf/link),
    or a plain label with the lesson title otherwise.
    A GtkStack is used to switch between the two widgets without recreating them.
    """
    factory = Gtk.SignalListItemFactory()

    def setup(_f, item):
        # Build both widgets once; bind() will show the appropriate one.
        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.NONE)

        lbl = Gtk.Label()
        lbl.set_xalign(0)
        lbl.set_margin_start(8)
        lbl.set_margin_end(8)
        lbl.add_css_class("dim-label")
        stack.add_named(lbl, "label")

        link = Gtk.LinkButton()
        link.set_margin_start(4)
        link.set_margin_end(4)
        link.set_halign(Gtk.Align.START)
        stack.add_named(link, "link")

        item.set_child(stack)

    def bind(_f, item):
        a = item.get_item().activity
        stack = item.get_child()
        if a.lesson_source_url:
            url = a.lesson_source_url
            # Raw file paths (legacy data) must be converted to file:// URIs.
            if url.startswith("/"):
                url = Gio.File.new_for_path(url).get_uri()
            link = stack.get_child_by_name("link")
            link.set_uri(url)
            link.set_label(a.lesson_title or a.lesson_source_url)
            stack.set_visible_child_name("link")
        else:
            lbl = stack.get_child_by_name("label")
            lbl.set_text(a.lesson_title or "—")
            stack.set_visible_child_name("label")

    factory.connect("setup", setup)
    factory.connect("bind", bind)
    return factory


class ActivityLogPage(Adw.NavigationPage):
    __gtype_name__ = "ActivityLogPage"

    def __init__(self, window):
        super().__init__(title="Study Log")
        self._window = window
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        self.set_child(toolbar_view)

        header = build_nav_header(self._window, "log")
        toolbar_view.add_top_bar(header)

        # Horizontal scroll is allowed so wide tables don't get clipped.
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        toolbar_view.set_content(scrolled)

        self._outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._outer_box.set_vexpand(True)
        scrolled.set_child(self._outer_box)

        # Empty-state page — shown when there are no activities yet.
        self._status_page = Adw.StatusPage()
        self._status_page.set_title("No Activity Yet")
        self._status_page.set_description("Completed lessons will appear here as your study history.")
        self._status_page.set_icon_name("document-open-recent-symbolic")
        self._status_page.set_vexpand(True)

        # The ListStore holds ActivityItem objects.
        # Gtk.NoSelection means rows are not selectable (read-only log).
        self._store = Gio.ListStore(item_type=ActivityItem)
        selection = Gtk.NoSelection.new(self._store)

        self._col_view = Gtk.ColumnView.new(selection)
        self._col_view.set_show_row_separators(True)
        self._col_view.set_show_column_separators(True)
        self._col_view.set_hexpand(True)
        self._col_view.set_vexpand(True)

        date_col = Gtk.ColumnViewColumn(
            title="Date / Time",
            factory=_make_label_factory(lambda a: _fmt_date(a.created_at)),
        )
        date_col.set_fixed_width(175)
        self._col_view.append_column(date_col)

        course_col = Gtk.ColumnViewColumn(
            title="Course",
            factory=_make_label_factory(lambda a: a.course_title or "—"),
        )
        course_col.set_fixed_width(200)
        self._col_view.append_column(course_col)

        # Milestone expands to fill available space.
        milestone_col = Gtk.ColumnViewColumn(
            title="Milestone",
            factory=_make_label_factory(lambda a: a.action),
        )
        milestone_col.set_expand(True)
        self._col_view.append_column(milestone_col)

        review_col = Gtk.ColumnViewColumn(
            title="Review",
            factory=_make_review_factory(),
        )
        review_col.set_fixed_width(220)
        self._col_view.append_column(review_col)

        self.refresh()

    def refresh(self):
        """Reload activities from the database and rebuild the table."""
        clear_children(self._outer_box)

        activities = Activity.all()

        if not activities:
            self._outer_box.append(self._status_page)
            return

        self._store.remove_all()
        for a in activities:
            self._store.append(ActivityItem(a))

        self._outer_box.append(self._col_view)
