"""Integration tests for the run_roundtable orchestrator with mocked CLIs."""

import os
import signal
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from ai_roundtable import (
    run_roundtable,
    RunnerResult,
    _PROJECT_DATA_TAG,
    sanitize_terminal_output,
)
from ai_roundtable._providers import AgentConfig


def _make_mock_agents():
    """Create mock agent configs for testing."""
    return [
        AgentConfig(name="Claude", agent_key="claude", cmd=["claude", "-p", "-"],
                     env_overrides={"CLAUDECODE": None}, color_code="\033[38;5;208m"),
        AgentConfig(name="Codex", agent_key="codex", cmd=["codex", "exec", "--skip-git-repo-check", "-"],
                     color_code="\033[38;5;40m"),
    ]


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

    @patch('ai_roundtable._orchestrator.run_agent')
    @patch('ai_roundtable._orchestrator.validate_agents', return_value=_make_mock_agents())
    def test_normal_4_round_flow(self, mock_validate, mock_run_agent):
        """Full 4-round flow should produce log with all rounds."""
        mock_run_agent.side_effect = [
            self._ok_result("Claude round 1 review"),
            self._ok_result("Codex round 2 counter"),
            self._ok_result("Claude round 3 rebuttal"),
            self._ok_result("Codex round 4 verdict"),
        ]
        output = os.path.join(self.tmpdir, "test_output.md")
        result = run_roundtable(self.tmpdir, num_rounds=4, interactive=False, output_file=output)
        self.assertIn("Claude round 1 review", result)
        self.assertIn("Codex round 2 counter", result)
        self.assertIn("Claude round 3 rebuttal", result)
        self.assertIn("Codex round 4 verdict", result)

    @patch('ai_roundtable._orchestrator.run_agent')
    @patch('ai_roundtable._orchestrator.validate_agents', return_value=_make_mock_agents())
    def test_error_skip_recovery(self, mock_validate, mock_run_agent):
        """When an agent fails Round 2, Round 3 should still get a prompt."""
        mock_run_agent.side_effect = [
            self._ok_result("Claude round 1"),
            self._err_result("Codex crashed"),
            self._ok_result("Claude round 3 synthesis"),
            self._ok_result("Codex round 4 final"),
        ]
        output = os.path.join(self.tmpdir, "test_output.md")
        result = run_roundtable(self.tmpdir, num_rounds=4, interactive=False, output_file=output)
        self.assertIn("Claude round 1", result)
        self.assertIn("AGENT ERROR", result)
        self.assertIn("Claude round 3 synthesis", result)
        self.assertIn("Codex round 4 final", result)

    @patch('ai_roundtable._orchestrator.run_agent')
    @patch('ai_roundtable._orchestrator.validate_agents')
    def test_dry_run_skips_agents(self, mock_validate, mock_run_agent):
        """Dry run should not call any agents."""
        output = os.path.join(self.tmpdir, "test_output.md")
        result = run_roundtable(self.tmpdir, num_rounds=2, interactive=False,
                                output_file=output, dry_run=True)
        mock_run_agent.assert_not_called()
        mock_validate.assert_not_called()
        self.assertIn("dry-run", result)

    @patch('ai_roundtable._orchestrator.validate_agents')
    def test_dry_run_skips_validation(self, mock_validate):
        """Dry run should not call validate_agents."""
        output = os.path.join(self.tmpdir, "test_output.md")
        run_roundtable(self.tmpdir, num_rounds=2, interactive=False,
                       output_file=output, dry_run=True)
        mock_validate.assert_not_called()

    @patch('ai_roundtable._orchestrator.build_web_context')
    @patch('ai_roundtable._orchestrator.validate_agents')
    def test_dry_run_skips_network_fetches(self, mock_validate, mock_web_context):
        """Dry run should call build_web_context with offline=True."""
        mock_web_context.return_value = "CURRENT TECH CONTEXT"
        output = os.path.join(self.tmpdir, "test_output.md")
        run_roundtable(self.tmpdir, num_rounds=2, interactive=False,
                       output_file=output, dry_run=True)
        mock_web_context.assert_called_once()
        _, kwargs = mock_web_context.call_args
        self.assertTrue(kwargs.get('offline', False))

    @patch('ai_roundtable._orchestrator.run_agent')
    @patch('ai_roundtable._orchestrator.validate_agents', return_value=_make_mock_agents())
    def test_failure_threads_to_next_round(self, mock_validate, mock_run_agent):
        """When an agent fails, the failure message should appear in the next round's prompt."""
        mock_run_agent.side_effect = [
            self._ok_result("Claude round 1 review"),
            self._err_result("Connection refused", "exit_error"),
            self._ok_result("Claude round 3 sees failure context"),
            self._ok_result("Codex round 4"),
        ]
        output = os.path.join(self.tmpdir, "test_output.md")
        run_roundtable(self.tmpdir, num_rounds=4, interactive=False, output_file=output)
        # Round 3 should have received the failure info in its prompt
        round3_call = mock_run_agent.call_args_list[2]
        prompt = round3_call[0][0]  # First positional arg is the prompt
        self.assertIn("AGENT FAILED", prompt)

    @patch('ai_roundtable._orchestrator.run_agent')
    @patch('ai_roundtable._orchestrator.validate_agents', return_value=_make_mock_agents())
    def test_output_file_fallback(self, mock_validate, mock_run_agent):
        """When no output file is specified, should create one in .roundtable/."""
        mock_run_agent.return_value = self._ok_result("review")
        run_roundtable(self.tmpdir, num_rounds=2, interactive=False)
        rt_dir = os.path.join(self.tmpdir, ".roundtable")
        self.assertTrue(os.path.isdir(rt_dir))
        files = os.listdir(rt_dir)
        self.assertTrue(any(f.startswith("roundtable_") for f in files))

    @patch('ai_roundtable._orchestrator.random.uniform', return_value=4.25)
    @patch('ai_roundtable._orchestrator.time.sleep')
    @patch('ai_roundtable._orchestrator.run_agent')
    @patch('ai_roundtable._orchestrator.validate_agents', return_value=_make_mock_agents())
    def test_retry_on_timeout(self, mock_validate, mock_run_agent, mock_sleep, mock_uniform):
        """Agent timeout should trigger a single retry with backoff."""
        timeout_result = self._err_result("timed out", "timeout")
        timeout_result.exit_code = None
        ok_result = self._ok_result("Claude review after retry")
        # First call times out, retry succeeds; then codex ok
        mock_run_agent.side_effect = [timeout_result, ok_result, self._ok_result("Codex review")]
        output = os.path.join(self.tmpdir, "test_output.md")
        result = run_roundtable(self.tmpdir, num_rounds=2, interactive=False, output_file=output)
        self.assertIn("Claude review after retry", result)
        # Backoff sleep was called
        mock_uniform.assert_called_once_with(3, 7)
        mock_sleep.assert_called_once_with(4.25)

    @patch('ai_roundtable._orchestrator.random.uniform', return_value=6.5)
    @patch('ai_roundtable._orchestrator.time.sleep')
    @patch('ai_roundtable._orchestrator.run_agent')
    @patch('ai_roundtable._orchestrator.validate_agents', return_value=_make_mock_agents())
    def test_retry_on_empty_response(self, mock_validate, mock_run_agent, mock_sleep, mock_uniform):
        """Empty response (exit 0, no output) should trigger a single retry."""
        empty_result = RunnerResult(ok=False, output="No response from Claude",
                                    exit_code=0, error_type="empty_response")
        ok_result = self._ok_result("Claude review after retry")
        mock_run_agent.side_effect = [empty_result, ok_result, self._ok_result("Codex review")]
        output = os.path.join(self.tmpdir, "test_output.md")
        result = run_roundtable(self.tmpdir, num_rounds=2, interactive=False, output_file=output)
        self.assertIn("Claude review after retry", result)
        mock_uniform.assert_called_once_with(3, 7)
        mock_sleep.assert_called_once_with(6.5)

    @patch('ai_roundtable._orchestrator.time.sleep')
    @patch('ai_roundtable._orchestrator.run_agent')
    @patch('ai_roundtable._orchestrator.validate_agents', return_value=_make_mock_agents())
    def test_no_retry_on_exit_error(self, mock_validate, mock_run_agent, mock_sleep):
        """Exit errors should NOT trigger retry (only timeout/exception do)."""
        mock_run_agent.side_effect = [
            self._ok_result("Claude round 1"),
            self._err_result("Codex crashed", "exit_error"),
            self._ok_result("Claude round 3"),
            self._ok_result("Codex round 4"),
        ]
        output = os.path.join(self.tmpdir, "test_output.md")
        run_roundtable(self.tmpdir, num_rounds=4, interactive=False, output_file=output)
        mock_sleep.assert_not_called()

    @patch('ai_roundtable._orchestrator.save_log')
    @patch('ai_roundtable._orchestrator.signal.signal')
    @patch('ai_roundtable._orchestrator.signal.getsignal')
    @patch('ai_roundtable._orchestrator.run_agent')
    @patch('ai_roundtable._orchestrator.validate_agents', return_value=_make_mock_agents())
    def test_sigterm_is_saved_from_main_loop(self, mock_validate, mock_run_agent,
                                             mock_getsignal, mock_signal, mock_save_log):
        """SIGTERM should only trigger partial-log saving from the main loop."""
        handlers = {}
        mock_getsignal.return_value = signal.SIG_DFL

        def _capture_handler(sig, handler):
            handlers[sig] = handler

        mock_signal.side_effect = _capture_handler

        def _trigger_sigterm(*args, **kwargs):
            handlers[signal.SIGTERM](signal.SIGTERM, None)
            return self._ok_result("Claude round 1 review")

        mock_run_agent.side_effect = _trigger_sigterm
        output = os.path.join(self.tmpdir, "test_output.md")

        with self.assertRaises(SystemExit) as ctx:
            run_roundtable(self.tmpdir, num_rounds=2, interactive=False, output_file=output)

        self.assertEqual(ctx.exception.code, 143)
        mock_save_log.assert_called_once()
        _, kwargs = mock_save_log.call_args
        self.assertTrue(kwargs.get("is_partial"))


class TestAutoTimeout(unittest.TestCase):
    """Tests for auto-timeout scaling based on project size."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Create a project with many files to trigger auto-scaling
        for i in range(250):
            Path(os.path.join(self.tmpdir, f"file_{i:04d}.py")).write_text(f"# file {i}")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _ok_result(self, text):
        return RunnerResult(ok=True, output=text, exit_code=0, error_type=None)

    @patch('ai_roundtable._orchestrator.run_agent')
    @patch('ai_roundtable._orchestrator.validate_agents', return_value=_make_mock_agents())
    def test_auto_scales_timeout_for_large_project(self, mock_validate, mock_run_agent):
        """Large projects should get an auto-scaled timeout."""
        mock_run_agent.return_value = self._ok_result("review")
        output = os.path.join(self.tmpdir, "test_output.md")
        run_roundtable(self.tmpdir, num_rounds=2, interactive=False, output_file=output)
        # The first agent call should use 300s (auto-scaled), not 120s
        first_call = mock_run_agent.call_args_list[0]
        agent_timeout = first_call[0][2]  # third positional arg is timeout
        self.assertGreaterEqual(agent_timeout, 300)

    @patch('ai_roundtable._orchestrator.run_agent')
    @patch('ai_roundtable._orchestrator.validate_agents', return_value=_make_mock_agents())
    def test_explicit_timeout_not_overridden(self, mock_validate, mock_run_agent):
        """User-specified timeout should not be auto-scaled."""
        mock_run_agent.return_value = self._ok_result("review")
        output = os.path.join(self.tmpdir, "test_output.md")
        run_roundtable(self.tmpdir, num_rounds=2, interactive=False,
                       output_file=output, timeout=60)
        first_call = mock_run_agent.call_args_list[0]
        agent_timeout = first_call[0][2]
        self.assertLessEqual(agent_timeout, 90)  # 60 * 1.5 max for codex


class TestAgentTimeoutMultiplier(unittest.TestCase):
    """Tests for per-agent timeout multipliers."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        Path(os.path.join(self.tmpdir, "main.py")).write_text("print('hello')")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _ok_result(self, text):
        return RunnerResult(ok=True, output=text, exit_code=0, error_type=None)

    @patch('ai_roundtable._orchestrator.run_agent')
    @patch('ai_roundtable._orchestrator.validate_agents', return_value=_make_mock_agents())
    def test_codex_gets_higher_timeout(self, mock_validate, mock_run_agent):
        """Codex agent should receive a multiplied timeout."""
        mock_run_agent.return_value = self._ok_result("review")
        output = os.path.join(self.tmpdir, "test_output.md")
        run_roundtable(self.tmpdir, num_rounds=2, interactive=False, output_file=output)
        # Claude (round 1) and Codex (round 2)
        claude_call = mock_run_agent.call_args_list[0]
        codex_call = mock_run_agent.call_args_list[1]
        claude_timeout = claude_call[0][2]
        codex_timeout = codex_call[0][2]
        self.assertGreater(codex_timeout, claude_timeout)


class TestProgressSidecar(unittest.TestCase):
    """Tests for incremental progress sidecar file."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        Path(os.path.join(self.tmpdir, "main.py")).write_text("print('hello')")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _ok_result(self, text):
        return RunnerResult(ok=True, output=text, exit_code=0, error_type=None)

    @patch('ai_roundtable._orchestrator.run_agent')
    @patch('ai_roundtable._orchestrator.validate_agents', return_value=_make_mock_agents())
    def test_progress_sidecar_cleaned_up(self, mock_validate, mock_run_agent):
        """Progress sidecar should be cleaned up after successful run."""
        mock_run_agent.return_value = self._ok_result("review")
        output = os.path.join(self.tmpdir, "test_output.md")
        run_roundtable(self.tmpdir, num_rounds=2, interactive=False, output_file=output)
        self.assertFalse(os.path.exists(output + ".progress"))


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

    @patch('ai_roundtable._orchestrator.run_agent')
    @patch('ai_roundtable._orchestrator.validate_agents', return_value=_make_mock_agents())
    @patch('ai_roundtable._orchestrator.scan_diff')
    def test_diff_mode_uses_scan_diff(self, mock_scan_diff, mock_validate, mock_run_agent):
        """When diff_target is set, should use scan_diff instead of scan_project."""
        mock_scan_diff.return_value = f"<{_PROJECT_DATA_TAG}>\ndiff content\n</{_PROJECT_DATA_TAG}>"
        mock_run_agent.return_value = self._ok_result("review")
        output = os.path.join(self.tmpdir, "test_output.md")
        result = run_roundtable(self.tmpdir, num_rounds=2, interactive=False,
                                output_file=output, diff_target="HEAD")
        mock_scan_diff.assert_called_once_with(self.tmpdir, "HEAD")
        self.assertIn("review", result)

    @patch('ai_roundtable._orchestrator.validate_agents')
    @patch('ai_roundtable._orchestrator.scan_diff')
    def test_diff_mode_no_changes_returns_early(self, mock_scan_diff, mock_validate):
        """When scan_diff returns None (no changes), should return early."""
        mock_scan_diff.return_value = None
        output = os.path.join(self.tmpdir, "test_output.md")
        result = run_roundtable(self.tmpdir, num_rounds=2, interactive=False,
                                output_file=output, diff_target="HEAD")
        self.assertEqual(result, "")


class TestVerboseFlag(unittest.TestCase):
    """Tests for --verbose flag passthrough."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        Path(os.path.join(self.tmpdir, "main.py")).write_text("print('hello')")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _ok_result(self, text):
        return RunnerResult(ok=True, output=text, exit_code=0, error_type=None)

    @patch('ai_roundtable._orchestrator.run_agent')
    @patch('ai_roundtable._orchestrator.validate_agents', return_value=_make_mock_agents())
    @patch('ai_roundtable._orchestrator.build_round_prompts')
    def test_verbose_passed_to_build_round_prompts(self, mock_prompts, mock_validate, mock_run_agent):
        """verbose=True should be passed to build_round_prompts."""
        from ai_roundtable._types import Round
        mock_prompts.return_value = [
            Round(agent="claude", label="Round 1 — Claude's Opening Review",
                  prompt="test prompt"),
            Round(agent="codex", label="Round 2 — Codex's Counter-Review",
                  prompt_template="test __PREV_RESPONSE__ __CONVERSATION_HISTORY__"),
        ]
        mock_run_agent.return_value = self._ok_result("review")
        output = os.path.join(self.tmpdir, "test_output.md")
        run_roundtable(self.tmpdir, num_rounds=2, interactive=False,
                       output_file=output, verbose=True)
        _, kwargs = mock_prompts.call_args
        self.assertTrue(kwargs.get('verbose', False))

    @patch('ai_roundtable._orchestrator.run_agent')
    @patch('ai_roundtable._orchestrator.validate_agents', return_value=_make_mock_agents())
    @patch('ai_roundtable._orchestrator.build_round_prompts')
    def test_compact_default_passed_to_build_round_prompts(self, mock_prompts, mock_validate, mock_run_agent):
        """Default (no verbose) should pass verbose=False to build_round_prompts."""
        from ai_roundtable._types import Round
        mock_prompts.return_value = [
            Round(agent="claude", label="Round 1 — Claude's Opening Review",
                  prompt="test prompt"),
            Round(agent="codex", label="Round 2 — Codex's Counter-Review",
                  prompt_template="test __PREV_RESPONSE__ __CONVERSATION_HISTORY__"),
        ]
        mock_run_agent.return_value = self._ok_result("review")
        output = os.path.join(self.tmpdir, "test_output.md")
        run_roundtable(self.tmpdir, num_rounds=2, interactive=False,
                       output_file=output)
        _, kwargs = mock_prompts.call_args
        self.assertFalse(kwargs.get('verbose', True))

    @patch('ai_roundtable._orchestrator.run_agent')
    @patch('ai_roundtable._orchestrator.validate_agents', return_value=_make_mock_agents())
    def test_compact_uses_smaller_response_budget(self, mock_validate, mock_run_agent):
        """Compact mode should truncate responses at COMPACT_MAX_RESPONSE_CHARS."""
        from ai_roundtable import COMPACT_MAX_RESPONSE_CHARS
        long_response = "x" * (COMPACT_MAX_RESPONSE_CHARS + 2000)
        mock_run_agent.side_effect = [
            RunnerResult(ok=True, output=long_response, exit_code=0, error_type=None),
            RunnerResult(ok=True, output="Codex review", exit_code=0, error_type=None),
        ]
        output = os.path.join(self.tmpdir, "test_output.md")
        run_roundtable(self.tmpdir, num_rounds=2, interactive=False, output_file=output)
        # The prompt passed to the second agent should have the response truncated
        second_call = mock_run_agent.call_args_list[1]
        prompt = second_call[0][0]
        self.assertNotIn(long_response, prompt)
        self.assertIn("response truncated for context budget", prompt)

    @patch('ai_roundtable._orchestrator.run_agent')
    @patch('ai_roundtable._orchestrator.validate_agents', return_value=_make_mock_agents())
    def test_verbose_uses_larger_response_budget(self, mock_validate, mock_run_agent):
        """Verbose mode should use the full MAX_RESPONSE_CHARS budget."""
        from ai_roundtable import MAX_RESPONSE_CHARS, COMPACT_MAX_RESPONSE_CHARS
        mid_response = "x" * (COMPACT_MAX_RESPONSE_CHARS + 2000)
        assert len(mid_response) < MAX_RESPONSE_CHARS, "Test assumes mid_response fits verbose budget"
        mock_run_agent.side_effect = [
            RunnerResult(ok=True, output=mid_response, exit_code=0, error_type=None),
            RunnerResult(ok=True, output="Codex review", exit_code=0, error_type=None),
        ]
        output = os.path.join(self.tmpdir, "test_output.md")
        run_roundtable(self.tmpdir, num_rounds=2, interactive=False,
                       output_file=output, verbose=True)
        second_call = mock_run_agent.call_args_list[1]
        prompt = second_call[0][0]
        self.assertNotIn("response truncated for context budget", prompt)


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

    @patch('ai_roundtable._orchestrator.run_agent')
    @patch('ai_roundtable._orchestrator.validate_agents', return_value=_make_mock_agents())
    def test_log_file_has_no_ansi(self, mock_validate, mock_run_agent):
        """Saved log files should not contain ANSI escape sequences."""
        mock_run_agent.side_effect = [
            self._ok_result("\x1b[31mRed review text\x1b[0m"),
            self._ok_result("\x1b[32mGreen counter\x1b[0m"),
        ]
        output = os.path.join(self.tmpdir, "test_output.md")
        run_roundtable(self.tmpdir, num_rounds=2, interactive=False, output_file=output)
        content = Path(output).read_text(encoding='utf-8')
        self.assertNotIn("\x1b", content)
        self.assertIn("Red review text", content)
        self.assertIn("Green counter", content)


class TestQuickMode(unittest.TestCase):
    """Tests for --quick mode."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        Path(os.path.join(self.tmpdir, "main.py")).write_text("print('hello')")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _ok_result(self, text):
        return RunnerResult(ok=True, output=text, exit_code=0, error_type=None)

    @patch('ai_roundtable._orchestrator.run_agent')
    @patch('ai_roundtable._orchestrator.validate_agents', return_value=_make_mock_agents())
    def test_quick_mode_log_contains_mode(self, mock_validate, mock_run_agent):
        """Quick mode should be noted in the log."""
        mock_run_agent.return_value = self._ok_result("review")
        output = os.path.join(self.tmpdir, "test_output.md")
        result = run_roundtable(self.tmpdir, num_rounds=2, interactive=False,
                                output_file=output, quick=True)
        self.assertIn("Quick", result)


class TestMultiAgent(unittest.TestCase):
    """Tests for multi-agent support."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        Path(os.path.join(self.tmpdir, "main.py")).write_text("print('hello')")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _ok_result(self, text):
        return RunnerResult(ok=True, output=text, exit_code=0, error_type=None)

    @patch('ai_roundtable._orchestrator.run_agent')
    @patch('ai_roundtable._orchestrator.validate_agents')
    def test_custom_agents_passed_through(self, mock_validate, mock_run_agent):
        """Custom agent specs should resolve and be used."""
        mock_agents = [
            AgentConfig(name="Claude", agent_key="claude", cmd=["claude", "-p", "-"],
                         color_code="\033[38;5;208m"),
            AgentConfig(name="Gemini", agent_key="gemini", cmd=["gemini", "-"],
                         color_code="\033[38;5;75m"),
        ]
        mock_validate.return_value = mock_agents
        mock_run_agent.return_value = self._ok_result("review")
        output = os.path.join(self.tmpdir, "test_output.md")
        result = run_roundtable(self.tmpdir, num_rounds=2, interactive=False,
                                output_file=output, agent_specs=["claude", "gemini"])
        self.assertIn("Claude", result)
        self.assertIn("Gemini", result)


class TestConflictAnalysis(unittest.TestCase):
    """Tests for post-discussion conflict analysis in the orchestrator."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        Path(os.path.join(self.tmpdir, "main.py")).write_text("print('hello')")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _ok_result(self, text):
        return RunnerResult(ok=True, output=text, exit_code=0, error_type=None)

    @patch('ai_roundtable._orchestrator.run_agent')
    @patch('ai_roundtable._orchestrator.validate_agents', return_value=_make_mock_agents())
    def test_conflict_analysis_in_log(self, mock_validate, mock_run_agent):
        """Log should contain conflict analysis when agents disagree."""
        mock_run_agent.side_effect = [
            self._ok_result("strengths:\n- good code\n\nconcerns:\n- sev: high\n  issue: bad security"),
            self._ok_result("agree:\n- good code\n\ndisagree:\n- security is actually fine\n\nmissed:\n- sev: H, issue: perf"),
        ]
        output = os.path.join(self.tmpdir, "test_output.md")
        result = run_roundtable(self.tmpdir, num_rounds=2, interactive=False, output_file=output)
        self.assertIn("Agreement Matrix", result)


if __name__ == "__main__":
    unittest.main()
