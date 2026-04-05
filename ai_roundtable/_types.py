"""
Core data types — error class, config, result, and round structures.
"""

from dataclasses import dataclass
from typing import Optional


class RoundtableError(Exception):
    """Raised for recoverable errors in roundtable operations."""
    pass


@dataclass(frozen=True)
class RuntimeConfig:
    """Resolved CLI paths from preflight check. Immutable after creation."""
    claude_cmd: str   # Absolute path to Claude CLI binary
    codex_cmd: str    # Absolute path to Codex CLI binary


@dataclass
class RunnerResult:
    """Structured result from a CLI agent invocation."""
    ok: bool                      # True if the agent produced usable output
    output: str                   # The agent's response text (or error message)
    exit_code: Optional[int]      # Process exit code, None on transport errors
    error_type: Optional[str]     # None, "timeout", "not_found", "exit_error", "empty_response", "exception"


@dataclass(frozen=True)
class ScanStats:
    """Metadata from project scanning, used for auto-tuning."""
    total_files: int        # Number of files found during scan
    source_chars: int       # Total characters of source code scanned
    is_monorepo: bool       # Whether the project was detected as a monorepo
    services: tuple         # Tuple of detected service directory names


@dataclass
class Round:
    """A single round in the roundtable discussion."""
    agent: str          # "claude" or "codex"
    label: str          # Display label for this round
    prompt: Optional[str] = None           # Static prompt (round 1)
    prompt_template: Optional[str] = None  # Template with sentinel tokens
