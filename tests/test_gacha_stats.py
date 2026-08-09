import unittest

from stellasora_toolkit.gacha_stats import (
    CATEGORY_DISC_LIMITED,
    CATEGORY_DISC_STANDARD,
    CATEGORY_TRAVELER_LIMITED,
    CATEGORY_TRAVELER_STANDARD,
    build_pool_stats,
    build_category_stat,
    classify_history_category,
)
from stellasora_toolkit.service import merge_gacha_categories


class GachaStatsTests(unittest.TestCase):
    def test_groups_by_pool_and_resets_pity_after_five_star(self):
        groups = [
            {"Gid": 10, "Time": 100, "Ids": [1, 2, 156, 3]},
            {"Gid": 10, "Time": 101, "Ids": [4, 160]},
            {"Gid": 20, "Time": 90, "Ids": [156]},
        ]
        pools = {pool.gid: pool for pool in build_pool_stats(groups)}
        self.assertEqual(pools[10].total_pulls, 6)
        self.assertEqual([pull.pity for pull in pools[10].five_stars], [3, 3])
        self.assertEqual(pools[10].average_pulls, 3)
        self.assertEqual(pools[20].five_stars[0].pity, 1)

    def test_pool_without_five_star_has_no_average(self):
        pool = build_pool_stats([{"Gid": 10, "Time": 100, "Ids": [1, 2]}])[0]
        self.assertIsNone(pool.average_pulls)

    def test_category_stat_merges_banner_ids(self):
        stat = build_category_stat([
            {"Gid": 10110, "Time": 100, "Ids": [1, 110]},
            {"Gid": 10120, "Time": 101, "Ids": [2, 120, 160]},
        ])
        self.assertIsNotNone(stat)
        self.assertEqual(stat.total_pulls, 5)
        self.assertEqual([hit.pity for hit in stat.five_stars], [3, 2])
        self.assertEqual([hit.item_id for hit in stat.five_stars], [160, 110])

    def test_classifies_the_four_official_history_types_from_pool_ids(self):
        self.assertEqual(classify_history_category([{"Gid": 10160}]), CATEGORY_TRAVELER_LIMITED)
        self.assertEqual(classify_history_category([{"Gid": 20160}]), CATEGORY_DISC_LIMITED)
        self.assertEqual(classify_history_category([{"Gid": 1}]), CATEGORY_TRAVELER_STANDARD)
        self.assertEqual(classify_history_category([{"Gid": 2}]), CATEGORY_DISC_STANDARD)

    def test_archive_merge_deduplicates_and_preserves_old_categories(self):
        old = {1: [{"Gid": 10, "Time": 100, "Ids": [1]}], 2: [{"Gid": 2, "Time": 90, "Ids": [2]}]}
        current = {1: [{"Gid": 10, "Time": 100, "Ids": [1]}, {"Gid": 11, "Time": 110, "Ids": [3]}]}
        merged = merge_gacha_categories(old, current)
        self.assertEqual(len(merged[1]), 2)
        self.assertIn(2, merged)


if __name__ == "__main__":
    unittest.main()
