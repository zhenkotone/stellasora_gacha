import unittest

from stellasora_toolkit.catalog import format_attr_value, gacha_item_name, traveler_name


class CatalogTests(unittest.TestCase):
    def test_known_traveler_name(self):
        self.assertEqual(traveler_name(142), "珂赛特")
        self.assertEqual(gacha_item_name(142), "珂赛特")

    def test_unknown_item_stays_identifiable(self):
        self.assertEqual(gacha_item_name(999999), "物品 #999999")

    def test_disc_ids_resolve_to_catalog_names(self):
        self.assertEqual(gacha_item_name(211002), "和煦")
        self.assertEqual(gacha_item_name(213026), "清扫时间DA♥YO")

    def test_small_float_is_formatted_as_percent(self):
        self.assertEqual(format_attr_value(0.063), "6.3%")


if __name__ == "__main__":
    unittest.main()
