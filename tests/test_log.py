"""Tests for log persistence."""

import os
import tempfile
import unittest
from pathlib import Path

from ai_roundtable import save_log


class TestSaveLog(unittest.TestCase):
    """Tests for log persistence."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.output_file = os.path.join(self.tmpdir, ".roundtable", "test.md")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_saves_log_to_file(self):
        log = ["# Discussion", "## Round 1", "Some content"]
        save_log(log, self.output_file, self.tmpdir)
        self.assertTrue(os.path.exists(self.output_file))
        content = Path(self.output_file).read_text()
        self.assertIn("# Discussion", content)
        self.assertIn("Some content", content)

    def test_partial_log_includes_marker(self):
        log = ["# Discussion", "## Round 1", "Partial"]
        save_log(log, self.output_file, self.tmpdir, is_partial=True)
        content = Path(self.output_file).read_text()
        self.assertIn("interrupted", content.lower())

    def test_creates_parent_directories(self):
        nested = os.path.join(self.tmpdir, "a", "b", "c", "log.md")
        save_log(["test"], nested, self.tmpdir)
        self.assertTrue(os.path.exists(nested))


if __name__ == "__main__":
    unittest.main()
