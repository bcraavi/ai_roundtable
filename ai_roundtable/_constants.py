"""
Constants — single source of truth for version, CLI config, and limits.
"""

import os

# ============================================================
# VERSION (single source of truth)
# ============================================================
__version__ = "0.8.0"

# ============================================================
# CONFIGURATION — Adjust CLI commands if needed
# ============================================================
CLAUDE_CMD = os.environ.get("ROUNDTABLE_CLAUDE_CMD", "claude")
CODEX_CMD = os.environ.get("ROUNDTABLE_CODEX_CMD", "codex")
CODEX_SUBCMD = "exec"       # Codex subcommand for non-interactive mode

# Claude CLI flags for non-interactive print mode
CLAUDE_FLAGS = ["-p"]

# Codex CLI flags
CODEX_FLAGS = ["--skip-git-repo-check"]

# Maximum character budget for conversation history injected into prompts.
# 12k chars ~3k tokens — keeps prompts within context limits for both CLIs
# while preserving enough history for meaningful multi-round debate.
MAX_HISTORY_CHARS = 12000

# Maximum depth for os.walk when scanning project files.
# Depth 4 covers typical src/app/module/file structures without runaway traversal.
MAX_SCAN_DEPTH = 4

# Maximum number of files listed in the project summary sent to agents.
# Caps prompt size — agents see enough structure without prompt bloat.
MAX_FILE_LIST = 200

# Hard cap on total files scanned during os.walk. Prevents slow traversal
# on monorepos with tens of thousands of files.
MAX_SCAN_FILES = 600

# Maximum characters per key config file included in the summary.
# 3k chars captures most config files in full; large ones get truncated.
MAX_CONFIG_FILE_CHARS = 3000

# Maximum total characters for source file content included in the summary.
# 30k chars ~7.5k tokens — provides meaningful code context without blowing
# context limits. Prioritizes entrypoint and key source files.
MAX_SOURCE_CHARS = 30000

# Maximum characters per individual source file.
MAX_SOURCE_FILE_CHARS = 5000

# Maximum agent response characters to inject as __PREV_RESPONSE__.
# Prevents context blowups when an agent produces very long output.
MAX_RESPONSE_CHARS = 15000

# Compact-mode budgets — used when agents talk to each other (default).
# Structured output is ~40-60% smaller than prose, so budgets shrink accordingly.
COMPACT_MAX_RESPONSE_CHARS = 6000
COMPACT_MAX_HISTORY_CHARS = 8000

# Maximum characters of subprocess output to retain per stream.
# With text=True on Popen, we count characters not bytes.
# 2M chars is generous — typical agent responses are 10-50K chars.
MAX_OUTPUT_CHARS = 2 * 1024 * 1024

# Global prompt budget (characters). Caps the total prompt sent to an agent
# to stay within model context windows. ~50k chars ~= 12-15k tokens.
MAX_PROMPT_CHARS = 50000

# Maximum number of workflow files to include from .github/workflows/.
# Prevents prompt bloat on monorepos with many CI configs.
MAX_WORKFLOW_FILES = 10

# Sentinel tokens for safe template substitution (avoids .format() brace crashes).
# These are substituted in a single-pass regex to prevent recursive expansion.
_PREV_RESPONSE = "__PREV_RESPONSE__"
_CONVERSATION_HISTORY = "__CONVERSATION_HISTORY__"
_SENTINELS = {_PREV_RESPONSE, _CONVERSATION_HISTORY}

# Tag used to wrap scanned project content as a trust boundary.
_PROJECT_DATA_TAG = "project-data-boundary"
