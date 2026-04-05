"""
Post-round analysis — conflict classification and dissenting opinion detection.

Inspired by karpathy/llm-council PRs #129 (minority opinion detection)
and #130 (ranking conflict detection).
"""

import re
from typing import Dict, List, Tuple


# Markers for conflict severity
CONFLICT_FUNDAMENTAL = "FUNDAMENTAL"
CONFLICT_STYLISTIC = "STYLISTIC"
CONFLICT_MINOR = "MINOR"


def classify_conflicts(history: List[dict]) -> List[dict]:
    """Analyze conversation history and classify disagreements.

    Returns a list of conflict records:
    [{"agents": (a, b), "severity": str, "topic": str, "summary": str}, ...]
    """
    conflicts = []

    for entry in history:
        response = entry.get("response", "")
        agent = entry.get("agent", "")

        # Look for disagreement markers in structured output
        disagree_blocks = _extract_section(response, "disagree")
        rebuttal_blocks = _extract_section(response, "rebuttals")

        for item in disagree_blocks + rebuttal_blocks:
            severity = _classify_severity(item)
            topic = _extract_topic(item)
            conflicts.append({
                "agent": agent,
                "severity": severity,
                "topic": topic,
                "summary": item.strip()[:150],
            })

    return conflicts


def detect_dissenting_opinions(history: List[dict]) -> List[dict]:
    """Detect when an agent holds a minority position.

    A dissent is when one agent's position on a topic is contradicted
    by all other agents' positions. In a 2-agent debate, this means
    any unresolved disagreement from the final rounds.
    """
    dissents = []

    # Look at later rounds for unresolved disagreements
    if len(history) < 3:
        return dissents

    # Check the last two entries for persistent disagreements
    for entry in history[-2:]:
        response = entry.get("response", "")
        agent = entry.get("agent", "")

        # Check for rebuttals (persistent disagreements)
        rebuttals = _extract_section(response, "rebuttals")
        open_items = _extract_section(response, "open")

        for item in rebuttals + open_items:
            dissents.append({
                "agent": agent,
                "position": item.strip()[:200],
                "type": "rebuttal" if item in rebuttals else "unresolved",
            })

    return dissents


def build_conflict_summary(conflicts: List[dict], dissents: List[dict]) -> str:
    """Build a markdown summary of conflicts and dissenting opinions."""
    if not conflicts and not dissents:
        return ""

    lines = []
    lines.append("\n## Conflict Analysis")
    lines.append("")

    if conflicts:
        # Count by severity
        by_severity: Dict[str, int] = {}
        for c in conflicts:
            by_severity[c["severity"]] = by_severity.get(c["severity"], 0) + 1

        lines.append("### Disagreement Classification")
        lines.append("")
        for sev in [CONFLICT_FUNDAMENTAL, CONFLICT_STYLISTIC, CONFLICT_MINOR]:
            count = by_severity.get(sev, 0)
            if count:
                icon = {"FUNDAMENTAL": "!!!", "STYLISTIC": "~~", "MINOR": "."}[sev]
                lines.append(f"- **{sev}** [{icon}]: {count} disagreement(s)")

        lines.append("")
        for c in conflicts:
            tag = f"[{c['severity'][:4]}]"
            lines.append(f"  - {tag} ({c['agent']}) {c['topic']}: {c['summary']}")

    if dissents:
        lines.append("")
        lines.append("### Dissenting Opinions")
        lines.append("")
        for d in dissents:
            dtype = "REBUTTAL" if d["type"] == "rebuttal" else "UNRESOLVED"
            lines.append(f"- **{d['agent']}** [{dtype}]: {d['position']}")

    lines.append("")
    return "\n".join(lines)


def build_agreement_matrix(history: List[dict]) -> str:
    """Build a terminal-friendly agreement matrix from the discussion.

    Shows which topics agents agreed/disagreed on.
    """
    if len(history) < 2:
        return ""

    agree_count = 0
    disagree_count = 0
    missed_count = 0

    for entry in history:
        response = entry.get("response", "")
        agree_count += len(_extract_section(response, "agree"))
        agree_count += len(_extract_section(response, "concessions"))
        disagree_count += len(_extract_section(response, "disagree"))
        disagree_count += len(_extract_section(response, "rebuttals"))
        missed_count += len(_extract_section(response, "missed"))

    total = agree_count + disagree_count + missed_count
    if total == 0:
        return ""

    lines = []
    lines.append("\n## Agreement Matrix")
    lines.append("")
    lines.append("```")
    lines.append(f"  Agreed:     {'=' * min(agree_count * 3, 40)} ({agree_count})")
    lines.append(f"  Disagreed:  {'#' * min(disagree_count * 3, 40)} ({disagree_count})")
    lines.append(f"  Missed:     {'?' * min(missed_count * 3, 40)} ({missed_count})")

    if total > 0:
        pct_agree = agree_count * 100 // total
        lines.append(f"")
        lines.append(f"  Consensus level: {pct_agree}%")

    lines.append("```")
    lines.append("")
    return "\n".join(lines)


# --- Internal helpers ---

def _extract_section(text: str, section_name: str) -> List[str]:
    """Extract items from a structured section like 'disagree:' or 'rebuttals:'."""
    pattern = rf'(?:^|\n){re.escape(section_name)}:\s*\n((?:[ \t]*[-\d].*\n?)*)'
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return []

    block = match.group(1)
    items = []
    for line in block.split("\n"):
        line = line.strip()
        if line and (line.startswith("-") or (len(line) > 1 and line[0].isdigit() and line[1] == ".")):
            items.append(line.lstrip("-0123456789. "))
    return items


def _classify_severity(text: str) -> str:
    """Classify disagreement severity based on content signals."""
    text_lower = text.lower()

    # Fundamental: architecture, security, design decisions
    fundamental_signals = [
        "architecture", "security", "design", "fundamental",
        "critical", "vulnerability", "breaking", "unsafe",
        "race condition", "injection", "data loss",
    ]
    if any(sig in text_lower for sig in fundamental_signals):
        return CONFLICT_FUNDAMENTAL

    # Stylistic: naming, formatting, style preferences
    stylistic_signals = [
        "naming", "style", "convention", "formatting",
        "readability", "preference", "cosmetic", "bikeshed",
    ]
    if any(sig in text_lower for sig in stylistic_signals):
        return CONFLICT_STYLISTIC

    return CONFLICT_MINOR


def _extract_topic(text: str) -> str:
    """Extract the topic/location from a disagreement line."""
    # Try to find file:line reference
    loc_match = re.search(r'(?:loc:\s*)?(\S+\.\w+:\d+)', text)
    if loc_match:
        return loc_match.group(1)

    # Try to find a file reference
    file_match = re.search(r'(\S+\.\w{1,5})', text)
    if file_match:
        return file_match.group(1)

    # Fall back to first few words
    words = text.split()[:4]
    return " ".join(words)
