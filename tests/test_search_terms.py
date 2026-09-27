import unittest

from dempa_site.catalog.search_terms import expanded_search_terms


class SearchAliasesTest(unittest.TestCase):
    def test_japanese_and_english_spelling_are_searchable(self):
        self.assertIn("Brouwer", expanded_search_terms("ブラウワーの不動点定理"))
        self.assertIn("ブラウワー", expanded_search_terms("Brouwer fixed-point theorem"))
        self.assertIn("Nikodym", expanded_search_terms("ラドン・ニコディムの定理"))
        self.assertIn("ラドン", expanded_search_terms("Ｒａｄｏｎ–Nikodym"))

    def test_aliases_do_not_infer_unmentioned_subjects(self):
        self.assertNotIn("Brouwer", expanded_search_terms("バナッハの不動点定理"))
        self.assertNotIn("Stone", expanded_search_terms("milestone"))
        self.assertNotIn("ブラウワー", expanded_search_terms("Brouwerian"))
