"""
Web context — tech stack detection, version lookup, and agent search instructions.

Always-active web search integration that enriches every round prompt with:
1. Agent-specific instructions to use web search tools
2. Detected tech stack from the project scan
3. Latest version info fetched from package registries (best-effort, zero external deps)
"""

import json
import re
import urllib.request
import urllib.error
from datetime import date
from typing import Dict, List, Optional

# Tech stack detection patterns (regex on project summary text)
_TECH_PATTERNS: Dict[str, re.Pattern] = {
    "Python": re.compile(r'(?:requirements\.txt|pyproject\.toml|setup\.py|\.py\b)', re.IGNORECASE),
    "JavaScript": re.compile(r'(?:package\.json|\.js\b|\.jsx\b)', re.IGNORECASE),
    "TypeScript": re.compile(r'(?:tsconfig\.json|\.ts\b|\.tsx\b)', re.IGNORECASE),
    "React": re.compile(r'(?:"react"|next\.config\.|\.jsx\b|\.tsx\b)', re.IGNORECASE),
    "Next.js": re.compile(r'(?:next\.config\.(?:js|mjs|ts)|"next")', re.IGNORECASE),
    "Go": re.compile(r'(?:go\.mod|go\.sum|\.go\b)', re.IGNORECASE),
    "Rust": re.compile(r'(?:Cargo\.toml|\.rs\b)', re.IGNORECASE),
    "Docker": re.compile(r'(?:Dockerfile|docker-compose\.yml)', re.IGNORECASE),
    "Ruby": re.compile(r'(?:Gemfile|\.rb\b)', re.IGNORECASE),
    "Java": re.compile(r'(?:pom\.xml|build\.gradle|\.java\b)', re.IGNORECASE),
    "C/C++": re.compile(r'(?:CMakeLists\.txt|\.c\b|\.cpp\b|\.h\b|\.hpp\b)', re.IGNORECASE),
    "Swift": re.compile(r'(?:Package\.swift|\.swift\b)', re.IGNORECASE),
    "Kotlin": re.compile(r'(?:\.kt\b|build\.gradle\.kts)', re.IGNORECASE),
    "Vue.js": re.compile(r'(?:\.vue\b|"vue")', re.IGNORECASE),
    "Django": re.compile(r'(?:manage\.py|django)', re.IGNORECASE),
    "Flask": re.compile(r'(?:flask)', re.IGNORECASE),
    "FastAPI": re.compile(r'(?:fastapi)', re.IGNORECASE),
}

# Registry URLs for version lookups (PyPI and npm only — zero deps)
_PYPI_URL = "https://pypi.org/pypi/{}/json"
_NPM_URL = "https://registry.npmjs.org/{}/latest"

# Packages to check by detected tech
_VERSION_CHECKS: Dict[str, List[tuple]] = {
    "Python": [("python", "pypi")],
    "React": [("react", "npm")],
    "Next.js": [("next", "npm")],
    "TypeScript": [("typescript", "npm")],
    "Vue.js": [("vue", "npm")],
    "Django": [("django", "pypi")],
    "Flask": [("flask", "pypi")],
    "FastAPI": [("fastapi", "pypi")],
}

_FETCH_TIMEOUT = 5  # seconds — best-effort, don't block the review


def detect_tech_stack(project_summary: str) -> List[str]:
    """Detect technologies used in the project from the scan summary."""
    detected = []
    for tech, pattern in _TECH_PATTERNS.items():
        if pattern.search(project_summary):
            detected.append(tech)
    return sorted(detected)


def _fetch_latest_version(package: str, registry: str) -> Optional[str]:
    """Fetch the latest version of a package from PyPI or npm. Best-effort."""
    try:
        if registry == "pypi":
            url = _PYPI_URL.format(package)
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
                return data.get("info", {}).get("version")
        elif registry == "npm":
            url = _NPM_URL.format(package)
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
                return data.get("version")
    except Exception:
        return None
    return None


def _fetch_versions(tech_stack: List[str]) -> Dict[str, str]:
    """Fetch latest versions for detected technologies. Best-effort, no failures."""
    versions = {}
    for tech in tech_stack:
        checks = _VERSION_CHECKS.get(tech, [])
        for package, registry in checks:
            ver = _fetch_latest_version(package, registry)
            if ver:
                versions[package] = ver
    return versions


def get_web_search_instruction(agent: str) -> str:
    """Return agent-specific web search instructions.

    Claude has WebSearch/WebFetch tools built in.
    Codex uses the --search flag (added to CODEX_FLAGS).
    """
    today = date.today().isoformat()

    if agent == "claude":
        return (
            f"TODAY'S DATE: {today}\n"
            "WEB SEARCH: You have WebSearch and WebFetch tools available. "
            "USE THEM to verify current best practices, check for known CVEs, "
            "look up latest stable versions of dependencies, and reference "
            "up-to-date documentation. Do not rely solely on training data — "
            "actively search for the most current information relevant to this review."
        )
    else:  # codex
        return (
            f"TODAY'S DATE: {today}\n"
            "WEB SEARCH: You have web search capabilities enabled. "
            "Use them to verify current best practices, check for known CVEs, "
            "look up latest stable versions of dependencies, and reference "
            "up-to-date documentation. Your reviews should reflect the latest "
            "information, not just training data."
        )


def build_web_context(project_summary: str) -> str:
    """Build a complete web context block for prompt injection.

    Combines:
    1. Agent-agnostic tech context (stack + versions)
    2. Today's date for knowledge cutoff awareness

    Agent-specific search instructions are added per-round by the orchestrator.
    """
    today = date.today().isoformat()
    tech_stack = detect_tech_stack(project_summary)
    versions = _fetch_versions(tech_stack)

    parts = [f"CURRENT TECH CONTEXT (as of {today}):"]

    if tech_stack:
        parts.append(f"Detected tech stack: {', '.join(tech_stack)}")

    if versions:
        ver_lines = [f"  {pkg}: {ver}" for pkg, ver in sorted(versions.items())]
        parts.append("Latest stable versions:\n" + "\n".join(ver_lines))

    if not tech_stack and not versions:
        parts.append("No specific tech stack detected from project scan.")

    return "\n".join(parts)
