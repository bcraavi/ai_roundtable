"""Tests for round prompt construction."""

import os
import unittest
import unittest.mock

from ai_roundtable import (
    build_round_prompts,
    substitute_sentinels,
    Round,
    _PREV_RESPONSE,
    _CONVERSATION_HISTORY,
)


class TestBuildRoundPrompts(unittest.TestCase):
    """Tests for round prompt construction (compact mode — default)."""

    def test_default_four_rounds(self):
        rounds = build_round_prompts("test summary", "all", 4)
        self.assertEqual(len(rounds), 4)

    def test_two_rounds(self):
        rounds = build_round_prompts("test summary", "all", 2)
        self.assertEqual(len(rounds), 2)
        self.assertEqual(rounds[0].agent, "claude")
        self.assertEqual(rounds[1].agent, "codex")

    def test_three_rounds(self):
        rounds = build_round_prompts("test summary", "all", 3)
        self.assertEqual(len(rounds), 3)
        self.assertEqual(rounds[2].agent, "claude")

    def test_six_rounds(self):
        rounds = build_round_prompts("test summary", "all", 6)
        self.assertEqual(len(rounds), 6)
        # Extra rounds alternate
        self.assertEqual(rounds[4].agent, "claude")
        self.assertEqual(rounds[5].agent, "codex")

    def test_round_types(self):
        rounds = build_round_prompts("test summary", "all", 4)
        # Round 1 has a static prompt
        self.assertIsNotNone(rounds[0].prompt)
        self.assertIsNone(rounds[0].prompt_template)
        # Rounds 2-4 have templates
        for r in rounds[1:]:
            self.assertIsNotNone(r.prompt_template)
            self.assertIsNone(r.prompt)

    def test_templates_contain_sentinel_tokens(self):
        rounds = build_round_prompts("test summary", "all", 4)
        for r in rounds[1:]:
            self.assertIn(_PREV_RESPONSE, r.prompt_template)
            self.assertIn(_CONVERSATION_HISTORY, r.prompt_template)

    def test_no_python_format_braces_in_templates(self):
        """Templates should not contain {previous_response} style placeholders."""
        rounds = build_round_prompts('{"key": "value"}', "all", 4)
        for r in rounds[1:]:
            # Ensure there are no .format()-style placeholders
            self.assertNotIn("{previous_response}", r.prompt_template)
            self.assertNotIn("{conversation_history}", r.prompt_template)

    def test_sentinel_replacement_with_braces(self):
        """Verify that sentinel replacement works when project content has braces."""
        summary = '{"name": "test", "scripts": {"build": "webpack"}}'
        rounds = build_round_prompts(summary, "all", 4)
        template = rounds[1].prompt_template

        # Use the actual substitute_sentinels function (not raw .replace())
        result = substitute_sentinels(template, {
            _PREV_RESPONSE: "Claude's {review} with braces",
            _CONVERSATION_HISTORY: "some {history}",
        })
        self.assertIn("Claude's {review} with braces", result)
        self.assertIn("some {history}", result)

    def test_focus_areas_included(self):
        for focus in ["architecture", "code_quality", "performance", "security", "all"]:
            rounds = build_round_prompts("summary", focus, 2)
            # Round 1 prompt should mention the focus area
            self.assertIn(focus.replace("_", " ") if focus != "all" else "architecture", rounds[0].prompt)

    def test_returns_round_dataclass(self):
        rounds = build_round_prompts("test", "all", 4)
        for r in rounds:
            self.assertIsInstance(r, Round)

    def test_agent_alternation(self):
        rounds = build_round_prompts("test", "all", 6)
        agents = [r.agent for r in rounds]
        self.assertEqual(agents, ["claude", "codex", "claude", "codex", "claude", "codex"])


class TestCompactPrompts(unittest.TestCase):
    """Tests specific to compact (default) prompt format."""

    def test_compact_round1_has_format_instructions(self):
        """Compact round 1 should include structured output format."""
        rounds = build_round_prompts("test summary", "all", 4)
        self.assertIn("strengths:", rounds[0].prompt)
        self.assertIn("concerns:", rounds[0].prompt)
        self.assertIn("Keep response under 4000 characters", rounds[0].prompt)

    def test_compact_round2_has_format_instructions(self):
        rounds = build_round_prompts("test summary", "all", 4)
        self.assertIn("agree:", rounds[1].prompt_template)
        self.assertIn("disagree:", rounds[1].prompt_template)
        self.assertIn("top5:", rounds[1].prompt_template)

    def test_compact_round3_has_format_instructions(self):
        rounds = build_round_prompts("test summary", "all", 4)
        self.assertIn("concessions:", rounds[2].prompt_template)
        self.assertIn("synthesis:", rounds[2].prompt_template)
        self.assertIn("feature_roadmap:", rounds[2].prompt_template)

    def test_compact_round4_has_format_instructions(self):
        rounds = build_round_prompts("test summary", "all", 4)
        self.assertIn("quick_wins:", rounds[3].prompt_template)
        self.assertIn("scores:", rounds[3].prompt_template)
        self.assertIn("verdict:", rounds[3].prompt_template)

    def test_compact_round4_has_peer_scorecard(self):
        """Final round should include peer evaluation scorecard."""
        rounds = build_round_prompts("test summary", "all", 4)
        self.assertIn("peer_scores:", rounds[3].prompt_template)
        self.assertIn("accuracy:", rounds[3].prompt_template)
        self.assertIn("thoroughness:", rounds[3].prompt_template)

    def test_compact_overflow_has_format_instructions(self):
        rounds = build_round_prompts("test summary", "all", 6)
        self.assertIn("resolved:", rounds[4].prompt_template)
        self.assertIn("open:", rounds[4].prompt_template)

    def test_compact_is_default(self):
        """Default (no verbose flag) should produce compact prompts."""
        compact = build_round_prompts("test", "all", 2)
        verbose = build_round_prompts("test", "all", 2, verbose=True)
        # Compact round 1 should have structured format markers
        self.assertIn("strengths:", compact[0].prompt)
        # Verbose round 1 should have prose instructions
        self.assertIn("STRENGTHS", verbose[0].prompt)
        self.assertNotIn("strengths:", verbose[0].prompt)


class TestVerbosePrompts(unittest.TestCase):
    """Tests for verbose (prose) prompt format."""

    def test_verbose_four_rounds(self):
        rounds = build_round_prompts("test summary", "all", 4, verbose=True)
        self.assertEqual(len(rounds), 4)

    def test_verbose_round_types(self):
        rounds = build_round_prompts("test summary", "all", 4, verbose=True)
        self.assertIsNotNone(rounds[0].prompt)
        self.assertIsNone(rounds[0].prompt_template)
        for r in rounds[1:]:
            self.assertIsNotNone(r.prompt_template)
            self.assertIsNone(r.prompt)

    def test_verbose_has_prose_instructions(self):
        """Verbose prompts should contain the original prose structure."""
        rounds = build_round_prompts("test summary", "all", 4, verbose=True)
        self.assertIn("STRENGTHS", rounds[0].prompt)
        self.assertIn("CONCERNS", rounds[0].prompt)
        self.assertIn("RECOMMENDATIONS", rounds[0].prompt)
        self.assertIn("QUESTIONS", rounds[0].prompt)
        self.assertIn("NEW FEATURE IDEAS", rounds[0].prompt)

    def test_verbose_no_compact_markers(self):
        """Verbose prompts should NOT contain compact format instructions."""
        rounds = build_round_prompts("test summary", "all", 4, verbose=True)
        self.assertNotIn("Keep response under 4000 characters", rounds[0].prompt)
        self.assertNotIn("sev: critical|high|medium|low", rounds[0].prompt)

    def test_verbose_templates_contain_sentinels(self):
        rounds = build_round_prompts("test summary", "all", 4, verbose=True)
        for r in rounds[1:]:
            self.assertIn(_PREV_RESPONSE, r.prompt_template)
            self.assertIn(_CONVERSATION_HISTORY, r.prompt_template)

    def test_verbose_agent_alternation(self):
        rounds = build_round_prompts("test", "all", 6, verbose=True)
        agents = [r.agent for r in rounds]
        self.assertEqual(agents, ["claude", "codex", "claude", "codex", "claude", "codex"])

    def test_verbose_six_rounds(self):
        rounds = build_round_prompts("test summary", "all", 6, verbose=True)
        self.assertEqual(len(rounds), 6)

    def test_verbose_final_round_has_peer_evaluation(self):
        """Verbose final round should include peer evaluation section."""
        rounds = build_round_prompts("test summary", "all", 4, verbose=True)
        self.assertIn("PEER EVALUATION", rounds[3].prompt_template)
        self.assertIn("Accuracy", rounds[3].prompt_template)


class TestMultiAgentPrompts(unittest.TestCase):
    """Tests for multi-agent prompt construction."""

    def test_custom_agent_names(self):
        """Custom agent names should appear in prompts."""
        rounds = build_round_prompts("test", "all", 2, agent_names=["Gemini", "Claude"])
        self.assertIn("Gemini", rounds[0].prompt)
        self.assertIn("Claude", rounds[1].prompt_template)

    def test_three_agents_round_robin(self):
        """Three agents should rotate through rounds."""
        rounds = build_round_prompts("test", "all", 6,
                                     agent_names=["Claude", "Codex", "Gemini"])
        agents = [r.agent for r in rounds]
        # Round robin: 0,1,2,0,1,2
        self.assertEqual(agents[0], "claude")
        self.assertEqual(agents[1], "codex")
        self.assertEqual(agents[2], "gemini")
        self.assertEqual(agents[3], "claude")
        self.assertEqual(agents[4], "codex")
        self.assertEqual(agents[5], "gemini")

    def test_agent_names_in_labels(self):
        """Agent names should appear in round labels."""
        rounds = build_round_prompts("test", "all", 2,
                                     agent_names=["MyAgent", "YourAgent"])
        self.assertIn("MyAgent", rounds[0].label)
        self.assertIn("YourAgent", rounds[1].label)

    def test_default_names_are_claude_codex(self):
        """Default agent names should be Claude and Codex."""
        rounds = build_round_prompts("test", "all", 2)
        self.assertIn("Claude", rounds[0].label)
        self.assertIn("Codex", rounds[1].label)


class TestRoundLabels(unittest.TestCase):
    """Verify round labeling conventions."""

    def test_round_labels_sequential(self):
        rounds = build_round_prompts("summary", "all", 6)
        for i, r in enumerate(rounds):
            self.assertIn(f"Round {i+1}", r.label)

    def test_round1_label(self):
        rounds = build_round_prompts("summary", "all", 4)
        self.assertIn("Opening Review", rounds[0].label)

    def test_round4_label(self):
        rounds = build_round_prompts("summary", "all", 4)
        self.assertIn("Final Recommendations", rounds[3].label)


class TestPromptBudget(unittest.TestCase):
    """Tests for global prompt budget enforcement."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        self.tmpdir = tempfile.mkdtemp()
        Path(os.path.join(self.tmpdir, "main.py")).write_text("print('hello')")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _ok_result(self, text):
        from ai_roundtable import RunnerResult
        return RunnerResult(ok=True, output=text, exit_code=0, error_type=None)

    @unittest.mock.patch('ai_roundtable._orchestrator.run_agent')
    @unittest.mock.patch('ai_roundtable._orchestrator.validate_agents')
    def test_prompt_trimmed_when_over_budget(self, mock_validate, mock_run_agent):
        """Prompts exceeding MAX_PROMPT_CHARS should be trimmed."""
        from ai_roundtable import run_roundtable, MAX_PROMPT_CHARS
        from ai_roundtable._providers import AgentConfig
        mock_validate.return_value = [
            AgentConfig(name="Claude", agent_key="claude", cmd=["claude", "-p", "-"],
                         color_code="\033[38;5;208m"),
            AgentConfig(name="Codex", agent_key="codex", cmd=["codex", "exec", "-"],
                         color_code="\033[38;5;40m"),
        ]
        mock_run_agent.side_effect = [
            self._ok_result("x" * (MAX_PROMPT_CHARS + 1000)),
            self._ok_result("Codex review"),
        ]
        output = os.path.join(self.tmpdir, "test_output.md")
        run_roundtable(self.tmpdir, num_rounds=2, interactive=False, output_file=output)
        second_call = mock_run_agent.call_args_list[1]
        prompt = second_call[0][0]
        self.assertLessEqual(len(prompt), MAX_PROMPT_CHARS + 100)


if __name__ == "__main__":
    unittest.main()
