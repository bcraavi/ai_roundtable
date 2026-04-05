# AI Roundtable

Multiple AI agents review your project in a structured debate. You run one command, they do the rest.

Supports Claude CLI, Codex CLI, Gemini CLI, OpenCode, Amazon Q, Aider, Ollama, and any CLI tool that reads from stdin.

## Requirements

- Python 3.9+
- At least 2 AI CLI tools installed and authenticated. Supported out of the box:
  - [Claude CLI](https://docs.anthropic.com/en/docs/claude-code) — `claude`
  - [Codex CLI](https://github.com/openai/codex) — `codex`
  - [Gemini CLI](https://github.com/google-gemini/gemini-cli) — `gemini`
  - [OpenCode](https://github.com/opencode-ai/opencode) — `opencode`
  - [Amazon Q Developer](https://aws.amazon.com/q/developer/) — `q`
  - [Aider](https://github.com/paul-gauthier/aider) — `aider`
  - [GitHub Copilot CLI](https://github.com/github/gh-copilot) — `copilot` (via `gh`)
  - [Ollama](https://ollama.ai) — `ollama:modelname` (local models)
  - Any CLI tool that accepts prompts via stdin

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
| `--quick` | Quick mode: 2 rounds, non-interactive, skip deep debate | off |
| `--agents A B ...` | Which agents to use (default: `claude codex`) | `claude codex` |
| `--verbose` | Use verbose prose output instead of compact structured format | off |

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

# Quick mode for trivial changes (2 rounds, non-interactive)
ai-roundtable ./my-app --quick

# Use Claude + Gemini instead of Claude + Codex
ai-roundtable ./my-app --agents claude gemini

# Three-agent debate
ai-roundtable ./my-app --agents claude codex gemini

# Use OpenCode as one of the agents
ai-roundtable ./my-app --agents claude opencode

# Amazon Q + Claude
ai-roundtable ./my-app --agents claude q

# Use a local Ollama model
ai-roundtable ./my-app --agents claude ollama:codellama

# Aider + Claude
ai-roundtable ./my-app --agents claude aider

# Any CLI tool that reads stdin
ai-roundtable ./my-app --agents claude mycustomtool
```

## What happens when you run it

1. Scans your project files
2. First agent gives an opening review
3. Second agent challenges and adds what was missed
4. Agents go back and forth for the configured number of rounds
5. **Conflict analysis** classifies disagreements as fundamental vs. stylistic
6. **Agreement matrix** shows consensus level
7. **Peer evaluation scorecard** rates each agent's contribution
8. Discussion is saved to `.roundtable/` in your project

In interactive mode (default), you can steer the conversation between rounds.

## Output

Discussion logs are saved to `.roundtable/roundtable_YYYYMMDD_HHMMSS_XXXX.md` in your project directory. Ctrl+C saves partial progress.

## Custom CLI paths

```bash
export ROUNDTABLE_CLAUDE_CMD="/path/to/claude"
export ROUNDTABLE_CODEX_CMD="/path/to/codex"
export ROUNDTABLE_GEMINI_CMD="/path/to/gemini"
export ROUNDTABLE_OPENCODE_CMD="/path/to/opencode"
export ROUNDTABLE_AIDER_CMD="/path/to/aider"
export ROUNDTABLE_Q_CMD="/path/to/q"
export ROUNDTABLE_COPILOT_CMD="/path/to/gh"
export ROUNDTABLE_OLLAMA_CMD="/path/to/ollama"
```

## New in v0.8.0

- **Multi-provider support**: Use any combination of AI agents (`--agents claude gemini ollama:codellama`)
- **Quick mode**: `--quick` for fast 2-round reviews on trivial changes
- **Conflict analysis**: Automatically classifies disagreements as fundamental, stylistic, or minor
- **Dissenting opinion detection**: Flags persistent disagreements and unresolved issues
- **Peer evaluation scorecards**: Agents rate each other on accuracy, thoroughness, and actionability
- **Agreement matrix**: Visual summary of consensus level between agents

## Tests

```bash
python3 -m unittest discover -s tests -v
```
