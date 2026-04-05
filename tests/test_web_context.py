"""Tests for web context — tech stack detection, search instructions, and context building."""

import unittest
import threading
from unittest.mock import patch, MagicMock
from datetime import date

from ai_roundtable._web_context import (
    detect_tech_stack,
    get_web_search_instruction,
    build_web_context,
    _fetch_latest_version,
    _fetch_versions,
    _VERSION_CHECKS,
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
        mock_fetch.return_value = "5.1.0"
        # Use a Django project so _VERSION_CHECKS has a match (Django → pypi)
        summary = "FILE TREE:\n  manage.py\n  requirements.txt\n  main.py"
        context = build_web_context(summary)
        self.assertIn("5.1.0", context)

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

    @patch('ai_roundtable._web_context._fetch_latest_version')
    def test_offline_skips_network_fetches(self, mock_fetch):
        """offline=True should skip version fetches entirely."""
        summary = "FILE TREE:\n  manage.py\n  requirements.txt\n  main.py"
        context = build_web_context(summary, offline=True)
        mock_fetch.assert_not_called()
        # Should still detect tech stack
        self.assertIn("Django", context)
        self.assertIn("Python", context)
        # Should NOT have version info
        self.assertNotIn("Latest stable versions", context)


class TestVersionChecks(unittest.TestCase):
    """Tests for _VERSION_CHECKS correctness."""

    def test_python_not_in_version_checks(self):
        """PyPI 'python' package is not CPython — must not be looked up."""
        self.assertNotIn("Python", _VERSION_CHECKS)


class TestFetchVersionsParallel(unittest.TestCase):
    """Tests for parallel version fetching."""

    @patch('ai_roundtable._web_context._fetch_latest_version')
    def test_fetches_in_parallel(self, mock_fetch):
        """Multiple packages should be fetched concurrently, not sequentially."""
        call_threads = []

        def _record_thread(package, registry):
            call_threads.append(threading.current_thread().name)
            return "1.0.0"

        mock_fetch.side_effect = _record_thread
        versions = _fetch_versions(["React", "Django", "Flask"])
        # Should have fetched react, django, flask
        self.assertEqual(len(versions), 3)
        self.assertIn("react", versions)
        self.assertIn("django", versions)
        self.assertIn("flask", versions)

    @patch('ai_roundtable._web_context._fetch_latest_version')
    def test_empty_tech_stack_returns_empty(self, mock_fetch):
        versions = _fetch_versions([])
        self.assertEqual(versions, {})
        mock_fetch.assert_not_called()

    @patch('ai_roundtable._web_context._fetch_latest_version')
    def test_unknown_tech_returns_empty(self, mock_fetch):
        versions = _fetch_versions(["UnknownLang"])
        self.assertEqual(versions, {})
        mock_fetch.assert_not_called()

    @patch('ai_roundtable._web_context._fetch_latest_version')
    def test_partial_failures_still_returns_successes(self, mock_fetch):
        def _selective(package, registry):
            if package == "react":
                return "19.0.0"
            return None

        mock_fetch.side_effect = _selective
        versions = _fetch_versions(["React", "Django"])
        self.assertEqual(versions, {"react": "19.0.0"})

    @patch('ai_roundtable._web_context._FETCH_DEADLINE', 2)
    @patch('ai_roundtable._web_context._fetch_latest_version')
    def test_global_deadline_bounds_wall_time(self, mock_fetch):
        """Total wall time should be bounded by _FETCH_DEADLINE, not N * deadline."""
        import time as _time

        def _slow_fetch(package, registry):
            _time.sleep(5)  # Each worker sleeps 5s (way over the 2s deadline)
            return "1.0.0"

        mock_fetch.side_effect = _slow_fetch
        start = _time.monotonic()
        versions = _fetch_versions(["React", "Django", "Flask"])
        elapsed = _time.monotonic() - start
        # Should complete in ~2s (deadline), not 15s (3 × 5s serial)
        self.assertLess(elapsed, 5.0)


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

    @patch('ai_roundtable._web_context.urllib.request.urlopen')
    def test_rejects_non_https_registry_urls(self, mock_urlopen):
        with patch('ai_roundtable._web_context._PYPI_URL', 'http://example.com/{}/json'):
            version = _fetch_latest_version("django", "pypi")
        self.assertIsNone(version)
        mock_urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
