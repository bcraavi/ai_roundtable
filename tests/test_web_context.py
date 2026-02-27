"""Tests for web context — tech stack detection, search instructions, and context building."""

import unittest
from unittest.mock import patch, MagicMock
from datetime import date

from ai_roundtable._web_context import (
    detect_tech_stack,
    get_web_search_instruction,
    build_web_context,
    _fetch_latest_version,
)


class TestDetectTechStack(unittest.TestCase):
    """Tests for technology detection from project summaries."""

    def test_detects_python(self):
        summary = "FILE TREE:\n  requirements.txt\n  main.py\n  utils.py"
        stack = detect_tech_stack(summary)
        self.assertIn("Python", stack)

    def test_detects_javascript_and_react(self):
        summary = 'FILE TREE:\n  package.json\n  src/App.tsx\nKEY CONFIG FILES:\n--- package.json ---\n{"react": "^18"}'
        stack = detect_tech_stack(summary)
        self.assertIn("JavaScript", stack)
        self.assertIn("React", stack)
        self.assertIn("TypeScript", stack)

    def test_detects_go(self):
        summary = "FILE TREE:\n  go.mod\n  main.go\n  handler.go"
        stack = detect_tech_stack(summary)
        self.assertIn("Go", stack)

    def test_detects_docker(self):
        summary = "FILE TREE:\n  Dockerfile\n  docker-compose.yml"
        stack = detect_tech_stack(summary)
        self.assertIn("Docker", stack)

    def test_empty_summary_returns_empty(self):
        stack = detect_tech_stack("")
        self.assertEqual(stack, [])

    def test_results_are_sorted(self):
        summary = "FILE TREE:\n  go.mod\n  main.go\n  Dockerfile\n  requirements.txt\n  main.py"
        stack = detect_tech_stack(summary)
        self.assertEqual(stack, sorted(stack))


class TestGetWebSearchInstruction(unittest.TestCase):
    """Tests for agent-specific web search instructions."""

    def test_claude_instruction_mentions_websearch(self):
        instruction = get_web_search_instruction("claude")
        self.assertIn("WebSearch", instruction)
        self.assertIn("WebFetch", instruction)

    def test_codex_instruction_mentions_web_search(self):
        instruction = get_web_search_instruction("codex")
        self.assertIn("web search", instruction.lower())

    def test_includes_todays_date(self):
        today = date.today().isoformat()
        for agent in ["claude", "codex"]:
            instruction = get_web_search_instruction(agent)
            self.assertIn(today, instruction)

    def test_mentions_cves(self):
        for agent in ["claude", "codex"]:
            instruction = get_web_search_instruction(agent)
            self.assertIn("CVE", instruction)


class TestBuildWebContext(unittest.TestCase):
    """Tests for complete web context building."""

    @patch('ai_roundtable._web_context._fetch_latest_version')
    def test_includes_tech_stack(self, mock_fetch):
        mock_fetch.return_value = None
        summary = "FILE TREE:\n  requirements.txt\n  main.py"
        context = build_web_context(summary)
        self.assertIn("Python", context)
        self.assertIn("CURRENT TECH CONTEXT", context)

    @patch('ai_roundtable._web_context._fetch_latest_version')
    def test_includes_date(self, mock_fetch):
        mock_fetch.return_value = None
        today = date.today().isoformat()
        context = build_web_context("FILE TREE:\n  main.py")
        self.assertIn(today, context)

    @patch('ai_roundtable._web_context._fetch_latest_version')
    def test_includes_versions_when_available(self, mock_fetch):
        mock_fetch.return_value = "3.12.0"
        summary = "FILE TREE:\n  requirements.txt\n  main.py"
        context = build_web_context(summary)
        self.assertIn("3.12.0", context)

    @patch('ai_roundtable._web_context._fetch_latest_version')
    def test_handles_fetch_failure_gracefully(self, mock_fetch):
        mock_fetch.return_value = None
        summary = "FILE TREE:\n  requirements.txt\n  main.py"
        # Should not raise
        context = build_web_context(summary)
        self.assertIsInstance(context, str)

    def test_no_tech_stack_message(self):
        with patch('ai_roundtable._web_context._fetch_latest_version', return_value=None):
            context = build_web_context("empty project")
        self.assertIn("No specific tech stack detected", context)


class TestFetchLatestVersion(unittest.TestCase):
    """Tests for version fetching (mocked network)."""

    @patch('ai_roundtable._web_context.urllib.request.urlopen')
    def test_pypi_fetch(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"info": {"version": "3.12.1"}}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        version = _fetch_latest_version("python", "pypi")
        self.assertEqual(version, "3.12.1")

    @patch('ai_roundtable._web_context.urllib.request.urlopen')
    def test_npm_fetch(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"version": "18.2.0"}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        version = _fetch_latest_version("react", "npm")
        self.assertEqual(version, "18.2.0")

    @patch('ai_roundtable._web_context.urllib.request.urlopen')
    def test_network_error_returns_none(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Network error")
        version = _fetch_latest_version("react", "npm")
        self.assertIsNone(version)


if __name__ == "__main__":
    unittest.main()
