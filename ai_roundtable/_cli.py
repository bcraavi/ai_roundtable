"""
CLI entry point — argparse-based command-line interface.
"""

import os
import sys
import argparse
import textwrap

from ._constants import __version__
from ._types import RoundtableError
from ._colors import Colors, print_error, print_warn
from ._diff import validate_diff_target
from ._orchestrator import run_roundtable


def main():
    Colors._resolve()

    parser = argparse.ArgumentParser(
        description="AI Roundtable — Multi-agent project review with pluggable AI agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              ai-roundtable ./my-webapp
              ai-roundtable ./my-webapp --focus architecture
              ai-roundtable ./my-webapp --rounds 6 --timeout 180
              ai-roundtable ./my-webapp --no-interactive
              ai-roundtable ./my-webapp --diff
              ai-roundtable ./my-webapp --diff main
              ai-roundtable ./my-webapp --quick
              ai-roundtable ./my-webapp --agents claude gemini
              ai-roundtable ./my-webapp --agents claude codex gemini

            Agent specs (--agents):
              claude, codex, gemini     Built-in providers
              opencode, aider, q        More built-in providers
              copilot                   GitHub Copilot (via gh)
              ollama:codellama          Ollama with specific model
              any-cli-tool              Generic CLI that reads stdin

            Round counts: minimum 2. Odd values mean the last round is
            always the first agent. Use even values for a balanced debate.
        """)
    )
    parser.add_argument("project_path", help="Path to your project directory")
    parser.add_argument("--focus", choices=["architecture", "code_quality", "performance", "security", "all"],
                        default="all", help="Focus area for the review (default: all)")
    parser.add_argument("--rounds", type=int, default=4,
                        help="Number of discussion rounds (min: 2, default: 4). Even values recommended.")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout per agent call in seconds (default: 120)")
    parser.add_argument("--no-interactive", action="store_true", help="Disable interactive mode (no user input between rounds)")
    parser.add_argument("--output", type=str, default=None, help="Output file path for discussion log")
    parser.add_argument("--dry-run", action="store_true", help="Show generated prompts without calling CLI agents")
    parser.add_argument("--diff", type=str, nargs="?", const="HEAD", default=None,
                        metavar="TARGET",
                        help="Review only changed files (diff mode). TARGET can be HEAD (default), a branch name, or HEAD~N.")
    parser.add_argument("--verbose", action="store_true",
                        help="Use verbose prose output (default: compact structured format for inter-agent efficiency)")
    parser.add_argument("--quick", action="store_true",
                        help="Quick mode: 2 rounds, non-interactive, skip deep debate (best for trivial changes)")
    parser.add_argument("--agents", nargs="+", default=None, metavar="AGENT",
                        help="Agent specs to use (default: claude codex). Examples: claude codex gemini ollama:codellama")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    args = parser.parse_args()

    # Validate timeout
    if args.timeout <= 0:
        print_error("--timeout must be a positive integer.")
        sys.exit(1)

    # Validate diff target (reject flag-like or malformed refs)
    if args.diff is not None:
        try:
            validate_diff_target(args.diff)
        except RoundtableError as e:
            print_error(str(e))
            sys.exit(1)

    # Quick mode overrides
    if args.quick:
        num_rounds = 2
        interactive = False
    else:
        num_rounds = max(2, args.rounds)
        interactive = not args.no_interactive

    if not args.quick and args.rounds < 2:
        print_warn(f"--rounds must be at least 2. Using {num_rounds}.")

    try:
        run_roundtable(
            project_path=os.path.abspath(args.project_path),
            focus=args.focus,
            num_rounds=num_rounds,
            timeout=args.timeout,
            interactive=interactive,
            output_file=args.output,
            dry_run=args.dry_run,
            diff_target=args.diff,
            verbose=args.verbose,
            agent_specs=args.agents,
            quick=args.quick,
        )
    except RoundtableError as e:
        print_error(str(e))
        sys.exit(1)
