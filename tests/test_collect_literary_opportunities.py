import unittest
import re
from datetime import date

from bs4 import BeautifulSoup

from scripts.collect_literary_opportunities import (
    SOURCES,
    DATE_RE,
    EXPIRED_MARKER,
    GENERIC_ROUNDUP_TITLE,
    canonical_url,
    collect_links,
    find_deadline,
    source_page_url,
    normalize_title,
    parse_date,
)


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
        match = re.search(r"(?<!\d)(\d{1,2})\s*(?:[./-]\s*)(\d{1,2})\s*(?:[./-]\s*)(20\d{2})(?!\d)", "01.12.2026")
        self.assertEqual(parse_date(match), date(2026, 12, 1))

    def test_parse_russian_month_date(self):
        match = DATE_RE.search("25 ноября 2026")
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

    def test_source_pagination_urls(self):
        self.assertEqual(source_page_url(SOURCES[0], 2), "https://vsekonkursy.ru/tvorcheskie-konkursy/literaturnye-konkursy/page/2")
        self.assertEqual(source_page_url(SOURCES[1], 2), "https://konkursy.pishi.pro/?page=2")
        self.assertEqual(source_page_url(SOURCES[2], 2), "https://pechorin.net/competitions?page=2")

    def test_pishi_listing_extracts_only_contest_detail_links(self):
        html = """
        <html><body>
          <div class="item"><h3><a href="/vse-literaturnye-konkursy/test-contest-123/">Конкурс литературной прозы</a></h3><p>Дедлайн 30 ноября 2026</p></div>
          <a href="/vse-literaturnye-konkursy/">Все конкурсы</a>
        </body></html>
        """
        links = collect_links(BeautifulSoup(html, "html.parser"), "https://konkursy.pishi.pro/")
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0][0], "Конкурс литературной прозы")
        self.assertEqual(links[0][1], "https://konkursy.pishi.pro/vse-literaturnye-konkursy/test-contest-123")

    def test_pechorin_listing_extracts_competition_detail_links(self):
        html = """
        <html><body>
          <div class="item"><h3><a href="/competitions/view/test-contest">Литературная премия для авторов</a></h3><p>Приём работ до: 30 ноября 2026 года</p></div>
          <a href="/competitions">Раздел конкурсов</a>
        </body></html>
        """
        links = collect_links(BeautifulSoup(html, "html.parser"), "https://pechorin.net/competitions")
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0][0], "Литературная премия для авторов")
        self.assertEqual(links[0][1], "https://pechorin.net/competitions/view/test-contest")

    def test_end_of_application_phrase_is_deadline_context(self):
        text = "Окончание приема заявок: 01 Декабря 2026. Организатор сообщает результаты позже."
        self.assertEqual(find_deadline(text, ""), date(2026, 12, 1))


if __name__ == "__main__":
    unittest.main()
