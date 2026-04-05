"""
Provider registry — pluggable agent backends for the roundtable.

Supports built-in agents (claude, codex) and custom CLI agents via
a simple provider:model syntax (e.g., ollama:codellama, gemini).

Inspired by multi-provider PRs on karpathy/llm-council.
"""

import os
import shutil
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ._constants import MAX_OUTPUT_CHARS
from ._types import RoundtableError, RunnerResult


@dataclass(frozen=True)
class AgentConfig:
    """Configuration for a single agent in the roundtable."""
    name: str           # Display name (e.g., "Claude", "Gemini", "Ollama/Codellama")
    agent_key: str      # Internal key (e.g., "claude", "codex", "gemini")
    cmd: List[str]      # Command template (e.g., ["claude", "-p", "-"])
    env_overrides: Optional[Dict[str, str]] = None  # Extra env vars to set/remove
    color_code: str = ""  # ANSI color for terminal output


# Built-in provider definitions
_BUILTIN_PROVIDERS: Dict[str, dict] = {
    "claude": {
        "name": "Claude",
        "cmd_env": "ROUNDTABLE_CLAUDE_CMD",
        "cmd_default": "claude",
        "flags": ["-p", "-"],
        "env_remove": ["CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT"],
    },
    "codex": {
        "name": "Codex",
        "cmd_env": "ROUNDTABLE_CODEX_CMD",
        "cmd_default": "codex",
        "flags": ["exec", "--skip-git-repo-check", "-"],
    },
    "gemini": {
        "name": "Gemini",
        "cmd_env": "ROUNDTABLE_GEMINI_CMD",
        "cmd_default": "gemini",
        "flags": ["-p", "-"],
    },
    "opencode": {
        "name": "OpenCode",
        "cmd_env": "ROUNDTABLE_OPENCODE_CMD",
        "cmd_default": "opencode",
        "flags": ["-p", "-"],
    },
    "aider": {
        "name": "Aider",
        "cmd_env": "ROUNDTABLE_AIDER_CMD",
        "cmd_default": "aider",
        "flags": ["--message", "-"],
    },
    "q": {
        "name": "Amazon Q",
        "cmd_env": "ROUNDTABLE_Q_CMD",
        "cmd_default": "q",
        "flags": ["chat", "-"],
    },
    "copilot": {
        "name": "Copilot",
        "cmd_env": "ROUNDTABLE_COPILOT_CMD",
        "cmd_default": "gh",
        "flags": ["copilot", "suggest", "-"],
    },
}


def parse_agent_spec(spec: str) -> Tuple[str, Optional[str]]:
    """Parse an agent spec like 'claude', 'ollama:codellama', or 'gemini'.

    Returns (provider, model_or_none).
    """
    if ":" in spec:
        provider, model = spec.split(":", 1)
        return provider.strip().lower(), model.strip()
    return spec.strip().lower(), None


def resolve_agents(agent_specs: Optional[List[str]] = None) -> List[AgentConfig]:
    """Resolve agent specifications into AgentConfig objects.

    If agent_specs is None, returns the default [claude, codex] pair.
    Validates that CLI tools are available on PATH.
    """
    if agent_specs is None:
        agent_specs = ["claude", "codex"]

    if len(agent_specs) < 2:
        raise RoundtableError("At least 2 agents are required for a roundtable discussion.")

    agents = []
    seen = set()
    colors = [
        "\033[38;5;208m",  # Orange
        "\033[38;5;40m",   # Green
        "\033[38;5;75m",   # Blue
        "\033[38;5;213m",  # Pink
        "\033[38;5;220m",  # Gold
        "\033[38;5;87m",   # Cyan
        "\033[38;5;156m",  # Light green
        "\033[38;5;183m",  # Lavender
    ]

    for idx, spec in enumerate(agent_specs):
        provider, model = parse_agent_spec(spec)

        # Generate unique key
        key = spec.lower().replace(":", "_")
        if key in seen:
            raise RoundtableError(f"Duplicate agent: {spec}")
        seen.add(key)

        color = colors[idx % len(colors)]

        if provider in _BUILTIN_PROVIDERS:
            defn = _BUILTIN_PROVIDERS[provider]
            cmd_str = os.environ.get(defn["cmd_env"], defn["cmd_default"])
            cmd = [cmd_str] + defn["flags"]

            env_overrides = {}
            for var in defn.get("env_remove", []):
                env_overrides[var] = None  # None = remove from env

            name = defn["name"]
            if model:
                name = f"{name}/{model}"

            agents.append(AgentConfig(
                name=name,
                agent_key=key,
                cmd=cmd,
                env_overrides=env_overrides,
                color_code=color,
            ))
        elif provider == "ollama":
            # Ollama: ollama run <model>
            model_name = model or "llama3"
            cmd_str = os.environ.get("ROUNDTABLE_OLLAMA_CMD", "ollama")
            agents.append(AgentConfig(
                name=f"Ollama/{model_name}",
                agent_key=key,
                cmd=[cmd_str, "run", model_name],
                color_code=color,
            ))
        else:
            # Generic: try running the provider name as a CLI command with stdin
            cmd_str = os.environ.get(
                f"ROUNDTABLE_{provider.upper()}_CMD", provider
            )
            agents.append(AgentConfig(
                name=provider.capitalize() + (f"/{model}" if model else ""),
                agent_key=key,
                cmd=[cmd_str] + ([model] if model else []),
                color_code=color,
            ))

    return agents


def validate_agents(agents: List[AgentConfig]) -> List[AgentConfig]:
    """Validate that agent CLI tools are available on PATH.

    Returns the list with resolved absolute paths.
    Raises RoundtableError if any required tool is missing.
    """
    missing = []
    resolved = []

    for agent in agents:
        cmd_name = agent.cmd[0]
        abs_path = shutil.which(cmd_name)
        if not abs_path:
            missing.append(f"'{cmd_name}' ({agent.name})")
            resolved.append(agent)
        else:
            # Replace command with absolute path for security
            new_cmd = [abs_path] + agent.cmd[1:]
            resolved.append(AgentConfig(
                name=agent.name,
                agent_key=agent.agent_key,
                cmd=new_cmd,
                env_overrides=agent.env_overrides,
                color_code=agent.color_code,
            ))

    if missing:
        msg = "Required CLI tools not found on PATH: " + ", ".join(missing)
        raise RoundtableError(msg)

    return resolved
