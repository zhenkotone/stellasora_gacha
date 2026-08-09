import unittest

from stellasora_toolkit.app_updater import is_newer_version


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


if __name__ == "__main__":
    unittest.main()
