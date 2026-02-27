"""Tests for the structured RunnerResult dataclass."""

import unittest

from ai_roundtable import RunnerResult


class TestRunnerResult(unittest.TestCase):
    """Tests for the structured RunnerResult dataclass."""

    def test_ok_result(self):
        r = RunnerResult(ok=True, output="Good response", exit_code=0, error_type=None)
        self.assertTrue(r.ok)
        self.assertEqual(r.output, "Good response")
        self.assertIsNone(r.error_type)

    def test_error_result(self):
        r = RunnerResult(ok=False, output="Claude exited with code 1: crash",
                         exit_code=1, error_type="exit_error")
        self.assertFalse(r.ok)
        self.assertEqual(r.error_type, "exit_error")

    def test_timeout_result(self):
        r = RunnerResult(ok=False, output="Claude CLI timed out",
                         exit_code=None, error_type="timeout")
        self.assertFalse(r.ok)
        self.assertIsNone(r.exit_code)

    def test_not_found_result(self):
        r = RunnerResult(ok=False, output="claude not found",
                         exit_code=None, error_type="not_found")
        self.assertEqual(r.error_type, "not_found")

    def test_no_false_positive_on_bracket_output(self):
        """A normal response starting with '[' should still be ok=True from runner."""
        r = RunnerResult(ok=True, output="[1] First point: the architecture is solid",
                         exit_code=0, error_type=None)
        self.assertTrue(r.ok)


if __name__ == "__main__":
    unittest.main()
