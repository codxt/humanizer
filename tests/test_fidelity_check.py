"""Regression checks for the mechanical source/edit preservation check."""

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "fidelity_check", Path(__file__).resolve().parents[1] / "scripts" / "fidelity_check.py"
)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def changes(source, edit):
    return {(item["change"], item["category"], item["item"]) for item in check.compare(source, edit)}


class FidelityCheckTests(unittest.TestCase):
    def test_identical_text_is_clean(self):
        text = "We can review the £22 fee if you send the statement by Friday, 14 March."
        self.assertEqual(check.compare(text, text), [])

    def test_filler_removal_is_clean(self):
        source = "It is important to note that the review takes 5 working days."
        edit = "The review takes 5 working days."
        self.assertEqual(check.compare(source, edit), [])

    def test_lost_cutoff_and_limit(self):
        found = changes("Cancel at least 24 hours before renewal.", "Cancel before renewal.")
        self.assertEqual(found, {("lost", "number", "24 hour"), ("lost", "qualifier", "at least")})

    def test_added_apology_and_first_person(self):
        found = changes("We consider the deposit deduction justified.",
                        "We're sorry we wrongly deducted your deposit.")
        self.assertIn(("added", "speech act", "apology"), found)
        self.assertIn(("added", "first person", "we/us/our"), found)

    def test_number_formats_are_equivalent(self):
        self.assertEqual(check.compare("Мы возвращаем 4 500 ₽.", "Мы возвращаем 4500 руб."), [])
        self.assertEqual(check.compare("The fee is $1,500.", "The fee is 1500 USD."), [])

    def test_changed_currency(self):
        found = changes("The fee is £45.", "The fee is $45.")
        self.assertEqual(found, {("lost", "currency", "GBP"), ("added", "currency", "USD")})

    def test_currency_words(self):
        self.assertEqual(check.compare("The fee is £45.", "The fee is 45 pounds."), [])
        self.assertEqual(check.compare("Сбор 45 ₽.", "Сбор 45 руб"), [])
        self.assertIn(("added", "currency", "JPY"), changes("It costs ¥1000.", "It costs 1000 yen."))

    def test_numeric_date_change(self):
        found = changes("Ответ до 12.10.2026.", "Ответ до 12.11.2026.")
        self.assertEqual(found, {("lost", "date", "12.10.2026"), ("added", "date", "12.11.2026")})

    def test_day_month_swap_is_a_change(self):
        self.assertTrue(changes("Ответ до 12.10.2026.", "Ответ до 10.12.2026."))
        self.assertTrue(changes("Due 2026-10-12.", "Due 2026-12-10."))
        self.assertEqual(check.compare("Due 12/10/2026.", "Due 12.10.2026."), [])

    def test_sign_unit_and_magnitude(self):
        self.assertEqual(changes("It was −5 °C.", "It was 5 °C."),
                         {("lost", "number", "-5 °C"), ("added", "number", "5 °C")})
        self.assertEqual(changes("Pay within 30 days.", "Pay within 30 weeks."),
                         {("lost", "number", "30 day"), ("added", "number", "30 week")})
        self.assertIn(("added", "number", "1.5 billion"),
                      changes("Revenue was 1.5 million dollars.", "Revenue was 1.5 billion dollars."))
        self.assertIn(("lost", "number", "5 %"), changes("A 5% fee applies.", "A 5 fee applies."))
        self.assertEqual(check.compare("Ответ в течение 10 рабочих дней.", "Ответим за 10 дней."), [])
        self.assertEqual(check.compare("Revenue was $5m.", "Revenue was 5 million USD."), [])
        self.assertEqual(check.compare("Pages 10-20.", "Pages 10-20."), [])

    def test_weekday_inflection_is_equivalent(self):
        self.assertEqual(check.compare("Пришлите выписку до пятницы.", "До пятницы пришлите выписку."), [])

    def test_lost_weekday(self):
        self.assertIn(("lost", "date word", "friday"),
                      changes("Send it by Friday.", "Send it soon."))

    def test_modality_and_negation(self):
        found = changes("You may not cancel after 5 days.", "You can cancel after 5 days.")
        self.assertIn(("lost", "modality", "may"), found)
        self.assertIn(("added", "modality", "can"), found)
        self.assertIn(("lost", "negation", "not"), found)

    def test_contractions_are_normalized(self):
        self.assertEqual(check.compare("We will not send it.", "We won't send it."), [])

    def test_russian_qualifier_and_modality(self):
        found = changes("Обычно мы обязаны ответить не позднее 3 дней.", "Мы отвечаем за 3 дня.")
        self.assertIn(("lost", "qualifier", "обычно"), found)
        self.assertIn(("lost", "qualifier", "не позднее"), found)
        self.assertIn(("lost", "modality", "обязан"), found)

    def test_names_added_and_lost(self):
        found = changes("The board approved it with Anna Smith.", "The board, led by John Smith, approved it.")
        self.assertIn(("added", "name", "john"), found)
        self.assertIn(("lost", "name", "anna"), found)
        self.assertNotIn(("lost", "name", "smith"), found)

    def test_sentence_initial_word_is_not_a_name(self):
        self.assertEqual(check.compare("Unfortunately, the fee stays.", "The fee stays."), [])
        self.assertEqual(check.compare("Terms: The buyer pays.", "Terms: shipping is included."), [])

    def test_names_in_tables_and_wrapped_lines(self):
        self.assertIn(("added", "name", "john"), changes("| Anna | 45 |", "| John | 45 |"))
        self.assertIn(("added", "name", "john"),
                      changes("The deal was signed with\nAnna Smith on Monday.",
                              "The deal was signed with\nJohn Smith on Monday."))

    def test_identifiers_are_not_names(self):
        for text in ["We use Python3 and GPT4 daily.", "See THIRD_PARTY_NOTICES.md and my_Variable.",
                     "HTTP2 and UTF8 and ISO9001 apply."]:
            self.assertEqual(check.compare(text, text), [], text)

    def test_repository_documents_compare_clean_with_themselves(self):
        root = Path(__file__).resolve().parents[1]
        for path in [root / "README.md", root / "SKILL.md", root / "THIRD_PARTY_NOTICES.md",
                     *sorted((root / "references").glob("*.md"))]:
            text = path.read_text(encoding="utf-8")
            self.assertEqual(check.compare(text, text), [], path.name)

    def test_acronyms_and_latin_abbreviations_are_not_first_person(self):
        found = changes("We approved the plan.", "The US approved the plan.")
        self.assertIn(("lost", "first person", "we/us/our"), found)
        self.assertNotIn(("lost", "first person", "we/us/our"),
                         changes("The US market grew, i.e. sales rose.", "The market grew; sales rose."))
        self.assertNotIn(("lost", "first person", "i/me/my"),
                         changes("The US market grew, i.e. sales rose.", "The market grew; sales rose."))

    def test_speech_act_words_are_specific(self):
        self.assertEqual(check.compare("It is a regrettable outcome.", "It is a bad outcome."), [])
        self.assertEqual(check.compare("Территория простирается на север.", "Территория тянется на север."), [])
        self.assertIn(("lost", "speech act", "apology"), changes("We apologise for the delay.", "The delay continues."))

    def test_english_month_needs_capital(self):
        self.assertEqual(check.compare("The protest march was peaceful.", "The protest walk was peaceful."), [])
        self.assertIn(("lost", "date word", "march"), changes("Due in March.", "Due soon."))

    def test_russian_name_inflection_is_equivalent(self):
        self.assertEqual(check.compare("Решение принял Петров.", "Решение принято Петровым."), [])

    def test_polite_pronoun_is_not_a_name(self):
        self.assertEqual(check.compare("Мы ответим Вам завтра.", "Мы ответим Вам завтра."), [])

    def test_quotation_change(self):
        found = changes('He said "we will refund it" on Monday.', 'He said "we refund it" on Monday.')
        self.assertIn(("lost", "quotation", "we will refund it"), found)
        self.assertIn(("added", "quotation", "we refund it"), found)

    def test_quote_mark_style_is_equivalent(self):
        self.assertEqual(check.compare('Он написал: "вернём деньги".', "Он написал: «вернём деньги»."), [])
        self.assertEqual(check.compare('He said "Hello," she replied.', 'He said "Hello", she replied.'), [])

    def test_blockquote_reflow_is_equivalent(self):
        source = "> We will refund\n> the full amount.\n\nThanks.\n"
        edit = "> We will refund the full amount.\n\nThanks.\n"
        self.assertEqual(check.compare(source, edit), [])

    def test_link_and_code_and_citation(self):
        source = "See https://example.org/terms and run `make test` [3]."
        edit = "See https://example.org/terms-v2 and run `make check` [4]."
        found = changes(source, edit)
        self.assertIn(("lost", "link", "https://example.org/terms"), found)
        self.assertIn(("added", "code", "`make check`"), found)
        self.assertIn(("lost", "citation", "[3]"), found)

    def test_words_inside_code_are_not_prose(self):
        found = check.compare("Run `if not ready: exit 2` now.", "Run `if ready: exit 3` now.")
        self.assertEqual({item["category"] for item in found}, {"code"})

    def test_code_indentation_counts(self):
        source = "```python\nif x:\n    y()\n```\n"
        self.assertTrue(changes(source, "```python\nif x:\ny()\n```\n"))
        self.assertEqual(check.compare(source, source.replace("\n", "\r\n")), [])

    def test_cli_report_strict_and_json(self):
        with tempfile.TemporaryDirectory() as directory:
            source, edit = Path(directory) / "source.md", Path(directory) / "edit.md"
            source.write_text("Pay within 30 days.\n", encoding="utf-8")
            edit.write_text("Pay soon.\n", encoding="utf-8")
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(check.main(["fidelity_check.py", str(source), str(edit)]), 0)
            self.assertIn("lost number: 30 day", out.getvalue())
            with redirect_stdout(io.StringIO()):
                self.assertEqual(check.main(["fidelity_check.py", "--strict", str(source), str(edit)]), 1)
            with redirect_stdout(io.StringIO()) as out:
                check.main(["fidelity_check.py", "--json", str(source), str(edit)])
            self.assertEqual(json.loads(out.getvalue())[0]["item"], "30 day")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(check.main(["fidelity_check.py", "--strict", str(source), str(source)]), 0)

    def test_cli_read_error(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stderr(io.StringIO()):
            missing = str(Path(directory) / "missing.md")
            self.assertEqual(check.main(["fidelity_check.py", missing, missing]), 2)


if __name__ == "__main__":
    unittest.main()
