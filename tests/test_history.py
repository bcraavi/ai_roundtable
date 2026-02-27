"""Tests for conversation history summarization."""

import unittest

from ai_roundtable import build_history_summary


class TestBuildHistorySummary(unittest.TestCase):
    """Tests for conversation history summarization."""

    def test_empty_history(self):
        self.assertEqual(build_history_summary([]), "")

    def test_single_entry(self):
        history = [{"label": "Round 1", "agent": "Claude", "response": "Good code."}]
        result = build_history_summary(history)
        self.assertIn("Round 1", result)
        self.assertIn("Claude", result)
        self.assertIn("Good code.", result)

    def test_within_budget(self):
        history = [
            {"label": "Round 1", "agent": "Claude", "response": "Short response."},
            {"label": "Round 2", "agent": "Codex", "response": "Also short."},
        ]
        result = build_history_summary(history, max_chars=10000)
        self.assertIn("Round 1", result)
        self.assertIn("Round 2", result)
        self.assertNotIn("truncated", result)

    def test_over_budget_preserves_round1(self):
        """When history exceeds budget, Round 1 should still be preserved."""
        history = [
            {"label": "Round 1", "agent": "Claude", "response": "Foundation analysis."},
            {"label": "Round 2", "agent": "Codex", "response": "x" * 500},
            {"label": "Round 3", "agent": "Claude", "response": "y" * 500},
            {"label": "Round 4", "agent": "Codex", "response": "Final verdict."},
        ]
        # Use a small budget that forces truncation
        result = build_history_summary(history, max_chars=300)
        self.assertIn("Foundation analysis", result)
        self.assertIn("Foundational review preserved", result)

    def test_over_budget_keeps_recent(self):
        """When history exceeds budget, the most recent round should be preserved."""
        history = [
            {"label": "Round 1", "agent": "Claude", "response": "Foundation."},
            {"label": "Round 2", "agent": "Codex", "response": "m" * 200},
            {"label": "Round 3", "agent": "Claude", "response": "m" * 200},
            {"label": "Round 4", "agent": "Codex", "response": "Final verdict here."},
        ]
        result = build_history_summary(history, max_chars=400)
        self.assertIn("Foundation.", result)
        self.assertIn("Final verdict here.", result)

    def test_truncation_indicates_dropped_rounds(self):
        history = [
            {"label": f"Round {i}", "agent": "Claude" if i % 2 == 1 else "Codex",
             "response": f"Response {i} " + "x" * 300}
            for i in range(1, 7)
        ]
        result = build_history_summary(history, max_chars=800)
        self.assertIn("truncated", result.lower())

    def test_developer_input_preserved(self):
        """Developer directives in history should be included."""
        history = [
            {"label": "Round 1", "agent": "Claude", "response": "Initial review."},
            {"label": "Developer direction before Round 2", "agent": "Developer",
             "response": "Focus on auth flow."},
            {"label": "Round 2", "agent": "Codex", "response": "Codex response."},
        ]
        result = build_history_summary(history, max_chars=10000)
        self.assertIn("Focus on auth flow", result)
        self.assertIn("Developer", result)


class TestBuildHistoryExcludeLast(unittest.TestCase):
    """Tests for the exclude_last parameter."""

    def test_exclude_last_drops_final_entry(self):
        history = [
            {"label": "Round 1", "agent": "Claude", "response": "First."},
            {"label": "Round 2", "agent": "Codex", "response": "Second."},
            {"label": "Round 3", "agent": "Claude", "response": "Third."},
        ]
        result = build_history_summary(history, exclude_last=True)
        self.assertIn("First.", result)
        self.assertIn("Second.", result)
        self.assertNotIn("Third.", result)

    def test_exclude_last_with_single_entry(self):
        """Single entry + exclude_last should still include it (nothing to drop)."""
        history = [{"label": "Round 1", "agent": "Claude", "response": "Only one."}]
        result = build_history_summary(history, exclude_last=True)
        self.assertIn("Only one.", result)

    def test_exclude_last_false_includes_all(self):
        history = [
            {"label": "Round 1", "agent": "Claude", "response": "First."},
            {"label": "Round 2", "agent": "Codex", "response": "Second."},
        ]
        result = build_history_summary(history, exclude_last=False)
        self.assertIn("First.", result)
        self.assertIn("Second.", result)


if __name__ == "__main__":
    unittest.main()
