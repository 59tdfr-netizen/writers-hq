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
    extract_eligibility,
    extract_fee_info,
    extract_organizer,
    is_poetry_only_opportunity,
    extract_eligible_formats,
    find_deadline,
    interleave_source_candidates,
    listing_page_signature,
    source_page_url,
    normalize_title,
    normalize_contest_identity,
    has_duplicate_contest_identity,
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

    def test_cross_source_title_variants_are_recognized_as_same_contest(self):
        title_a = "Конкурс рукописей «Под солнцем фантастики» издательства «Бумба»: научная фантастика и фэнтези (2026)"
        title_b = "Литературный конкурс «Под солнцем фантастики»"
        identity_a = normalize_contest_identity(title_a)
        identity_b = normalize_contest_identity(title_b)
        self.assertTrue(identity_a)
        self.assertTrue(identity_b)
        self.assertTrue(has_duplicate_contest_identity(title_b, "2026-11-30", {identity_a + "|2026-11-30"}))

    def test_cross_source_identity_requires_same_deadline(self):
        title_a = "Конкурс рукописей «Под солнцем фантастики» издательства «Бумба»"
        identity_a = normalize_contest_identity(title_a)
        self.assertFalse(has_duplicate_contest_identity("Литературный конкурс «Под солнцем фантастики»", "2026-12-01", {identity_a + "|2026-11-30"}))

    def test_parse_numeric_date(self):
        match = re.search(r"(?<!\d)(\d{1,2})\s*(?:[./-]\s*)(\d{1,2})\s*(?:[./-]\s*)(20\d{2})(?!\d)", "01.12.2026")
        self.assertEqual(parse_date(match), date(2026, 12, 1))

    def test_parse_russian_month_date(self):
        match = DATE_RE.search("25 ноября 2026")
        self.assertEqual(parse_date(match), date(2026, 11, 25))

    def test_deadline_context_does_not_pick_publication_date(self):
        text = "Опубликовано 10 ноября 2026. Приём заявок до 1 декабря 2026 года."
        self.assertEqual(find_deadline(text, ""), date(2026, 12, 1))

    def test_explicit_closing_date_wins_over_conflicting_summary_date(self):
        text = "Окончание приема заявок: 26 ноября 2026. Срок приема работ: с момента публикации положения до 24 ноября 2026 включительно."
        self.assertEqual(find_deadline(text, ""), date(2026, 11, 24))

    def test_date_range_uses_end_date_not_start_date(self):
        text = "Срок приема работ: с 1 ноября 2026 до 30 декабря 2026."
        self.assertEqual(find_deadline(text, ""), date(2026, 12, 30))

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
        by_name = {source["name"]: source for source in SOURCES}
        self.assertEqual(source_page_url(by_name["ВсеКонкурсы"], 2), "https://vsekonkursy.ru/tvorcheskie-konkursy/literaturnye-konkursy/page/2")
        self.assertEqual(source_page_url(by_name["Конкурсы.Пиши.про"], 2), "https://konkursy.pishi.pro/?page=2")
        self.assertEqual(source_page_url(by_name["Печорин.net"], 2), "https://pechorin.net/competitions?page=2")

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

    def test_source_links_work_without_heading_card_markup(self):
        html = """
        <html><body><table><tr><td>
          <a href="/vse-literaturnye-konkursy/contest-987/">Конкурс прозы для авторов</a>
          <span>Окончание приема заявок: 30 Ноября 2026</span>
        </td></tr></table></body></html>
        """
        links = collect_links(BeautifulSoup(html, "html.parser"), "https://konkursy.pishi.pro/")
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0][0], "Конкурс прозы для авторов")
        self.assertIn("30 Ноября 2026", links[0][2])

    def test_expired_notice_elsewhere_does_not_hide_active_source_link(self):
        html = """
        <html><body>
          <div class="list">
            <div class="contest">
              <h3><a href="/vse-literaturnye-konkursy/active-contest-987/">Активный литературный конкурс</a></h3>
              <p>Окончание приема заявок: 30 Ноября 2026</p>
            </div>
            <div class="notice">Приём заявок завершён у другого конкурса.</div>
          </div>
        </body></html>
        """
        links = collect_links(BeautifulSoup(html, "html.parser"), "https://konkursy.pishi.pro/")
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0][0], "Активный литературный конкурс")

    def test_repeated_listing_page_signature_is_stable(self):
        page_one = [("A", "https://konkursy.pishi.pro/a", "a"), ("B", "https://konkursy.pishi.pro/b", "b")]
        page_two = [("B", "https://konkursy.pishi.pro/b", "other text"), ("A", "https://konkursy.pishi.pro/a", "different text")]
        page_three = [("C", "https://konkursy.pishi.pro/c", "c")]
        self.assertEqual(listing_page_signature(page_one), listing_page_signature(page_two))
        self.assertNotEqual(listing_page_signature(page_one), listing_page_signature(page_three))

    def test_sources_are_interleaved_before_insert_cap(self):
        by_source = {
            SOURCES[0]["name"]: [("P1", "https://konkursy.pishi.pro/1", "p1"), ("P2", "https://konkursy.pishi.pro/2", "p2")],
            SOURCES[1]["name"]: [("C1", "https://pechorin.net/competitions/view/1", "c1")],
            SOURCES[2]["name"]: [("V1", "https://vsekonkursy.ru/1", "v1"), ("V2", "https://vsekonkursy.ru/2", "v2")],
        }
        ordered = list(interleave_source_candidates(by_source).values())
        self.assertEqual([item[0] for item in ordered], ["P1", "C1", "V1", "P2", "V2"])

    def test_eligibility_extracts_minimum_age_from_source(self):
        text = "К участию приглашаются авторы в возрасте от 7 лет независимо от места проживания."
        self.assertIn("от 7 лет", extract_eligibility(text))

    def test_fee_extracts_free_participation(self):
        text = "Участие бесплатное, организационный взнос не предусмотрен."
        fee = extract_fee_info(text)
        self.assertIn("бесплатное", fee)
        self.assertIn("взнос не предусмотрен", fee)

    def test_missing_fee_is_not_claimed_free(self):
        fee = extract_fee_info("Условия подачи заявки опубликованы на сайте организатора.")
        self.assertIn("не указаны", fee)

    def test_eligibility_preserves_age_limit_alongside_general_rules(self):
        text = "К участию в конкурсе приглашаются все желающие, независимо от гражданства и места проживания. Возрастное ограничение от +18."
        eligibility = extract_eligibility(text)
        self.assertIn("независимо от гражданства", eligibility)
        self.assertIn("18", eligibility)

    def test_fee_extracts_exact_entry_fee_amount(self):
        text = "Стоимость участия: Платное. Вступительный взнос: Сумма взноса составляет 555₽."
        self.assertIn("555₽", extract_fee_info(text))

    def test_organizer_extraction_stops_before_next_section(self):
        text = "Организатор: Центральная городская библиотека при поддержке управления культуры. О конкурсе Конкурс посвящён литературе."
        self.assertEqual(
            extract_organizer(text),
            "Центральная городская библиотека при поддержке управления культуры",
        )

    def test_eligible_formats_extracts_explicit_format_label(self):
        text = "Тип принимаемых произведений: Проза, Поэзия. Далее описание конкурса."
        self.assertEqual(extract_eligible_formats(text), ["Проза", "Поэзия"])


    def test_poetry_only_contest_is_rejected(self):
        self.assertTrue(is_poetry_only_opportunity("Конкурс стихов «В рифме Москвы»", "Приём авторских стихотворений", ["Поэзия"]))

    def test_mixed_prose_and_poetry_contest_is_preserved(self):
        self.assertFalse(is_poetry_only_opportunity("Литературный конкурс «Голоса»", "Принимаются рассказы и стихи", ["Проза", "Поэзия"]))

    def test_prose_contest_that_mentions_poetry_is_preserved(self):
        self.assertFalse(is_poetry_only_opportunity("Конкурс прозы «Новые истории»", "Вдохновлённый поэзией конкурс коротких рассказов", ["Проза"]))

    def test_poetry_essay_mixed_contest_is_preserved(self):
        self.assertFalse(is_poetry_only_opportunity("Конкурс стихотворений и эссе «Традиция»", "Принимаются стихи и эссе", ["Поэзия", "Эссе"]))

    def test_organizer_can_be_extracted_from_contest_founders(self):
        self.assertEqual(extract_organizer("Ссылка на профиль организатора: Иван Окончание приема заявок: 30 ноября 2026. Учредители конкурса: lovelegend.online Жюри: автоматически"), "lovelegend.online")

    def test_eligible_formats_stop_before_source_navigation(self):
        self.assertEqual(extract_eligible_formats("Тип принимаемых произведений: Проза Перейти на сайт конкурса Если у вас появились вопросы"), ["Проза"])


if __name__ == "__main__":
    unittest.main()
