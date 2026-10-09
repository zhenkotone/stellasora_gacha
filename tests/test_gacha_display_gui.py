import unittest
from datetime import datetime
from unittest.mock import Mock, patch

from stellasora_toolkit.gacha_display import CN_TIMEZONE, SparkReward
from stellasora_toolkit.gacha_stats import (
    CATEGORY_DISC_LIMITED,
    CATEGORY_TRAVELER_LIMITED,
    FiveStarPull,
)
from stellasora_toolkit.gui import GACHA_CATEGORY_ORDER, StellaSoraApp


def reward_only_groups(gid=10139):
    timestamp = int(datetime(2026, 10, 8, 12, tzinfo=CN_TIMEZONE).timestamp())
    return [{"Gid": gid, "Time": timestamp, "Ids": [211001] * 120}]


def mock_app(categories):
    app = StellaSoraApp.__new__(StellaSoraApp)
    app.snapshot = object()
    app._semantic_gacha_categories = Mock(return_value=categories)
    app.stats_content = Mock()
    app.stats_content.winfo_children.return_value = []
    app.avatar_images = []
    app.pool_columns = Mock()
    app.pool_columns.get.return_value = 2
    app._build_home_summary = Mock()
    app._build_pool_section = Mock()
    app._build_missing_category = Mock()
    app.gacha_rows_content = Mock()
    app.gacha_rows_content.winfo_children.return_value = []
    app.gacha_rows = {}
    app.gacha_avatar_images = []
    app.gacha_category_filter = Mock()
    app.gacha_category_filter.get.return_value = "all"
    app._add_gacha_category_heading = Mock()
    app._add_five_star_banner_card = Mock()
    return app


class SparkDisplayGuiTests(unittest.TestCase):
    def test_reward_progress_has_only_spark_label_and_fixed_short_bar(self):
        reward = SparkReward(10139, 139, "up", 0, 1, 0)
        for available in (200, 500, 1000):
            with self.subTest(available=available):
                canvas = Mock()
                StellaSoraApp._draw_history_progress(canvas, available, reward, 160)
                canvas.delete.assert_called_once_with("all")
                canvas.create_rectangle.assert_called_once_with(0, 3, 80, 41, fill="#e7c65e", outline="")
                canvas.create_text.assert_called_once()
                self.assertEqual(canvas.create_text.call_args.kwargs["text"], "\u4e95")

    def test_real_history_progress_preserves_numeric_label_color_and_scale(self):
        for pity, limit, expected_width, expected_color in (
            (20, 160, 80, "#50c69f"),
            (50, 160, 155, "#e7c65e"),
            (75, 160, 232, "#df654f"),
            (90, 120, 372, "#df654f"),
            (160, 160, 496, "#df654f"),
        ):
            with self.subTest(pity=pity, limit=limit):
                canvas = Mock()
                pull = FiveStarPull(139, "traveler", "up", pity, 0, pity, 10139)
                StellaSoraApp._draw_history_progress(canvas, 500, pull, limit)
                canvas.create_rectangle.assert_called_once_with(0, 3, expected_width, 41, fill=expected_color, outline="")
                canvas.create_text.assert_called_once()
                self.assertEqual(canvas.create_text.call_args.kwargs["text"], f"{pity} \u62bd")

    def test_home_renders_reward_only_banner_without_adding_real_statistics(self):
        app = mock_app({CATEGORY_TRAVELER_LIMITED: reward_only_groups()})
        with patch("stellasora_toolkit.gui.ttk.Frame"), patch("stellasora_toolkit.gui.ttk.Label"), patch("stellasora_toolkit.gui.ttk.Radiobutton"):
            app._fill_five_star_stats()
        app._build_pool_section.assert_called_once()
        call = app._build_pool_section.call_args
        pool = call.args[0]
        self.assertEqual(pool.total_pulls, 120)
        self.assertEqual(pool.five_stars, ())
        entries = call.kwargs["display_entries"]
        self.assertEqual(len(entries), 1)
        self.assertIsInstance(entries[0], SparkReward)
        self.assertEqual(entries[0].item_id, 139)
        self.assertEqual(call.kwargs["category"], CATEGORY_TRAVELER_LIMITED)
        self.assertEqual(app._build_missing_category.call_count, len(GACHA_CATEGORY_ORDER) - 1)
        summary = app._build_home_summary.call_args.args[0][CATEGORY_TRAVELER_LIMITED]
        self.assertEqual(summary.current_pity, 120)
        self.assertEqual(summary.five_stars, ())

    def test_history_renders_reward_only_banner_but_not_disc_reward(self):
        app = mock_app({
            CATEGORY_TRAVELER_LIMITED: reward_only_groups(),
            CATEGORY_DISC_LIMITED: reward_only_groups(20139),
        })
        app._fill_gacha()
        app._add_gacha_category_heading.assert_called_once_with(0, CATEGORY_TRAVELER_LIMITED, 1)
        app._add_five_star_banner_card.assert_called_once()
        call = app._add_five_star_banner_card.call_args
        self.assertEqual(call.args[0:2], (1, CATEGORY_TRAVELER_LIMITED))
        self.assertEqual(call.args[2].five_stars, ())
        self.assertEqual(call.args[2].total_pulls, 120)
        self.assertIsInstance(call.kwargs["reward"], SparkReward)
        self.assertEqual(call.kwargs["reward"].item_id, 139)


if __name__ == "__main__":
    unittest.main()
