"""
Log persistence — saves discussion logs to disk.
"""

import os
from typing import List

from ._colors import Colors, print_warn


def save_log(log: List[str], output_file: str, project_path: str, is_partial: bool = False):
    """Save the discussion log to disk. Used for both normal and interrupt-safe saves."""
    log_content = "\n".join(log)
    if is_partial:
        log_content += "\n\n---\n*Discussion interrupted. Partial log saved.*\n"
    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(log_content)
        label = "Partial discussion" if is_partial else "Discussion"
        print(f"\n{Colors.HEADER}{'=' * 64}")
        print(f"  {label} saved to: {output_file}")
        print(f"{'=' * 64}{Colors.RESET}")

        # Suggest .gitignore entry
        gitignore = os.path.join(project_path, '.gitignore')
        if os.path.isdir(os.path.join(project_path, '.git')):
            has_entry = False
            if os.path.exists(gitignore):
                with open(gitignore, 'r', encoding='utf-8', errors='replace') as f:
                    has_entry = '.roundtable' in f.read()
            if not has_entry:
                print(f"{Colors.DIM}Tip: Add '.roundtable/' to your .gitignore{Colors.RESET}")
    except Exception as e:
        print_warn(f"Could not save log: {e}")
        print("\n--- FULL DISCUSSION LOG ---")
        print(log_content)
    return log_content
