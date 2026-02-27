"""Tests for content sanitization and terminal output sanitization."""

import sys
import unittest

from ai_roundtable import (
    sanitize_project_content,
    sanitize_terminal_output,
    _is_within_root,
    _PREV_RESPONSE,
    _CONVERSATION_HISTORY,
    _PROJECT_DATA_TAG,
)
import os
import tempfile
from pathlib import Path


class TestSanitizeProjectContent(unittest.TestCase):
    """Tests for the content sanitization function."""

    def test_escapes_closing_tag(self):
        text = f"Hello </{_PROJECT_DATA_TAG}> world"
        result = sanitize_project_content(text)
        self.assertNotIn(f"</{_PROJECT_DATA_TAG}>", result)
        self.assertIn(f"<\\/{_PROJECT_DATA_TAG}>", result)

    def test_escapes_opening_tag(self):
        text = f"Fake <{_PROJECT_DATA_TAG}> injection"
        result = sanitize_project_content(text)
        self.assertNotIn(f"<{_PROJECT_DATA_TAG}>", result)
        self.assertIn(f"<\\{_PROJECT_DATA_TAG}>", result)

    def test_preserves_normal_text(self):
        text = "Normal project content with {braces} and <tags>"
        result = sanitize_project_content(text)
        self.assertEqual(text, result)

    def test_escapes_multiple_occurrences(self):
        text = f"a</{_PROJECT_DATA_TAG}>b</{_PROJECT_DATA_TAG}>c"
        result = sanitize_project_content(text)
        self.assertEqual(result.count(f"<\\/{_PROJECT_DATA_TAG}>"), 2)
        self.assertNotIn(f"</{_PROJECT_DATA_TAG}>", result)

    def test_escapes_both_tags_in_same_text(self):
        text = f"<{_PROJECT_DATA_TAG}>fake data</{_PROJECT_DATA_TAG}>"
        result = sanitize_project_content(text)
        self.assertNotIn(f"<{_PROJECT_DATA_TAG}>", result)
        self.assertNotIn(f"</{_PROJECT_DATA_TAG}>", result)

    def test_strips_sentinel_tokens_from_content(self):
        """Sentinel tokens in scanned project files should be stripped."""
        text = f"Code with {_PREV_RESPONSE} and {_CONVERSATION_HISTORY} literals"
        result = sanitize_project_content(text)
        self.assertNotIn(_PREV_RESPONSE, result)
        self.assertNotIn(_CONVERSATION_HISTORY, result)


class TestSanitizeTerminalOutput(unittest.TestCase):
    """Tests for terminal output sanitization."""

    def test_strips_ansi_color_codes(self):
        text = "\x1b[31mred text\x1b[0m"
        self.assertEqual(sanitize_terminal_output(text), "red text")

    def test_strips_csi_sequences(self):
        text = "\x1b[2J\x1b[H screen clear"
        result = sanitize_terminal_output(text)
        self.assertNotIn("\x1b", result)

    def test_preserves_normal_text(self):
        text = "Normal agent response with [brackets] and {braces}"
        self.assertEqual(sanitize_terminal_output(text), text)

    def test_strips_osc_sequences(self):
        text = "\x1b]0;malicious title\x07safe text"
        result = sanitize_terminal_output(text)
        self.assertIn("safe text", result)
        self.assertNotIn("malicious", result)

    def test_strips_private_mode_csi(self):
        """Private mode CSI sequences like ?25l (hide cursor) should be stripped."""
        text = "\x1b[?25lhidden cursor\x1b[?25h"
        result = sanitize_terminal_output(text)
        self.assertNotIn("\x1b", result)
        self.assertIn("hidden cursor", result)

    def test_strips_bracketed_paste(self):
        """Bracketed paste mode escape should be stripped."""
        text = "\x1b[?2004h pasted\x1b[?2004l"
        result = sanitize_terminal_output(text)
        self.assertNotIn("\x1b", result)
        self.assertIn("pasted", result)

    def test_strips_alternate_screen(self):
        """Alternate screen buffer escape should be stripped."""
        text = "\x1b[?1049h screen\x1b[?1049l"
        result = sanitize_terminal_output(text)
        self.assertNotIn("\x1b", result)
        self.assertIn("screen", result)


class TestC0Sanitization(unittest.TestCase):
    """Tests for C0 control character sanitization."""

    def test_strips_carriage_return(self):
        text = "fake\rreal output"
        result = sanitize_terminal_output(text)
        self.assertNotIn("\r", result)
        self.assertIn("real output", result)

    def test_strips_backspace(self):
        text = "password\b\b\b\b\b\b\b\bsafe text"
        result = sanitize_terminal_output(text)
        self.assertNotIn("\b", result)

    def test_strips_del(self):
        text = "text\x7f with delete"
        result = sanitize_terminal_output(text)
        self.assertNotIn("\x7f", result)

    def test_preserves_newlines_and_tabs(self):
        text = "line1\nline2\twith tab"
        result = sanitize_terminal_output(text)
        self.assertEqual(result, text)

    def test_strips_null(self):
        text = "null\x00byte"
        result = sanitize_terminal_output(text)
        self.assertNotIn("\x00", result)


class TestIsWithinRoot(unittest.TestCase):
    """Tests for symlink traversal protection."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmpdir, "src"))
        Path(os.path.join(self.tmpdir, "src", "main.py")).write_text("print('hi')")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_normal_file_is_within_root(self):
        root = Path(self.tmpdir)
        target = root / "src" / "main.py"
        self.assertTrue(_is_within_root(target, root))

    def test_parent_escape_rejected(self):
        root = Path(self.tmpdir)
        target = root / ".." / "etc" / "passwd"
        self.assertFalse(_is_within_root(target, root))

    def test_symlink_escape_rejected(self):
        """A symlink pointing outside the root should be rejected."""
        root = Path(self.tmpdir)
        link = root / "escape_link"
        try:
            link.symlink_to("/tmp")
            self.assertFalse(_is_within_root(link, root))
        except OSError:
            self.skipTest("Cannot create symlinks on this platform")

    def test_root_itself(self):
        root = Path(self.tmpdir)
        self.assertTrue(_is_within_root(root, root))


if __name__ == "__main__":
    unittest.main()
