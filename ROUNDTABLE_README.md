# AI Roundtable — Multi-Agent Project Discussion

Have Claude CLI and Codex CLI review your project together in a structured debate, with you jumping in to steer the conversation.

## Prerequisites

- **Claude CLI** installed and authenticated (`claude` command works)
- **Codex CLI** installed and authenticated (`codex` command works)
- **Python 3.8+**

Both tools are verified at startup — the script will fail fast with a clear message if either is missing.

## Quick Start

```bash
# Basic usage — full comprehensive review
python3 ai_roundtable.py /path/to/your/project

# Focus on architecture only
python3 ai_roundtable.py /path/to/your/project --focus architecture

# More rounds for deeper discussion
python3 ai_roundtable.py /path/to/your/project --rounds 6

# Fewer rounds for a quick back-and-forth
python3 ai_roundtable.py /path/to/your/project --rounds 2

# Non-interactive mode (no pauses for your input)
python3 ai_roundtable.py /path/to/your/project --no-interactive

# Longer timeout for large projects
python3 ai_roundtable.py /path/to/your/project --timeout 180

# Save output to a specific file
python3 ai_roundtable.py /path/to/your/project --output review.md

# Dry run — see generated prompts without calling any CLIs
python3 ai_roundtable.py /path/to/your/project --dry-run

# Install as a CLI tool
pip install .
ai-roundtable /path/to/your/project
```

## How It Works

The script runs a structured **4-round discussion** (configurable, minimum 2):

| Round | Agent  | Purpose |
|-------|--------|---------|
| 1     | Claude | Opens with a thorough initial review |
| 2     | Codex  | Challenges Claude, adds missed issues |
| 3     | Claude | Rebuts, concedes, synthesizes both views |
| 4     | Codex  | Final verdict with scores and priorities |

Between each round, **you can jump in** to ask questions, redirect the discussion, or add context the agents might be missing. Your directives are preserved in the conversation history so later rounds remember your guidance.

Each agent receives a rolling conversation history (budget-limited, anchor-and-recency strategy) so context is preserved across all rounds — Round 1's foundational analysis is always kept even when middle rounds are truncated.

**Round count notes:** Use even values for a balanced debate ending with Codex's scoring. Odd values mean the last round is always Claude (no Codex final verdict).

## Focus Areas

| Flag | What It Covers |
|------|----------------|
| `--focus all` | Everything (default) |
| `--focus architecture` | Design patterns, scalability, modularity |
| `--focus code_quality` | Bugs, tech debt, naming, DRY |
| `--focus performance` | Speed, memory, bundle size, rendering |
| `--focus security` | Auth, injection, secrets, CORS |

## Output

The full discussion is saved as a Markdown file in a `.roundtable/` subdirectory of your project:
`.roundtable/roundtable_YYYYMMDD_HHMMSS.md`

If you hit Ctrl+C during a run, the partial discussion is saved automatically.

If your project is a git repo, consider adding `.roundtable/` to your `.gitignore`.

## Customizing CLI Commands

If your CLI commands are different, edit the top of `ai_roundtable.py`:

```python
CLAUDE_CMD = "claude"                    # Change if different
CODEX_CMD = "codex"                      # Change if different
CLAUDE_FLAGS = ["-p"]                    # Claude print mode flags
CODEX_FLAGS = ["--skip-git-repo-check"]  # Codex flags
```

## Running Tests

```bash
python3 -m unittest test_ai_roundtable -v
```

82 tests cover the core logic: project scanning (including source file ingestion and binary file filtering), prompt building, history truncation, sentinel replacement, boundary sanitization, terminal output sanitization, structured runner results, orchestrator integration (normal flow, error recovery, failure threading, dry-run), and scan early termination.

## Tips

- Start with `--focus architecture` for the most strategic insights
- Use 6+ rounds if you want the agents to really dig in
- Use `--rounds 2` for a quick review + counter-review
- Jump in during interactive mode to ask "what about testing?" or "focus on the auth flow"
- The saved Markdown log makes a great reference for sprint planning
