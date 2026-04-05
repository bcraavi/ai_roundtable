"""Tests for CLI runners with mocked subprocess."""

import os
import queue
import threading
import time
import unittest
from unittest.mock import patch, MagicMock

from ai_roundtable import (
    run_claude,
    run_codex,
    _run_cli_streaming,
    RunnerResult,
    MAX_OUTPUT_CHARS,
    CLAUDE_CMD,
    CLAUDE_FLAGS,
    CODEX_CMD,
    CODEX_FLAGS,
)


class TestCLIRunners(unittest.TestCase):
    """Integration tests for CLI runners with mocked subprocess (Popen-based)."""

    def _mock_popen_proc(self, stdout="Agent response", stderr="", returncode=0):
        """Create a mock Popen process with readable stdout/stderr for bounded drain."""
        proc = MagicMock()
        proc.stdin = MagicMock()

        stdout_mock = MagicMock()
        stdout_mock.read.side_effect = [stdout, ""] if stdout else [""]
        stdout_mock.closed = False
        proc.stdout = stdout_mock

        stderr_mock = MagicMock()
        stderr_mock.read.side_effect = [stderr, ""] if stderr else [""]
        stderr_mock.closed = False
        proc.stderr = stderr_mock

        proc.returncode = returncode
        proc.poll.return_value = returncode
        proc.wait.return_value = returncode
        return proc

    @patch('ai_roundtable._runners.subprocess.Popen')
    def test_run_claude_command_structure(self, mock_popen):
        """Verify Claude CLI is invoked with correct command and stdin."""
        mock_popen.return_value = self._mock_popen_proc(stdout="Claude says hi")
        result = run_claude("test prompt", "/tmp/project", timeout=60)

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        self.assertEqual(cmd, [CLAUDE_CMD] + CLAUDE_FLAGS + ["-"])
        self.assertIsInstance(result, RunnerResult)
        self.assertTrue(result.ok)
        self.assertEqual(result.output, "Claude says hi")
        self.assertIsNone(result.error_type)

    @patch('ai_roundtable._runners.subprocess.Popen')
    def test_run_codex_command_structure(self, mock_popen):
        """Verify Codex CLI is invoked with correct command and stdin."""
        mock_popen.return_value = self._mock_popen_proc(stdout="Codex says hi")
        result = run_codex("test prompt", "/tmp/project", timeout=90)

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        self.assertEqual(cmd, [CODEX_CMD, "exec"] + CODEX_FLAGS + ["-"])
        self.assertTrue(result.ok)
        self.assertEqual(result.output, "Codex says hi")

    @patch('ai_roundtable._runners.subprocess.Popen')
    def test_run_claude_nonzero_exit_with_output(self, mock_popen):
        """Non-zero exit with stdout should warn but return output as ok."""
        mock_popen.return_value = self._mock_popen_proc(
            stdout="Partial output", stderr="some warning", returncode=1
        )
        result = run_claude("prompt", "/tmp/project")
        self.assertTrue(result.ok)
        self.assertEqual(result.output, "Partial output")

    @patch('ai_roundtable._runners.subprocess.Popen')
    def test_run_claude_nonzero_exit_no_output(self, mock_popen):
        """Non-zero exit without stdout should return structured error."""
        mock_popen.return_value = self._mock_popen_proc(
            stdout="", stderr="fatal error", returncode=1
        )
        result = run_claude("prompt", "/tmp/project")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_type, "exit_error")
        self.assertIn("fatal error", result.output)
        self.assertEqual(result.exit_code, 1)

    @patch('ai_roundtable._runners.subprocess.Popen')
    def test_run_codex_timeout(self, mock_popen):
        """Timeout should return structured timeout error."""
        import subprocess
        proc = self._mock_popen_proc()
        proc.wait.side_effect = subprocess.TimeoutExpired(cmd="codex", timeout=120)
        proc.poll.return_value = None  # process still running
        mock_popen.return_value = proc
        result = run_codex("prompt", "/tmp/project")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_type, "timeout")
        self.assertIn("timed out", result.output)
        self.assertIsNone(result.exit_code)

    @patch('ai_roundtable._runners.subprocess.Popen')
    def test_run_claude_not_found(self, mock_popen):
        """Missing binary should return structured not_found error."""
        mock_popen.side_effect = FileNotFoundError()
        result = run_claude("prompt", "/tmp/project")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_type, "not_found")
        self.assertIn("not found", result.output)

    @patch('ai_roundtable._runners.subprocess.Popen')
    def test_run_claude_strips_claudecode_env(self, mock_popen):
        """CLAUDECODE should be removed from env to allow nesting."""
        mock_popen.return_value = self._mock_popen_proc()
        with patch.dict(os.environ, {"CLAUDECODE": "1"}):
            run_claude("prompt", "/tmp/project")
        call_kwargs = mock_popen.call_args[1]
        env = call_kwargs.get('env')
        self.assertIsNotNone(env)
        self.assertNotIn("CLAUDECODE", env)

    @patch('ai_roundtable._runners.subprocess.Popen')
    def test_run_codex_no_env_mutation(self, mock_popen):
        """Codex runner should not pass custom env (uses system default)."""
        mock_popen.return_value = self._mock_popen_proc()
        run_codex("prompt", "/tmp/project")
        call_kwargs = mock_popen.call_args[1]
        self.assertIsNone(call_kwargs.get('env'))

    @patch('ai_roundtable._runners.subprocess.Popen')
    def test_runner_result_exception(self, mock_popen):
        """Generic exception should return structured error."""
        mock_popen.side_effect = OSError("pipe broken")
        result = run_claude("prompt", "/tmp/project")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_type, "exception")
        self.assertIn("pipe broken", result.output)

    @patch('ai_roundtable._runners.subprocess.Popen')
    def test_nonstream_output_bounded(self, mock_popen):
        """Non-stream Popen path should enforce MAX_OUTPUT_CHARS during read."""
        huge_output = "x" * (MAX_OUTPUT_CHARS + 10000)
        mock_popen.return_value = self._mock_popen_proc(stdout=huge_output)
        result = run_claude("prompt", "/tmp/project")
        self.assertTrue(result.ok)
        self.assertLessEqual(len(result.output), MAX_OUTPUT_CHARS)

    @patch('ai_roundtable._runners.subprocess.Popen')
    def test_run_claude_empty_response_exit0(self, mock_popen):
        """Exit code 0 with empty stdout should return empty_response error type."""
        mock_popen.return_value = self._mock_popen_proc(stdout="", returncode=0)
        result = run_claude("prompt", "/tmp/project")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_type, "empty_response")
        self.assertIn("No response", result.output)

    @patch('ai_roundtable._runners.subprocess.Popen')
    def test_run_claude_strips_claude_code_entrypoint_env(self, mock_popen):
        """CLAUDE_CODE_ENTRYPOINT should be removed from env to allow nesting."""
        mock_popen.return_value = self._mock_popen_proc()
        with patch.dict(os.environ, {"CLAUDE_CODE_ENTRYPOINT": "cli"}):
            run_claude("prompt", "/tmp/project")
        call_kwargs = mock_popen.call_args[1]
        env = call_kwargs.get('env')
        self.assertIsNotNone(env)
        self.assertNotIn("CLAUDE_CODE_ENTRYPOINT", env)

    @patch('ai_roundtable._runners.subprocess.Popen')
    def test_run_claude_uses_file_stdin(self, mock_popen):
        """Claude runner should pass a file object (not PIPE) as stdin."""
        mock_popen.return_value = self._mock_popen_proc()
        run_claude("test prompt", "/tmp/project")
        call_kwargs = mock_popen.call_args[1]
        # stdin should NOT be subprocess.PIPE when using file-based delivery
        import subprocess
        self.assertNotEqual(call_kwargs.get('stdin'), subprocess.PIPE)

    @patch('ai_roundtable._runners.subprocess.Popen')
    def test_nonstream_kills_on_cap(self, mock_popen):
        """Process should be killed when output exceeds cap to prevent pipe deadlock."""
        huge_output = "x" * (MAX_OUTPUT_CHARS + 10000)
        proc = self._mock_popen_proc(stdout=huge_output)
        proc.poll.return_value = None  # process still running
        mock_popen.return_value = proc
        result = run_claude("prompt", "/tmp/project")
        proc.kill.assert_called()

    @patch('ai_roundtable._runners.os.unlink')
    @patch('ai_roundtable._runners.subprocess.Popen')
    def test_nonstream_unlinks_prompt_after_wait(self, mock_popen, mock_unlink):
        """Prompt temp file should be unlinked only after the subprocess is reaped."""
        proc = self._mock_popen_proc(stdout="Claude says hi")
        events = []

        def _wait(*args, **kwargs):
            events.append("wait")
            return proc.returncode

        proc.wait.side_effect = _wait
        mock_popen.return_value = proc
        mock_unlink.side_effect = lambda path: events.append("unlink")

        result = run_claude("prompt", "/tmp/project")

        self.assertTrue(result.ok)
        self.assertIn("wait", events)
        self.assertIn("unlink", events)
        self.assertLess(events.index("wait"), events.index("unlink"))

    @patch('ai_roundtable._runners.subprocess.Popen')
    def test_empty_response_sanitizes_stderr_detail(self, mock_popen):
        """Empty-response stderr detail should be sanitized before embedding."""
        mock_popen.return_value = self._mock_popen_proc(
            stdout="", stderr="\x1b[31mfatal\x1b[0m", returncode=0
        )

        result = run_claude("prompt", "/tmp/project")

        self.assertFalse(result.ok)
        self.assertEqual(result.error_type, "empty_response")
        self.assertIn("fatal", result.output)
        self.assertNotIn("\x1b", result.output)


class TestRunCliStreaming(unittest.TestCase):
    """Tests for the streaming subprocess runner."""

    def _make_mock_proc(self, stdout_chunks, stderr_text="", returncode=0):
        """Create a mock Popen process with readable stdout/stderr pipes.

        stdout_chunks: list of strings returned by successive read(4096) calls.
        The last call returns '' to signal EOF.
        """
        proc = MagicMock()
        proc.stdin = MagicMock()
        # stdout/stderr use .read(N) for chunk-based draining
        stdout_mock = MagicMock()
        stdout_mock.read.side_effect = list(stdout_chunks) + [""]
        stdout_mock.closed = False
        proc.stdout = stdout_mock
        stderr_mock = MagicMock()
        stderr_mock.read.side_effect = ([stderr_text] + [""]) if stderr_text else [""]
        stderr_mock.closed = False
        proc.stderr = stderr_mock
        proc.returncode = returncode
        proc.poll.return_value = returncode
        proc.wait.return_value = returncode
        return proc

    @patch('ai_roundtable._runners.subprocess.Popen')
    @patch('ai_roundtable._runners.sys.stdout')
    def test_streaming_normal_completion(self, mock_stdout_stream, mock_popen):
        """Normal streaming should collect all chunks and return ok."""
        proc = self._make_mock_proc(["line 1\nline 2\n"])
        mock_popen.return_value = proc
        mock_stdout_stream.isatty.return_value = True
        result = _run_cli_streaming(
            ["test-cmd"], "prompt", "/tmp", timeout=30, agent_name="TestAgent"
        )
        self.assertTrue(result.ok)
        self.assertIn("line 1", result.output)
        self.assertIn("line 2", result.output)

    @patch('ai_roundtable._runners.subprocess.Popen')
    @patch('ai_roundtable._runners.sys.stdout')
    def test_streaming_no_output(self, mock_stdout_stream, mock_popen):
        """Empty output with exit code 0 should return empty_response error."""
        proc = self._make_mock_proc([])
        mock_popen.return_value = proc
        mock_stdout_stream.isatty.return_value = True
        result = _run_cli_streaming(
            ["test-cmd"], "prompt", "/tmp", timeout=30, agent_name="TestAgent"
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error_type, "empty_response")

    @patch('ai_roundtable._runners.subprocess.Popen')
    @patch('ai_roundtable._runners.sys.stdout')
    def test_streaming_nonzero_exit_with_output(self, mock_stdout_stream, mock_popen):
        """Non-zero exit with output should still return ok."""
        proc = self._make_mock_proc(["output\n"], stderr_text="warning\n", returncode=1)
        mock_popen.return_value = proc
        mock_stdout_stream.isatty.return_value = True
        result = _run_cli_streaming(
            ["test-cmd"], "prompt", "/tmp", timeout=30, agent_name="TestAgent"
        )
        self.assertTrue(result.ok)
        self.assertIn("output", result.output)

    @patch('ai_roundtable._runners.os.unlink')
    @patch('ai_roundtable._runners.subprocess.Popen')
    @patch('ai_roundtable._runners.sys.stdout')
    def test_streaming_unlinks_prompt_after_wait(self, mock_stdout_stream, mock_popen, mock_unlink):
        """Streaming runner should keep the prompt file until the subprocess is reaped."""
        proc = self._make_mock_proc(["output\n"])
        events = []

        def _wait(*args, **kwargs):
            events.append("wait")
            return proc.returncode

        proc.wait.side_effect = _wait
        mock_popen.return_value = proc
        mock_stdout_stream.isatty.return_value = True
        mock_unlink.side_effect = lambda path: events.append("unlink")

        result = _run_cli_streaming(
            ["test-cmd"], "prompt", "/tmp", timeout=30, agent_name="TestAgent"
        )

        self.assertTrue(result.ok)
        self.assertIn("wait", events)
        self.assertIn("unlink", events)
        self.assertLess(events.index("wait"), events.index("unlink"))

    @patch('ai_roundtable._runners.subprocess.Popen')
    @patch('ai_roundtable._runners.sys.stdout')
    def test_streaming_file_not_found(self, mock_stdout_stream, mock_popen):
        """Missing command should return not_found error."""
        mock_popen.side_effect = FileNotFoundError()
        mock_stdout_stream.isatty.return_value = True
        result = _run_cli_streaming(
            ["missing-cmd"], "prompt", "/tmp", timeout=30, agent_name="TestAgent"
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error_type, "not_found")

    @patch('ai_roundtable._runners.subprocess.Popen')
    @patch('ai_roundtable._runners.sys.stdout')
    def test_streaming_timeout(self, mock_stdout_stream, mock_popen):
        """Timeout should kill process and return timeout error."""
        # Simulate a process that hangs: stdout.read() blocks
        block_event = threading.Event()
        def slow_read(n):
            if not hasattr(slow_read, '_called'):
                slow_read._called = True
                return "first chunk\n"
            block_event.wait(timeout=5)  # simulate hang
            return ""
        proc = self._make_mock_proc([])  # placeholder
        proc.stdout.read = slow_read
        mock_popen.return_value = proc
        mock_stdout_stream.isatty.return_value = True
        result = _run_cli_streaming(
            ["test-cmd"], "prompt", "/tmp", timeout=1, agent_name="TestAgent"
        )
        block_event.set()  # unblock the thread
        self.assertFalse(result.ok)
        self.assertEqual(result.error_type, "timeout")


if __name__ == "__main__":
    unittest.main()
