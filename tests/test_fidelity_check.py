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
        self.assertEqual(found, {("lost", "number", "24"), ("lost", "qualifier", "at least")})

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

    def test_dotted_date_splits_into_parts(self):
        found = changes("Ответ до 12.10.2026.", "Ответ до 12.11.2026.")
        self.assertEqual(found, {("lost", "number", "10"), ("added", "number", "11")})

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
        self.assertEqual(check.compare("Run `if not ready: exit 2`.", "Run `if not ready: exit 2`."), [])
        self.assertEqual(check.compare("Use `--no-cache`.", "Use `--no-cache` here."), [])

    def test_cli_report_strict_and_json(self):
        with tempfile.TemporaryDirectory() as directory:
            source, edit = Path(directory) / "source.md", Path(directory) / "edit.md"
            source.write_text("Pay within 30 days.\n", encoding="utf-8")
            edit.write_text("Pay soon.\n", encoding="utf-8")
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(check.main(["fidelity_check.py", str(source), str(edit)]), 0)
            self.assertIn("lost number: 30", out.getvalue())
            with redirect_stdout(io.StringIO()):
                self.assertEqual(check.main(["fidelity_check.py", "--strict", str(source), str(edit)]), 1)
            with redirect_stdout(io.StringIO()) as out:
                check.main(["fidelity_check.py", "--json", str(source), str(edit)])
            self.assertEqual(json.loads(out.getvalue())[0]["item"], "30")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(check.main(["fidelity_check.py", "--strict", str(source), str(source)]), 0)

    def test_cli_read_error(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stderr(io.StringIO()):
            missing = str(Path(directory) / "missing.md")
            self.assertEqual(check.main(["fidelity_check.py", missing, missing]), 2)


if __name__ == "__main__":
    unittest.main()
