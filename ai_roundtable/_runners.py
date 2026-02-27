"""
CLI runners — subprocess-based agent invocation with streaming and bounded output.
"""

import os
import queue
import subprocess
import sys
import threading
import tempfile
import time
from typing import Optional, List

from ._constants import (
    CLAUDE_CMD, CODEX_CMD, CODEX_SUBCMD,
    CLAUDE_FLAGS, CODEX_FLAGS,
    MAX_OUTPUT_CHARS,
)
from ._types import RunnerResult
from ._sanitize import sanitize_terminal_output
from ._colors import Colors, print_warn


def _run_cli(cmd: List[str], prompt: str, project_path: str, timeout: int,
             agent_name: str, env: Optional[dict] = None,
             stream: bool = False) -> RunnerResult:
    """Shared runner for CLI agents. Sends prompt via stdin and returns a structured result.

    When stream=True, prints stdout lines as they arrive (streaming UX).
    Output is bounded to MAX_OUTPUT_CHARS characters to prevent OOM.
    """
    try:
        if stream and sys.stdout.isatty():
            return _run_cli_streaming(cmd, prompt, project_path, timeout, agent_name, env)
        # Non-streaming: bounded Popen reads (prevents OOM from runaway output).
        # Use temp file for stdin to avoid pipe buffer issues with large prompts
        # (see https://github.com/anthropics/claude-code/issues/7263).
        prompt_fd, prompt_path = tempfile.mkstemp(suffix='.txt', prefix='rt_prompt_')
        try:
            with os.fdopen(prompt_fd, 'w') as f:
                f.write(prompt)
            with open(prompt_path, 'r') as prompt_file:
                try:
                    proc = subprocess.Popen(
                        cmd,
                        stdin=prompt_file,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        cwd=project_path,
                        env=env,
                    )
                except FileNotFoundError:
                    return RunnerResult(ok=False,
                        output=f"'{cmd[0]}' not found. Is {agent_name} CLI installed and in PATH?",
                        exit_code=None, error_type="not_found")
        except Exception:
            try:
                os.unlink(prompt_path)
            except OSError:
                pass
            raise
        try:
            os.unlink(prompt_path)
        except OSError:
            pass

        # Drain stdout/stderr concurrently with hard char cap.
        # When cap is hit, kill the process to prevent pipe deadlock
        # (child blocked on writes after reader stops).
        stdout_chunks: List[str] = []
        stderr_chunks: List[str] = []

        def _drain_bounded(stream, chunks):
            total = 0
            try:
                while True:
                    data = stream.read(4096)
                    if not data:
                        break
                    remaining = MAX_OUTPUT_CHARS - total
                    if remaining <= 0:
                        try:
                            if proc.poll() is None:
                                proc.kill()
                        except OSError:
                            pass
                        break
                    if len(data) > remaining:
                        chunks.append(data[:remaining])
                        try:
                            if proc.poll() is None:
                                proc.kill()
                        except OSError:
                            pass
                        break
                    chunks.append(data)
                    total += len(data)
            except (OSError, ValueError):
                pass

        try:
            out_t = threading.Thread(target=_drain_bounded, args=(proc.stdout, stdout_chunks), daemon=True)
            err_t = threading.Thread(target=_drain_bounded, args=(proc.stderr, stderr_chunks), daemon=True)
            out_t.start()
            err_t.start()

            timed_out = False
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                if proc.poll() is None:
                    try:
                        proc.kill()
                    except OSError:
                        pass

            out_t.join(timeout=2 if timed_out else 30)
            err_t.join(timeout=2 if timed_out else 30)

            if timed_out:
                return RunnerResult(ok=False, output=f"{agent_name} CLI timed out — try increasing --timeout",
                                    exit_code=None, error_type="timeout")

            stdout = "".join(stdout_chunks).strip()
            stderr = "".join(stderr_chunks).strip()

            if proc.returncode != 0:
                if stderr:
                    print_warn(f"{agent_name} CLI exited with code {proc.returncode}: {sanitize_terminal_output(stderr[:200])}")
                if not stdout:
                    return RunnerResult(
                        ok=False, output=f"{agent_name} exited with code {proc.returncode}: {sanitize_terminal_output(stderr) or 'No output'}",
                        exit_code=proc.returncode, error_type="exit_error"
                    )
                print_warn(f"{agent_name} CLI exited with code {proc.returncode} but produced output; using it.")
            if not stdout:
                err_detail = f": {stderr[:200]}" if stderr else ""
                etype = "empty_response" if (proc.returncode or 0) == 0 else "exit_error"
                return RunnerResult(ok=False, output=f"No response from {agent_name}{err_detail}",
                                    exit_code=proc.returncode, error_type=etype)
            return RunnerResult(ok=True, output=stdout, exit_code=proc.returncode, error_type=None)
        finally:
            # Ensure process is reaped and pipes closed (matches streaming path)
            try:
                if proc.poll() is None:
                    proc.kill()
            except OSError:
                pass
            for pipe in (proc.stdout, proc.stderr):
                try:
                    if pipe and not pipe.closed:
                        pipe.close()
                except OSError:
                    pass
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
    except Exception as e:
        return RunnerResult(ok=False, output=f"{agent_name} error: {str(e)}",
                            exit_code=None, error_type="exception")


def _run_cli_streaming(cmd: List[str], prompt: str, project_path: str, timeout: int,
                       agent_name: str, env: Optional[dict] = None) -> RunnerResult:
    """Streaming variant: reads stdout line-by-line and prints as received.

    Uses background threads for both stdout and stderr draining, with a
    queue-based reader for stdout. This prevents:
    - Pipe deadlock: stderr and stdout are drained concurrently
    - Silent stalls: timeout is checked via queue.get(), not between lines
    - Cap-break deadlock: process is killed before joining threads
    """
    proc = None
    try:
        # Use temp file for stdin to avoid pipe buffer issues with large prompts
        prompt_fd, prompt_path = tempfile.mkstemp(suffix='.txt', prefix='rt_prompt_')
        try:
            with os.fdopen(prompt_fd, 'w') as f:
                f.write(prompt)
            with open(prompt_path, 'r') as prompt_file:
                try:
                    proc = subprocess.Popen(
                        cmd,
                        stdin=prompt_file,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        cwd=project_path,
                        env=env,
                    )
                except FileNotFoundError:
                    return RunnerResult(ok=False,
                        output=f"'{cmd[0]}' not found. Is {agent_name} CLI installed and in PATH?",
                        exit_code=None, error_type="not_found")
        except Exception:
            try:
                os.unlink(prompt_path)
            except OSError:
                pass
            raise
        try:
            os.unlink(prompt_path)
        except OSError:
            pass

        # Queue-based stdout reader thread — enables deadline-aware timeout.
        # Uses chunk-based reads (read(4096)) instead of line iteration to
        # prevent deadlock when a process emits long output without newlines.
        stdout_queue = queue.Queue()
        _SENTINEL = None  # marks end-of-stream

        def _drain_stdout():
            try:
                while True:
                    chunk = proc.stdout.read(4096)
                    if not chunk:
                        break
                    stdout_queue.put(chunk)
            except (OSError, ValueError):
                pass
            finally:
                stdout_queue.put(_SENTINEL)

        # Drain stderr in a background thread to prevent pipe deadlock.
        # Uses chunk-based reads matching stdout for consistency.
        # Kill process on cap to prevent stall from blocked pipe writes.
        stderr_chunks: List[str] = []
        def _drain_stderr():
            stderr_total = 0
            try:
                while True:
                    chunk = proc.stderr.read(4096)
                    if not chunk:
                        break
                    stderr_chunks.append(chunk)
                    stderr_total += len(chunk)
                    if stderr_total > MAX_OUTPUT_CHARS:
                        try:
                            if proc.poll() is None:
                                proc.kill()
                        except OSError:
                            pass
                        break
            except (OSError, ValueError):
                pass

        stdout_thread = threading.Thread(target=_drain_stdout, daemon=True)
        stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
        stdout_thread.start()
        stderr_thread.start()

        chunks = []
        total_chars = 0
        deadline = time.monotonic() + timeout
        capped = False
        timed_out = False

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            try:
                chunk = stdout_queue.get(timeout=min(remaining, 1.0))
            except queue.Empty:
                continue  # re-check deadline
            if chunk is _SENTINEL:
                break  # stdout exhausted

            total_chars += len(chunk)
            if total_chars > MAX_OUTPUT_CHARS:
                capped = True
                break
            chunks.append(chunk)
            # Print sanitized streaming chunk (prevents terminal injection)
            safe_chunk = sanitize_terminal_output(chunk)
            sys.stdout.write(f"{Colors.DIM}  {safe_chunk}{Colors.RESET}")
            sys.stdout.flush()

        if capped:
            print_warn(f"{agent_name} output exceeded {MAX_OUTPUT_CHARS} chars — truncated.")

        # Kill process before joining threads to prevent deadlock on cap/timeout
        if capped or timed_out:
            try:
                if proc.poll() is None:
                    proc.kill()
            except OSError:
                pass

        if timed_out:
            stdout_thread.join(timeout=2)
            stderr_thread.join(timeout=2)
            return RunnerResult(ok=False, output=f"{agent_name} CLI timed out — try increasing --timeout",
                                exit_code=None, error_type="timeout")

        stdout_thread.join(timeout=30)
        stderr_thread.join(timeout=30)
        stderr = "".join(stderr_chunks)

        proc.wait(timeout=10)
        stdout = "".join(chunks).strip()
        returncode = proc.returncode or 0

        if returncode != 0:
            if stderr.strip():
                print_warn(f"{agent_name} CLI exited with code {returncode}: {sanitize_terminal_output(stderr.strip()[:200])}")
            if not stdout:
                return RunnerResult(ok=False, output=f"{agent_name} exited with code {returncode}: {sanitize_terminal_output(stderr.strip()) or 'No output'}",
                                    exit_code=returncode, error_type="exit_error")
        if not stdout:
            err_detail = f": {stderr.strip()[:200]}" if stderr.strip() else ""
            etype = "empty_response" if returncode == 0 else "exit_error"
            return RunnerResult(ok=False, output=f"No response from {agent_name}{err_detail}",
                                exit_code=returncode, error_type=etype)
        return RunnerResult(ok=True, output=stdout, exit_code=returncode, error_type=None)
    except Exception as e:
        return RunnerResult(ok=False, output=f"{agent_name} error: {str(e)}",
                            exit_code=None, error_type="exception")
    finally:
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.kill()
            except OSError:
                pass
            for pipe in (proc.stdout, proc.stderr, proc.stdin):
                try:
                    if pipe and not pipe.closed:
                        pipe.close()
                except OSError:
                    pass
            try:
                proc.wait(timeout=5)
            except Exception:
                pass


def run_claude(prompt: str, project_path: str, timeout: int = 120,
               cmd_path: Optional[str] = None) -> RunnerResult:
    """Run Claude CLI with prompt via stdin and return a structured result."""
    claude = cmd_path or CLAUDE_CMD
    cmd = [claude] + CLAUDE_FLAGS + ["-"]
    env = os.environ.copy()
    # CLAUDECODE is set by Claude Code when running inside a session.
    # Removing it allows nested claude CLI invocations (e.g., when this
    # tool is launched from within a Claude Code terminal).
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)
    return _run_cli(cmd, prompt, project_path, timeout, "Claude", env=env, stream=True)


def run_codex(prompt: str, project_path: str, timeout: int = 120,
              cmd_path: Optional[str] = None) -> RunnerResult:
    """Run Codex CLI with prompt via stdin and return a structured result.

    Codex exec accepts '-' as the prompt argument to read from stdin,
    which avoids ARG_MAX limits on large prompts.
    """
    codex = cmd_path or CODEX_CMD
    cmd = [codex, CODEX_SUBCMD] + CODEX_FLAGS + ["-"]
    return _run_cli(cmd, prompt, project_path, timeout, "Codex", stream=True)
