# AI Roundtable

Two AI agents (Claude CLI + Codex CLI) review your project in a structured debate. You run one command, they do the rest.

## Requirements

- Python 3.9+
- [Claude CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated
- [Codex CLI](https://github.com/openai/codex) installed and authenticated

## Install

```bash
pip install .
```

## Usage

```bash
# Review a project (that's it)
ai-roundtable /path/to/your/project

# Or without installing
python3 -m ai_roundtable /path/to/your/project
```

### Options

| Flag | What it does | Default |
|------|-------------|---------|
| `--focus AREA` | `all`, `architecture`, `code_quality`, `performance`, `security` | `all` |
| `--rounds N` | Number of debate rounds (min 2, even recommended) | `4` |
| `--timeout N` | Seconds per agent call | `120` |
| `--no-interactive` | Skip user input between rounds | off |
| `--diff [TARGET]` | Review only changed files (vs HEAD, branch, or HEAD~N) | off |
| `--output FILE` | Save discussion to a specific file | auto |
| `--dry-run` | Show prompts without calling agents | off |

### Examples

```bash
# Quick 2-round review focused on security
ai-roundtable ./my-app --focus security --rounds 2

# Deep architecture review, no interruptions
ai-roundtable ./my-app --focus architecture --rounds 6 --no-interactive

# Review only your uncommitted changes
ai-roundtable ./my-app --diff

# Review changes vs main branch
ai-roundtable ./my-app --diff main

# Large project, give agents more time
ai-roundtable ./my-app --timeout 300
```

## What happens when you run it

1. Scans your project files
2. Claude CLI gives an opening review
3. Codex CLI challenges Claude and adds what was missed
4. They go back and forth for the configured number of rounds
5. Discussion is saved to `.roundtable/` in your project

In interactive mode (default), you can steer the conversation between rounds.

## Output

Discussion logs are saved to `.roundtable/roundtable_YYYYMMDD_HHMMSS_XXXX.md` in your project directory. Ctrl+C saves partial progress.

## Custom CLI paths

```bash
export ROUNDTABLE_CLAUDE_CMD="/path/to/claude"
export ROUNDTABLE_CODEX_CMD="/path/to/codex"
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```
