# Converts Markdown text to a complete HTML document for display in a WebView,
# or applies formatting directly to a Gtk.TextBuffer when WebKit is unavailable.
#
# render()           — HTML string for WebView.load_html()
# render_to_buffer() — applies TextTags directly to a Gtk.TextBuffer (no WebKit needed)
#
# To change the visual style, edit the CSS strings below.
# To support additional Markdown features, add extension names to the
# extensions list in render(). Available extensions:
#   https://python-markdown.github.io/extensions/

import html.parser
import re
import markdown

_WHITESPACE_RE = re.compile(r"\s+")
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Pango

# CSS for lesson content (white background).
LESSON_CSS = """
body { font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 1rem; }
h1, h2, h3 { margin-top: 1.5rem; }
code { background: #f4f4f4; padding: 2px 4px; border-radius: 3px; font-size: 0.9em; }
pre  { background: #f4f4f4; padding: 1rem; border-radius: 6px; overflow-x: auto; }
pre code { background: none; padding: 0; }
blockquote { border-left: 3px solid #ccc; margin: 0; padding-left: 1rem; color: #555; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
th { background: #f4f4f4; }
img { max-width: 100%; }
"""

# CSS for Feynman notes — inherits LESSON_CSS and adds a tinted background
# so it is visually distinct from lesson content.
NOTES_CSS = LESSON_CSS + """
body { background: #fafafa; }
"""


def render(md_text: str, notes: bool = False) -> str:
    """Convert Markdown to a complete HTML string.

    Args:
        md_text: The raw Markdown text.
        notes:   If True, use the notes style (tinted background).

    Returns a full <html>...</html> document ready for WebView.load_html().
    """
    css = NOTES_CSS if notes else LESSON_CSS
    body = markdown.markdown(md_text or "", extensions=["fenced_code", "tables"])
    return f"<html><head><style>{css}</style></head><body>{body}</body></html>"


# ---------------------------------------------------------------------------
# TextBuffer renderer — fallback when WebKit is not available
# ---------------------------------------------------------------------------

def _ensure_tags(buf: Gtk.TextBuffer) -> None:
    """Create text formatting tags in the buffer's tag table (idempotent)."""
    table = buf.get_tag_table()
    if table.lookup("md-h1"):
        return  # already set up

    specs = [
        ("md-h1",     {"weight": Pango.Weight.BOLD, "size-points": 20.0}),
        ("md-h2",     {"weight": Pango.Weight.BOLD, "size-points": 16.0}),
        ("md-h3",     {"weight": Pango.Weight.BOLD, "size-points": 14.0}),
        ("md-h4",     {"weight": Pango.Weight.BOLD, "size-points": 12.0}),
        ("md-bold",   {"weight": Pango.Weight.BOLD}),
        ("md-italic", {"style": Pango.Style.ITALIC}),
        ("md-code",   {"family": "monospace", "background": "#f4f4f4",
                       "foreground": "#333333"}),
        ("md-pre",    {"family": "monospace", "background": "#f4f4f4",
                       "left-margin": 12, "paragraph-background": "#f4f4f4"}),
        ("md-para",   {"pixels-below-lines": 8}),
        ("md-notes",  {"background": "#fafafa"}),
    ]
    for name, props in specs:
        tag = Gtk.TextTag(name=name)
        for prop, val in props.items():
            tag.set_property(prop, val)
        table.add(tag)


class _HTMLParser(html.parser.HTMLParser):
    """Parse HTML produced by python-markdown and write tagged text into a
    Gtk.TextBuffer."""

    # Maps HTML tag names to TextTag names.
    _INLINE_TAGS = {
        "b": "md-bold", "strong": "md-bold",
        "em": "md-italic", "i": "md-italic",
        "code": "md-code",
    }
    _HEADING_TAGS = {"h1": "md-h1", "h2": "md-h2", "h3": "md-h3", "h4": "md-h4"}

    def __init__(self, buf: Gtk.TextBuffer, notes: bool):
        super().__init__(convert_charrefs=True)
        self._buf = buf
        self._notes = notes
        # Stack of (tag_name, start_iter_offset) tuples for range tagging.
        self._tag_stack: list[tuple[str, int]] = []
        # Track whether we're inside a <pre> block (suppress extra whitespace).
        self._in_pre = False
        self._in_li = False

    def _offset(self) -> int:
        return self._buf.get_char_count()

    def _apply_tag(self, tag_name: str, start_offset: int) -> None:
        start = self._buf.get_iter_at_offset(start_offset)
        end = self._buf.get_end_iter()
        self._buf.apply_tag_by_name(tag_name, start, end)

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self._INLINE_TAGS:
            self._tag_stack.append((self._INLINE_TAGS[tag], self._offset()))
        elif tag in self._HEADING_TAGS:
            self._tag_stack.append((self._HEADING_TAGS[tag], self._offset()))
            self._tag_stack.append(("md-para", self._offset()))
        elif tag == "p":
            self._tag_stack.append(("md-para", self._offset()))
        elif tag == "pre":
            self._in_pre = True
            self._tag_stack.append(("md-pre", self._offset()))
        elif tag == "li":
            self._in_li = True
            self._buf.insert(self._buf.get_end_iter(), "  • ")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self._INLINE_TAGS:
            tname = self._INLINE_TAGS[tag]
            # Pop the matching entry.
            for i in range(len(self._tag_stack) - 1, -1, -1):
                if self._tag_stack[i][0] == tname:
                    _, start_off = self._tag_stack.pop(i)
                    self._apply_tag(tname, start_off)
                    break
        elif tag in self._HEADING_TAGS:
            tname = self._HEADING_TAGS[tag]
            for i in range(len(self._tag_stack) - 1, -1, -1):
                if self._tag_stack[i][0] == tname:
                    _, start_off = self._tag_stack.pop(i)
                    self._apply_tag(tname, start_off)
                    break
            # Close the para tag too and add a newline.
            for i in range(len(self._tag_stack) - 1, -1, -1):
                if self._tag_stack[i][0] == "md-para":
                    _, start_off = self._tag_stack.pop(i)
                    self._buf.insert(self._buf.get_end_iter(), "\n")
                    self._apply_tag("md-para", start_off)
                    break
        elif tag == "p":
            for i in range(len(self._tag_stack) - 1, -1, -1):
                if self._tag_stack[i][0] == "md-para":
                    _, start_off = self._tag_stack.pop(i)
                    self._buf.insert(self._buf.get_end_iter(), "\n")
                    self._apply_tag("md-para", start_off)
                    break
        elif tag == "pre":
            self._in_pre = False
            for i in range(len(self._tag_stack) - 1, -1, -1):
                if self._tag_stack[i][0] == "md-pre":
                    _, start_off = self._tag_stack.pop(i)
                    self._buf.insert(self._buf.get_end_iter(), "\n")
                    self._apply_tag("md-pre", start_off)
                    break
        elif tag == "li":
            self._in_li = False
            self._buf.insert(self._buf.get_end_iter(), "\n")
        elif tag in ("ul", "ol"):
            self._buf.insert(self._buf.get_end_iter(), "\n")

    def handle_data(self, data):
        if not self._in_pre:
            # Collapse multiple whitespace characters outside <pre>.
            data = _WHITESPACE_RE.sub(" ", data)
        self._buf.insert(self._buf.get_end_iter(), data)


def render_to_buffer(md_text: str, buf: Gtk.TextBuffer, notes: bool = False) -> None:
    """Render markdown into a Gtk.TextBuffer with basic formatting.

    Converts markdown → HTML via python-markdown, then walks the HTML and
    applies TextTags for headings, bold, italic, code, and paragraphs.
    Used as the non-WebKit fallback in lesson_view.py.

    Args:
        md_text: Raw Markdown string.
        buf:     The TextBuffer to write into (will be cleared first).
        notes:   If True, apply a tinted-background tag to the whole buffer.
    """
    buf.set_text("")
    _ensure_tags(buf)

    html_text = markdown.markdown(md_text or "", extensions=["fenced_code", "tables"])
    parser = _HTMLParser(buf, notes=notes)
    parser.feed(html_text)

    if notes:
        start = buf.get_start_iter()
        end = buf.get_end_iter()
        buf.apply_tag_by_name("md-notes", start, end)
