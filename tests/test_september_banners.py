import unittest
from pathlib import Path

from PIL import Image

from stellasora_toolkit.catalog import gacha_item_name, is_five_star_item
from stellasora_toolkit.gacha_stats import (
    CATEGORY_DISC_LIMITED,
    CATEGORY_TRAVELER_LIMITED,
    build_banner_stats_with_shared_pity,
    build_category_stat,
    classify_history_category,
)
from stellasora_toolkit.gui import OFFICIAL_LIMITED_POOL_INFO, StellaSoraApp


BANNERS = (
    (10139, 139, "艾蕾", "沐于温情笑意中", "2026-09-29", "2026-10-20", "traveler"),
    (20139, 214061, "睡前童话", "空白的稚梦", "2026-09-29", "2026-10-20", "disc"),
    (11110, 110, "翡冷翠", "辉映碧玉的理型", "2026-10-06", "2026-10-27", "traveler"),
    (21110, 214004, "仙踪良梦", "微醺茶香，藤花幽梦", "2026-10-06", "2026-10-27", "disc"),
)


class SeptemberBannerTests(unittest.TestCase):
    def test_names_rarity_and_banner_metadata(self):
        for gid, item_id, name, title, start, end, kind in BANNERS:
            with self.subTest(gid=gid):
                self.assertTrue(is_five_star_item(item_id))
                self.assertEqual(gacha_item_name(item_id), name)
                self.assertEqual(OFFICIAL_LIMITED_POOL_INFO[gid], (title, start, end, name))
                category = CATEGORY_TRAVELER_LIMITED if kind == "traveler" else CATEGORY_DISC_LIMITED
                self.assertEqual(classify_history_category([{"Gid": gid}]), category)

    def test_each_banner_distinguishes_up_from_off_banner(self):
        for gid, item_id, _name, _title, _start, _end, kind in BANNERS:
            with self.subTest(gid=gid):
                self.assertTrue(StellaSoraApp._is_up_item(gid, item_id))
                off_banner = 135 if kind == "traveler" else 214001
                self.assertFalse(StellaSoraApp._is_up_item(gid, off_banner))

    def test_bundled_artwork_decodes(self):
        root = Path(__file__).resolve().parents[1] / "assets"
        for _gid, item_id, _name, _title, _start, _end, kind in BANNERS:
            with self.subTest(item_id=item_id):
                folder = "travelers" if kind == "traveler" else "discs"
                with Image.open(root / folder / f"{item_id}.png") as image:
                    image.load()
                    self.assertEqual(image.format, "PNG")
                    self.assertGreaterEqual(min(image.size), 128)
                    if item_id == 214061:
                        self.assertEqual(image.size, (512, 512))

    def test_home_pity_and_five_star_intervals_stay_separate(self):
        for gid, item_id, _name, _title, _start, _end, kind in BANNERS:
            with self.subTest(gid=gid):
                off_banner = 135 if kind == "traveler" else 214001
                groups = [{"Gid": gid, "Time": 100, "Ids": [item_id, 211001, off_banner, 211001]}]
                home = build_category_stat(groups, is_up=StellaSoraApp._is_up_item)
                history = build_category_stat(groups)
                self.assertEqual(home.current_pity, 3)
                self.assertEqual(history.current_pity, 1)
                groups.append({"Gid": gid, "Time": 200, "Ids": [item_id]})
                history = build_banner_stats_with_shared_pity(groups)[0]
                self.assertEqual(history.five_stars[0].pity, 2)
                self.assertEqual(build_category_stat(groups, is_up=StellaSoraApp._is_up_item).current_pity, 0)

    def test_rerun_has_own_totals_and_inherits_five_star_interval(self):
        for old_gid, new_gid, item_id in ((10110, 11110, 110), (20110, 21110, 214004)):
            with self.subTest(gid=new_gid):
                pools = {pool.gid: pool for pool in build_banner_stats_with_shared_pity([
                    {"Gid": old_gid, "Time": 100, "Ids": [item_id, 211001, 211001]},
                    {"Gid": new_gid, "Time": 200, "Ids": [211001, item_id]},
                ])}
                self.assertEqual(pools[old_gid].total_pulls, 3)
                self.assertEqual(pools[new_gid].total_pulls, 2)
                self.assertEqual(pools[new_gid].five_stars[0].pity, 4)
