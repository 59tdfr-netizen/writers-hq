import unittest

from scripts.collect_literary_opportunities import is_roundup_title


class RoundupTitleTests(unittest.TestCase):
    def test_monthly_roundup_is_rejected(self):
        self.assertTrue(is_roundup_title("Конкурсы ноября"))
        self.assertTrue(is_roundup_title("Конкурсы ноября 2026"))
        self.assertTrue(is_roundup_title("Подборка конкурсов декабря"))
        self.assertTrue(is_roundup_title("Список конкурсов на марта"))

    def test_individual_opportunities_are_not_rejected(self):
        self.assertFalse(is_roundup_title("Литературный конкурс «Есть только музыка одна»"))
        self.assertFalse(is_roundup_title("Конкурс «Живое слово» для школьников"))
        self.assertFalse(is_roundup_title("Литературный конкурс авторской сказки «Новые мифы Сибири»"))


if __name__ == "__main__":
    unittest.main()
