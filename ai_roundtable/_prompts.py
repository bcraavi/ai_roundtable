"""
Prompt construction — builds the sequence of round prompts for the discussion.
"""

import textwrap
from typing import List

from ._constants import _PREV_RESPONSE, _CONVERSATION_HISTORY
from ._types import Round

FOCUS_PROMPTS = {
    "architecture": "system architecture, design patterns, folder structure, separation of concerns, scalability, and modularity",
    "code_quality": "code quality, bugs, error handling, type safety, naming conventions, DRY violations, and technical debt",
    "performance": "performance bottlenecks, memory leaks, unnecessary re-renders, slow queries, bundle size, and optimization opportunities",
    "security": "security vulnerabilities, authentication flaws, injection risks, exposed secrets, CORS issues, and data validation",
    "all": "architecture, code quality, performance, security, developer experience, testing, and overall product maturity"
}


def build_round_prompts(project_summary: str, focus: str, num_rounds: int,
                        web_context: str = "") -> List[Round]:
    """Build the sequence of prompts for the discussion.

    Uses sentinel tokens (__PREV_RESPONSE__, __CONVERSATION_HISTORY__)
    substituted via single-pass regex to prevent recursive expansion.

    When web_context is provided, it is prepended to every prompt so agents
    have up-to-date technology context and web search instructions.
    """
    focus_desc = FOCUS_PROMPTS.get(focus, FOCUS_PROMPTS["all"])

    # Web context prefix (empty string if no web context)
    web_prefix = f"{web_context}\n\n" if web_context else ""

    rounds: List[Round] = []

    # Round 1: Claude opens with initial review
    rounds.append(Round(
        agent="claude",
        label="Round 1 — Claude's Opening Review",
        prompt=web_prefix + textwrap.dedent(f"""\
            You are participating in a multi-agent code review roundtable.
            You are Agent A (Claude). Another AI agent (Codex) will review your analysis and respond.

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
        rounds.append(Round(
            agent="codex",
            label="Round 2 — Codex's Counter-Review",
            prompt_template=web_prefix + textwrap.dedent(f"""\
                You are participating in a multi-agent code review roundtable.
                You are Agent B (Codex). Another AI agent (Claude) has just reviewed this project.

                {project_summary}

                PRIOR DISCUSSION:
                {_CONVERSATION_HISTORY}

                CLAUDE'S LATEST REVIEW:
                {_PREV_RESPONSE}

                YOUR TASK:
                1. AGREEMENTS — Where you agree with Claude and why
                2. DISAGREEMENTS — Where you disagree, and your alternative take
                3. MISSED ISSUES — Important things Claude overlooked
                4. DEEPER DIVES — Pick 2-3 of Claude's points and go deeper with specific fixes
                5. PRIORITY RANKING — Rank the top 5 most impactful improvements
                6. FEATURE IDEAS — Respond to Claude's feature suggestions and add 2-3 of your own.
                   What would make this tool a must-have for developers?

                Focus areas: {focus_desc}
                Be direct. If Claude is wrong about something, say so and explain why.""")
        ))

    if num_rounds >= 3:
        rounds.append(Round(
            agent="claude",
            label="Round 3 — Claude's Rebuttal & Synthesis",
            prompt_template=web_prefix + textwrap.dedent(f"""\
                You are Agent A (Claude) in a code review roundtable.
                Agent B (Codex) has responded to your initial review.

                {project_summary}

                PRIOR DISCUSSION:
                {_CONVERSATION_HISTORY}

                CODEX'S LATEST RESPONSE:
                {_PREV_RESPONSE}

                YOUR TASK:
                1. CONCESSIONS — Where Codex changed your mind
                2. REBUTTALS — Where you still disagree, with evidence
                3. SYNTHESIS — Combine the best insights from both reviews
                4. ACTION PLAN — Create a prioritized list of improvements the developer should make,
                   with estimated effort (quick win / medium / large) for each item
                5. FEATURE ROADMAP — Synthesize the best feature ideas from both reviews into
                   a prioritized roadmap. Which features should be built first? Why?

                Focus areas: {focus_desc}
                Be constructive. The goal is to give the developer the clearest possible path forward.""")
        ))

    if num_rounds >= 4:
        rounds.append(Round(
            agent="codex",
            label="Round 4 — Codex's Final Recommendations",
            prompt_template=web_prefix + textwrap.dedent(f"""\
                You are Agent B (Codex) in a code review roundtable.
                This is the final round. Claude has synthesized both your reviews.

                {project_summary}

                PRIOR DISCUSSION:
                {_CONVERSATION_HISTORY}

                CLAUDE'S SYNTHESIS:
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

                Be decisive and specific.""")
        ))

    if num_rounds > 4:
        for i in range(4, num_rounds):
            agent = "claude" if i % 2 == 0 else "codex"
            other = "Codex" if agent == "claude" else "Claude"
            rounds.append(Round(
                agent=agent,
                label=f"Round {i+1} — {'Claude' if agent == 'claude' else 'Codex'} Follow-up",
                prompt_template=web_prefix + textwrap.dedent(f"""\
                    Continue the code review roundtable discussion.

                    PRIOR DISCUSSION:
                    {_CONVERSATION_HISTORY}

                    {other}'s last response:
                    {_PREV_RESPONSE}

                    Dig deeper into any unresolved points. Suggest specific code changes
                    or architectural patterns. Also propose any additional feature ideas
                    or improvements. Focus on: {focus_desc}""")
            ))

    return rounds
