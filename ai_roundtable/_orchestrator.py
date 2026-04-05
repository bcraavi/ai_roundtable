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
from ._providers import resolve_agents, validate_agents, AgentConfig
from ._scanner import scan_project
from ._diff import scan_diff
from ._runners import run_agent, run_claude, run_codex
from ._history import build_history_summary
from ._prompts import build_round_prompts
from ._web_context import build_web_context, get_web_search_instruction
from ._interactive import get_user_input
from ._log import save_log
from ._analysis import classify_conflicts, detect_dissenting_opinions, build_conflict_summary, build_agreement_matrix


def run_roundtable(project_path: str, focus: str = "all", num_rounds: int = 4,
                   timeout: int = 120, interactive: bool = True, output_file: Optional[str] = None,
                   dry_run: bool = False, diff_target: Optional[str] = None,
                   verbose: bool = False, agent_specs: Optional[List[str]] = None,
                   quick: bool = False):
    """Run the full multi-agent roundtable discussion."""
    Colors._resolve()

    # Auto-disable interactive mode when stdin is not a TTY (CI, pipes)
    if interactive and not (hasattr(sys.stdin, "isatty") and sys.stdin.isatty()):
        interactive = False

    print_banner()

    # Resolve agent configuration
    agents = resolve_agents(agent_specs)
    agent_names = [a.name for a in agents]

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
    if not dry_run:
        agents = validate_agents(agents)

    # Build agent lookup by key
    agent_map = {}
    for a in agents:
        agent_map[a.name.lower().replace("/", "_").replace(" ", "_")] = a

    agent_display = ", ".join(a.name for a in agents)
    print(f"{Colors.DIM}Agents: {agent_display}{Colors.RESET}")
    if quick:
        print(f"{Colors.DIM}Quick mode: 2 rounds, non-interactive{Colors.RESET}")

    print_separator()

    # Build web context (always active — enriches prompts with current tech info)
    # Skip network fetches in dry-run mode to avoid unexpected outbound calls
    web_context = build_web_context(project_summary, offline=dry_run)

    # Select budgets based on verbose mode
    max_response = MAX_RESPONSE_CHARS if verbose else COMPACT_MAX_RESPONSE_CHARS
    max_history = MAX_HISTORY_CHARS if verbose else COMPACT_MAX_HISTORY_CHARS

    # Build prompts with agent names
    rounds = build_round_prompts(project_summary, focus, num_rounds,
                                 web_context=web_context, verbose=verbose,
                                 agent_names=agent_names)

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
    log.append(f"**Agents:** {agent_display}")
    log.append(f"**Rounds:** {len(rounds)}")
    if quick:
        log.append(f"**Mode:** Quick")
    log.append("")

    previous_response = ""
    conversation_history: List[dict] = []

    # Register SIGTERM handler for graceful shutdown in CI / process managers
    # Only register from the main thread (signal handlers can't be set from worker threads)
    _prev_sigterm = None
    sigterm_received = False

    def _exit_on_sigterm():
        if not sigterm_received:
            return
        print(f"\n\n{Colors.WARN}SIGTERM received! Saving partial discussion log...{Colors.RESET}")
        save_log(log, output_file, project_path, is_partial=True)
        raise SystemExit(143)  # 128 + 15 (SIGTERM)

    if threading.current_thread() is threading.main_thread():
        _prev_sigterm = signal.getsignal(signal.SIGTERM)
        def _sigterm_handler(signum, frame):
            nonlocal sigterm_received
            sigterm_received = True
        signal.signal(signal.SIGTERM, _sigterm_handler)

    try:
        for i, round_info in enumerate(rounds):
            _exit_on_sigterm()
            agent_key = round_info.agent
            label = round_info.label

            # Look up agent config
            agent_cfg = agent_map.get(agent_key)
            if agent_cfg is None:
                # Fallback: try to match by name prefix
                for cfg in agents:
                    if cfg.agent_key == agent_key or cfg.name.lower().startswith(agent_key):
                        agent_cfg = cfg
                        break

            agent_name = agent_cfg.name if agent_cfg else agent_key.capitalize()
            color = (agent_cfg.color_code if agent_cfg else Colors.DIM) or Colors.DIM

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
            search_instruction = get_web_search_instruction(agent_key)
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
                if agent_cfg:
                    return run_agent(prompt, project_path, t, agent_config=agent_cfg)
                # Legacy fallback for default agents without config
                if agent_key == "claude":
                    return run_claude(prompt, project_path, t)
                else:
                    return run_codex(prompt, project_path, t)

            result = _call_agent(timeout)

            # Retry once for transient failures (timeout, exception)
            if not result.ok and result.error_type in ("timeout", "exception", "empty_response"):
                retry_timeout = min(timeout * 2, 600)
                backoff = random.uniform(3, 7)
                print_warn(f"{agent_name} failed ({result.error_type}). Retrying in {backoff:.1f}s with {retry_timeout}s timeout...")
                time.sleep(backoff)
                _exit_on_sigterm()
                result = _call_agent(retry_timeout)

            _exit_on_sigterm()
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

    # Post-discussion analysis: conflict classification & agreement matrix
    if conversation_history and not dry_run:
        conflicts = classify_conflicts(conversation_history)
        dissents = detect_dissenting_opinions(conversation_history)
        conflict_summary = build_conflict_summary(conflicts, dissents)
        agreement_matrix = build_agreement_matrix(conversation_history)

        if conflict_summary:
            log.append(conflict_summary)
            print(f"\n{Colors.HEADER}--- Conflict Analysis ---{Colors.RESET}")
            print(conflict_summary)

        if agreement_matrix:
            log.append(agreement_matrix)
            print(agreement_matrix)

    # Save full discussion log
    log_content = save_log(log, output_file, project_path)
    print(f"\n{Colors.DIM}Roundtable complete!{Colors.RESET}\n")
    return log_content
