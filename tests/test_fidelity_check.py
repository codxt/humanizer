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

    def test_very_long_digit_run_does_not_crash(self):
        text = "Code " + "7" * 5000 + "."
        self.assertEqual(check.compare(text, text), [])
        self.assertTrue(changes(text, "Code 7."))

    def test_dots_never_group_thousands(self):
        self.assertTrue(changes("Yield was 1.500 tons.", "Yield was 1500 tons."))
        self.assertNotIn(("added", "number", "250"), changes("Take 0.25 mg daily.", "Take 0.250 mg daily."))

    def test_comma_is_decimal_in_cyrillic_text(self):
        self.assertTrue(changes("Вес 1,500 кг.", "Вес 1500 кг."))
        self.assertEqual(check.compare("Вес 1,5 кг.", "Вес 1.5 кг."), [])
        self.assertEqual(check.compare("The fee is 1,500 USD.", "The fee is 1500 USD."), [])

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
        self.assertEqual(check.compare("Ответ в течение 10 календарных дней.", "Ответим за 10 дней."), [])
        self.assertIn(("lost", "number", "10 business day"),
                      changes("Ответ в течение 10 рабочих дней.", "Ответим за 10 дней."))
        self.assertIn(("lost", "number", "10 business day"),
                      changes("Payment is due in 10 business days.", "Payment is due in 10 days."))
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

    def test_names_after_abbreviations_and_initials(self):
        self.assertIn(("added", "name", "petrov"),
                      changes("We paid Dr. Ivanov 500 rubles.", "We paid Dr. Petrov 500 rubles."))
        self.assertIn(("added", "name", "globex"),
                      changes("Some vendors, e.g. Acme, refused.", "Some vendors, e.g. Globex, refused."))
        self.assertIn(("added", "name", "сидор"),
                      changes("Подписал И. Петров.", "Подписал И. Сидоров."))

    def test_business_prefix_applies_to_every_time_unit(self):
        self.assertEqual(changes("We respond within 10 working hours.", "We respond within 10 working minutes."),
                         {("lost", "number", "10 business hour"), ("added", "number", "10 business minute")})
        self.assertIn(("lost", "number", "10 business hour"),
                      changes("Срок 10 рабочих часов.", "Срок 10 часов."))

    def test_dotted_and_russian_abbreviations(self):
        self.assertIn(("added", "name", "congress"),
                      changes("The U.S. Treasury issued notes.", "The U.S. Congress issued notes."))
        self.assertIn(("added", "name", "sidorov"), changes("Ph.D. Ivanov signed.", "Ph.D. Sidorov signed."))
        self.assertIn(("added", "name", "сидор"), changes("См. Петров в приложении.", "См. Сидоров в приложении."))

    def test_ruble_adjectives(self):
        self.assertIn(("lost", "currency", "RUB"), changes("Рублёвые активы выросли.", "Валютные активы выросли."))
        self.assertEqual(check.compare("Оплата рублём.", "Оплата в рублях."), [])

    def test_appreciation_as_gratitude_only(self):
        self.assertEqual(check.compare("The asset appreciation was noted.", "The asset value increase was noted."), [])
        self.assertEqual(check.compare("We express our appreciation for your patience.",
                                       "We express our gratitude for your patience."), [])

    def test_state_code_me_is_not_first_person(self):
        self.assertNotIn(("lost", "first person", "i/me/my"), changes("Maine (ME) operations.", "Maine operations."))

    def test_sign_kept_in_a_number_list(self):
        self.assertIn(("lost", "number", "-20"), changes("Readings 1 2 -20 were logged.", "Readings 1 2 20 were logged."))

    def test_wednesday_with_na_and_modifier(self):
        self.assertEqual(check.compare("Встреча на прошлую среду.", "Встреча в прошлую среду."), [])

    def test_inline_code_with_long_delimiters(self):
        self.assertTrue(changes("Run ```x``` now.", "Run ```y``` now."))
        self.assertEqual(check.compare("Run ``x`` now.", "Run ```x``` now."), [])

    def test_appreciative_counts_as_thanks(self):
        self.assertEqual(check.compare("We are appreciative of your help.", "We are grateful for your help."), [])

    def test_range_after_space_grouped_number(self):
        self.assertEqual(check.compare("Pages 10 000 -20 000.", "Pages 10 000–20 000."), [])
        self.assertIn(("lost", "number", "-20"), changes("Readings 1 2 -20 were logged.", "Readings 1 2 20 were logged."))

    def test_ruble_adjective_is_not_a_place_or_surname(self):
        self.assertEqual(check.compare("Мы говорили о Рублёвке. Рублёвка застроена.",
                                       "Мы говорили о Рублёвке. Этот район застроен."), [])
        self.assertEqual(check.compare("Рублёв написал икону.", "Он написал икону."), [])
        self.assertIn(("lost", "currency", "RUB"), changes("Рублёвые активы выросли.", "Активы выросли."))

    def test_seconds_and_milliseconds(self):
        self.assertTrue(changes("Wait 10 seconds.", "Wait 10 milliseconds."))
        self.assertEqual(check.compare("Latency is 10ms.", "Latency is 10 ms."), [])
        self.assertEqual(check.compare("Latency is 10 ms.", "Latency is 10 msec."), [])
        self.assertEqual(check.compare("Wait 10 sec.", "Wait 10 s."), [])
        self.assertEqual(check.compare("2 MS patients were enrolled.", "2 patients with MS were enrolled."), [])

    def test_glued_and_spaced_units_agree(self):
        for source, edit in [("Wait 10s.", "Wait 10 s."), ("Wait 10 s.", "Wait 10sec."),
                             ("Wait 10 msec.", "Wait 10msec."), ("Wait 10 msec.", "Wait 10 msecs."),
                             ("Wait 10min.", "Wait 10 minutes."), ("Latency 10MS.", "Latency 10 MS."),
                             ("Wait 10msecs.", "Wait 10 msecs."), ("Wait 10hours.", "Wait 10 hours."),
                             ("Wait 10hr.", "Wait 10 h."), ("Wait 10day.", "Wait 10 d."),
                             ("Срок 10час.", "Срок 10 ч."), ("Rate 10percent.", "Rate 10 %."),
                             ("Rate 10percent.", "Rate 10 per cent."), ("Rate 10 percent.", "Rate 10 per cent."),
                             ("We spent 5 bn.", "We spent 5 billion."),
                             ("# 10 Per Cent Growth", "# 10 per cent growth"), ("Rate 10 per  cent now.", "Rate 10 per cent now."),
                             ("Rate 10 per\u00a0cent.", "Rate 10 per cent."), ("Rate 10 per\ncent.", "Rate 10 per cent."),
                             ("Rate 10-per-cent now.", "Rate 10 per cent now."),
                             ("Revenue 4K.", "Revenue 4 thousand."), ("It took 10H.", "It took 10 h."),
                             ("Rate 10 Per Cent now.", "Rate 10% now."), ("Rate 10 PER CENT now.", "Rate 10 percent now.")]:
            self.assertEqual(check.compare(source, edit), [], (source, edit))
        self.assertEqual(check.compare("Revenue was $5m.", "Revenue was 5 million USD."), [])
        self.assertEqual(check.compare("It took 24h.", "It took 24 hours."), [])
        self.assertTrue(changes("Wait 10 ms.", "Wait 10 s."))
        self.assertTrue(changes("It took 5m.", "It took 5 m."))  # glued m is million; spaced m is not a unit
        self.assertTrue(changes("It took 10 H.", "It took 10 h."))  # spaced uppercase H is not a unit

    def test_closing_fence_width_is_style(self):
        self.assertEqual(check.compare("```\na\n```\nb\n", "```\na\n````\nb\n"), [])

    def test_code_spans_and_bodies_agree_on_line_ends(self):
        # U+2029 is not a line end, so the fence stays open and the rest of the text is code.
        self.assertEqual(check._code("```\na\u2029```\nb\n"), {"a\u2029```\nb": 1})
        self.assertEqual(check._code("```\na\n```\nb\n"), {"a": 1})
        self.assertEqual(check._code("```\na\n```\rprose"), {"a": 1})  # a lone CR ends the closing fence
        self.assertEqual(check._code("```\na\x0c```\nb\n"), {"a\x0c```\nb": 1})  # nor does a form feed
        self.assertEqual(check._code("Run ```a\u2028b``` now."), {"a\u2028b": 1})

    def test_percent_words_are_names_outside_a_percent(self):
        self.assertIn(("lost", "name", "per"), changes("We met Per Hansen.", "We met Hansen."))
        self.assertIn(("lost", "name", "cent"), changes("We liked 50 Cent.", "We liked 50."))
        self.assertEqual(check.compare("Rate 10 Per Cent now.", "Rate 10% now."), [])

    def test_unit_does_not_cross_a_block(self):
        self.assertEqual(check.compare("- Revenue: 10\n- Per cent growth target", "- Revenue: 10\n- Growth target"), [])
        self.assertEqual(check.compare("Revenue: 10\n\n---\n\nPer cent growth.", "Revenue: 10\n\n---\n\nGrowth."), [])
        self.assertEqual(check.compare("We waited 10\nhours.", "We waited 10 hours."), [])  # a soft wrap still joins
        self.assertEqual(check.compare("Rate 10\u2009hours.", "Rate 10 hours."), [])  # thin space
        self.assertEqual(check.compare("Rate 10\u202fhours.", "Rate 10 hours."), [])  # narrow no-break space
        self.assertEqual(check.compare("It took 24\n-hour.", "It took 24-hour."), [])  # wrapped hyphen, not a list
        self.assertEqual(check.compare("Срок 10\n-рабочих дней.", "Срок 10 рабочих дней."), [])
        self.assertIn(("lost", "name", "percent"), changes("We use Percent.", "We use it."))

    def test_sign_kept_after_comma_separated_numbers(self):
        self.assertIn(("lost", "number", "-20 °C"),
                      changes("In March 2024, 500 -20 °C readings were logged.",
                              "In March 2024, 500 20 °C readings were logged."))

    def test_colloquial_ruble_genitive(self):
        self.assertEqual(check.compare("Он заплатил 100 рублёв.", "Он заплатил 100 рублей."), [])
        self.assertIn(("lost", "currency", "RUB"), changes("Рублёвою монетой заплатили.", "Монетой заплатили."))

    def test_code_body_ignores_other_line_separators(self):
        self.assertTrue(changes("Run ```a\u2029b``` now.", "Run ```x\u2029b``` now."))

    def test_inline_code_inner_space_counts(self):
        self.assertTrue(changes("Run ` make` now.", "Run `make` now."))
        self.assertEqual(check.compare("Run `` `x` `` now.", "Run `` `x` `` now."), [])

    def test_mixed_script_word_compares_clean_with_itself(self):
        self.assertEqual(check.compare("We met BweMEдней yesterday.", "We met BweMEдней yesterday."), [])

    def test_names_after_a_colon_are_compared(self):
        self.assertIn(("added", "name", "jane"), changes("Attendees: Anna and John.", "Attendees: Jane and John."))
        self.assertIn(("added", "name", "jane"),
                      changes("The signatory was: John Smith.", "The signatory was: Jane Smith."))

    def test_all_caps_first_person_counts(self):
        self.assertEqual(check.compare("We approved the plan.", "WE APPROVED THE PLAN."), [])
        self.assertEqual(check.compare("Мы согласны.", "МЫ СОГЛАСНЫ."), [])

    def test_more_speech_act_forms(self):
        self.assertIn(("lost", "speech act", "thanks"),
                      changes("We express our appreciation for your patience.", "We acknowledge your patience."))
        self.assertIn(("lost", "speech act", "apology"),
                      changes("I regretfully inform you that the date moved.", "I inform you that the date moved."))

    def test_ruble_words_are_specific(self):
        self.assertEqual(check.compare("Приготовьте рубленую капусту.", "Приготовьте шинкованную капусту."), [])
        self.assertEqual(check.compare("Сбор 45 рублей.", "Сбор 45 ₽."), [])

    def test_wednesday_phrases(self):
        self.assertIn(("lost", "date word", "wednesday"), changes("Ответим в эту среду.", "Ответим на этой неделе."))
        self.assertEqual(check.compare("Влияние на среду велико.", "Влияние на окружающую среду велико."), [])

    def test_code_fence_tag_and_backtick_width_are_style(self):
        self.assertEqual(check.compare("```python\nx = 1\n```\n", "```py\nx = 1\n```\n"), [])
        self.assertEqual(check.compare("Run `make` now.", "Run ``make`` now."), [])

    def test_spaced_hyphen_after_number_is_a_range(self):
        self.assertEqual(check.compare("Pages 10 -20.", "Pages 10-20."), [])
        self.assertIn(("lost", "number", "-20 °C"), changes("It fell to -20 °C.", "It fell to 20 °C."))

    def test_many_quotations_are_fast(self):
        import time
        text = " ".join(f'"quote {i}"' for i in range(4000))
        start = time.monotonic()
        self.assertEqual(check.compare(text, text), [])
        self.assertLess(time.monotonic() - start, 3)

    def test_nested_quotation_is_compared_once(self):
        self.assertEqual(check.compare("Он сказал: «Это „важно“ для нас».", "Он сказал: «Это „важно“ для нас»."), [])
        self.assertIn(("added", "quotation", "Это „срочно“ для нас"),
                      changes("Он сказал: «Это „важно“ для нас».", "Он сказал: «Это „срочно“ для нас»."))

    def test_trailing_ellipsis_is_not_part_of_a_link(self):
        self.assertEqual(check.compare("See https://x.test/a…", "See https://x.test/a."), [])

    def test_names_in_tables_and_wrapped_lines(self):
        self.assertIn(("added", "name", "john"), changes("| Anna | 45 |", "| John | 45 |"))
        self.assertIn(("added", "name", "john"),
                      changes("The deal was signed with\nAnna Smith on Monday.",
                              "The deal was signed with\nJohn Smith on Monday."))

    def test_long_all_caps_name_may_change_case(self):
        found = changes("Договор с ООО РОМАШКА подписан.", "Договор с ООО Ромашка подписан.")
        self.assertNotIn(("lost", "name", "РОМАШКА"), found)
        self.assertIn(("lost", "name", "US"), changes("The US approved it.", "The us approved it."))

    def test_wednesday_only_as_a_day(self):
        self.assertIn(("lost", "date word", "wednesday"), changes("Ответим в среду.", "Ответим на этой неделе."))
        self.assertEqual(check.compare("Это важно в среде разработчиков.", "Это важно для разработчиков."), [])

    def test_long_unspaced_input_is_linear(self):
        import time
        start = time.monotonic()
        check.profile("a.b.c.d." * 8000)
        self.assertLess(time.monotonic() - start, 5)

    def test_identifiers_are_not_names(self):
        for text in ["We use Python3 and GPT4 daily.", "See THIRD_PARTY_NOTICES.md and my_Variable.",
                     "HTTP2 and UTF8 and ISO9001 apply."]:
            self.assertEqual(check.compare(text, text), [], text)

    def test_repository_documents_compare_clean_with_themselves(self):
        root = Path(__file__).resolve().parents[1]
        # An installed copy of the skill may carry only SKILL.md and references/.
        paths = [root / "README.md", root / "SKILL.md", root / "THIRD_PARTY_NOTICES.md",
                 *sorted((root / "references").glob("*.md"))]
        present = [path for path in paths if path.is_file()]
        self.assertIn(root / "SKILL.md", present)
        for path in present:
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

    def test_quotation_next_to_inline_code(self):
        for source, edit in (
            ('Run `x`"we will refund it" now.', "Run `x` now."),
            ('Run "we will refund it"`x` now.', "Run `x` now."),
            ('Run "`save` we will refund it" now.', "Run now."),
            ('Run **"we will refund it"** now.', "Run now."),
        ):
            with self.subTest(source=source):
                self.assertIn(("lost", "quotation", "we will refund it" if "`save`" not in source else "`save` we will refund it"),
                              changes(source, edit))

    def test_quotation_ending_in_a_digit(self):
        self.assertIn(("lost", "quotation", "Version 2"), changes('He said "Version 2" and left.', "He said Version 2 and left."))

    def test_quote_mark_style_is_equivalent(self):
        self.assertEqual(check.compare('Он написал: "вернём деньги".', "Он написал: «вернём деньги»."), [])
        self.assertEqual(check.compare('He said "Hello," she replied.', 'He said "Hello", she replied.'), [])

    def test_blockquote_reflow_is_equivalent(self):
        source = "> We will refund\n> the full amount.\n\nThanks.\n"
        edit = "> We will refund the full amount.\n\nThanks.\n"
        self.assertEqual(check.compare(source, edit), [])

    def test_blockquote_path_of_quotation_check(self):
        self.assertIn(("lost", "quotation", "We will refund it"),
                      changes("> We will refund it.\n\nThanks.\n", "Thanks.\n"))
        # text after a thematic break is outside the blockquote, so rewriting it is not a quotation change
        self.assertFalse([item for item in changes("> Old promise.\n---\nSee you soon.\n", "> Old promise.\n---\nBye.\n")
                          if item[1] == "quotation"])
        self.assertIn(("lost", "quotation", "Old promise"),
                      changes("> Old promise.\n---\nSee you soon.\n", "---\nSee you soon.\n"))

    def test_link_and_code_and_citation(self):
        source = "See https://example.org/terms and run `make test` [3]."
        edit = "See https://example.org/terms-v2 and run `make check` [4]."
        found = changes(source, edit)
        self.assertIn(("lost", "link", "https://example.org/terms"), found)
        self.assertIn(("added", "code", "make check"), found)
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
