"""Tests for conflict classification and dissenting opinion detection."""

import unittest

from ai_roundtable._analysis import (
    classify_conflicts,
    detect_dissenting_opinions,
    build_conflict_summary,
    build_agreement_matrix,
    CONFLICT_FUNDAMENTAL,
    CONFLICT_STYLISTIC,
    CONFLICT_MINOR,
    _extract_section,
    _classify_severity,
)


class TestExtractSection(unittest.TestCase):
    """Tests for section extraction from structured output."""

    def test_extract_disagree_section(self):
        text = "agree:\n- good point\n\ndisagree:\n- bad approach\n- wrong assumption\n\nmissed:\n- perf issue"
        items = _extract_section(text, "disagree")
        self.assertEqual(len(items), 2)
        self.assertIn("bad approach", items[0])

    def test_extract_empty_section(self):
        text = "agree:\n- good\n\nother:\n- stuff"
        items = _extract_section(text, "disagree")
        self.assertEqual(items, [])

    def test_extract_section_case_insensitive(self):
        text = "DISAGREE:\n- point one\n"
        items = _extract_section(text, "disagree")
        self.assertEqual(len(items), 1)

    def test_extract_numbered_items(self):
        text = "top5:\n1. item one\n2. item two\n3. item three\n"
        items = _extract_section(text, "top5")
        self.assertEqual(len(items), 3)

    def test_extract_rebuttals(self):
        text = "rebuttals:\n- loc: main.py:10, position: disagree, evidence: tested\n"
        items = _extract_section(text, "rebuttals")
        self.assertEqual(len(items), 1)
        self.assertIn("main.py:10", items[0])


class TestClassifySeverity(unittest.TestCase):
    """Tests for disagreement severity classification."""

    def test_architecture_is_fundamental(self):
        self.assertEqual(_classify_severity("The architecture is wrong"), CONFLICT_FUNDAMENTAL)

    def test_security_is_fundamental(self):
        self.assertEqual(_classify_severity("security vulnerability in auth"), CONFLICT_FUNDAMENTAL)

    def test_naming_is_stylistic(self):
        self.assertEqual(_classify_severity("naming convention should be snake_case"), CONFLICT_STYLISTIC)

    def test_generic_is_minor(self):
        self.assertEqual(_classify_severity("I think we should add a test"), CONFLICT_MINOR)


class TestClassifyConflicts(unittest.TestCase):
    """Tests for conflict classification from history."""

    def test_detects_disagreements(self):
        history = [
            {"agent": "Claude", "response": "strengths:\n- good code"},
            {"agent": "Codex", "response": "disagree:\n- architecture is wrong\n- naming is bad"},
        ]
        conflicts = classify_conflicts(history)
        self.assertGreater(len(conflicts), 0)
        self.assertEqual(conflicts[0]["agent"], "Codex")

    def test_empty_history(self):
        conflicts = classify_conflicts([])
        self.assertEqual(conflicts, [])

    def test_no_disagreements(self):
        history = [
            {"agent": "Claude", "response": "strengths:\n- good code"},
            {"agent": "Codex", "response": "agree:\n- indeed good code"},
        ]
        conflicts = classify_conflicts(history)
        self.assertEqual(conflicts, [])


class TestDetectDissent(unittest.TestCase):
    """Tests for dissenting opinion detection."""

    def test_needs_3_rounds_minimum(self):
        history = [
            {"agent": "A", "response": "stuff"},
            {"agent": "B", "response": "more stuff"},
        ]
        dissents = detect_dissenting_opinions(history)
        self.assertEqual(dissents, [])

    def test_detects_rebuttals_in_later_rounds(self):
        history = [
            {"agent": "Claude", "response": "review"},
            {"agent": "Codex", "response": "counter"},
            {"agent": "Claude", "response": "rebuttals:\n- loc: main.py:5, position: disagree, evidence: tested"},
        ]
        dissents = detect_dissenting_opinions(history)
        self.assertGreater(len(dissents), 0)
        self.assertEqual(dissents[0]["agent"], "Claude")
        self.assertEqual(dissents[0]["type"], "rebuttal")

    def test_detects_open_items(self):
        history = [
            {"agent": "A", "response": "r1"},
            {"agent": "B", "response": "r2"},
            {"agent": "A", "response": "r3"},
            {"agent": "B", "response": "open:\n- sev: H, issue: unresolved perf bug"},
        ]
        dissents = detect_dissenting_opinions(history)
        self.assertTrue(any(d["type"] == "unresolved" for d in dissents))


class TestBuildConflictSummary(unittest.TestCase):
    """Tests for conflict summary rendering."""

    def test_empty_inputs(self):
        result = build_conflict_summary([], [])
        self.assertEqual(result, "")

    def test_with_conflicts(self):
        conflicts = [
            {"agent": "Codex", "severity": CONFLICT_FUNDAMENTAL, "topic": "main.py:10", "summary": "arch issue"},
            {"agent": "Claude", "severity": CONFLICT_STYLISTIC, "topic": "utils.py:5", "summary": "naming"},
        ]
        result = build_conflict_summary(conflicts, [])
        self.assertIn("Conflict Analysis", result)
        self.assertIn("FUNDAMENTAL", result)
        self.assertIn("STYLISTIC", result)

    def test_with_dissents(self):
        dissents = [
            {"agent": "Codex", "position": "I still disagree", "type": "rebuttal"},
        ]
        result = build_conflict_summary([], dissents)
        self.assertIn("Dissenting Opinions", result)
        self.assertIn("REBUTTAL", result)


class TestBuildAgreementMatrix(unittest.TestCase):
    """Tests for agreement matrix rendering."""

    def test_empty_history(self):
        result = build_agreement_matrix([])
        self.assertEqual(result, "")

    def test_single_round(self):
        result = build_agreement_matrix([{"response": "stuff"}])
        self.assertEqual(result, "")

    def test_with_agreements_and_disagreements(self):
        history = [
            {"response": "strengths:\n- good"},
            {"response": "agree:\n- point 1\n- point 2\n\ndisagree:\n- bad approach\n\nmissed:\n- perf issue"},
        ]
        result = build_agreement_matrix(history)
        self.assertIn("Agreement Matrix", result)
        self.assertIn("Agreed", result)
        self.assertIn("Disagreed", result)

    def test_consensus_percentage(self):
        history = [
            {"response": "stuff"},
            {"response": "agree:\n- a\n- b\n- c\n\ndisagree:\n- d"},
        ]
        result = build_agreement_matrix(history)
        self.assertIn("Consensus level:", result)


if __name__ == "__main__":
    unittest.main()
