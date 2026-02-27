"""Tests for lazy color resolution."""

import sys
import unittest

from ai_roundtable import Colors


class TestLazyColors(unittest.TestCase):
    """Tests for lazy color resolution."""

    def test_colors_resolve_without_tty(self):
        """Colors should be empty strings when stdout is not a TTY."""
        Colors._resolved = False
        Colors._resolve()
        # In test env, stdout is typically not a TTY
        if not sys.stdout.isatty():
            self.assertEqual(Colors.CLAUDE, "")
            self.assertEqual(Colors.RESET, "")


if __name__ == "__main__":
    unittest.main()
