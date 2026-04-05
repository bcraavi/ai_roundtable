"""
Interactive mode — user input between rounds.
"""

import select
import sys

from ._constants import INTERACTIVE_AUTO_CONTINUE_SECONDS
from ._colors import Colors


def get_user_input(round_num: int) -> str:
    """Optionally let the user inject a question or direction.

    Includes an auto-continue timeout so backgrounded or non-TTY processes
    don't hang indefinitely waiting for input that will never come.
    """
    timeout = INTERACTIVE_AUTO_CONTINUE_SECONDS
    print(f"\n{Colors.YOU}{Colors.BOLD}+-- YOUR TURN (optional){Colors.RESET}")
    print(f"{Colors.YOU}|{Colors.RESET} Type a question, redirect the discussion, or press Enter to skip.")
    print(f"{Colors.YOU}|{Colors.RESET} Type 'quit' to end the discussion early.")
    print(f"{Colors.YOU}|{Colors.RESET} {Colors.DIM}(auto-continues in {timeout}s){Colors.RESET}")
    try:
        # Use select() for timeout-aware input on Unix
        if hasattr(select, 'select') and hasattr(sys.stdin, 'fileno'):
            sys.stdout.write(f"{Colors.YOU}| > {Colors.RESET}")
            sys.stdout.flush()
            ready, _, _ = select.select([sys.stdin], [], [], timeout)
            if ready:
                user_input = sys.stdin.readline().strip()
            else:
                print(f"\n{Colors.DIM}  (auto-continuing){Colors.RESET}")
                user_input = ""
        else:
            # Fallback for platforms without select (Windows)
            user_input = input(f"{Colors.YOU}| > {Colors.RESET}").strip()
    except (EOFError, KeyboardInterrupt):
        user_input = ""
    except (OSError, ValueError):
        # select() can fail on non-selectable stdin (e.g., redirected)
        user_input = ""
    print(f"{Colors.YOU}+{'─' * 50}{Colors.RESET}")
    return user_input
