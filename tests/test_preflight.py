"""Tests for CLI command preflight verification."""

import unittest
from unittest.mock import patch

from ai_roundtable import (
    preflight_check,
    RuntimeConfig,
    RoundtableError,
    CLAUDE_CMD,
    CODEX_CMD,
)


class TestPreflightCheck(unittest.TestCase):
    """Tests for CLI command preflight verification."""

    @patch('ai_roundtable._preflight.shutil.which')
    def test_preflight_raises_when_claude_missing(self, mock_which):
        """Missing claude binary should raise RoundtableError."""
        mock_which.side_effect = lambda x: None if x == CLAUDE_CMD else "/usr/bin/codex"
        with self.assertRaises(RoundtableError) as ctx:
            preflight_check()
        self.assertIn("not found", str(ctx.exception).lower())

    @patch('ai_roundtable._preflight.shutil.which')
    def test_preflight_raises_when_codex_missing(self, mock_which):
        """Missing codex binary should raise RoundtableError."""
        mock_which.side_effect = lambda x: "/usr/bin/claude" if x == CLAUDE_CMD else None
        with self.assertRaises(RoundtableError) as ctx:
            preflight_check()
        self.assertIn("not found", str(ctx.exception).lower())

    @patch('ai_roundtable._preflight.shutil.which')
    def test_preflight_returns_runtime_config(self, mock_which):
        """Both commands present should return RuntimeConfig with absolute paths."""
        mock_which.side_effect = lambda x: f"/usr/bin/{x}"
        config = preflight_check()
        self.assertIsInstance(config, RuntimeConfig)
        self.assertEqual(config.claude_cmd, f"/usr/bin/{CLAUDE_CMD}")
        self.assertEqual(config.codex_cmd, f"/usr/bin/{CODEX_CMD}")


if __name__ == "__main__":
    unittest.main()
