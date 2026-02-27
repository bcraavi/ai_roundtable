"""Integration tests for the run_roundtable orchestrator with mocked CLIs."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_roundtable import (
    run_roundtable,
    RunnerResult,
    _PROJECT_DATA_TAG,
    sanitize_terminal_output,
)


class TestOrchestratorIntegration(unittest.TestCase):
    """Integration tests for the run_roundtable orchestrator with mocked CLIs."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        Path(os.path.join(self.tmpdir, "main.py")).write_text("print('hello')")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _ok_result(self, text):
        return RunnerResult(ok=True, output=text, exit_code=0, error_type=None)

    def _err_result(self, text, error_type="exit_error"):
        return RunnerResult(ok=False, output=text, exit_code=1, error_type=error_type)

    @patch('ai_roundtable._orchestrator.run_codex')
    @patch('ai_roundtable._orchestrator.run_claude')
    @patch('ai_roundtable._orchestrator.preflight_check')
    def test_normal_4_round_flow(self, mock_preflight, mock_claude, mock_codex):
        """Full 4-round flow should produce log with all rounds."""
        mock_claude.side_effect = [
            self._ok_result("Claude round 1 review"),
            self._ok_result("Claude round 3 rebuttal"),
        ]
        mock_codex.side_effect = [
            self._ok_result("Codex round 2 counter"),
            self._ok_result("Codex round 4 verdict"),
        ]
        output = os.path.join(self.tmpdir, "test_output.md")
        result = run_roundtable(self.tmpdir, num_rounds=4, interactive=False, output_file=output)
        self.assertIn("Claude round 1 review", result)
        self.assertIn("Codex round 2 counter", result)
        self.assertIn("Claude round 3 rebuttal", result)
        self.assertIn("Codex round 4 verdict", result)

    @patch('ai_roundtable._orchestrator.run_codex')
    @patch('ai_roundtable._orchestrator.run_claude')
    @patch('ai_roundtable._orchestrator.preflight_check')
    def test_error_skip_recovery(self, mock_preflight, mock_claude, mock_codex):
        """When Codex fails Round 2, Claude Round 3 should still get a prompt."""
        mock_claude.side_effect = [
            self._ok_result("Claude round 1"),
            self._ok_result("Claude round 3 synthesis"),
        ]
        mock_codex.side_effect = [
            self._err_result("Codex crashed"),
            self._ok_result("Codex round 4 final"),
        ]
        output = os.path.join(self.tmpdir, "test_output.md")
        result = run_roundtable(self.tmpdir, num_rounds=4, interactive=False, output_file=output)
        self.assertIn("Claude round 1", result)
        self.assertIn("AGENT ERROR", result)
        self.assertIn("Claude round 3 synthesis", result)
        self.assertIn("Codex round 4 final", result)

    @patch('ai_roundtable._orchestrator.run_codex')
    @patch('ai_roundtable._orchestrator.run_claude')
    @patch('ai_roundtable._orchestrator.preflight_check')
    def test_dry_run_skips_agents(self, mock_preflight, mock_claude, mock_codex):
        """Dry run should not call any agents."""
        output = os.path.join(self.tmpdir, "test_output.md")
        result = run_roundtable(self.tmpdir, num_rounds=2, interactive=False,
                                output_file=output, dry_run=True)
        mock_claude.assert_not_called()
        mock_codex.assert_not_called()
        self.assertIn("dry-run", result)

    @patch('ai_roundtable._orchestrator.preflight_check')
    def test_dry_run_skips_preflight(self, mock_preflight):
        """Dry run should not call preflight_check."""
        output = os.path.join(self.tmpdir, "test_output.md")
        run_roundtable(self.tmpdir, num_rounds=2, interactive=False,
                       output_file=output, dry_run=True)
        mock_preflight.assert_not_called()

    @patch('ai_roundtable._orchestrator.build_web_context')
    @patch('ai_roundtable._orchestrator.preflight_check')
    def test_dry_run_skips_network_fetches(self, mock_preflight, mock_web_context):
        """Dry run should call build_web_context with offline=True."""
        mock_web_context.return_value = "CURRENT TECH CONTEXT"
        output = os.path.join(self.tmpdir, "test_output.md")
        run_roundtable(self.tmpdir, num_rounds=2, interactive=False,
                       output_file=output, dry_run=True)
        mock_web_context.assert_called_once()
        _, kwargs = mock_web_context.call_args
        self.assertTrue(kwargs.get('offline', False))

    @patch('ai_roundtable._orchestrator.run_codex')
    @patch('ai_roundtable._orchestrator.run_claude')
    @patch('ai_roundtable._orchestrator.preflight_check')
    def test_failure_threads_to_next_round(self, mock_preflight, mock_claude, mock_codex):
        """When an agent fails, the failure message should appear in the next round's prompt."""
        mock_claude.side_effect = [
            self._ok_result("Claude round 1 review"),
            self._ok_result("Claude round 3 sees failure context"),
        ]
        mock_codex.side_effect = [
            self._err_result("Connection refused", "exit_error"),
            self._ok_result("Codex round 4"),
        ]
        output = os.path.join(self.tmpdir, "test_output.md")
        run_roundtable(self.tmpdir, num_rounds=4, interactive=False, output_file=output)
        # Round 3 (Claude) should have received the failure info in its prompt
        round3_call = mock_claude.call_args_list[1]
        prompt = round3_call[0][0]  # First positional arg is the prompt
        self.assertIn("AGENT FAILED", prompt)

    @patch('ai_roundtable._orchestrator.run_codex')
    @patch('ai_roundtable._orchestrator.run_claude')
    @patch('ai_roundtable._orchestrator.preflight_check')
    def test_output_file_fallback(self, mock_preflight, mock_claude, mock_codex):
        """When no output file is specified, should create one in .roundtable/."""
        mock_claude.return_value = self._ok_result("review")
        mock_codex.return_value = self._ok_result("counter")
        run_roundtable(self.tmpdir, num_rounds=2, interactive=False)
        rt_dir = os.path.join(self.tmpdir, ".roundtable")
        self.assertTrue(os.path.isdir(rt_dir))
        files = os.listdir(rt_dir)
        self.assertTrue(any(f.startswith("roundtable_") for f in files))

    @patch('ai_roundtable._orchestrator.time.sleep')
    @patch('ai_roundtable._orchestrator.run_codex')
    @patch('ai_roundtable._orchestrator.run_claude')
    @patch('ai_roundtable._orchestrator.preflight_check')
    def test_retry_on_timeout(self, mock_preflight, mock_claude, mock_codex, mock_sleep):
        """Agent timeout should trigger a single retry with backoff."""
        timeout_result = self._err_result("timed out", "timeout")
        timeout_result.exit_code = None
        ok_result = self._ok_result("Claude review after retry")
        # First call times out, retry succeeds
        mock_claude.side_effect = [timeout_result, ok_result]
        mock_codex.return_value = self._ok_result("Codex review")
        output = os.path.join(self.tmpdir, "test_output.md")
        result = run_roundtable(self.tmpdir, num_rounds=2, interactive=False, output_file=output)
        self.assertIn("Claude review after retry", result)
        # Claude called twice: first attempt + retry
        self.assertEqual(mock_claude.call_count, 2)
        # Backoff sleep was called
        mock_sleep.assert_called_once_with(5)

    @patch('ai_roundtable._orchestrator.time.sleep')
    @patch('ai_roundtable._orchestrator.run_codex')
    @patch('ai_roundtable._orchestrator.run_claude')
    @patch('ai_roundtable._orchestrator.preflight_check')
    def test_retry_on_empty_response(self, mock_preflight, mock_claude, mock_codex, mock_sleep):
        """Empty response (exit 0, no output) should trigger a single retry."""
        empty_result = RunnerResult(ok=False, output="No response from Claude",
                                    exit_code=0, error_type="empty_response")
        ok_result = self._ok_result("Claude review after retry")
        mock_claude.side_effect = [empty_result, ok_result]
        mock_codex.return_value = self._ok_result("Codex review")
        output = os.path.join(self.tmpdir, "test_output.md")
        result = run_roundtable(self.tmpdir, num_rounds=2, interactive=False, output_file=output)
        self.assertIn("Claude review after retry", result)
        self.assertEqual(mock_claude.call_count, 2)
        mock_sleep.assert_called_once_with(5)

    @patch('ai_roundtable._orchestrator.time.sleep')
    @patch('ai_roundtable._orchestrator.run_codex')
    @patch('ai_roundtable._orchestrator.run_claude')
    @patch('ai_roundtable._orchestrator.preflight_check')
    def test_no_retry_on_exit_error(self, mock_preflight, mock_claude, mock_codex, mock_sleep):
        """Exit errors should NOT trigger retry (only timeout/exception do)."""
        mock_claude.side_effect = [
            self._ok_result("Claude round 1"),
            self._ok_result("Claude round 3"),
        ]
        mock_codex.side_effect = [
            self._err_result("Codex crashed", "exit_error"),
            self._ok_result("Codex round 4"),
        ]
        output = os.path.join(self.tmpdir, "test_output.md")
        run_roundtable(self.tmpdir, num_rounds=4, interactive=False, output_file=output)
        # Codex called twice (round 2 + round 4), no retry
        self.assertEqual(mock_codex.call_count, 2)
        mock_sleep.assert_not_called()


class TestDiffModeOrchestrator(unittest.TestCase):
    """Integration test for diff mode in the orchestrator."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        Path(os.path.join(self.tmpdir, "main.py")).write_text("print('hello')")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _ok_result(self, text):
        return RunnerResult(ok=True, output=text, exit_code=0, error_type=None)

    @patch('ai_roundtable._orchestrator.run_codex')
    @patch('ai_roundtable._orchestrator.run_claude')
    @patch('ai_roundtable._orchestrator.preflight_check')
    @patch('ai_roundtable._orchestrator.scan_diff')
    def test_diff_mode_uses_scan_diff(self, mock_scan_diff, mock_preflight, mock_claude, mock_codex):
        """When diff_target is set, should use scan_diff instead of scan_project."""
        mock_scan_diff.return_value = f"<{_PROJECT_DATA_TAG}>\ndiff content\n</{_PROJECT_DATA_TAG}>"
        mock_claude.return_value = self._ok_result("Claude diff review")
        mock_codex.return_value = self._ok_result("Codex diff review")
        output = os.path.join(self.tmpdir, "test_output.md")
        result = run_roundtable(self.tmpdir, num_rounds=2, interactive=False,
                                output_file=output, diff_target="HEAD")
        mock_scan_diff.assert_called_once_with(self.tmpdir, "HEAD")
        self.assertIn("Claude diff review", result)

    @patch('ai_roundtable._orchestrator.preflight_check')
    @patch('ai_roundtable._orchestrator.scan_diff')
    def test_diff_mode_no_changes_returns_early(self, mock_scan_diff, mock_preflight):
        """When scan_diff returns None (no changes), should return early."""
        mock_scan_diff.return_value = None
        output = os.path.join(self.tmpdir, "test_output.md")
        result = run_roundtable(self.tmpdir, num_rounds=2, interactive=False,
                                output_file=output, diff_target="HEAD")
        self.assertEqual(result, "")


class TestLogSanitization(unittest.TestCase):
    """Tests for ANSI sanitization in persisted logs."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        Path(os.path.join(self.tmpdir, "main.py")).write_text("print('hello')")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _ok_result(self, text):
        return RunnerResult(ok=True, output=text, exit_code=0, error_type=None)

    @patch('ai_roundtable._orchestrator.run_codex')
    @patch('ai_roundtable._orchestrator.run_claude')
    @patch('ai_roundtable._orchestrator.preflight_check')
    def test_log_file_has_no_ansi(self, mock_preflight, mock_claude, mock_codex):
        """Saved log files should not contain ANSI escape sequences."""
        mock_claude.return_value = self._ok_result("\x1b[31mRed review text\x1b[0m")
        mock_codex.return_value = self._ok_result("\x1b[32mGreen counter\x1b[0m")
        output = os.path.join(self.tmpdir, "test_output.md")
        run_roundtable(self.tmpdir, num_rounds=2, interactive=False, output_file=output)
        content = Path(output).read_text(encoding='utf-8')
        self.assertNotIn("\x1b", content)
        self.assertIn("Red review text", content)
        self.assertIn("Green counter", content)


if __name__ == "__main__":
    unittest.main()
