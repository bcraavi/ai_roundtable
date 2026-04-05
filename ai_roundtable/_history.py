"""
Conversation history — rolling summary with anchor-and-recency strategy.
"""

import re
from typing import List

from ._constants import MAX_HISTORY_CHARS


def build_history_summary(history: List[dict], max_chars: int = MAX_HISTORY_CHARS,
                          exclude_last: bool = False, compact: bool = False) -> str:
    """Build a rolling conversation summary from all prior rounds, truncated to budget.

    Preserves Round 1 (foundational analysis) and the most recent rounds,
    dropping middle rounds when the history exceeds the character budget.

    When exclude_last=True, omits the last entry to avoid duplication with
    the separate __PREV_RESPONSE__ injection.

    When compact=True, uses shorter round headers (e.g. "### R1 (Claude)")
    to save tokens in inter-agent communication.
    """
    if not history:
        return ""

    entries = history[:-1] if (exclude_last and len(history) > 1) else history

    parts = []
    for entry in entries:
        if compact:
            # Extract round number from label like "Round 3 — Claude's Rebuttal & Synthesis"
            label = entry['label']
            # Try to shorten "Round N — ..." to "RN"
            match = re.match(r'Round (\d+)', label)
            short_label = f"R{match.group(1)}" if match else label
            parts.append(f"### {short_label} ({entry['agent']})\n{entry['response']}")
        else:
            parts.append(f"### {entry['label']} ({entry['agent']})\n{entry['response']}")

    if not parts:
        return ""

    full = "\n\n".join(parts)

    # If within budget, return as-is
    if len(full) <= max_chars:
        return full

    # Anchor-and-recency strategy: keep Round 1 + most recent rounds, drop the middle.
    round1 = parts[0]
    round1_header = "[Foundational review preserved]\n" + round1

    # Budget for the anchor round
    remaining_budget = max_chars - len(round1_header) - 60
    if remaining_budget <= 0:
        return round1[:max_chars]

    # Fill from the back with recent rounds
    recent_parts = []
    used = 0
    for part in reversed(parts[1:]):
        if used + len(part) + 2 > remaining_budget:
            break
        recent_parts.insert(0, part)
        used += len(part) + 2

    if recent_parts:
        dropped = len(parts) - 1 - len(recent_parts)
        separator = f"\n\n[... {dropped} middle round(s) truncated for context budget ...]\n\n" if dropped > 0 else "\n\n"
        return round1_header + separator + "\n\n".join(recent_parts)
    else:
        return round1_header + "\n\n[All subsequent rounds truncated for context budget]"
