"""
Terminal colors and styled output helpers.
"""

import os
import sys

from ._sanitize import sanitize_terminal_output


class Colors:
    # Respect NO_COLOR convention (https://no-color.org/) and non-TTY output.
    # Lazy-evaluated: call Colors._resolve() before first output so that
    # stdout redirection after import is handled correctly.
    _resolved = False
    _enabled = False
    CLAUDE = CODEX = YOU = HEADER = DIM = WARN = ERROR = RESET = BOLD = SEPARATOR = ""

    @classmethod
    def _resolve(cls):
        if cls._resolved:
            return
        cls._resolved = True
        cls._enabled = (
            "NO_COLOR" not in os.environ
            and hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
        )
        if cls._enabled:
            cls.CLAUDE = "\033[38;5;208m"   # Orange for Claude
            cls.CODEX = "\033[38;5;40m"      # Green for Codex
            cls.YOU = "\033[38;5;75m"         # Blue for You
            cls.HEADER = "\033[1;97m"         # Bold white
            cls.DIM = "\033[2m"               # Dim
            cls.WARN = "\033[38;5;214m"       # Yellow for warnings
            cls.ERROR = "\033[38;5;196m"      # Red for errors
            cls.RESET = "\033[0m"
            cls.BOLD = "\033[1m"
            cls.SEPARATOR = "\033[38;5;240m"


def print_banner():
    banner = f"""
{Colors.HEADER}+==============================================================+
|              AI ROUNDTABLE DISCUSSION                        |
|         Claude CLI  x  Codex CLI  x  You                     |
+==============================================================+{Colors.RESET}
"""
    print(banner)


def print_separator():
    print(f"{Colors.SEPARATOR}{'─' * 64}{Colors.RESET}")


def print_agent(name, color, message):
    """Pretty-print an agent's response."""
    safe_msg = sanitize_terminal_output(message)
    print(f"\n{color}{Colors.BOLD}+-- {name}{Colors.RESET}")
    for line in safe_msg.strip().split('\n'):
        print(f"{color}|{Colors.RESET} {line}")
    print(f"{color}+{'─' * 50}{Colors.RESET}\n")


def print_warn(message):
    print(f"{Colors.WARN}Warning: {sanitize_terminal_output(str(message))}{Colors.RESET}")


def print_error(message):
    print(f"{Colors.ERROR}Error: {sanitize_terminal_output(str(message))}{Colors.RESET}")
