"""
Main orchestrator — runs the full multi-agent roundtable discussion.
"""

import os
import random
import signal
import sys
import tempfile
import threading
import time
from datetime import datetime
from typing import Optional, List

from ._constants import (
    MAX_RESPONSE_CHARS, MAX_PROMPT_CHARS,
    MAX_HISTORY_CHARS,
    COMPACT_MAX_RESPONSE_CHARS, COMPACT_MAX_HISTORY_CHARS,
    _PREV_RESPONSE, _CONVERSATION_HISTORY,
)
from ._types import RoundtableError
from ._colors import Colors, print_banner, print_separator, print_agent, print_warn, print_error
from ._sanitize import sanitize_project_content, sanitize_terminal_output, strip_sentinels, substitute_sentinels
from ._preflight import preflight_check
from ._scanner import scan_project
from ._diff import scan_diff
from ._runners import run_claude, run_codex
from ._history import build_history_summary
from ._prompts import build_round_prompts
from ._web_context import build_web_context, get_web_search_instruction
from ._interactive import get_user_input
from ._log import save_log


def run_roundtable(project_path: str, focus: str = "all", num_rounds: int = 4,
                   timeout: int = 120, interactive: bool = True, output_file: Optional[str] = None,
                   dry_run: bool = False, diff_target: Optional[str] = None,
                   verbose: bool = False):
    """Run the full multi-agent roundtable discussion."""
    Colors._resolve()

    # Auto-disable interactive mode when stdin is not a TTY (CI, pipes)
    if interactive and not (hasattr(sys.stdin, "isatty") and sys.stdin.isatty()):
        interactive = False

    print_banner()

    # Scan project first (diff mode can exit early without needing CLI tools)
    if diff_target is not None:
        print(f"{Colors.DIM}Scanning diff at: {project_path} (target: {diff_target}){Colors.RESET}")
        project_summary = scan_diff(project_path, diff_target)
        if project_summary is None:
            print(f"{Colors.DIM}No changes detected. Nothing to review.{Colors.RESET}")
            return ""
        print(f"{Colors.DIM}Found changes. Starting diff review...{Colors.RESET}")
    else:
        print(f"{Colors.DIM}Scanning project at: {project_path}{Colors.RESET}")
        project_summary = scan_project(project_path)
        print(f"{Colors.DIM}Found project files. Starting discussion...{Colors.RESET}")

    # Preflight: verify CLI tools are available (skip in dry-run mode)
    config = None
    if not dry_run:
        config = preflight_check()

    print_separator()

    # Build web context (always active — enriches prompts with current tech info)
    # Skip network fetches in dry-run mode to avoid unexpected outbound calls
    web_context = build_web_context(project_summary, offline=dry_run)

    # Select budgets based on verbose mode
    max_response = MAX_RESPONSE_CHARS if verbose else COMPACT_MAX_RESPONSE_CHARS
    max_history = MAX_HISTORY_CHARS if verbose else COMPACT_MAX_HISTORY_CHARS

    # Build prompts (web context is baked into each round's prompt)
    rounds = build_round_prompts(project_summary, focus, num_rounds,
                                 web_context=web_context, verbose=verbose)

    # Resolve output file path early so interrupt handler can use it.
    # Fall back to a temp directory if the project directory is not writable.
    if output_file is None:
        output_dir = os.path.join(project_path, ".roundtable")
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError:
            try:
                output_dir = os.path.join(tempfile.gettempdir(), "ai_roundtable")
                os.makedirs(output_dir, exist_ok=True)
                print_warn(f"Cannot write to project directory. Saving to: {output_dir}")
            except OSError:
                # Last resort: use tempfile.mkdtemp which finds a writable location
                output_dir = tempfile.mkdtemp(prefix="ai_roundtable_")
                print_warn(f"Cannot write to temp directory. Saving to: {output_dir}")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=4))
        output_file = os.path.join(output_dir, f"roundtable_{timestamp}_{suffix}.md")

    # Discussion log
    log = []
    log.append(f"# AI Roundtable Discussion")
    log.append(f"**Project:** {project_path}")
    log.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.append(f"**Focus:** {focus}")
    log.append(f"**Rounds:** {len(rounds)}")
    log.append("")

    previous_response = ""
    conversation_history: List[dict] = []

    # Register SIGTERM handler for graceful shutdown in CI / process managers
    # Only register from the main thread (signal handlers can't be set from worker threads)
    _prev_sigterm = None
    if threading.current_thread() is threading.main_thread():
        _prev_sigterm = signal.getsignal(signal.SIGTERM)
        def _sigterm_handler(signum, frame):
            print(f"\n\n{Colors.WARN}SIGTERM received! Saving partial discussion log...{Colors.RESET}")
            save_log(log, output_file, project_path, is_partial=True)
            sys.exit(143)  # 128 + 15 (SIGTERM)
        signal.signal(signal.SIGTERM, _sigterm_handler)

    try:
        for i, round_info in enumerate(rounds):
            agent = round_info.agent
            label = round_info.label
            agent_name = "Claude" if agent == "claude" else "Codex"
            color = Colors.CLAUDE if agent == "claude" else Colors.CODEX

            print(f"\n{Colors.HEADER}{'=' * 64}")
            print(f"  {label}")
            print(f"{'=' * 64}{Colors.RESET}")

            # Build prompt using single-pass sentinel substitution
            if round_info.prompt_template is not None:
                history_text = build_history_summary(
                    conversation_history, max_chars=max_history,
                    exclude_last=True, compact=not verbose
                )
                # Truncate previous response to prevent context blowups
                prev = previous_response
                if len(prev) > max_response:
                    prev = prev[:max_response] + "\n... (response truncated for context budget)"
                prompt = substitute_sentinels(round_info.prompt_template, {
                    _PREV_RESPONSE: prev,
                    _CONVERSATION_HISTORY: history_text or "(This is the first exchange.)",
                })
            else:
                prompt = round_info.prompt

            # Prepend agent-specific web search instruction
            search_instruction = get_web_search_instruction(agent)
            prompt = search_instruction + "\n\n" + prompt

            # Enforce global prompt budget
            if len(prompt) > MAX_PROMPT_CHARS:
                overage = len(prompt) - MAX_PROMPT_CHARS
                print_warn(f"Prompt exceeds budget by {overage} chars — trimming to {MAX_PROMPT_CHARS}.")
                prompt = prompt[:MAX_PROMPT_CHARS] + "\n... (prompt trimmed to fit context budget)"

            # Inject user input if interactive (sanitized to strip sentinel tokens)
            if interactive and i > 0:
                user_input = get_user_input(i)
                if user_input.lower() == 'quit':
                    print(f"\n{Colors.DIM}Ending discussion early.{Colors.RESET}")
                    break
                if user_input:
                    safe_input = sanitize_project_content(strip_sentinels(user_input))
                    prompt += f"\n\nADDITIONAL DIRECTION FROM THE DEVELOPER:\n{safe_input}"
                    # Re-enforce budget after user input append
                    if len(prompt) > MAX_PROMPT_CHARS:
                        prompt = prompt[:MAX_PROMPT_CHARS] + "\n... (prompt trimmed to fit context budget)"
                    log.append(f"## Developer Input (before {label})")
                    log.append(f"{safe_input}\n")
                    conversation_history.append({
                        "agent": "Developer",
                        "label": f"Developer direction before {label}",
                        "response": safe_input
                    })

            # Dry-run: print the prompt and skip the actual agent call
            if dry_run:
                budget_pct = len(prompt) * 100 // MAX_PROMPT_CHARS
                budget_warn = " [OVER BUDGET]" if len(prompt) > MAX_PROMPT_CHARS else ""
                print(f"\n{Colors.DIM}--- DRY-RUN PROMPT ({agent_name}, {len(prompt)} chars, {budget_pct}% of budget{budget_warn}) ---{Colors.RESET}")
                print(prompt[:2000])
                if len(prompt) > 2000:
                    print(f"\n{Colors.DIM}... ({len(prompt) - 2000} chars truncated){Colors.RESET}")
                print(f"{Colors.DIM}--- END DRY-RUN PROMPT ---{Colors.RESET}")
                log.append(f"## {label} (dry-run)")
                log.append(f"Prompt length: {len(prompt)} chars ({budget_pct}% of {MAX_PROMPT_CHARS} budget)\n")
                continue

            # Run the agent (with single retry for transient failures)
            print(f"{Colors.DIM}Waiting for {agent_name}...{Colors.RESET}")
            round_start = time.monotonic()

            def _call_agent(t):
                if agent == "claude":
                    return run_claude(prompt, project_path, t,
                                      cmd_path=config.claude_cmd if config else None)
                else:
                    return run_codex(prompt, project_path, t,
                                     cmd_path=config.codex_cmd if config else None)

            result = _call_agent(timeout)

            # Retry once for transient failures (timeout, exception)
            if not result.ok and result.error_type in ("timeout", "exception", "empty_response"):
                retry_timeout = min(timeout * 2, 600)
                backoff = 5
                print_warn(f"{agent_name} failed ({result.error_type}). Retrying in {backoff}s with {retry_timeout}s timeout...")
                time.sleep(backoff)
                result = _call_agent(retry_timeout)

            elapsed = time.monotonic() - round_start
            elapsed_str = f"{elapsed:.1f}s"
            print(f"{Colors.DIM}  ({agent_name} responded in {elapsed_str}){Colors.RESET}")

            # Check for error responses — thread failure context so next agent is aware
            if not result.ok:
                failure_msg = strip_sentinels(f"[AGENT FAILED: {result.error_type} — {result.output[:200]}]")
                print_error(f"{agent_name} failed this round: {result.output}")
                log.append(f"## {label} ({elapsed_str})")
                log.append(f"**[AGENT ERROR]** {sanitize_terminal_output(result.output)}\n")
                # Update previous_response so the next round's __PREV_RESPONSE__ reflects the failure
                previous_response = failure_msg
                conversation_history.append({
                    "agent": agent_name,
                    "label": label,
                    "response": failure_msg
                })
                continue

            response = result.output

            # Display
            print_agent(agent_name, color, response)
            previous_response = response

            # Track conversation history for context threading
            conversation_history.append({
                "agent": agent_name,
                "label": label,
                "response": response
            })

            # Log (sanitize ANSI before persisting to markdown)
            log.append(f"## {label} ({elapsed_str})")
            log.append(f"{sanitize_terminal_output(response)}\n")

    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARN}Interrupted! Saving partial discussion log...{Colors.RESET}")
        save_log(log, output_file, project_path, is_partial=True)
        print(f"\n{Colors.DIM}Roundtable interrupted.{Colors.RESET}\n")
        return "\n".join(log)

    finally:
        if _prev_sigterm is not None:
            signal.signal(signal.SIGTERM, _prev_sigterm)

    # Save full discussion log
    log_content = save_log(log, output_file, project_path)
    print(f"\n{Colors.DIM}Roundtable complete!{Colors.RESET}\n")
    return log_content
