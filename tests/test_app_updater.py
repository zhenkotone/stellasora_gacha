import hashlib
import tempfile
import unittest
from pathlib import Path

from stellasora_toolkit.app_updater import is_newer_version, sha256_file


class AppUpdaterTests(unittest.TestCase):
    def test_detects_newer_semantic_version(self):
        self.assertTrue(is_newer_version("1.1.0", "1.0.2"))
        self.assertTrue(is_newer_version("v2.0", "1.9.9"))

    def test_equal_or_older_version_is_not_newer(self):
        self.assertFalse(is_newer_version("1.1", "1.1.0"))
        self.assertFalse(is_newer_version("1.0.9", "1.1.0"))

    def test_rejects_invalid_version(self):
        with self.assertRaises(ValueError):
            is_newer_version("latest", "1.0.0")

    def test_hashes_downloaded_update_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "update.exe"
            path.write_bytes(b"verified update")
            self.assertEqual(sha256_file(path), hashlib.sha256(b"verified update").hexdigest())


if __name__ == "__main__":
    unittest.main()
