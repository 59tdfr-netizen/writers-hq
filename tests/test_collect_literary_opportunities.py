import unittest
from datetime import date

from scripts.collect_literary_opportunities import (
    EXPIRED_MARKER,
    GENERIC_ROUNDUP_TITLE,
    canonical_url,
    find_deadline,
    normalize_title,
    parse_date,
)
import re


class CollectorParsingTests(unittest.TestCase):
    def test_canonical_url_removes_tracking_and_trailing_slash(self):
        self.assertEqual(
            canonical_url("HTTPS://VSEKONKURSY.RU/example/?utm_source=test#top"),
            "https://vsekonkursy.ru/example",
        )

    def test_title_normalization_matches_database_key_style(self):
        self.assertEqual(
            normalize_title(" Конкурс «В рифме Москвы»! "),
            "конкурсврифмемосквы",
        )

    def test_parse_numeric_date(self):
        match = re.search(r"(?<!\\d)(\\d{1,2})\\s*(?:[./-]\\s*)(\\d{1,2})\\s*(?:[./-]\\s*)(20\\d{2})(?!\\d)", "01.12.2026")
        self.assertEqual(parse_date(match), date(2026, 12, 1))

    def test_parse_russian_month_date(self):
        match = re.search(r"(\\d{1,2})\\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\\s+(20\\d{2})", "25 ноября 2026")
        self.assertEqual(parse_date(match), date(2026, 11, 25))

    def test_deadline_context_does_not_pick_publication_date(self):
        text = "Опубликовано 10 ноября 2026. Приём заявок до 1 декабря 2026 года."
        self.assertEqual(find_deadline(text, ""), date(2026, 12, 1))

    def test_roundup_is_not_individual_opportunity(self):
        self.assertTrue(GENERIC_ROUNDUP_TITLE.fullmatch("Конкурсы ноября"))
        self.assertTrue(GENERIC_ROUNDUP_TITLE.fullmatch("Все конкурсы декабря 2026"))
        self.assertFalse(GENERIC_ROUNDUP_TITLE.fullmatch("Конкурс рассказов «Новые мифы Сибири»"))

    def test_explicit_expired_marker_detected(self):
        self.assertTrue(EXPIRED_MARKER.search("Приём заявок завершён"))
        self.assertFalse(EXPIRED_MARKER.search("Читайте наш архив конкурсов"))

    def test_missing_deadline_is_not_guessed(self):
        self.assertIsNone(find_deadline("Подробности на сайте организатора", ""))


if __name__ == "__main__":
    unittest.main()
