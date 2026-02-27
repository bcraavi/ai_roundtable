"""
Sanitization utilities — ANSI stripping, boundary escaping, sentinel handling.
"""

import re
from pathlib import Path
from typing import Dict

from ._constants import _PROJECT_DATA_TAG, _SENTINELS

# Full ECMA-48 CSI: private modes (?25l), intermediates
_ANSI_RE = re.compile(
    r'\x1b\[[\x20-\x3f]*[\x40-\x7e]'
    r'|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)'  # OSC sequences (BEL or ST terminated)
    r'|\x1bP[^\x1b]*\x1b\\'     # DCS sequences
    r'|\x1b[^[\]P]'             # Other ESC sequences (e.g., \x1b=)
)

# C0 control characters to strip (except \n=0x0a and \t=0x09 which are safe formatting)
_C0_RE = re.compile(r'[\x00-\x08\x0b-\x1f\x7f]')


def sanitize_terminal_output(text: str) -> str:
    """Strip ANSI/CSI/OSC escape sequences and C0 controls from agent output.

    Preserves \\n (newlines) and \\t (tabs) for formatting. Strips all other
    control characters including \\r (carriage return), \\b (backspace),
    \\x7f (DEL), and other non-printables that could spoof terminal output.
    """
    text = _ANSI_RE.sub('', text)
    text = _C0_RE.sub('', text)
    return text


def sanitize_project_content(text: str) -> str:
    """Escape content that could break the project-data trust boundary.

    Replaces any occurrence of both the opening and closing boundary tags
    inside scanned content so it cannot inject fake boundaries or
    prematurely terminate the data block. Also strips sentinel tokens
    to prevent accidental substitution when project files contain them.
    """
    text = text.replace(f"<{_PROJECT_DATA_TAG}>", f"<\\{_PROJECT_DATA_TAG}>")
    text = text.replace(f"</{_PROJECT_DATA_TAG}>", f"<\\/{_PROJECT_DATA_TAG}>")
    for sentinel in _SENTINELS:
        text = text.replace(sentinel, "")
    return text


def _is_within_root(file_path: Path, root: Path) -> bool:
    """Check if a file's real path is within the project root (symlink protection)."""
    try:
        file_path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def substitute_sentinels(template: str, replacements: Dict[str, str]) -> str:
    """Replace sentinel tokens in a single pass to prevent recursive expansion.

    Unlike chained .replace() calls, this ensures that content inserted for
    one sentinel (e.g., agent output containing __CONVERSATION_HISTORY__)
    cannot trigger substitution of another sentinel.
    """
    if not replacements:
        return template
    pattern = re.compile("|".join(re.escape(k) for k in replacements))
    return pattern.sub(lambda m: replacements[m.group(0)], template)


def strip_sentinels(text: str) -> str:
    """Remove sentinel tokens from text to prevent accidental substitution."""
    for sentinel in _SENTINELS:
        text = text.replace(sentinel, "")
    return text
