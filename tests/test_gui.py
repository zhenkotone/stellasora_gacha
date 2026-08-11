import unittest
from unittest.mock import patch

from stellasora_toolkit.gui import StellaSoraApp, is_running_as_administrator


class GuiTests(unittest.TestCase):
    def test_non_windows_is_treated_as_supported(self):
        with patch("stellasora_toolkit.gui.os.name", "posix"):
            self.assertTrue(is_running_as_administrator())

    def test_up_name_comparison_normalizes_parentheses_and_spaces(self):
        self.assertTrue(StellaSoraApp._same_item_name("薇洛（盛夏）", "薇洛(盛夏)"))
        self.assertFalse(StellaSoraApp._same_item_name("归途", "鹿鸣"))

    def test_pity_colors_use_green_yellow_and_red_ranges(self):
        self.assertEqual(StellaSoraApp._pity_color(30), "#50c69f")
        self.assertEqual(StellaSoraApp._pity_color(31), "#e7c65e")
        self.assertEqual(StellaSoraApp._pity_color(61), "#df654f")

    def test_pity_bar_uses_the_160_pull_guarantee_scale(self):
        self.assertEqual(StellaSoraApp._pity_bar_width(120, 500), 375)
        self.assertEqual(StellaSoraApp._pity_bar_width(80, 500), 250)
        self.assertEqual(StellaSoraApp._pity_bar_width(160, 500), 500)
