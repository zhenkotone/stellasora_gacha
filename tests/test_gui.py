import unittest
from unittest.mock import patch

from stellasora_toolkit.gui import is_running_as_administrator


class GuiTests(unittest.TestCase):
    def test_non_windows_is_treated_as_supported(self):
        with patch("stellasora_toolkit.gui.os.name", "posix"):
            self.assertTrue(is_running_as_administrator())
