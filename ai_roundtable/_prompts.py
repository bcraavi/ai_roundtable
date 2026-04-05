"""
Prompt construction — builds the sequence of round prompts for the discussion.
"""

import textwrap
from typing import List, Optional

from ._constants import _PREV_RESPONSE, _CONVERSATION_HISTORY
from ._types import Round

FOCUS_PROMPTS = {
    "architecture": "system architecture, design patterns, folder structure, separation of concerns, scalability, and modularity",
    "code_quality": "code quality, bugs, error handling, type safety, naming conventions, DRY violations, and technical debt",
    "performance": "performance bottlenecks, memory leaks, unnecessary re-renders, slow queries, bundle size, and optimization opportunities",
    "security": "security vulnerabilities, authentication flaws, injection risks, exposed secrets, CORS issues, and data validation",
    "all": "architecture, code quality, performance, security, developer experience, testing, and overall product maturity"
}

# ============================================================
# Compact format instructions (default — inter-agent communication)
# ============================================================

_COMPACT_FORMAT_R1 = """\
OUTPUT FORMAT (compact — another AI agent reads this, not a human):

strengths:
- brief description (1 line each)

concerns:
- sev: critical|high|medium|low
  loc: file:line
  issue: one-line description
  fix: suggested fix (1 line)

recommendations:
- effort: quick|medium|large
  action: what to do (1 line)

questions:
- question (1 line each)

features:
- name: feature name
  value: why it matters (1 line)

Reference files:lines. No paragraphs. Keep response under 4000 characters."""

_COMPACT_FORMAT_R2 = """\
OUTPUT FORMAT (compact — another AI agent reads this, not a human):

agree:
- loc: file:line, why (1 line)

disagree:
- loc: file:line, counter: alternative take (1 line)

missed:
- sev: H|M|L, loc: file:line, issue: desc, fix: suggestion

top5:
1. [sev] issue — fix (1 line each)

features:
- name: feature, value: why (1 line each)

Keep response under 4000 characters."""

_COMPACT_FORMAT_R3 = """\
OUTPUT FORMAT (compact — another AI agent reads this, not a human):

concessions:
- what changed your mind (1 line each)

rebuttals:
- loc: file:line, position: your stance, evidence: why (1 line)

synthesis:
- priority: H|M|L, action: what to do, effort: quick|medium|large

feature_roadmap:
1. name — why build first (1 line each)

Keep response under 4000 characters."""

_COMPACT_FORMAT_R4 = """\
OUTPUT FORMAT (compact — another AI agent reads this, not a human):

quick_wins:
- action (1 line each, top 3)

strategic:
- action (1 line each, top 3)

features:
- name: brief spec (1 line each, top 3)

scores:
  architecture: N/10, reason (1 line)
  code_quality: N/10, reason (1 line)
  production_readiness: N/10, reason (1 line)

verdict: single most important thing to fix or build (1 line)

Keep response under 4000 characters."""

_COMPACT_FORMAT_OVERFLOW = """\
OUTPUT FORMAT (compact — another AI agent reads this, not a human):

resolved:
- item (1 line each)

open:
- sev: H|M|L, issue: desc, fix: suggestion (1 line each)

new_insights:
- insight (1 line each)

Keep response under 4000 characters."""

# Peer evaluation scorecard (appended to the final round)
_SCORECARD_FORMAT = """

PEER EVALUATION (rate the other agent's review):

peer_scores:
  accuracy: N/10 — how correct were their findings?
  thoroughness: N/10 — did they cover all important areas?
  actionability: N/10 — how practical and specific were their suggestions?
  missed_issues: N/10 — how well did they catch non-obvious problems?
  overall: N/10

peer_notes: 1-2 sentence assessment of the other agent's contribution"""


def build_round_prompts(project_summary: str, focus: str, num_rounds: int,
                        web_context: str = "", verbose: bool = False,
                        agent_names: Optional[List[str]] = None) -> List[Round]:
    """Build the sequence of prompts for the discussion.

    Uses sentinel tokens (__PREV_RESPONSE__, __CONVERSATION_HISTORY__)
    substituted via single-pass regex to prevent recursive expansion.

    When agent_names is provided, prompts use those names instead of
    the default Claude/Codex pair. Supports N agents in round-robin.
    """
    focus_desc = FOCUS_PROMPTS.get(focus, FOCUS_PROMPTS["all"])
    web_prefix = f"{web_context}\n\n" if web_context else ""

    if agent_names is None:
        agent_names = ["Claude", "Codex"]

    if verbose:
        return _build_verbose_prompts(project_summary, focus_desc, num_rounds, web_prefix, agent_names)
    return _build_compact_prompts(project_summary, focus_desc, num_rounds, web_prefix, agent_names)


def _build_compact_prompts(project_summary: str, focus_desc: str,
                           num_rounds: int, web_prefix: str,
                           agent_names: List[str]) -> List[Round]:
    """Build compact structured-output prompts for inter-agent communication."""
    rounds: List[Round] = []
    n_agents = len(agent_names)

    # Assign agent keys (lowercase for internal use)
    agent_keys = [name.lower().replace("/", "_").replace(" ", "_") for name in agent_names]

    # Round 1: First agent opens with initial review
    first = agent_names[0]
    second = agent_names[1] if n_agents > 1 else "another agent"
    rounds.append(Round(
        agent=agent_keys[0],
        label=f"Round 1 — {first}'s Opening Review",
        prompt=web_prefix + textwrap.dedent(f"""\
            You are participating in a multi-agent code review roundtable.
            You are Agent A ({first}). Another AI agent ({second}) will review your analysis and respond.

            {project_summary}

            YOUR TASK:
            Review this project focusing on: {focus_desc}

            {_COMPACT_FORMAT_R1}""")
    ))

    if num_rounds >= 2:
        second_name = agent_names[1 % n_agents]
        rounds.append(Round(
            agent=agent_keys[1 % n_agents],
            label=f"Round 2 — {second_name}'s Counter-Review",
            prompt_template=web_prefix + textwrap.dedent(f"""\
                You are participating in a multi-agent code review roundtable.
                You are Agent B ({second_name}). Another AI agent ({first}) has just reviewed this project.

                {project_summary}

                PRIOR DISCUSSION:
                {_CONVERSATION_HISTORY}

                {first}'S LATEST REVIEW:
                {_PREV_RESPONSE}

                YOUR TASK:
                Respond to {first}'s review. Focus areas: {focus_desc}

                {_COMPACT_FORMAT_R2}""")
        ))

    if num_rounds >= 3:
        third_name = agent_names[2 % n_agents]
        prev_name = agent_names[(2 - 1) % n_agents]
        rounds.append(Round(
            agent=agent_keys[2 % n_agents],
            label=f"Round 3 — {third_name}'s Rebuttal & Synthesis",
            prompt_template=web_prefix + textwrap.dedent(f"""\
                You are Agent C ({third_name}) in a code review roundtable.
                {prev_name} has responded to the initial review.

                {project_summary}

                PRIOR DISCUSSION:
                {_CONVERSATION_HISTORY}

                {prev_name}'S LATEST RESPONSE:
                {_PREV_RESPONSE}

                YOUR TASK:
                Synthesize all reviews so far. Focus areas: {focus_desc}

                {_COMPACT_FORMAT_R3}""")
        ))

    if num_rounds >= 4:
        fourth_name = agent_names[3 % n_agents]
        prev_name = agent_names[(3 - 1) % n_agents]
        # Final round gets scorecard
        fmt = _COMPACT_FORMAT_R4 + _SCORECARD_FORMAT
        rounds.append(Round(
            agent=agent_keys[3 % n_agents],
            label=f"Round 4 — {fourth_name}'s Final Recommendations",
            prompt_template=web_prefix + textwrap.dedent(f"""\
                You are Agent D ({fourth_name}) in a code review roundtable.
                This is the final round. {prev_name} has synthesized all reviews.

                {project_summary}

                PRIOR DISCUSSION:
                {_CONVERSATION_HISTORY}

                {prev_name}'S SYNTHESIS:
                {_PREV_RESPONSE}

                YOUR TASK:
                Give your final verdict.

                {fmt}""")
        ))

    if num_rounds > 4:
        for i in range(4, num_rounds):
            agent_idx = i % n_agents
            prev_idx = (i - 1) % n_agents
            agent_name = agent_names[agent_idx]
            other_name = agent_names[prev_idx]
            is_final = (i == num_rounds - 1)
            fmt = _COMPACT_FORMAT_OVERFLOW
            if is_final:
                fmt = _COMPACT_FORMAT_OVERFLOW + _SCORECARD_FORMAT
            rounds.append(Round(
                agent=agent_keys[agent_idx],
                label=f"Round {i+1} — {agent_name} Follow-up",
                prompt_template=web_prefix + textwrap.dedent(f"""\
                    Continue the code review roundtable discussion.

                    PRIOR DISCUSSION:
                    {_CONVERSATION_HISTORY}

                    {other_name}'s last response:
                    {_PREV_RESPONSE}

                    Focus on: {focus_desc}

                    {fmt}""")
            ))

    return rounds


def _build_verbose_prompts(project_summary: str, focus_desc: str,
                           num_rounds: int, web_prefix: str,
                           agent_names: List[str]) -> List[Round]:
    """Build verbose prose prompts for human-readable output (original format)."""
    rounds: List[Round] = []
    n_agents = len(agent_names)
    agent_keys = [name.lower().replace("/", "_").replace(" ", "_") for name in agent_names]

    first = agent_names[0]
    second = agent_names[1] if n_agents > 1 else "another agent"

    # Round 1: First agent opens
    rounds.append(Round(
        agent=agent_keys[0],
        label=f"Round 1 — {first}'s Opening Review",
        prompt=web_prefix + textwrap.dedent(f"""\
            You are participating in a multi-agent code review roundtable.
            You are Agent A ({first}). Another AI agent ({second}) will review your analysis and respond.

            {project_summary}

            YOUR TASK:
            Provide a thorough initial review focusing on: {focus_desc}

            Structure your review as:
            1. STRENGTHS — What's done well
            2. CONCERNS — Issues you've identified (ranked by severity)
            3. RECOMMENDATIONS — Specific, actionable improvements
            4. QUESTIONS — Things you'd want to investigate further

            Additionally, suggest 2-3 NEW FEATURE IDEAS that would make this project
            significantly more useful or innovative. Think beyond bug fixes — what would
            make users excited about this tool?

            Be specific. Reference actual files and code patterns you see in the project structure.
            Be opinionated — take clear positions so the other agent can agree or challenge you.""")
    ))

    if num_rounds >= 2:
        second_name = agent_names[1 % n_agents]
        rounds.append(Round(
            agent=agent_keys[1 % n_agents],
            label=f"Round 2 — {second_name}'s Counter-Review",
            prompt_template=web_prefix + textwrap.dedent(f"""\
                You are participating in a multi-agent code review roundtable.
                You are Agent B ({second_name}). Another AI agent ({first}) has just reviewed this project.

                {project_summary}

                PRIOR DISCUSSION:
                {_CONVERSATION_HISTORY}

                {first}'S LATEST REVIEW:
                {_PREV_RESPONSE}

                YOUR TASK:
                1. AGREEMENTS — Where you agree with {first} and why
                2. DISAGREEMENTS — Where you disagree, and your alternative take
                3. MISSED ISSUES — Important things {first} overlooked
                4. DEEPER DIVES — Pick 2-3 of {first}'s points and go deeper with specific fixes
                5. PRIORITY RANKING — Rank the top 5 most impactful improvements
                6. FEATURE IDEAS — Respond to {first}'s feature suggestions and add 2-3 of your own.
                   What would make this tool a must-have for developers?

                Focus areas: {focus_desc}
                Be direct. If {first} is wrong about something, say so and explain why.""")
        ))

    if num_rounds >= 3:
        third_name = agent_names[2 % n_agents]
        prev_name = agent_names[(2 - 1) % n_agents]
        rounds.append(Round(
            agent=agent_keys[2 % n_agents],
            label=f"Round 3 — {third_name}'s Rebuttal & Synthesis",
            prompt_template=web_prefix + textwrap.dedent(f"""\
                You are Agent C ({third_name}) in a code review roundtable.
                {prev_name} has responded to the initial review.

                {project_summary}

                PRIOR DISCUSSION:
                {_CONVERSATION_HISTORY}

                {prev_name}'S LATEST RESPONSE:
                {_PREV_RESPONSE}

                YOUR TASK:
                1. CONCESSIONS — Where the other agents changed your mind
                2. REBUTTALS — Where you still disagree, with evidence
                3. SYNTHESIS — Combine the best insights from all reviews
                4. ACTION PLAN — Create a prioritized list of improvements the developer should make,
                   with estimated effort (quick win / medium / large) for each item
                5. FEATURE ROADMAP — Synthesize the best feature ideas from all reviews into
                   a prioritized roadmap. Which features should be built first? Why?

                Focus areas: {focus_desc}
                Be constructive. The goal is to give the developer the clearest possible path forward.""")
        ))

    if num_rounds >= 4:
        fourth_name = agent_names[3 % n_agents]
        prev_name = agent_names[(3 - 1) % n_agents]
        rounds.append(Round(
            agent=agent_keys[3 % n_agents],
            label=f"Round 4 — {fourth_name}'s Final Recommendations",
            prompt_template=web_prefix + textwrap.dedent(f"""\
                You are Agent D ({fourth_name}) in a code review roundtable.
                This is the final round. {prev_name} has synthesized all reviews.

                {project_summary}

                PRIOR DISCUSSION:
                {_CONVERSATION_HISTORY}

                {prev_name}'S SYNTHESIS:
                {_PREV_RESPONSE}

                YOUR TASK:
                Give your FINAL VERDICT:
                1. TOP 3 QUICK WINS — Changes that take <1 hour but have big impact
                2. TOP 3 STRATEGIC IMPROVEMENTS — Larger changes for long-term health
                3. TOP 3 FEATURE IDEAS — The most exciting features to build next, with brief specs
                4. ARCHITECTURE SCORE — Rate the project 1-10 with justification
                5. CODE QUALITY SCORE — Rate 1-10 with justification
                6. PRODUCTION READINESS — Rate 1-10 with justification
                7. ONE SENTENCE SUMMARY — The single most important thing to fix or build

                PEER EVALUATION:
                Rate the other agents' contributions:
                - Accuracy (1-10): How correct were their findings?
                - Thoroughness (1-10): Did they cover all important areas?
                - Actionability (1-10): How practical were their suggestions?
                - Overall assessment (1-2 sentences)

                Be decisive and specific.""")
        ))

    if num_rounds > 4:
        for i in range(4, num_rounds):
            agent_idx = i % n_agents
            prev_idx = (i - 1) % n_agents
            agent_name = agent_names[agent_idx]
            other_name = agent_names[prev_idx]
            rounds.append(Round(
                agent=agent_keys[agent_idx],
                label=f"Round {i+1} — {agent_name} Follow-up",
                prompt_template=web_prefix + textwrap.dedent(f"""\
                    Continue the code review roundtable discussion.

                    PRIOR DISCUSSION:
                    {_CONVERSATION_HISTORY}

                    {other_name}'s last response:
                    {_PREV_RESPONSE}

                    Dig deeper into any unresolved points. Suggest specific code changes
                    or architectural patterns. Also propose any additional feature ideas
                    or improvements. Focus on: {focus_desc}""")
            ))

    return rounds
