# Converts Markdown text to a complete HTML document for display in a WebView.
#
# Used in two places:
#   lesson_view.py  — renders lesson content (text lessons)
#   lesson_view.py  — renders saved Feynman notes (completed lessons)
#
# To change the visual style, edit the CSS strings below.
# To support additional Markdown features, add extension names to the
# extensions list in render(). Available extensions:
#   https://python-markdown.github.io/extensions/

import markdown

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
