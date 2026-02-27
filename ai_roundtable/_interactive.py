"""
Interactive mode — user input between rounds.
"""

from ._colors import Colors


def get_user_input(round_num: int) -> str:
    """Optionally let the user inject a question or direction."""
    print(f"\n{Colors.YOU}{Colors.BOLD}+-- YOUR TURN (optional){Colors.RESET}")
    print(f"{Colors.YOU}|{Colors.RESET} Type a question, redirect the discussion, or press Enter to skip.")
    print(f"{Colors.YOU}|{Colors.RESET} Type 'quit' to end the discussion early.")
    try:
        user_input = input(f"{Colors.YOU}| > {Colors.RESET}").strip()
    except (EOFError, KeyboardInterrupt):
        user_input = ""
    print(f"{Colors.YOU}+{'─' * 50}{Colors.RESET}")
    return user_input
