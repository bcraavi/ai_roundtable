"""
Preflight checks — verify required CLI tools before starting.
"""

import shutil

from ._constants import CLAUDE_CMD, CODEX_CMD
from ._types import RoundtableError, RuntimeConfig


def preflight_check():
    """Verify required CLI tools are installed before starting.

    Resolves CLI commands to absolute paths for security (prevents PATH hijacking)
    and returns a RuntimeConfig with the resolved paths.
    Raises RoundtableError if required tools are missing.
    """
    missing = []
    claude_path = shutil.which(CLAUDE_CMD)
    codex_path = shutil.which(CODEX_CMD)
    if not claude_path:
        missing.append(f"'{CLAUDE_CMD}' (Claude CLI)")
    if not codex_path:
        missing.append(f"'{CODEX_CMD}' (Codex CLI)")
    if missing:
        msg = "Required CLI tools not found on PATH: " + ", ".join(missing)
        raise RoundtableError(msg)
    return RuntimeConfig(claude_cmd=claude_path, codex_cmd=codex_path)
