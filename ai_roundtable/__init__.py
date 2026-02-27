"""
AI Roundtable — Multi-Agent Project Discussion Tool
====================================================
Orchestrates a structured discussion between Claude CLI and Codex CLI
about your project. Both agents review your code, challenge each other's
findings, and produce actionable improvement recommendations.

Usage:
    ai-roundtable /path/to/your/project
    ai-roundtable /path/to/your/project --rounds 5
    ai-roundtable /path/to/your/project --focus architecture
    python -m ai_roundtable /path/to/your/project
"""

# Re-export the full public API for backward compatibility.
# Consumers can import from ai_roundtable directly or from submodules.

from ._constants import (
    __version__,
    CLAUDE_CMD,
    CODEX_CMD,
    CODEX_SUBCMD,
    CLAUDE_FLAGS,
    CODEX_FLAGS,
    MAX_HISTORY_CHARS,
    MAX_SCAN_DEPTH,
    MAX_FILE_LIST,
    MAX_SCAN_FILES,
    MAX_CONFIG_FILE_CHARS,
    MAX_SOURCE_CHARS,
    MAX_SOURCE_FILE_CHARS,
    MAX_RESPONSE_CHARS,
    MAX_OUTPUT_CHARS,
    MAX_PROMPT_CHARS,
    MAX_WORKFLOW_FILES,
    COMPACT_MAX_RESPONSE_CHARS,
    COMPACT_MAX_HISTORY_CHARS,
)

# Private constants — imported for backward compatibility and test access
# but excluded from __all__ to avoid public API surface creep.
from ._constants import (  # noqa: F811
    _PREV_RESPONSE,
    _CONVERSATION_HISTORY,
    _SENTINELS,
    _PROJECT_DATA_TAG,
)

from ._types import (
    RoundtableError,
    RuntimeConfig,
    RunnerResult,
    Round,
)

from ._protocols import (
    AgentRunner,
    ProjectScanner,
    WebContextProvider,
)

from ._sanitize import (
    sanitize_terminal_output,
    sanitize_project_content,
    substitute_sentinels,
    strip_sentinels,
)

# Private sanitize functions — available for test imports but not in __all__
from ._sanitize import _is_within_root  # noqa: F811

from ._colors import (
    Colors,
    print_banner,
    print_separator,
    print_agent,
    print_warn,
    print_error,
)

from ._preflight import preflight_check

from ._scanner import scan_project

from ._diff import (
    validate_diff_target,
    scan_diff,
)

from ._runners import (
    run_claude,
    run_codex,
)

# Private runner functions — available for test imports but not in __all__
from ._runners import _run_cli, _run_cli_streaming  # noqa: F811

from ._history import build_history_summary

from ._prompts import (
    FOCUS_PROMPTS,
    build_round_prompts,
)

from ._web_context import (
    detect_tech_stack,
    get_web_search_instruction,
    build_web_context,
)

from ._interactive import get_user_input

from ._log import save_log

from ._orchestrator import run_roundtable

from ._cli import main

__all__ = [
    # Constants (public)
    "__version__",
    "CLAUDE_CMD", "CODEX_CMD", "CODEX_SUBCMD",
    "CLAUDE_FLAGS", "CODEX_FLAGS",
    "MAX_HISTORY_CHARS", "MAX_SCAN_DEPTH", "MAX_FILE_LIST", "MAX_SCAN_FILES",
    "MAX_CONFIG_FILE_CHARS", "MAX_SOURCE_CHARS", "MAX_SOURCE_FILE_CHARS",
    "MAX_RESPONSE_CHARS", "MAX_OUTPUT_CHARS", "MAX_PROMPT_CHARS",
    "MAX_WORKFLOW_FILES",
    "COMPACT_MAX_RESPONSE_CHARS", "COMPACT_MAX_HISTORY_CHARS",
    # Types
    "RoundtableError", "RuntimeConfig", "RunnerResult", "Round",
    # Protocols
    "AgentRunner", "ProjectScanner", "WebContextProvider",
    # Sanitize (public)
    "sanitize_terminal_output", "sanitize_project_content",
    "substitute_sentinels", "strip_sentinels",
    # Colors
    "Colors", "print_banner", "print_separator", "print_agent",
    "print_warn", "print_error",
    # Preflight
    "preflight_check",
    # Scanner
    "scan_project",
    # Diff
    "validate_diff_target", "scan_diff",
    # Runners (public)
    "run_claude", "run_codex",
    # History
    "build_history_summary",
    # Prompts
    "FOCUS_PROMPTS", "build_round_prompts",
    # Web context
    "detect_tech_stack", "get_web_search_instruction", "build_web_context",
    # Interactive
    "get_user_input",
    # Log
    "save_log",
    # Orchestrator
    "run_roundtable",
    # CLI
    "main",
]
