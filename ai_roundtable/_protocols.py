"""
Protocol interfaces — extensibility contracts for agents, scanners, and providers.

Implement these protocols to plug in new agents (Gemini, DeepSeek, etc.),
alternative scanning strategies, or different web context sources.
"""

from typing import Optional, Protocol, runtime_checkable

from ._types import RunnerResult


@runtime_checkable
class AgentRunner(Protocol):
    """Protocol for CLI agent runners.

    Implement this to add a new AI agent to the roundtable.
    The runner receives a prompt, runs the agent CLI, and returns
    a structured result.
    """
    def __call__(self, prompt: str, project_path: str, timeout: int = 120,
                 cmd_path: Optional[str] = None) -> RunnerResult: ...


@runtime_checkable
class ProjectScanner(Protocol):
    """Protocol for project scanning strategies.

    Implement this to provide alternative ways of gathering
    project context (e.g., AST-based scanning, LSP integration).
    """
    def __call__(self, project_path: str) -> str: ...


@runtime_checkable
class WebContextProvider(Protocol):
    """Protocol for web context enrichment.

    Implement this to provide alternative sources of up-to-date
    technical context (e.g., cached version databases, custom APIs).
    """
    def __call__(self, project_summary: str) -> str: ...
