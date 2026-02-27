"""Tests for sentinel substitution and stripping."""

import unittest

from ai_roundtable import (
    substitute_sentinels,
    strip_sentinels,
    _PREV_RESPONSE,
    _CONVERSATION_HISTORY,
    _SENTINELS,
)


class TestSubstituteSentinels(unittest.TestCase):
    """Tests for single-pass sentinel substitution."""

    def test_basic_replacement(self):
        template = f"Previous: {_PREV_RESPONSE}\nHistory: {_CONVERSATION_HISTORY}"
        result = substitute_sentinels(template, {
            _PREV_RESPONSE: "agent said hello",
            _CONVERSATION_HISTORY: "round 1 summary",
        })
        self.assertIn("agent said hello", result)
        self.assertIn("round 1 summary", result)
        self.assertNotIn(_PREV_RESPONSE, result)
        self.assertNotIn(_CONVERSATION_HISTORY, result)

    def test_prevents_recursive_expansion(self):
        """If agent output contains a sentinel token, it must NOT get expanded."""
        template = f"Prev: {_PREV_RESPONSE}\nHist: {_CONVERSATION_HISTORY}"
        # Agent output itself contains the CONVERSATION_HISTORY sentinel
        result = substitute_sentinels(template, {
            _PREV_RESPONSE: f"The agent said {_CONVERSATION_HISTORY} literally",
            _CONVERSATION_HISTORY: "real history",
        })
        # The literal sentinel inside the agent output should survive untouched
        self.assertIn(f"The agent said {_CONVERSATION_HISTORY} literally", result)
        self.assertIn("Hist: real history", result)

    def test_no_sentinels_in_template(self):
        result = substitute_sentinels("plain text", {_PREV_RESPONSE: "X"})
        self.assertEqual(result, "plain text")

    def test_empty_replacements(self):
        template = f"before {_PREV_RESPONSE} after"
        result = substitute_sentinels(template, {_PREV_RESPONSE: ""})
        self.assertEqual(result, "before  after")

    def test_braces_in_replacement_values(self):
        """Values with braces (JSON) should not cause issues."""
        template = f"Data: {_PREV_RESPONSE}"
        result = substitute_sentinels(template, {
            _PREV_RESPONSE: '{"key": "value", "nested": {"a": 1}}',
        })
        self.assertIn('"key": "value"', result)


class TestStripSentinels(unittest.TestCase):
    """Tests for sentinel stripping from user input."""

    def test_strips_prev_response(self):
        text = f"Focus on {_PREV_RESPONSE} improvements"
        result = strip_sentinels(text)
        self.assertNotIn(_PREV_RESPONSE, result)
        self.assertIn("Focus on  improvements", result)

    def test_strips_conversation_history(self):
        text = f"Ignore {_CONVERSATION_HISTORY} for now"
        result = strip_sentinels(text)
        self.assertNotIn(_CONVERSATION_HISTORY, result)

    def test_strips_all_sentinels(self):
        text = f"{_PREV_RESPONSE} and {_CONVERSATION_HISTORY}"
        result = strip_sentinels(text)
        for s in _SENTINELS:
            self.assertNotIn(s, result)

    def test_preserves_normal_text(self):
        text = "Normal user input with no sentinels"
        result = strip_sentinels(text)
        self.assertEqual(text, result)


if __name__ == "__main__":
    unittest.main()
