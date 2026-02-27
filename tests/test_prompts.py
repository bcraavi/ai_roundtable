"""Tests for round prompt construction."""

import unittest

from ai_roundtable import (
    build_round_prompts,
    substitute_sentinels,
    Round,
    _PREV_RESPONSE,
    _CONVERSATION_HISTORY,
)


class TestBuildRoundPrompts(unittest.TestCase):
    """Tests for round prompt construction."""

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

    @unittest.mock.patch('ai_roundtable._orchestrator.run_codex')
    @unittest.mock.patch('ai_roundtable._orchestrator.run_claude')
    @unittest.mock.patch('ai_roundtable._orchestrator.preflight_check')
    def test_prompt_trimmed_when_over_budget(self, mock_preflight, mock_claude, mock_codex):
        """Prompts exceeding MAX_PROMPT_CHARS should be trimmed."""
        from ai_roundtable import run_roundtable, MAX_PROMPT_CHARS
        mock_claude.return_value = self._ok_result("x" * (MAX_PROMPT_CHARS + 1000))
        mock_codex.return_value = self._ok_result("Codex review")
        output = os.path.join(self.tmpdir, "test_output.md")
        run_roundtable(self.tmpdir, num_rounds=2, interactive=False, output_file=output)
        # Round 2 prompt should have been trimmed — verify codex was called
        # and the prompt it received is within budget
        codex_call = mock_codex.call_args
        prompt = codex_call[0][0]
        self.assertLessEqual(len(prompt), MAX_PROMPT_CHARS + 100)  # small overhead from trim message


import os
import unittest.mock

if __name__ == "__main__":
    unittest.main()
