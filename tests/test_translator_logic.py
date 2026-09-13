"""Unit tests for Plume's deterministic logic.

These tests exercise only the pure functions (configuration, placeholder
protection, prompt construction, response parsing, status formatting and the
stale-request guard). They do not require CustomTkinter or a display, so they
run headless in CI.

Run from the project root:

    python -m unittest discover -s tests -v
"""

import http.server
import io
import json
import os
import ssl
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import wave
from email.utils import formatdate
from unittest import mock

# Make the parent directory importable so `import plume` works from tests/.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import plume  # noqa: E402


def valid_result(source="English", target="French", main="Bonjour tout le monde"):
    """Build a well-formed response object with five distinct variations."""
    variations = [
        {"translation": "Salut la compagnie", "english_meaning_check": "Hi everyone"},
        {"translation": "Coucou vous deux", "english_meaning_check": "Hey you two"},
        {"translation": "Bonsoir a tous", "english_meaning_check": "Good evening all"},
        {"translation": "Hello tout le monde", "english_meaning_check": "Hello everybody"},
        {"translation": "Bien le bonjour", "english_meaning_check": "A good hello"},
    ]
    return {
        "source_language": source,
        "target_language": target,
        "language_confidence": "high",
        "language_note": "",
        "main_translation": main,
        "variations": variations,
        "notes": [],
    }


def as_json(obj):
    return json.dumps(obj, ensure_ascii=False)


class TestParseValid(unittest.TestCase):
    def test_valid_english_to_french(self):
        result = plume.parse_translation_result(as_json(valid_result()), plume.DIR_AUTO)
        self.assertEqual(result["source_language"], "English")
        self.assertEqual(result["target_language"], "French")
        self.assertEqual(len(result["variations"]), 5)

    def test_valid_french_to_english(self):
        obj = valid_result(source="French", target="English", main="Hi there")
        obj["variations"] = [
            {"translation": "Hey there", "english_meaning_check": "Hey there"},
            {"translation": "Hello there", "english_meaning_check": "Hello there"},
            {"translation": "Hi you", "english_meaning_check": "Hi you"},
            {"translation": "Greetings", "english_meaning_check": "Greetings"},
            {"translation": "Well hello", "english_meaning_check": "Well hello"},
        ]
        result = plume.parse_translation_result(as_json(obj), plume.DIR_AUTO)
        self.assertEqual(result["source_language"], "French")
        self.assertEqual(result["target_language"], "English")

    def test_tolerates_single_code_fence(self):
        fenced = "```json\n" + as_json(valid_result()) + "\n```"
        result = plume.parse_translation_result(fenced, plume.DIR_AUTO)
        self.assertEqual(len(result["variations"]), 5)


class TestParseMalformed(unittest.TestCase):
    def _expect_error(self, raw, direction=plume.DIR_AUTO):
        with self.assertRaises(plume.TranslationValidationError):
            plume.parse_translation_result(raw, direction)

    def test_invalid_json(self):
        self._expect_error("this is not json at all")

    def test_scalar_json(self):
        self._expect_error("42")

    def test_list_json(self):
        self._expect_error("[1, 2, 3]")

    def test_empty_string(self):
        self._expect_error("")

    def test_missing_primary(self):
        obj = valid_result()
        del obj["main_translation"]
        self._expect_error(as_json(obj))

    def test_empty_primary(self):
        obj = valid_result(main="   ")
        self._expect_error(as_json(obj))

    def test_variations_not_a_list(self):
        obj = valid_result()
        obj["variations"] = {"not": "a list"}
        self._expect_error(as_json(obj))

    def test_fewer_than_five(self):
        obj = valid_result()
        obj["variations"] = obj["variations"][:4]
        self._expect_error(as_json(obj))

    def test_more_than_five(self):
        obj = valid_result()
        obj["variations"].append(
            {"translation": "Salutations distinguees", "english_meaning_check": "Distinguished greetings"}
        )
        self._expect_error(as_json(obj))

    def test_bad_variation_object(self):
        obj = valid_result()
        obj["variations"][2] = "just a string"
        self._expect_error(as_json(obj))

    def test_empty_translation(self):
        obj = valid_result()
        obj["variations"][0]["translation"] = ""
        self._expect_error(as_json(obj))

    def test_empty_meaning_check(self):
        obj = valid_result()
        obj["variations"][1]["english_meaning_check"] = "   "
        self._expect_error(as_json(obj))

    def test_same_source_and_target(self):
        obj = valid_result(source="English", target="English")
        self._expect_error(as_json(obj))

    def test_unknown_language(self):
        obj = valid_result(source="Spanish", target="French")
        self._expect_error(as_json(obj))


class TestUniqueness(unittest.TestCase):
    def test_duplicate_alternatives_after_normalisation(self):
        obj = valid_result()
        # Same phrase, differing only by casing and terminal punctuation.
        obj["variations"][0]["translation"] = "Salut la compagnie"
        obj["variations"][1]["translation"] = "salut la compagnie!"
        with self.assertRaises(plume.TranslationValidationError):
            plume.parse_translation_result(as_json(obj), plume.DIR_AUTO)

    def test_primary_duplicated_as_alternative(self):
        obj = valid_result(main="Salut la compagnie")
        # variations[0] already equals the main translation
        with self.assertRaises(plume.TranslationValidationError):
            plume.parse_translation_result(as_json(obj), plume.DIR_AUTO)

    def test_normalise_ignores_case_and_terminal_punctuation(self):
        a = plume.normalise_for_uniqueness("Ca va bien !")
        b = plume.normalise_for_uniqueness("ca va bien")
        self.assertEqual(a, b)

    def test_normalise_keeps_internal_difference(self):
        a = plume.normalise_for_uniqueness("Ca va bien")
        b = plume.normalise_for_uniqueness("Ca va tres bien")
        self.assertNotEqual(a, b)


class TestForcedDirection(unittest.TestCase):
    def test_manual_direction_mismatch(self):
        # Model says English->French but the user forced French->English.
        obj = valid_result(source="English", target="French")
        with self.assertRaises(plume.TranslationValidationError):
            plume.parse_translation_result(as_json(obj), plume.DIR_FR_EN)

    def test_manual_direction_match(self):
        obj = valid_result(source="English", target="French")
        result = plume.parse_translation_result(as_json(obj), plume.DIR_EN_FR)
        self.assertEqual(result["target_language"], "French")

    def test_swap_direction_inverts_fixed_directions(self):
        self.assertEqual(plume.swap_direction(plume.DIR_EN_FR), plume.DIR_FR_EN)
        self.assertEqual(plume.swap_direction(plume.DIR_FR_EN), plume.DIR_EN_FR)

    def test_swap_direction_is_noop_on_auto(self):
        self.assertEqual(plume.swap_direction(plume.DIR_AUTO), plume.DIR_AUTO)


class TestConfig(unittest.TestCase):
    def test_malformed_config_not_overwritten_by_automatic_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, plume.CONFIG_FILENAME)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{ this is not valid json ")
            with mock.patch.object(plume, "config_path", return_value=path):
                # Automatic save must refuse and leave the file untouched.
                with self.assertRaises(plume.ConfigError):
                    plume.save_config(dict(plume.DEFAULT_CONFIG), force=False)
                with open(path, "r", encoding="utf-8") as fh:
                    self.assertIn("not valid json", fh.read())
                # An explicit recovery save replaces it.
                plume.save_config(dict(plume.DEFAULT_CONFIG), force=True)
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                self.assertEqual(data["backend"], "anthropic")

    def test_load_reports_malformed_without_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, plume.CONFIG_FILENAME)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("not json")
            with mock.patch.object(plume, "config_path", return_value=path):
                config, error = plume.load_config()
                self.assertIsNotNone(error)
                self.assertEqual(config["backend"], "anthropic")  # defaults returned
            # File still malformed on disk.
            with open(path, "r", encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "not json")

    def test_atomic_save_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, plume.CONFIG_FILENAME)
            with mock.patch.object(plume, "config_path", return_value=path):
                cfg = dict(plume.DEFAULT_CONFIG)
                cfg["ollama_model"] = "mistral:latest"
                plume.save_config(cfg)
                loaded, error = plume.load_config()
                self.assertIsNone(error)
                self.assertEqual(loaded["ollama_model"], "mistral:latest")


class TestPlaceholders(unittest.TestCase):
    def test_round_trip_restores_tokens(self):
        text = "Hi [Name], see {amount} at https://example.com on 2026-01-05"
        masked, mapping = plume.protect_text(text, enabled=True)
        self.assertNotIn("[Name]", masked)
        self.assertNotIn("https://example.com", masked)
        self.assertEqual(len(mapping), 4)  # [Name], {amount}, URL, ISO date
        restored = plume.restore_tokens(masked, mapping)
        self.assertEqual(restored, text)

    def test_disabled_protection_is_noop(self):
        text = "Hi [Name]"
        masked, mapping = plume.protect_text(text, enabled=False)
        self.assertEqual(masked, text)
        self.assertEqual(mapping, {})

    def test_missing_token_creates_warning(self):
        # Model dropped the protected token from its output.
        mapping = {plume.PH_TOKEN.format(0): "[Name]"}
        result = valid_result()
        result["main_translation"] = "Bonjour, ravi de vous voir"  # token absent
        _, warnings = plume.restore_result_tokens(result, mapping)
        self.assertTrue(warnings)

    def test_present_token_no_warning_and_restored(self):
        token = plume.PH_TOKEN.format(0)
        mapping = {token: "[Name]"}
        result = valid_result()
        result["main_translation"] = "Bonjour " + token
        result, warnings = plume.restore_result_tokens(result, mapping)
        self.assertFalse(warnings)
        self.assertIn("[Name]", result["main_translation"])

    def test_warning_does_not_leak_original_value(self):
        mapping = {plume.PH_TOKEN.format(0): "SecretName"}
        result = valid_result()
        result["main_translation"] = "Bonjour"  # token missing
        _, warnings = plume.restore_result_tokens(result, mapping)
        self.assertTrue(warnings)
        self.assertNotIn("SecretName", " ".join(warnings))

    def test_keep_as_is_masks_and_restores_a_name(self):
        masked, mapping = plume.protect_text(
            "Tell Kes I am on my way.", extra_terms=["Kes"]
        )
        self.assertNotIn("Kes", masked)
        self.assertEqual(
            plume.restore_tokens(masked, mapping), "Tell Kes I am on my way."
        )

    def test_keep_as_is_longest_term_wins(self):
        masked, mapping = plume.protect_text(
            "Marie-Claire called.", extra_terms=["Marie", "Marie-Claire"]
        )
        restored = plume.restore_tokens(masked, mapping)
        self.assertEqual(restored, "Marie-Claire called.")
        self.assertEqual(len(mapping), 1)

    def test_keep_as_is_does_not_eat_longer_word(self):
        masked, mapping = plume.protect_text(
            "Anne is arriving.", extra_terms=["Ann"]
        )
        self.assertEqual(masked, "Anne is arriving.")
        self.assertEqual(mapping, {})

    def test_normalise_keep_as_is_terms_caps_and_dedupes(self):
        got = plume.normalise_keep_as_is_terms(
            ["Kes", "kes", "  ", "A" * 41, "Hawkeye"]
        )
        self.assertEqual(got, ["Kes", "Hawkeye"])


class TestTranslationGlossary(unittest.TestCase):
    def test_accepts_list_of_dicts(self):
        got = plume.normalise_glossary_entries(
            [{"term": "deadline", "translation": "délai"}]
        )
        self.assertEqual(got, [{"term": "deadline", "translation": "délai"}])

    def test_parses_settings_textbox_format(self):
        got = plume.normalise_glossary_entries("deadline = délai\nmeeting = réunion")
        self.assertEqual(
            got,
            [
                {"term": "deadline", "translation": "délai"},
                {"term": "meeting", "translation": "réunion"},
            ],
        )

    def test_line_without_equals_is_skipped(self):
        got = plume.normalise_glossary_entries("deadline = délai\njust some text\n")
        self.assertEqual(got, [{"term": "deadline", "translation": "délai"}])

    def test_blank_translation_or_term_is_dropped(self):
        got = plume.normalise_glossary_entries("deadline =\n= délai\nok = fine")
        self.assertEqual(got, [{"term": "ok", "translation": "fine"}])

    def test_dedupes_by_term_case_insensitively_first_wins(self):
        got = plume.normalise_glossary_entries(
            [
                {"term": "deadline", "translation": "délai"},
                {"term": "Deadline", "translation": "date limite"},
            ]
        )
        self.assertEqual(got, [{"term": "deadline", "translation": "délai"}])

    def test_oversized_entry_dropped(self):
        got = plume.normalise_glossary_entries(
            [{"term": "x" * 41, "translation": "y"}]
        )
        self.assertEqual(got, [])

    def test_caps_at_max_entries(self):
        many = [{"term": "t{}".format(i), "translation": "x{}".format(i)} for i in range(30)]
        got = plume.normalise_glossary_entries(many)
        self.assertEqual(len(got), plume.GLOSSARY_MAX_ENTRIES)

    def test_rejects_non_list_non_string(self):
        self.assertEqual(plume.normalise_glossary_entries(42), [])

    def test_entries_to_text_round_trips(self):
        entries = [{"term": "deadline", "translation": "délai"}]
        text = plume.glossary_entries_to_text(entries)
        self.assertEqual(plume.normalise_glossary_entries(text), entries)

    def test_instruction_omitted_when_empty(self):
        self.assertEqual(plume.build_glossary_instruction([]), "")
        self.assertEqual(plume.build_glossary_instruction(None), "")

    def test_instruction_is_background_only_and_names_the_pair(self):
        text = plume.build_glossary_instruction(
            [{"term": "deadline", "translation": "délai"}]
        )
        self.assertIn("background only", text)
        self.assertIn("deadline", text)
        self.assertIn("délai", text)
        self.assertIn("source text's own meaning always wins", text.lower())

    def test_instruction_mentions_elision_guidance(self):
        # notes_021: a gaming term like Auridon/Auridia should be adaptable
        # to "d'Auridia" without the user having to store that form itself.
        text = plume.build_glossary_instruction(
            [{"term": "Auridon", "translation": "Auridia"}]
        )
        self.assertIn("elision", text.lower())

    def test_instruction_covers_bidirectional_gaming_pair(self):
        entries = [
            {"term": "Auridon", "translation": "Auridia"},
            {"term": "Auridia", "translation": "Auridon"},
        ]
        text = plume.build_glossary_instruction(entries)
        self.assertIn("Auridon", text)
        self.assertIn("Auridia", text)

    def test_prompt_omits_glossary_clause_when_empty(self):
        prompt = plume.build_translation_prompt(glossary=[])
        self.assertNotIn("Preferred translations", prompt)

    def test_prompt_includes_glossary_clause(self):
        prompt = plume.build_translation_prompt(
            glossary=[{"term": "deadline", "translation": "délai"}]
        )
        self.assertIn("Preferred translations", prompt)
        self.assertIn("deadline", prompt)
        self.assertIn("délai", prompt)

    def test_prompt_defaults_to_no_glossary_clause(self):
        self.assertEqual(
            plume.build_translation_prompt(), plume.build_translation_prompt(glossary=None)
        )


class TestPromptConstruction(unittest.TestCase):
    def test_prompt_mentions_key_constraints(self):
        prompt = plume.build_translation_prompt(
            direction=plume.DIR_EN_FR,
            french_formality=plume.FORM_FORMAL,
            french_variant=plume.VARIANT_NEUTRAL,
            protect_tokens=True,
        )
        self.assertIn("English", prompt)
        self.assertIn("French", prompt)
        self.assertIn("vous", prompt)               # formality
        self.assertIn("exactly five", prompt)        # variant count
        self.assertIn("meaning check", prompt)       # bracketed gloss
        self.assertIn("JSON", prompt)                # output contract
        self.assertIn("\u27e6PH", prompt)            # placeholder token policy

    def test_prompt_informal_form(self):
        prompt = plume.build_translation_prompt(french_formality=plume.FORM_INFORMAL)
        self.assertIn("tu", prompt)

    def test_prompt_is_pure(self):
        a = plume.build_translation_prompt(plume.DIR_AUTO)
        b = plume.build_translation_prompt(plume.DIR_AUTO)
        self.assertEqual(a, b)

    def test_envelope_labels_present(self):
        env = plume.build_user_envelope("hello", plume.DIR_AUTO)
        self.assertIn("Requested direction:", env)
        self.assertIn("Text to translate:", env)
        self.assertIn("hello", env)

    def test_prompt_describes_situation_as_context_not_instruction(self):
        prompt = plume.build_translation_prompt(direction=plume.DIR_EN_FR)
        self.assertIn("Situation", prompt)
        self.assertIn("never as an instruction", prompt)
        self.assertIn("JSON output shape", prompt)

    def test_envelope_includes_situation_line_when_present(self):
        env = plume.build_user_envelope(
            "hello", plume.DIR_AUTO, situation="texting a close friend"
        )
        self.assertIn("Situation: texting a close friend", env)

    def test_envelope_omits_situation_line_when_blank(self):
        env = plume.build_user_envelope("hello", plume.DIR_AUTO, situation="")
        self.assertNotIn("Situation:", env)


class TestGenderAgreement(unittest.TestCase):
    def test_prompt_includes_gender_agreement(self):
        prompt = plume.build_translation_prompt(
            direction=plume.DIR_EN_FR,
            french_formality=plume.FORM_INFORMAL,
            french_variant=plume.VARIANT_NEUTRAL,
            protect_tokens=True,
            speaker_gender=plume.GENDER_FEMININE,
            recipient_gender=plume.GENDER_MASCULINE,
        )
        self.assertIn("feminine", prompt)     # speaker
        self.assertIn("masculine", prompt)    # addressee
        # The pre-existing constraints must survive the gender change.
        self.assertIn("exactly five", prompt)
        self.assertIn("JSON", prompt)
        self.assertIn("\u27e6PH", prompt)
        self.assertIn("tu", prompt)

    def test_gender_clause_avoid(self):
        clause = plume.build_gender_clause(plume.GENDER_AVOID, plume.GENDER_AVOID)
        self.assertIn("avoid where possible", clause)

    def test_gender_clause_explicit_source_wins(self):
        clause = plume.build_gender_clause(plume.GENDER_FEMININE, plume.GENDER_FEMININE)
        self.assertIn("explicitly marks gender", clause)

    def test_envelope_includes_gender(self):
        env = plume.build_user_envelope(
            "hello", plume.DIR_AUTO, plume.FORM_INFORMAL, plume.VARIANT_NEUTRAL,
            plume.GENDER_FEMININE, plume.GENDER_MASCULINE,
        )
        self.assertIn("French speaker agreement: Feminine", env)
        self.assertIn("French addressee agreement: Masculine", env)

    def test_defaults_include_gender_keys(self):
        self.assertEqual(plume.DEFAULT_CONFIG["default_french_speaker_gender"], "Feminine")
        self.assertEqual(plume.DEFAULT_CONFIG["default_french_recipient_gender"], "Feminine")


class TestTones(unittest.TestCase):
    def test_caps_at_three(self):
        self.assertEqual(
            len(plume.validate_tones(
                ["Warm", "Precise", "Courteous", "Direct"]
            )),
            3,
        )

    def test_later_wins_conflict(self):
        self.assertEqual(
            plume.validate_tones(["Terse", "Playful"]),
            ["Playful"],
        )

    def test_earlier_kept_when_no_conflict(self):
        self.assertEqual(
            plume.validate_tones(["Warm", "Courteous"]),
            ["Warm", "Courteous"],
        )

    def test_none_and_unknown_dropped(self):
        self.assertEqual(
            plume.validate_tones(["None", "Sarcastic", "Warm"]),
            ["Warm"],
        )

    def test_duplicate_ignored(self):
        self.assertEqual(plume.validate_tones(["Warm", "Warm"]), ["Warm"])

    def test_rejects_non_list(self):
        self.assertEqual(plume.validate_tones("Warm"), [])

    def test_unhashable_member_does_not_raise(self):
        # v1.33: a hand-edited config could hold a stray list/dict entry;
        # this must be dropped, not crash config loading with a TypeError.
        self.assertEqual(
            plume.validate_tones(["Warm", ["nested"], {"a": 1}, "Precise"]),
            ["Warm", "Precise"],
        )

    def test_all_conflict_pairs_resolve_to_later(self):
        for a, b in (
            ("Terse", "Playful"), ("Terse", "Warm"),
            ("Playful", "Precise"), ("Direct", "Reassuring"),
        ):
            self.assertEqual(plume.validate_tones([a, b]), [b])

    def test_instruction_omitted_when_empty(self):
        self.assertEqual(plume.build_tone_instruction([]), "")

    def test_instruction_is_background_only(self):
        text = plume.build_tone_instruction(["Warm", "Precise"])
        self.assertIn("background only", text)
        self.assertIn("source text wins", text.lower())
        self.assertIn("warm", text)
        self.assertIn("precise", text)

    def test_instruction_forbids_uninvited_embellishment(self):
        # v1.33: source slang licenses translating slang faithfully, not
        # inventing reassurance/gratitude/agreement the source never said.
        text = plume.build_tone_instruction(["Warm"])
        self.assertIn("Preserve negation", text)
        self.assertIn("Do not introduce reassurance", text)
        self.assertIn("Source slang is content to translate faithfully", text)
        self.assertIn("all five alternatives", text)

    def test_prompt_omits_tone_clause_when_empty(self):
        prompt = plume.build_translation_prompt(tones=[])
        self.assertNotIn("Register tones", prompt)

    def test_prompt_includes_tone_clause(self):
        prompt = plume.build_translation_prompt(tones=["Warm"])
        self.assertIn("Register tones", prompt)
        self.assertIn("warm", prompt)

    def test_envelope_omits_tones_line_when_empty(self):
        env = plume.build_user_envelope("hello", tones=[])
        self.assertNotIn("Tones:", env)

    def test_envelope_includes_tones_line(self):
        env = plume.build_user_envelope("hello", tones=["Warm", "Precise"])
        self.assertIn("Tones: Warm, Precise", env)


class TestWritingProfile(unittest.TestCase):
    def test_defaults_for_none(self):
        profile = plume.normalise_writing_profile(None)
        self.assertEqual(profile["mode"], plume.WRITING_MODE_TRANSLATE)
        self.assertEqual(profile["strength"], plume.WRITING_STRENGTH_SOURCE_LED)
        self.assertEqual(profile["role"], "General")
        self.assertEqual(profile["version"], 1)

    def test_defaults_for_non_dict(self):
        self.assertEqual(
            plume.normalise_writing_profile("not a dict"),
            plume.normalise_writing_profile(None),
        )

    def test_unknown_values_fall_back_to_defaults(self):
        profile = plume.normalise_writing_profile(
            {"mode": "Sideways", "strength": "Extreme", "role": "Stranger"}
        )
        self.assertEqual(profile["mode"], plume.WRITING_MODE_TRANSLATE)
        self.assertEqual(profile["strength"], plume.WRITING_STRENGTH_SOURCE_LED)
        self.assertEqual(profile["role"], "General")

    def test_valid_values_round_trip(self):
        profile = plume.normalise_writing_profile(
            {"mode": "Correct English then translate", "strength": "Light", "role": "Friend"}
        )
        self.assertEqual(profile["mode"], "Correct English then translate")
        self.assertEqual(profile["strength"], "Light")
        self.assertEqual(profile["role"], "Friend")

    def test_source_led_produces_no_instruction(self):
        self.assertEqual(
            plume.build_writing_profile_instruction({"strength": "Source-led"}), "",
        )
        self.assertEqual(plume.build_writing_profile_instruction(None), "")

    def test_light_strength_produces_background_only_instruction(self):
        text = plume.build_writing_profile_instruction(
            {"strength": "Light", "role": "Colleague"}
        )
        self.assertIn("background only", text)
        self.assertIn("colleague", text)
        self.assertIn("source text wins", text.lower())

    def test_balanced_strength_mentions_tones(self):
        text = plume.build_writing_profile_instruction(
            {"strength": "Balanced", "role": "Friend"}
        )
        self.assertIn("register tones", text.lower())

    def test_never_claims_identity_or_authority(self):
        text = plume.build_writing_profile_instruction(
            {"strength": "Light", "role": "Customer"}
        )
        self.assertIn("Do not assume a relationship, identity, expertise", text)

    def test_prompt_omits_writing_clause_when_source_led(self):
        prompt = plume.build_translation_prompt(writing={"strength": "Source-led"})
        self.assertNotIn("Background relationship", prompt)

    def test_prompt_includes_writing_clause_when_not_source_led(self):
        prompt = plume.build_translation_prompt(
            writing={"strength": "Light", "role": "Friend"}
        )
        self.assertIn("Background relationship", prompt)
        self.assertIn("friend", prompt)

    def test_prompt_defaults_to_no_writing_clause(self):
        # writing=None (the default) must not change existing prompt output.
        self.assertEqual(
            plume.build_translation_prompt(),
            plume.build_translation_prompt(writing=None),
        )


class TestStatusState(unittest.TestCase):
    def test_status_honours_explicit_state(self):
        cfg = dict(plume.DEFAULT_CONFIG)
        self.assertTrue(plume.format_status(cfg, 47, "translating\u2026").endswith("translating\u2026"))

    def test_status_uses_char_count_when_ready(self):
        cfg = dict(plume.DEFAULT_CONFIG)
        self.assertTrue(plume.format_status(cfg, 47).endswith("47 characters"))
        self.assertTrue(plume.format_status(cfg, 47, "ready").endswith("47 characters"))

    def test_status_ready_when_no_count(self):
        cfg = dict(plume.DEFAULT_CONFIG)
        self.assertTrue(plume.format_status(cfg, None).endswith("ready"))


class TestAdvisories(unittest.TestCase):
    def test_advisory_text_includes_language_note_and_notes(self):
        result = valid_result()
        result["language_note"] = "Ambiguous source language."
        result["notes"] = ["Check the protected placeholder."]
        text = plume.advisory_text_from_result(result)
        self.assertIn("Ambiguous source language.", text)
        self.assertIn("Check the protected placeholder.", text)

    def test_advisory_text_ignores_blank_and_non_string_values(self):
        result = valid_result()
        result["language_note"] = " "
        result["notes"] = ["", 42, "Useful note."]
        self.assertEqual(plume.advisory_text_from_result(result), "Useful note.")

    def test_advisory_text_can_append_extra_notes(self):
        result = valid_result()
        result["language_note"] = "Language note."
        text = plume.advisory_text_from_result(result, extra_notes=["Input changed."])
        self.assertIn("Language note.", text)
        self.assertIn("Input changed.", text)


class TestConfigCoercion(unittest.TestCase):
    def _load_with(self, raw_dict):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, plume.CONFIG_FILENAME)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(raw_dict, fh)
            with mock.patch.object(plume, "config_path", return_value=path):
                config, error = plume.load_config()
            return config, error

    def test_bad_backend_coerced_to_anthropic(self):
        config, _ = self._load_with({"backend": "Ollama-typo"})
        self.assertEqual(config["backend"], "anthropic")

    def test_ollama_backend_preserved(self):
        config, _ = self._load_with({"backend": "ollama"})
        self.assertEqual(config["backend"], "ollama")

    def test_non_numeric_limit_falls_back(self):
        config, _ = self._load_with({"max_input_chars": "banana"})
        self.assertEqual(config["max_input_chars"], plume.DEFAULT_MAX_INPUT_CHARS)

    def test_negative_limit_falls_back(self):
        config, _ = self._load_with({"max_input_chars": -5})
        self.assertEqual(config["max_input_chars"], plume.DEFAULT_MAX_INPUT_CHARS)

    def test_positive_limit_is_preserved(self):
        config, _ = self._load_with({"max_input_chars": "5000"})
        self.assertEqual(config["max_input_chars"], 5000)

    def test_send_to_shortcut_coerced_to_bool(self):
        config, _ = self._load_with({"send_to_shortcut": "yes"})
        self.assertIs(config["send_to_shortcut"], True)

    def test_send_to_shortcut_defaults_false(self):
        config, _ = self._load_with({})
        self.assertIs(config["send_to_shortcut"], False)

    def test_user_situation_presets_normalised_on_load(self):
        config, _ = self._load_with(
            {"user_situation_presets": ["Guild raid chat", "close friend"]}
        )
        self.assertEqual(config["user_situation_presets"], ["Guild raid chat"])

    def test_user_situation_presets_defaults_empty(self):
        config, _ = self._load_with({})
        self.assertEqual(config["user_situation_presets"], [])

    def test_default_tones_validated_on_load(self):
        config, _ = self._load_with(
            {"default_tones": ["Warm", ["nested"], "Sarcastic"]}
        )
        self.assertEqual(config["default_tones"], ["Warm"])

    def test_default_tones_defaults_empty(self):
        config, _ = self._load_with({})
        self.assertEqual(config["default_tones"], [])

    def test_default_writing_profile_normalised_on_load(self):
        config, _ = self._load_with(
            {"default_writing_profile": {"strength": "Balanced", "role": "bogus"}}
        )
        self.assertEqual(config["default_writing_profile"]["strength"], "Balanced")
        self.assertEqual(config["default_writing_profile"]["role"], "General")

    def test_default_writing_profile_defaults_to_source_led(self):
        config, _ = self._load_with({})
        self.assertEqual(
            config["default_writing_profile"]["strength"],
            plume.WRITING_STRENGTH_SOURCE_LED,
        )

    def test_french_typography_coerced_to_bool(self):
        config, _ = self._load_with({"french_typography": "yes"})
        self.assertIs(config["french_typography"], True)

    def test_french_typography_defaults_false(self):
        config, _ = self._load_with({})
        self.assertIs(config["french_typography"], False)

    def test_fallback_to_ollama_coerced_to_bool(self):
        config, _ = self._load_with({"fallback_to_ollama": "yes"})
        self.assertIs(config["fallback_to_ollama"], True)

    def test_fallback_to_ollama_defaults_false(self):
        config, _ = self._load_with({})
        self.assertIs(config["fallback_to_ollama"], False)

    def test_coerce_positive_int(self):
        self.assertEqual(plume.coerce_positive_int("5000", 2000), 5000)
        self.assertEqual(plume.coerce_positive_int("banana", 2000), 2000)
        self.assertEqual(plume.coerce_positive_int(0, 2000), 2000)

    def test_unknown_gender_falls_back_to_feminine(self):
        config, _ = self._load_with({"default_french_speaker_gender": "nonsense"})
        self.assertEqual(config["default_french_speaker_gender"], "Feminine")

    def test_unknown_direction_falls_back_to_auto(self):
        config, _ = self._load_with({"default_direction": "Sideways"})
        self.assertEqual(config["default_direction"], plume.DIR_AUTO)

    def test_normalise_backend_accepts_only_ollama_literal(self):
        self.assertEqual(plume.normalise_backend("ollama"), "ollama")
        self.assertEqual(plume.normalise_backend("Ollama-typo"), "anthropic")
        self.assertEqual(plume.normalise_backend(None), "anthropic")
        self.assertEqual(plume.normalise_backend(""), "anthropic")

    def test_always_on_top_defaults_false(self):
        config, _ = self._load_with({})
        self.assertIs(config["always_on_top"], False)

    def test_always_on_top_coerced_to_bool(self):
        config, _ = self._load_with({"always_on_top": "yes"})
        self.assertIs(config["always_on_top"], True)

    def test_keep_as_is_terms_normalised_on_load(self):
        config, _ = self._load_with(
            {"keep_as_is_terms": ["Kes", "kes", "  ", "A" * 41]}
        )
        self.assertEqual(config["keep_as_is_terms"], ["Kes"])

    def test_translation_glossary_default_empty(self):
        config, _ = self._load_with({})
        self.assertEqual(config["translation_glossary"], [])

    def test_translation_glossary_normalised_on_load(self):
        config, _ = self._load_with({
            "translation_glossary": [
                {"term": "deadline", "translation": "délai"},
                {"not": "a valid entry"},
            ]
        })
        self.assertEqual(
            config["translation_glossary"],
            [{"term": "deadline", "translation": "délai"}],
        )

    def test_conversation_presets_default_empty(self):
        config, _ = self._load_with({})
        self.assertEqual(config["conversation_presets"], [])

    def test_conversation_presets_normalised_on_load(self):
        config, _ = self._load_with({
            "conversation_presets": [
                {"name": "Work email", "direction": "Sideways"},
                {"not": "a valid preset"},
            ]
        })
        self.assertEqual(len(config["conversation_presets"]), 1)
        self.assertEqual(config["conversation_presets"][0]["name"], "Work email")
        self.assertEqual(config["conversation_presets"][0]["direction"], plume.DIR_AUTO)

    def test_tray_settings_default_false(self):
        config, _ = self._load_with({})
        self.assertIs(config["launch_at_sign_in"], False)
        self.assertIs(config["start_minimised_to_tray"], False)
        self.assertIs(config["close_to_tray"], False)

    def test_tray_settings_coerced_to_bool(self):
        config, _ = self._load_with({
            "launch_at_sign_in": "yes",
            "start_minimised_to_tray": 1,
            "close_to_tray": "true",
        })
        self.assertIs(config["launch_at_sign_in"], True)
        self.assertIs(config["start_minimised_to_tray"], True)
        self.assertIs(config["close_to_tray"], True)


class TestConversationPresets(unittest.TestCase):
    def _preset(self, **overrides):
        base = {
            "name": "Work email",
            "direction": plume.DIR_EN_FR,
            "french_formality": plume.FORM_FORMAL,
            "speaker_gender": plume.GENDER_FEMININE,
            "recipient_gender": plume.GENDER_MASCULINE,
            "situation": "formal work email",
        }
        base.update(overrides)
        return base

    def test_rejects_non_dict(self):
        self.assertIsNone(plume.normalise_conversation_preset("not a dict"))

    def test_rejects_blank_name(self):
        self.assertIsNone(plume.normalise_conversation_preset(self._preset(name="   ")))

    def test_name_truncated_to_max(self):
        clean = plume.normalise_conversation_preset(self._preset(name="x" * 60))
        self.assertEqual(len(clean["name"]), plume.PRESET_NAME_MAX)

    def test_unknown_direction_falls_back_to_auto(self):
        clean = plume.normalise_conversation_preset(self._preset(direction="Sideways"))
        self.assertEqual(clean["direction"], plume.DIR_AUTO)

    def test_unknown_gender_falls_back_to_feminine(self):
        clean = plume.normalise_conversation_preset(
            self._preset(speaker_gender="nonsense")
        )
        self.assertEqual(clean["speaker_gender"], plume.GENDER_FEMININE)

    def test_assigns_id_when_missing(self):
        clean = plume.normalise_conversation_preset(self._preset())
        self.assertTrue(clean["id"])

    def test_preserves_given_id(self):
        clean = plume.normalise_conversation_preset(self._preset(id="abc123"))
        self.assertEqual(clean["id"], "abc123")

    def test_valid_preset_round_trips(self):
        clean = plume.normalise_conversation_preset(self._preset())
        self.assertEqual(clean["name"], "Work email")
        self.assertEqual(clean["direction"], plume.DIR_EN_FR)
        self.assertEqual(clean["french_formality"], plume.FORM_FORMAL)
        self.assertEqual(clean["recipient_gender"], plume.GENDER_MASCULINE)
        self.assertEqual(clean["situation"], "formal work email")

    def test_list_drops_malformed_entries(self):
        presets = plume.normalise_conversation_presets([
            self._preset(id="1"), {"bad": "entry"}, self._preset(id="2", name="Chat"),
        ])
        self.assertEqual(len(presets), 2)

    def test_list_deduplicates_by_id(self):
        presets = plume.normalise_conversation_presets([
            self._preset(id="1"), self._preset(id="1", name="Different name"),
        ])
        self.assertEqual(len(presets), 1)

    def test_list_caps_at_max(self):
        many = [self._preset(id=str(i), name="P{}".format(i)) for i in range(20)]
        presets = plume.normalise_conversation_presets(many)
        self.assertEqual(len(presets), plume.MAX_CONVERSATION_PRESETS)

    def test_list_rejects_non_list(self):
        self.assertEqual(plume.normalise_conversation_presets("not a list"), [])

    def test_tones_default_to_empty_list(self):
        clean = plume.normalise_conversation_preset(self._preset())
        self.assertEqual(clean["tones"], [])

    def test_tones_are_validated_and_stored(self):
        clean = plume.normalise_conversation_preset(
            self._preset(tones=["Warm", "Precise", "not-a-tone"])
        )
        self.assertEqual(clean["tones"], ["Warm", "Precise"])

    def test_tones_conflicts_resolved_on_normalise(self):
        clean = plume.normalise_conversation_preset(
            self._preset(tones=["Terse", "Playful"])
        )
        self.assertEqual(clean["tones"], ["Playful"])

    def test_writing_profile_defaults_when_absent(self):
        clean = plume.normalise_conversation_preset(self._preset())
        self.assertEqual(clean["writing"], plume.normalise_writing_profile(None))

    def test_writing_profile_is_validated_and_stored(self):
        clean = plume.normalise_conversation_preset(
            self._preset(writing={"strength": "Light", "role": "Friend"})
        )
        self.assertEqual(clean["writing"]["strength"], "Light")
        self.assertEqual(clean["writing"]["role"], "Friend")

    def test_list_repairs_duplicate_display_name(self):
        presets = plume.normalise_conversation_presets([
            self._preset(id="1", name="Chat"), self._preset(id="2", name="Chat"),
        ])
        self.assertEqual(len(presets), 2)
        names = sorted(p["name"] for p in presets)
        self.assertEqual(names, ["Chat", "Chat (2)"])

    def test_list_repairs_name_colliding_with_placeholder(self):
        presets = plume.normalise_conversation_presets([
            self._preset(id="1", name=plume.CONVERSATION_PRESET_PLACEHOLDER),
        ])
        self.assertEqual(len(presets), 1)
        self.assertNotEqual(presets[0]["name"], plume.CONVERSATION_PRESET_PLACEHOLDER)


class TestResourceDir(unittest.TestCase):
    def test_not_frozen_uses_module_directory(self):
        with mock.patch.object(plume.sys, "frozen", False, create=True):
            self.assertEqual(
                plume.resource_dir(),
                os.path.dirname(os.path.abspath(plume.__file__)),
            )

    def test_frozen_uses_meipass_not_file(self):
        with mock.patch.object(plume.sys, "frozen", True, create=True), \
                mock.patch.object(plume.sys, "_MEIPASS", r"C:\fake\meipass", create=True):
            self.assertEqual(plume.resource_dir(), r"C:\fake\meipass")

    def test_frozen_without_meipass_falls_back(self):
        # Defensive only: PyInstaller always sets _MEIPASS when frozen is
        # True, but resource_dir() must not raise if that ever changes.
        with mock.patch.object(plume.sys, "frozen", True, create=True):
            if hasattr(plume.sys, "_MEIPASS"):
                delattr(plume.sys, "_MEIPASS")
            self.assertEqual(
                plume.resource_dir(),
                os.path.dirname(os.path.abspath(plume.__file__)),
            )


class TestUserSituations(unittest.TestCase):
    def test_accepts_a_plain_list(self):
        self.assertEqual(
            plume.normalise_user_situations(["Guild raid chat"]),
            ["Guild raid chat"],
        )

    def test_accepts_newline_separated_string(self):
        self.assertEqual(
            plume.normalise_user_situations("Guild raid chat\nSchool gate"),
            ["Guild raid chat", "School gate"],
        )

    def test_strips_whitespace_and_drops_blanks(self):
        self.assertEqual(
            plume.normalise_user_situations(["  Guild raid chat  ", "", "   "]),
            ["Guild raid chat"],
        )

    def test_drops_entries_matching_a_built_in_preset_case_insensitively(self):
        self.assertEqual(plume.normalise_user_situations(["close friend"]), [])
        self.assertEqual(plume.normalise_user_situations(["CLOSE FRIEND"]), [])

    def test_drops_entries_matching_the_placeholder_or_heading(self):
        self.assertEqual(
            plume.normalise_user_situations(
                [plume.SITUATION_PRESET_PLACEHOLDER, plume.USER_SITUATION_HEADING]
            ),
            [],
        )

    def test_drops_case_insensitive_duplicates_keeping_the_first(self):
        self.assertEqual(
            plume.normalise_user_situations(["Guild raid chat", "guild RAID chat"]),
            ["Guild raid chat"],
        )

    def test_drops_oversized_entry(self):
        long_entry = "x" * (plume.USER_SITUATION_MAX_CHARS + 1)
        self.assertEqual(plume.normalise_user_situations([long_entry]), [])

    def test_caps_at_max_entries(self):
        many = ["Situation {}".format(i) for i in range(plume.MAX_USER_SITUATIONS + 5)]
        result = plume.normalise_user_situations(many)
        self.assertEqual(len(result), plume.MAX_USER_SITUATIONS)
        self.assertEqual(result, many[: plume.MAX_USER_SITUATIONS])

    def test_rejects_non_list_non_string(self):
        self.assertEqual(plume.normalise_user_situations(42), [])
        self.assertEqual(plume.normalise_user_situations(None), [])


class TestSituationMenuValues(unittest.TestCase):
    def test_starts_with_placeholder_then_built_ins(self):
        values = plume.situation_menu_values([])
        self.assertEqual(
            values[: 1 + len(plume.SITUATION_PRESETS)],
            [plume.SITUATION_PRESET_PLACEHOLDER] + list(plume.SITUATION_PRESETS),
        )

    def test_omits_heading_when_no_user_entries(self):
        values = plume.situation_menu_values([])
        self.assertNotIn(plume.USER_SITUATION_HEADING, values)

    def test_appends_heading_and_user_entries_when_present(self):
        values = plume.situation_menu_values(["Guild raid chat"])
        self.assertEqual(values[-2:], [plume.USER_SITUATION_HEADING, "Guild raid chat"])


class TestAutostart(unittest.TestCase):
    def test_autostart_command_contains_start_minimised_flag(self):
        self.assertIn("--start-minimised", plume.autostart_command())

    def test_autostart_command_quotes_executable(self):
        command = plume.autostart_command()
        self.assertTrue(command.startswith('"'))

    def test_set_launch_at_sign_in_refuses_without_winreg(self):
        with mock.patch.object(plume, "WINREG_AVAILABLE", False):
            with self.assertRaises(plume.ConfigError):
                plume.set_launch_at_sign_in(True)

    def test_disable_without_winreg_is_a_no_op(self):
        with mock.patch.object(plume, "WINREG_AVAILABLE", False):
            plume.set_launch_at_sign_in(False)  # must not raise

    def test_set_launch_at_sign_in_refuses_without_tray(self):
        with mock.patch.object(plume, "WINREG_AVAILABLE", True), \
                mock.patch.object(plume, "TRAY_AVAILABLE", False):
            with self.assertRaises(plume.ConfigError):
                plume.set_launch_at_sign_in(True)

    def test_set_launch_at_sign_in_writes_registry_value(self):
        fake_winreg = mock.MagicMock()
        with mock.patch.object(plume, "WINREG_AVAILABLE", True), \
                mock.patch.object(plume, "TRAY_AVAILABLE", True), \
                mock.patch.object(plume, "_winreg", fake_winreg):
            plume.set_launch_at_sign_in(True)
        fake_winreg.SetValueEx.assert_called_once()
        args = fake_winreg.SetValueEx.call_args[0]
        self.assertEqual(args[1], plume.AUTOSTART_VALUE_NAME)
        self.assertIn("--start-minimised", args[4])

    def test_set_launch_at_sign_in_deletes_registry_value(self):
        fake_winreg = mock.MagicMock()
        with mock.patch.object(plume, "WINREG_AVAILABLE", True), \
                mock.patch.object(plume, "_winreg", fake_winreg):
            plume.set_launch_at_sign_in(False)
        fake_winreg.DeleteValue.assert_called_once()

    def test_set_launch_at_sign_in_disable_tolerates_missing_value(self):
        fake_winreg = mock.MagicMock()
        fake_winreg.DeleteValue.side_effect = FileNotFoundError
        with mock.patch.object(plume, "WINREG_AVAILABLE", True), \
                mock.patch.object(plume, "_winreg", fake_winreg):
            plume.set_launch_at_sign_in(False)  # must not raise

    def test_launch_at_sign_in_is_set_false_without_winreg(self):
        with mock.patch.object(plume, "WINREG_AVAILABLE", False):
            self.assertFalse(plume.launch_at_sign_in_is_set())

    def test_launch_at_sign_in_is_set_true_when_value_present(self):
        fake_winreg = mock.MagicMock()
        fake_winreg.QueryValueEx.return_value = (plume.autostart_command(), 1)
        with mock.patch.object(plume, "WINREG_AVAILABLE", True), \
                mock.patch.object(plume, "_winreg", fake_winreg):
            self.assertTrue(plume.launch_at_sign_in_is_set())

    def test_launch_at_sign_in_is_set_false_when_value_missing(self):
        fake_winreg = mock.MagicMock()
        fake_winreg.OpenKey.side_effect = FileNotFoundError
        with mock.patch.object(plume, "WINREG_AVAILABLE", True), \
                mock.patch.object(plume, "_winreg", fake_winreg):
            self.assertFalse(plume.launch_at_sign_in_is_set())


class TestSendToShortcut(unittest.TestCase):
    def test_send_to_cmd_path_uses_appdata(self):
        with mock.patch.dict(os.environ, {"APPDATA": r"C:\Fake\AppData"}):
            path = plume.send_to_cmd_path()
        self.assertTrue(path.startswith(r"C:\Fake\AppData"))
        self.assertTrue(path.endswith(plume.SENDTO_SHORTCUT_NAME))
        self.assertIn("SendTo", path)

    def test_set_send_to_shortcut_writes_import_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"APPDATA": tmp}):
                plume.set_send_to_shortcut(True)
                path = plume.send_to_cmd_path()
                self.assertTrue(os.path.isfile(path))
                with open(path, "r", encoding="ascii") as fh:
                    body = fh.read()
        self.assertIn("--import", body)
        self.assertIn('"%~1"', body)
        self.assertNotIn("--start-minimised", body)

    def test_set_send_to_shortcut_removes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"APPDATA": tmp}):
                plume.set_send_to_shortcut(True)
                plume.set_send_to_shortcut(False)
                self.assertFalse(os.path.isfile(plume.send_to_cmd_path()))

    def test_set_send_to_shortcut_disable_tolerates_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"APPDATA": tmp}):
                plume.set_send_to_shortcut(False)  # must not raise


class TestParseImportPath(unittest.TestCase):
    def test_finds_explicit_import_flag(self):
        path, extra = plume.parse_import_path(
            ["plume.py", "--import", r"D:\draft.txt"]
        )
        self.assertEqual(path, r"D:\draft.txt")
        self.assertFalse(extra)

    def test_finds_bare_markdown_argument(self):
        path, extra = plume.parse_import_path(["plume.py", r"D:\notes.md"])
        self.assertEqual(path, r"D:\notes.md")
        self.assertFalse(extra)

    def test_ignores_other_flags(self):
        path, extra = plume.parse_import_path(
            ["plume.py", "--start-minimised", r"D:\a.txt"]
        )
        self.assertEqual(path, r"D:\a.txt")
        self.assertFalse(extra)

    def test_no_candidate_returns_empty(self):
        path, extra = plume.parse_import_path(["plume.py", "--start-minimised"])
        self.assertEqual(path, "")
        self.assertFalse(extra)

    def test_extra_bare_paths_are_flagged_not_dropped_silently(self):
        path, extra = plume.parse_import_path(
            ["plume.py", r"D:\a.txt", r"D:\b.md"]
        )
        self.assertEqual(path, r"D:\a.txt")
        self.assertTrue(extra)

    def test_import_flag_without_a_value_is_ignored(self):
        path, extra = plume.parse_import_path(["plume.py", "--import"])
        self.assertEqual(path, "")
        self.assertFalse(extra)

    def test_empty_argv_returns_empty(self):
        path, extra = plume.parse_import_path([])
        self.assertEqual(path, "")
        self.assertFalse(extra)


class TestLooksLikeImportablePath(unittest.TestCase):
    def test_accepts_existing_quoted_txt_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.txt")
            open(path, "w").close()
            self.assertEqual(
                plume.looks_like_importable_path('"{}"'.format(path)), path
            )

    def test_rejects_prose(self):
        self.assertEqual(plume.looks_like_importable_path("Bonjour tout le monde"), "")

    def test_rejects_missing_file(self):
        self.assertEqual(plume.looks_like_importable_path(r"D:\missing.txt"), "")

    def test_rejects_wrong_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.docx")
            open(path, "w").close()
            self.assertEqual(plume.looks_like_importable_path(path), "")

    def test_rejects_empty_string(self):
        self.assertEqual(plume.looks_like_importable_path(""), "")


class TestBackendHardening(unittest.TestCase):
    KEY_CONFIG = {"anthropic_api_key": "sk-test", "anthropic_model": "m"}

    def test_anthropic_max_tokens_cutoff(self):
        payload = {"stop_reason": "max_tokens", "content": [{"type": "text", "text": "..."}]}
        with mock.patch.object(plume, "_http_post_json", return_value=payload):
            with self.assertRaises(plume.BackendError):
                plume.call_anthropic(self.KEY_CONFIG, "sys", "user")

    def test_anthropic_non_dict_response(self):
        with mock.patch.object(plume, "_http_post_json", return_value=["oops"]):
            with self.assertRaises(plume.BackendError):
                plume.call_anthropic(self.KEY_CONFIG, "sys", "user")

    def test_ollama_error_field(self):
        payload = {"error": "model not found", "message": {"content": "{}"}}
        with mock.patch.object(plume, "_http_post_json", return_value=payload):
            with self.assertRaises(plume.BackendError):
                plume.call_ollama({"ollama_model": "x"}, "sys", "user")

    def test_ollama_non_dict_response(self):
        with mock.patch.object(plume, "_http_post_json", return_value=[1, 2]):
            with self.assertRaises(plume.BackendError):
                plume.call_ollama({"ollama_model": "x"}, "sys", "user")

    def test_ollama_error_message_has_no_prompt_fragment(self):
        payload = {"error": "leaked-prompt-fragment", "message": {}}
        with mock.patch.object(plume, "_http_post_json", return_value=payload):
            try:
                plume.call_ollama({"ollama_model": "x"}, "sys", "user")
            except plume.BackendError as exc:
                self.assertNotIn("leaked-prompt-fragment", str(exc))
            else:
                self.fail("expected BackendError")

    def test_ollama_http_error_names_ollama_not_claude(self):
        # 429 is now retried (v1.17); mock the sleep so this stays instant.
        with mock.patch.object(plume, "time"), \
                mock.patch("urllib.request.urlopen", side_effect=self._http_error(429)):
            try:
                plume.call_ollama({"ollama_model": "x"}, "sys", "user")
            except plume.BackendError as exc:
                message = str(exc)
                self.assertIn("Ollama", message)
                self.assertNotIn("Claude", message)
            else:
                self.fail("expected BackendError")

    def test_list_models_non_dict_body(self):
        class _Resp:
            def __enter__(self_inner):
                return self_inner
            def __exit__(self_inner, *a):
                return False
            def read(self_inner):
                return b"[]"  # a JSON list, not an object
        with mock.patch("urllib.request.urlopen", return_value=_Resp()):
            with self.assertRaises(plume.BackendError):
                plume.list_ollama_models()

    @staticmethod
    def _http_error(code):
        def _raise(*args, **kwargs):
            raise urllib.error.HTTPError(
                "http://localhost:11434/api/chat", code, "err", {},
                io.BytesIO(b"detail"),
            )
        return _raise


class TestRunBackendFallback(unittest.TestCase):
    """v1.38, notes_015 2.E: opt-in one-shot Ollama fallback after Claude."""

    def test_no_fallback_by_default(self):
        snapshot = {"backend": "anthropic", "ollama_model": "llama3"}
        with mock.patch.object(
            plume, "call_anthropic", side_effect=plume.BackendError("down")
        ), mock.patch.object(plume, "call_ollama") as ollama:
            with self.assertRaises(plume.BackendError):
                plume.run_backend(snapshot, "sys", "user")
        ollama.assert_not_called()

    def test_falls_back_when_opted_in_with_a_model_configured(self):
        snapshot = {
            "backend": "anthropic", "ollama_model": "llama3",
            "fallback_to_ollama": True,
        }
        with mock.patch.object(
            plume, "call_anthropic", side_effect=plume.BackendError("down")
        ), mock.patch.object(plume, "call_ollama", return_value="Bonjour"):
            result = plume.run_backend(snapshot, "sys", "user")
        self.assertEqual(result, "Bonjour")
        self.assertTrue(snapshot["_used_fallback"])

    def test_no_fallback_without_an_ollama_model(self):
        snapshot = {
            "backend": "anthropic", "ollama_model": "  ",
            "fallback_to_ollama": True,
        }
        with mock.patch.object(
            plume, "call_anthropic", side_effect=plume.BackendError("down")
        ), mock.patch.object(plume, "call_ollama") as ollama:
            with self.assertRaises(plume.BackendError):
                plume.run_backend(snapshot, "sys", "user")
        ollama.assert_not_called()

    def test_no_fallback_for_a_cancelled_request(self):
        snapshot = {
            "backend": "anthropic", "ollama_model": "llama3",
            "fallback_to_ollama": True,
        }
        with mock.patch.object(
            plume, "call_anthropic",
            side_effect=plume.BackendError("The request was cancelled."),
        ), mock.patch.object(plume, "call_ollama") as ollama:
            with self.assertRaises(plume.BackendError):
                plume.run_backend(snapshot, "sys", "user")
        ollama.assert_not_called()

    def test_ollama_never_falls_back_to_claude(self):
        snapshot = {
            "backend": "ollama", "ollama_model": "llama3",
            "fallback_to_ollama": True,
        }
        with mock.patch.object(
            plume, "call_ollama", side_effect=plume.BackendError("down")
        ), mock.patch.object(plume, "call_anthropic") as anthropic:
            with self.assertRaises(plume.BackendError):
                plume.run_backend(snapshot, "sys", "user")
        anthropic.assert_not_called()

    def test_translate_appends_fallback_note(self):
        snapshot = {"default_direction": plume.DIR_AUTO}

        def fake_run_backend(config_snapshot, system_prompt, user_text):
            config_snapshot["_used_fallback"] = True
            return as_json(valid_result())

        with mock.patch.object(plume, "run_backend", side_effect=fake_run_backend):
            result = plume.translate(snapshot, "Hello")
        self.assertTrue(
            any("Ollama" in note for note in result["notes"])
        )

    def test_translate_omits_fallback_note_when_not_used(self):
        snapshot = {"default_direction": plume.DIR_AUTO}

        with mock.patch.object(
            plume, "run_backend", return_value=as_json(valid_result())
        ):
            result = plume.translate(snapshot, "Hello")
        self.assertFalse(any("Ollama" in note for note in result["notes"]))


class TestHttpBackoff(unittest.TestCase):
    def test_retries_transient_failure_then_succeeds(self):
        calls = {"n": 0}

        def fake_urlopen(request, timeout=None):
            calls["n"] += 1
            if calls["n"] < 3:
                raise urllib.error.HTTPError(
                    "https://x", 503, "busy", {}, io.BytesIO(b""),
                )
            return mock.MagicMock(
                __enter__=lambda s: s,
                __exit__=lambda *a: None,
                read=lambda *a, **k: b'{"ok": true}',
            )

        with mock.patch.object(plume, "time"), \
                mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            data = plume._http_post_json(
                "https://x", {}, {"content-type": "application/json"}, 5
            )
        self.assertEqual(data, {"ok": True})
        self.assertEqual(calls["n"], 3)

    def test_401_is_not_retried(self):
        def fake_urlopen(request, timeout=None):
            raise urllib.error.HTTPError(
                "https://x", 401, "no", {}, io.BytesIO(b""),
            )

        with mock.patch.object(plume, "time") as fake_time, \
                mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(plume.BackendError):
                plume._http_post_json(
                    "https://x", {}, {"content-type": "application/json"}, 5
                )
        fake_time.sleep.assert_not_called()

    def test_exhausts_retries_and_raises(self):
        calls = {"n": 0}

        def fake_urlopen(request, timeout=None):
            calls["n"] += 1
            raise urllib.error.HTTPError(
                "https://x", 503, "busy", {}, io.BytesIO(b""),
            )

        with mock.patch.object(plume, "time"), \
                mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(plume.BackendError):
                plume._http_post_json(
                    "https://x", {}, {"content-type": "application/json"}, 5,
                    max_attempts=3,
                )
        self.assertEqual(calls["n"], 3)

    def test_dropped_connection_is_retried(self):
        calls = {"n": 0}

        def fake_urlopen(request, timeout=None):
            calls["n"] += 1
            if calls["n"] < 2:
                raise urllib.error.URLError("connection reset")
            return mock.MagicMock(
                __enter__=lambda s: s,
                __exit__=lambda *a: None,
                read=lambda *a, **k: b'{"ok": true}',
            )

        with mock.patch.object(plume, "time"), \
                mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            data = plume._http_post_json(
                "https://x", {}, {"content-type": "application/json"}, 5
            )
        self.assertEqual(data, {"ok": True})

    def test_backoff_delay_honours_retry_after_header(self):
        self.assertEqual(plume._backoff_delay(0, retry_after="2"), 2.0)

    def test_backoff_delay_does_not_shorten_a_long_retry_after(self):
        # v1.27: a server-requested wait longer than the exponential cap is
        # returned as-is rather than silently shortened; whether it fits
        # the retry-wait budget is _http_post_json's decision.
        self.assertEqual(plume._backoff_delay(0, retry_after="999"), 999.0)

    def test_backoff_delay_honours_http_date_retry_after(self):
        future = formatdate(timeval=None, usegmt=True)  # "now" as an HTTP-date
        delay = plume._backoff_delay(0, retry_after=future)
        self.assertGreaterEqual(delay, 0.0)
        self.assertLess(delay, 5.0)  # "now" -> a few seconds at most, not huge

    def test_backoff_delay_past_http_date_is_zero_not_negative(self):
        past = formatdate(timeval=0, usegmt=True)  # 1970-01-01
        self.assertEqual(plume._backoff_delay(0, retry_after=past), 0.0)

    def test_backoff_delay_ignores_invalid_retry_after(self):
        delay = plume._backoff_delay(0, retry_after="not-a-number")
        self.assertGreater(delay, 0.0)
        self.assertLessEqual(delay, plume.HTTP_BACKOFF_BASE)

    def test_backoff_delay_exponential_never_exceeds_cap(self):
        # v1.27: jitter is applied inside the cap, not added on top of it.
        for attempt in range(12):
            delay = plume._backoff_delay(attempt)
            self.assertGreater(delay, 0.0)
            self.assertLessEqual(delay, plume.HTTP_BACKOFF_CAP)

    def test_retry_after_exceeding_budget_is_refused(self):
        def fake_urlopen(request, timeout=None):
            raise urllib.error.HTTPError(
                "https://x", 503, "busy", {"Retry-After": "999"}, io.BytesIO(b""),
            )

        with mock.patch.object(plume, "time"), \
                mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(plume.BackendError) as ctx:
                plume._http_post_json(
                    "https://x", {}, {"content-type": "application/json"}, 5,
                    max_retry_wait=30.0,
                )
        self.assertIn("longer pause", str(ctx.exception))

    def test_http_error_body_is_closed_before_retry(self):
        closed = {"n": 0}

        class TrackedBody(io.BytesIO):
            def close(self_inner):
                closed["n"] += 1
                super().close()

        calls = {"n": 0}

        def fake_urlopen(request, timeout=None):
            calls["n"] += 1
            if calls["n"] < 2:
                raise urllib.error.HTTPError(
                    "https://x", 503, "busy", {}, TrackedBody(b""),
                )
            return mock.MagicMock(
                __enter__=lambda s: s, __exit__=lambda *a: None,
                read=lambda *a, **k: b'{"ok": true}',
            )

        with mock.patch.object(plume, "time"), \
                mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            plume._http_post_json(
                "https://x", {}, {"content-type": "application/json"}, 5
            )
        self.assertEqual(closed["n"], 1)

    def test_incomplete_read_is_retried(self):
        calls = {"n": 0}

        def fake_urlopen(request, timeout=None):
            calls["n"] += 1
            if calls["n"] < 2:
                raise plume.http.client.IncompleteRead(b"partial")
            return mock.MagicMock(
                __enter__=lambda s: s, __exit__=lambda *a: None,
                read=lambda *a, **k: b'{"ok": true}',
            )

        with mock.patch.object(plume, "time"), \
                mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            data = plume._http_post_json(
                "https://x", {}, {"content-type": "application/json"}, 5
            )
        self.assertEqual(data, {"ok": True})
        self.assertEqual(calls["n"], 2)

    def test_default_retryable_codes_exclude_529(self):
        def fake_urlopen(request, timeout=None):
            raise urllib.error.HTTPError(
                "https://x", 529, "overloaded", {}, io.BytesIO(b""),
            )

        with mock.patch.object(plume, "time") as fake_time, \
                mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(plume.BackendError):
                plume._http_post_json(
                    "https://x", {}, {"content-type": "application/json"}, 5
                )
        fake_time.sleep.assert_not_called()

    def test_retryable_codes_can_opt_in_extra_codes(self):
        calls = {"n": 0}

        def fake_urlopen(request, timeout=None):
            calls["n"] += 1
            if calls["n"] < 2:
                raise urllib.error.HTTPError(
                    "https://x", 529, "overloaded", {}, io.BytesIO(b""),
                )
            return mock.MagicMock(
                __enter__=lambda s: s, __exit__=lambda *a: None,
                read=lambda *a, **k: b'{"ok": true}',
            )

        with mock.patch.object(plume, "time"), \
                mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            data = plume._http_post_json(
                "https://x", {}, {"content-type": "application/json"}, 5,
                retryable_codes=plume.HTTP_RETRYABLE_CODES | {529},
            )
        self.assertEqual(data, {"ok": True})

    def test_oversized_response_is_rejected_without_retry(self):
        calls = {"n": 0}

        def fake_urlopen(request, timeout=None):
            calls["n"] += 1
            return mock.MagicMock(
                __enter__=lambda s: s, __exit__=lambda *a: None,
                read=lambda *a, **k: b"x" * (plume.HTTP_MAX_RESPONSE_BYTES + 1),
            )

        with mock.patch.object(plume, "time"), \
                mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(plume.BackendError) as ctx:
                plume._http_post_json(
                    "https://x", {}, {"content-type": "application/json"}, 5
                )
        self.assertIn("size limit", str(ctx.exception))
        self.assertEqual(calls["n"], 1)

    def test_http_error_body_is_not_read_before_close(self):
        # v1.38: retrying must not wait for a potentially unbounded error
        # body to drain; only close() is called, never read().
        read_calls = {"n": 0}

        class TrackedBody(io.BytesIO):
            def read(self_inner, *a, **k):
                read_calls["n"] += 1
                return super().read(*a, **k)

        calls = {"n": 0}

        def fake_urlopen(request, timeout=None):
            calls["n"] += 1
            if calls["n"] < 2:
                raise urllib.error.HTTPError(
                    "https://x", 503, "busy", {}, TrackedBody(b"error detail"),
                )
            return mock.MagicMock(
                __enter__=lambda s: s, __exit__=lambda *a: None,
                read=lambda *a, **k: b'{"ok": true}',
            )

        with mock.patch.object(plume, "time"), \
                mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            plume._http_post_json(
                "https://x", {}, {"content-type": "application/json"}, 5
            )
        self.assertEqual(read_calls["n"], 0)

    def test_ssl_error_is_not_retried(self):
        calls = {"n": 0}

        def fake_urlopen(request, timeout=None):
            calls["n"] += 1
            raise ssl.SSLError("certificate verify failed")

        with mock.patch.object(plume, "time"), \
                mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(plume.BackendError) as ctx:
                plume._http_post_json(
                    "https://x", {}, {"content-type": "application/json"}, 5
                )
        self.assertIn("secure connection", str(ctx.exception).lower())
        self.assertEqual(calls["n"], 1)

    def test_urlerror_wrapping_ssl_error_is_not_retried(self):
        calls = {"n": 0}

        def fake_urlopen(request, timeout=None):
            calls["n"] += 1
            raise urllib.error.URLError(ssl.SSLError("certificate verify failed"))

        with mock.patch.object(plume, "time"), \
                mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(plume.BackendError) as ctx:
                plume._http_post_json(
                    "https://x", {}, {"content-type": "application/json"}, 5
                )
        self.assertIn("secure connection", str(ctx.exception).lower())
        self.assertEqual(calls["n"], 1)

    def test_url_error_message_omits_raw_reason(self):
        def fake_urlopen(request, timeout=None):
            raise urllib.error.URLError("a secret internal detail")

        with mock.patch.object(plume, "time"), \
                mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(plume.BackendError) as ctx:
                plume._http_post_json(
                    "https://x", {}, {"content-type": "application/json"}, 5,
                    max_attempts=1,
                )
        self.assertNotIn("a secret internal detail", str(ctx.exception))

    def test_cancelled_before_first_attempt_raises_immediately(self):
        event = threading.Event()
        event.set()

        def fake_urlopen(request, timeout=None):
            self.fail("urlopen should not be called when already cancelled")

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(plume.BackendError) as ctx:
                plume._http_post_json(
                    "https://x", {}, {"content-type": "application/json"}, 5,
                    cancel_event=event,
                )
        self.assertIn("cancelled", str(ctx.exception).lower())

    def test_cancelled_before_backoff_wait_stops_retry(self):
        # Despite the name this replaces, this mocks plume.time entirely and
        # sets the event before wait_or_give_up's own cancelled() check —
        # i.e. cancellation observed before backoff starts, not a cancel
        # arriving while a wait is already blocked (notes_017 3 flagged the
        # old name as overstating that coverage). See
        # TestHttpLoopbackIntegration.test_cancellation_during_backoff_wait_wakes_promptly
        # for a genuine mid-wait cancellation against a real clock/socket.
        event = threading.Event()
        calls = {"n": 0}

        def fake_urlopen(request, timeout=None):
            calls["n"] += 1
            # Simulate a cancel arriving while this attempt was in flight.
            event.set()
            raise urllib.error.HTTPError(
                "https://x", 503, "busy", {}, io.BytesIO(b""),
            )

        with mock.patch.object(plume, "time"), \
                mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(plume.BackendError) as ctx:
                plume._http_post_json(
                    "https://x", {}, {"content-type": "application/json"}, 5,
                    cancel_event=event,
                )
        self.assertEqual(calls["n"], 1)
        self.assertIn("cancelled", str(ctx.exception).lower())

    def test_cancelled_after_successful_read_is_not_delivered(self):
        event = threading.Event()

        def fake_urlopen(request, timeout=None):
            event.set()
            return mock.MagicMock(
                __enter__=lambda s: s, __exit__=lambda *a: None,
                read=lambda *a, **k: b'{"ok": true}',
            )

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(plume.BackendError) as ctx:
                plume._http_post_json(
                    "https://x", {}, {"content-type": "application/json"}, 5,
                    cancel_event=event,
                )
        self.assertIn("cancelled", str(ctx.exception).lower())

    def test_not_cancelled_delivers_normally(self):
        event = threading.Event()  # never set

        def fake_urlopen(request, timeout=None):
            return mock.MagicMock(
                __enter__=lambda s: s, __exit__=lambda *a: None,
                read=lambda *a, **k: b'{"ok": true}',
            )

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            data = plume._http_post_json(
                "https://x", {}, {"content-type": "application/json"}, 5,
                cancel_event=event,
            )
        self.assertEqual(data, {"ok": True})


class _QuietHandler(http.server.BaseHTTPRequestHandler):
    """Base for loopback fixtures below: no per-request stderr logging."""

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        pass

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)

    def _send_json(self, status, body, headers=None):
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def _start_loopback_server(handler_cls):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _stop_loopback_server(server, thread):
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


class TestHttpLoopbackIntegration(unittest.TestCase):
    """Real local-socket coverage for the v1.38 cooperative-cancel contract
    (notes_017 follow-up): a genuine ThreadingHTTPServer, real threads and
    real threading.Event objects — no mocked urlopen or clock, so backoff
    waiting and cancellation are exercised exactly as they run in
    production. This covers the transport-level criteria from notes_017's
    "Recommended completion criteria"; the literal button-click GUI
    scenario (Clear/close against a real window) was verified separately
    by hand against the real PlumeApp, the same one-off pattern v1.38
    used, and is not part of this headless suite.
    """

    def test_uncancelled_delayed_request_still_succeeds(self):
        class Handler(_QuietHandler):
            def do_POST(self):
                self._read_body()
                time.sleep(0.15)
                self._send_json(200, {"ok": True})

        server, thread = _start_loopback_server(Handler)
        try:
            url = "http://127.0.0.1:{}/".format(server.server_port)
            started = time.monotonic()
            data = plume._http_post_json(
                url, {}, {"content-type": "application/json"}, timeout=5,
            )
            elapsed = time.monotonic() - started
        finally:
            _stop_loopback_server(server, thread)
        self.assertEqual(data, {"ok": True})
        self.assertGreaterEqual(elapsed, 0.15)

    def test_cancellation_during_backoff_wait_wakes_promptly(self):
        request_count = {"n": 0}

        class Handler(_QuietHandler):
            def do_POST(self):
                self._read_body()
                request_count["n"] += 1
                self._send_json(503, {"error": "busy"}, {"Retry-After": "2"})

        server, thread = _start_loopback_server(Handler)
        try:
            url = "http://127.0.0.1:{}/".format(server.server_port)
            cancel_event = threading.Event()
            threading.Timer(0.1, cancel_event.set).start()
            started = time.monotonic()
            with self.assertRaises(plume.BackendError) as ctx:
                plume._http_post_json(
                    url, {}, {"content-type": "application/json"}, timeout=5,
                    cancel_event=cancel_event, max_attempts=4, max_retry_wait=30.0,
                )
            elapsed = time.monotonic() - started
        finally:
            _stop_loopback_server(server, thread)
        # The Retry-After: 2 backoff would take ~2s uninterrupted; waking
        # promptly on cancellation keeps this well under that, with a
        # generous bound (notes_017 3) to absorb real scheduling jitter.
        self.assertLess(elapsed, 1.0)
        self.assertIn("cancelled", str(ctx.exception).lower())
        self.assertEqual(request_count["n"], 1)

    def test_newer_request_succeeds_while_an_older_one_is_cancelled_mid_backoff(self):
        # Mirrors PlumeApp._clear()/_translate(): an in-flight request's own
        # cancel_event is .set() (what _new_http_cancel does to the old
        # event) while a second call proceeds on a fresh event, exercising
        # the real mechanism behind "Clear supersedes a pending request"
        # without needing a live window.
        old_request_count = {"n": 0}

        class OldHandler(_QuietHandler):
            def do_POST(self):
                self._read_body()
                old_request_count["n"] += 1
                self._send_json(503, {"error": "busy"}, {"Retry-After": "2"})

        class NewHandler(_QuietHandler):
            def do_POST(self):
                self._read_body()
                self._send_json(200, {"ok": True, "which": "new"})

        old_server, old_thread = _start_loopback_server(OldHandler)
        new_server, new_thread = _start_loopback_server(NewHandler)
        try:
            old_url = "http://127.0.0.1:{}/".format(old_server.server_port)
            new_url = "http://127.0.0.1:{}/".format(new_server.server_port)
            old_cancel_event = threading.Event()
            old_result = {}

            def run_old():
                try:
                    plume._http_post_json(
                        old_url, {}, {"content-type": "application/json"},
                        timeout=5, cancel_event=old_cancel_event,
                        max_attempts=4, max_retry_wait=30.0,
                    )
                except plume.BackendError as exc:
                    old_result["error"] = str(exc)

            old_thread_runner = threading.Thread(target=run_old, daemon=True)
            old_thread_runner.start()
            # Give the old request time to reach the server and enter its
            # backoff wait before "superseding" it, the same way a user's
            # Clear click would land while a real request is retrying.
            time.sleep(0.1)
            old_cancel_event.set()

            new_cancel_event = threading.Event()
            new_data = plume._http_post_json(
                new_url, {}, {"content-type": "application/json"}, timeout=5,
                cancel_event=new_cancel_event,
            )

            old_thread_runner.join(timeout=2)
        finally:
            _stop_loopback_server(old_server, old_thread)
            _stop_loopback_server(new_server, new_thread)

        self.assertEqual(new_data, {"ok": True, "which": "new"})
        self.assertIn("cancelled", old_result.get("error", "").lower())
        self.assertEqual(old_request_count["n"], 1)


class TestResponseExtraction(unittest.TestCase):
    def test_anthropic_text_from_response_extracts_text(self):
        data = {"content": [{"type": "text", "text": "Bonjour"}]}
        self.assertEqual(plume._anthropic_text_from_response(data), "Bonjour")

    def test_anthropic_text_from_response_cut_short(self):
        data = {"stop_reason": "max_tokens", "content": []}
        with self.assertRaises(plume.BackendError):
            plume._anthropic_text_from_response(data)

    def test_anthropic_text_from_response_rejects_non_dict(self):
        with self.assertRaises(plume.BackendError):
            plume._anthropic_text_from_response(["oops"])

    def test_ollama_text_from_response_extracts_content(self):
        data = {"message": {"content": "Bonjour"}}
        self.assertEqual(plume._ollama_text_from_response(data), "Bonjour")

    def test_ollama_text_from_response_error_field(self):
        with self.assertRaises(plume.BackendError):
            plume._ollama_text_from_response({"error": "boom", "message": {}})


class TestElevenLabsTTS(unittest.TestCase):
    def test_missing_key_raises_without_network_call(self):
        with self.assertRaises(plume.BackendError):
            plume.call_elevenlabs_tts({"elevenlabs_api_key": ""}, "Bonjour")

    def test_success_returns_raw_audio_bytes(self):
        class _Resp:
            def __enter__(self_inner):
                return self_inner
            def __exit__(self_inner, *a):
                return False
            def read(self_inner):
                return b"\x01\x02\x03\x04"  # stand-in for raw PCM audio

        with mock.patch("urllib.request.urlopen", return_value=_Resp()):
            audio = plume.call_elevenlabs_tts(
                {"elevenlabs_api_key": "sk_test"}, "Bonjour"
            )
        self.assertEqual(audio, b"\x01\x02\x03\x04")

    def test_401_maps_to_api_key_hint(self):
        with mock.patch("urllib.request.urlopen", side_effect=self._http_error(401)):
            with self.assertRaises(plume.BackendError) as ctx:
                plume.call_elevenlabs_tts({"elevenlabs_api_key": "bad"}, "hi")
            self.assertIn("API key", str(ctx.exception))

    def test_error_message_never_contains_spoken_text(self):
        secret = "meet me at the old bridge"
        with mock.patch("urllib.request.urlopen", side_effect=self._http_error(500)):
            try:
                plume.call_elevenlabs_tts({"elevenlabs_api_key": "k"}, secret)
            except plume.BackendError as exc:
                self.assertNotIn(secret, str(exc))
            else:
                self.fail("expected BackendError")

    @staticmethod
    def _http_error(code):
        def _raise(*args, **kwargs):
            raise urllib.error.HTTPError(
                "https://api.elevenlabs.io/v1/text-to-speech/x", code, "err",
                {}, io.BytesIO(b"detail"),
            )
        return _raise


class TestPcmToWav(unittest.TestCase):
    def test_round_trip_preserves_pcm_and_format(self):
        pcm = b"\x00\x01\x02\x03" * 100
        wav_bytes = plume.pcm_to_wav_bytes(pcm, sample_rate=16000, sample_width=2, channels=1)
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
            self.assertEqual(wav_file.getnchannels(), 1)
            self.assertEqual(wav_file.getsampwidth(), 2)
            self.assertEqual(wav_file.getframerate(), 16000)
            self.assertEqual(wav_file.readframes(wav_file.getnframes()), pcm)

    def test_output_starts_with_riff_header(self):
        wav_bytes = plume.pcm_to_wav_bytes(b"\x00\x01", sample_rate=16000)
        self.assertTrue(wav_bytes.startswith(b"RIFF"))

    def test_slow_speech_rate_scales_frame_rate(self):
        # Pins the v1.12 "Slow" mechanism: no extra synthesis call, just a
        # lower WAV frame rate on the same PCM data.
        pcm = b"\x00\x01\x02\x03" * 50
        slow_rate = int(plume.ELEVENLABS_SAMPLE_RATE * plume.SLOW_SPEECH_RATE_FACTOR)
        wav_bytes = plume.pcm_to_wav_bytes(pcm, sample_rate=slow_rate)
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
            self.assertEqual(wav_file.getframerate(), slow_rate)
            self.assertLess(wav_file.getframerate(), plume.ELEVENLABS_SAMPLE_RATE)
            self.assertEqual(wav_file.readframes(wav_file.getnframes()), pcm)


class TestPrivacyOfDiagnostics(unittest.TestCase):
    SECRET = "please meet me at the old bridge at midnight"

    def test_status_line_excludes_source(self):
        line = plume.format_status(dict(plume.DEFAULT_CONFIG), len(self.SECRET))
        self.assertNotIn(self.SECRET, line)

    def test_status_line_reports_backend(self):
        line = plume.format_status(dict(plume.DEFAULT_CONFIG), 10)
        self.assertIn("Anthropic", line)

    def test_backend_errors_never_contain_source(self):
        # A validation error message must not echo submitted content.
        try:
            plume.parse_translation_result(self.SECRET, plume.DIR_AUTO)
        except plume.TranslationValidationError as exc:
            self.assertNotIn(self.SECRET, str(exc))
        else:
            self.fail("expected a validation error")

    def test_masked_key(self):
        masked = plume.mask_api_key("sk-ant-abcdefghijklmnop")
        self.assertTrue(masked.startswith("sk-a"))
        self.assertIn("\u2022", masked)
        self.assertNotIn("abcdefghij", masked)


class TestSourceSize(unittest.TestCase):
    def test_empty_rejected(self):
        ok, _ = plume.validate_source_size("   ")
        self.assertFalse(ok)

    def test_too_long_rejected(self):
        ok, msg = plume.validate_source_size("x" * 3000, limit=2000)
        self.assertFalse(ok)
        self.assertIn("longer", msg)

    def test_normal_accepted(self):
        ok, _ = plume.validate_source_size("Bonjour", limit=2000)
        self.assertTrue(ok)


class TestFileImport(unittest.TestCase):
    def _write(self, tmp, name, data: bytes) -> str:
        path = os.path.join(tmp, name)
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def test_reads_utf8_text_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "a.txt", "Bonjour café".encode("utf-8"))
            self.assertEqual(plume.read_import_text(path, 2000), "Bonjour café")

    def test_reads_utf8_bom_text_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "a.txt", b"\xef\xbb\xbfBonjour")
            self.assertEqual(plume.read_import_text(path, 2000), "Bonjour")

    def test_reads_utf16_bom_text_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "a.txt", "Bonjour".encode("utf-16"))
            self.assertEqual(plume.read_import_text(path, 2000), "Bonjour")

    def test_reads_markdown_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "a.md", "# Title".encode("utf-8"))
            self.assertEqual(plume.read_import_text(path, 2000), "# Title")

    def test_rejects_unsupported_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "a.docx", b"whatever")
            with self.assertRaises(ValueError):
                plume.read_import_text(path, 2000)

    def test_rejects_oversized_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "a.txt", b"x" * (plume.IMPORT_BYTE_LIMIT + 1))
            with self.assertRaises(ValueError):
                plume.read_import_text(path, 10_000_000)

    def test_rejects_over_character_limit_without_truncating(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "a.txt", ("x" * 50).encode("utf-8"))
            with self.assertRaises(ValueError):
                plume.read_import_text(path, 10)

    def test_normalises_crlf_line_endings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "a.txt", "line one\r\nline two".encode("utf-8"))
            self.assertEqual(plume.read_import_text(path, 2000), "line one\nline two")

    def test_rejects_embedded_null_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "a.txt", b"before\x00after")
            with self.assertRaises(ValueError):
                plume.read_import_text(path, 2000)

    def test_rejects_invalid_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            # 0xff is never a valid UTF-8 byte; two of them also do not
            # match the UTF-16 BOM prefix (which is 0xff 0xfe specifically).
            path = self._write(tmp, "a.txt", b"broken \xff\xff bytes")
            with self.assertRaises(ValueError):
                plume.read_import_text(path, 2000)

    def test_rejects_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                plume.read_import_text(os.path.join(tmp, "missing.txt"), 2000)

    def test_rejects_a_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                plume.read_import_text(tmp, 2000)


class TestStaleRequest(unittest.TestCase):
    def test_earlier_result_cannot_replace_later(self):
        # Simulate two requests: rid 1 launched, then rid 2 launched (current=2).
        current = 2
        earlier_rid = 1
        later_rid = 2
        # The earlier response arriving after the later request must be treated
        # as stale and discarded.
        self.assertTrue(plume.result_is_stale(earlier_rid, current))
        self.assertFalse(plume.result_is_stale(later_rid, current))

    def test_cleared_request_is_stale(self):
        # After Clear increments nothing but a new request supersedes.
        self.assertTrue(plume.result_is_stale(3, 5))


class TestFinishingTouch(unittest.TestCase):
    def test_appends_with_single_space(self):
        self.assertEqual(
            plume.append_finishing_touch("J'espère que tu vas bien !", ":p"),
            "J'espère que tu vas bien ! :p",
        )

    def test_trims_trailing_space_before_touch(self):
        self.assertEqual(plume.append_finishing_touch("Salut   ", ":)"), "Salut :)")

    def test_none_sentinel_leaves_text_unchanged(self):
        self.assertEqual(
            plume.append_finishing_touch("À bientôt", plume.FINISHING_TOUCH_NONE),
            "À bientôt",
        )

    def test_blank_or_missing_touch_leaves_text_unchanged(self):
        self.assertEqual(plume.append_finishing_touch("À bientôt", ""), "À bientôt")
        self.assertEqual(plume.append_finishing_touch("À bientôt", "   "), "À bientôt")
        self.assertEqual(plume.append_finishing_touch("À bientôt", None), "À bientôt")

    def test_empty_base_returns_empty(self):
        self.assertEqual(plume.append_finishing_touch("", ":p"), "")
        self.assertEqual(plume.append_finishing_touch(None, ":p"), "")

    def test_catalogue_starts_with_none_and_holds_emotes(self):
        self.assertEqual(plume.FINISHING_TOUCHES[0], plume.FINISHING_TOUCH_NONE)
        for mark in (
            ":)", ":p", ";)", "xD", "mdr", "ptdr", "jpp",
            ":D", ":/", ":'(", ":o", "^^", "<3", "xo",
        ):
            self.assertIn(mark, plume.FINISHING_TOUCHES)

    def test_catalogue_excludes_greetings_and_in_sentence_abbreviations(self):
        # Curation guard: greetings, in-sentence abbreviations and standalone
        # replies must never be offered as an appendable finishing touch.
        for banned in ("slt", "bjr", "rdv", "bcp", "mtn", "wesh", "meuf"):
            self.assertNotIn(banned, plume.FINISHING_TOUCHES)


class TestCasualSignoff(unittest.TestCase):
    def test_catalogue_starts_with_none_and_holds_curated_terms(self):
        self.assertEqual(plume.CASUAL_SIGNOFFS[0], plume.CASUAL_SIGNOFF_NONE)
        self.assertIn("tkt", plume.CASUAL_SIGNOFFS)
        self.assertIn("grave", plume.CASUAL_SIGNOFFS)

    def test_catalogue_holds_the_v1_41_expansion(self):
        # v1.41 (notes_018): further register-shifting-but-self-contained
        # suffixes, still each a reassurance/farewell/plain reaction rather
        # than a comment on a person or thing.
        for term in (
            "dsl", "bof", "nickel", "tranquille", "carrément", "biz", "a+",
            "merci", "trop bien",
        ):
            self.assertIn(term, plume.CASUAL_SIGNOFFS)

    def test_catalogue_excludes_wider_slang_and_greetings(self):
        # Curation guard: v1.14 ships only the two terms notes_004 named as
        # safe examples. Greetings, in-sentence abbreviations, nouns, and
        # harsher or more culturally loaded slang must never appear here,
        # even though several are listed in Essential Shortcuts.txt.
        banned = (
            "slt", "bjr", "rdv", "bcp", "mtn", "jsp", "oklm",
            "wesh", "meuf", "keuf", "boloss", "bg", "sah", "askip", "frr",
            "s/o", "chelou", "ouf", "relou", "stylé", "kiffer", "chanmé",
            # notes_018 (v1.41) also proposed these; held out for the same
            # reason as the rest of this list (a verdict on a person/thing,
            # a question or greeting fragment rather than a suffix, or not
            # meaningfully distinct from an already-banned near-synonym).
            "cheum", "pk", "cv", "mortel", "gèrer", "tu gères",
        )
        for term in banned:
            self.assertNotIn(term, plume.CASUAL_SIGNOFFS)

    def test_catalogue_disjoint_from_emote_group(self):
        # The two pickers are independent controls (v1.14 is not a copy of
        # the v1.2 mechanism): no actionable term should appear in both
        # catalogues (both legitimately share their own "None" sentinel).
        signoffs = set(plume.CASUAL_SIGNOFFS) - {plume.CASUAL_SIGNOFF_NONE}
        emotes = set(plume.FINISHING_TOUCHES) - {plume.FINISHING_TOUCH_NONE}
        self.assertFalse(signoffs & emotes)

    def test_compose_joins_emote_and_signoff(self):
        self.assertEqual(plume.compose_finishing_touch(":)", "tkt"), ":) tkt")

    def test_compose_emote_only(self):
        self.assertEqual(
            plume.compose_finishing_touch(":)", plume.CASUAL_SIGNOFF_NONE), ":)"
        )

    def test_compose_signoff_only(self):
        self.assertEqual(
            plume.compose_finishing_touch(plume.FINISHING_TOUCH_NONE, "grave"), "grave"
        )

    def test_compose_both_none_is_empty(self):
        self.assertEqual(
            plume.compose_finishing_touch(
                plume.FINISHING_TOUCH_NONE, plume.CASUAL_SIGNOFF_NONE
            ),
            "",
        )

    def test_compose_feeds_append_finishing_touch(self):
        composed = plume.compose_finishing_touch(":)", "tkt")
        self.assertEqual(
            plume.append_finishing_touch("On se voit demain", composed),
            "On se voit demain :) tkt",
        )

    def test_display_shows_bracketed_gloss(self):
        self.assertEqual(plume.casual_signoff_display("tkt"), "tkt (don't worry)")
        self.assertEqual(
            plume.casual_signoff_display("grave"), "grave (seriously / totally)"
        )

    def test_display_of_none_has_no_bracket(self):
        self.assertEqual(
            plume.casual_signoff_display(plume.CASUAL_SIGNOFF_NONE), "None"
        )

    def test_raw_value_reverses_display(self):
        for term in plume.CASUAL_SIGNOFFS:
            display = plume.casual_signoff_display(term)
            self.assertEqual(plume.casual_signoff_raw_value(display), term)

    def test_raw_value_resolves_unrecognised_to_none_sentinel(self):
        # v1.33: an unrecognised label (a stale value from a since-changed
        # catalogue) must never be passed through as if it were a term.
        self.assertEqual(
            plume.casual_signoff_raw_value("not a real label"),
            plume.CASUAL_SIGNOFF_NONE,
        )

    def test_raw_value_resolves_non_string_to_none_sentinel(self):
        self.assertEqual(plume.casual_signoff_raw_value(None), plume.CASUAL_SIGNOFF_NONE)
        self.assertEqual(plume.casual_signoff_raw_value(42), plume.CASUAL_SIGNOFF_NONE)

    def test_raw_value_also_accepts_the_bare_raw_term(self):
        self.assertEqual(plume.casual_signoff_raw_value("tkt"), "tkt")

    def test_only_the_raw_term_is_composed_not_the_gloss(self):
        display = plume.casual_signoff_display("tkt")
        composed = plume.compose_finishing_touch(
            plume.FINISHING_TOUCH_NONE, plume.casual_signoff_raw_value(display)
        )
        self.assertEqual(composed, "tkt")
        self.assertNotIn("don't worry", composed)


class TestMmorpgTerms(unittest.TestCase):
    def test_catalogue_starts_with_none_and_holds_curated_terms(self):
        self.assertEqual(plume.MMORPG_TERMS[0], plume.MMORPG_TERM_NONE)
        for term in ("dispo", "rez", "bj", "osef", "oklm", "aïe"):
            self.assertIn(term, plume.MMORPG_TERMS)

    def test_catalogue_holds_the_v1_41_expansion(self):
        # v1.41 (notes_018): common session-status and farewell shorthand,
        # each self-referential rather than a verdict on another player.
        for term in (
            "gg", "gl", "hf", "afk", "brb", "sec", "lag", "gj", "go", "gn",
            "cya", "cyl", "ttyl", "ttys",
        ):
            self.assertIn(term, plume.MMORPG_TERMS)

    def test_catalogue_excludes_domain_nouns_and_standalone_replies(self):
        # Same curation bar as Casual sign-off: gaming NOUNS describing
        # gear/content (not an appendable mood tag) and standalone replies/
        # comments about someone else's play stay out.
        banned = (
            "le stuff", "l'aggro", "les trash", "HL", "dj", "voc", "abo",
            "kikimeter", "bg", "rede", "wé", "ouai",
            # notes_018 (v1.41) also proposed these; held out as a comment
            # aimed at someone else's play ("nt") or a plain verdict on a
            # person/thing ("nul", "relou", "bouffon"), the same reason
            # "bg"/"rede" stay out. "bb" is excluded separately: it is as
            # commonly read as the endearment "baby" as it is "bye bye",
            # and a one-click append should not risk sending the former.
            "nt", "bb", "nul", "relou", "bouffon",
        )
        for term in banned:
            self.assertNotIn(term, plume.MMORPG_TERMS)

    def test_catalogue_disjoint_from_other_pickers(self):
        mmorpg = set(plume.MMORPG_TERMS) - {plume.MMORPG_TERM_NONE}
        signoffs = set(plume.CASUAL_SIGNOFFS) - {plume.CASUAL_SIGNOFF_NONE}
        emotes = set(plume.FINISHING_TOUCHES) - {plume.FINISHING_TOUCH_NONE}
        self.assertFalse(mmorpg & signoffs)
        self.assertFalse(mmorpg & emotes)

    def test_display_shows_bracketed_gloss(self):
        self.assertEqual(plume.mmorpg_term_display("rez"), "rez (resurrect me)")

    def test_raw_value_reverses_display(self):
        for term in plume.MMORPG_TERMS:
            display = plume.mmorpg_term_display(term)
            self.assertEqual(plume.mmorpg_term_raw_value(display), term)

    def test_raw_value_resolves_unrecognised_to_none_sentinel(self):
        self.assertEqual(
            plume.mmorpg_term_raw_value("not a real label"), plume.MMORPG_TERM_NONE
        )
        self.assertEqual(plume.mmorpg_term_raw_value(None), plume.MMORPG_TERM_NONE)

    def test_compose_joins_all_three_pickers(self):
        composed = plume.compose_finishing_touch(":)", "tkt", "rez")
        self.assertEqual(composed, ":) tkt rez")

    def test_compose_joins_one_v1_41_term_from_each_picker(self):
        composed = plume.compose_finishing_touch(":D", "nickel", "gg")
        self.assertEqual(composed, ":D nickel gg")

    def test_compose_mmorpg_only(self):
        composed = plume.compose_finishing_touch(
            plume.FINISHING_TOUCH_NONE, plume.CASUAL_SIGNOFF_NONE, "dispo"
        )
        self.assertEqual(composed, "dispo")

    def test_compose_mmorpg_none_is_omitted(self):
        composed = plume.compose_finishing_touch(":)", "tkt", plume.MMORPG_TERM_NONE)
        self.assertEqual(composed, ":) tkt")

    def test_compose_defaults_mmorpg_to_none_for_backward_compatibility(self):
        # v1.14-era two-argument call sites (and any test written against
        # that signature) must still work unchanged.
        self.assertEqual(plume.compose_finishing_touch(":)", "tkt"), ":) tkt")


class TestSlangCatalogue(unittest.TestCase):
    def test_ids_are_unique(self):
        ids = [record[0] for record in plume.SLANG_CATALOGUE]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_record_has_seven_columns(self):
        for record in plume.SLANG_CATALOGUE:
            self.assertEqual(len(record), 7)

    def test_id_term_meaning_category_register_are_non_empty(self):
        for ident, term, _expansion, meaning, category, register, note in (
            plume.SLANG_CATALOGUE
        ):
            self.assertTrue(ident)
            self.assertTrue(term)
            self.assertTrue(meaning)
            self.assertTrue(category)
            self.assertTrue(register)
            self.assertTrue(note)

    def test_holds_at_least_the_first_reviewed_batch(self):
        # v1.34 ships the notes_014 candidate batch; the wider 195-row
        # attachment is editorial backlog, not shipped catalogue content.
        self.assertGreaterEqual(len(plume.SLANG_CATALOGUE), 18)

    def test_holds_the_second_reviewed_batch(self):
        # v1.42 (notes_018): a further dictionary-stable, learner-safe batch
        # of everyday vocabulary and phrases.
        self.assertGreaterEqual(len(plume.SLANG_CATALOGUE), 33)
        ids = [record[0] for record in plume.SLANG_CATALOGUE]
        for ident in (
            "mec", "nana", "flemme", "nimp", "c-clair", "boite", "gosse",
            "super", "chouette", "cool", "frerot", "vasy", "ca-passe",
            "j-ai-la-flemme", "c-bon",
        ):
            self.assertIn(ident, ids)


class TestSlangSearchKey(unittest.TestCase):
    def test_folds_accents(self):
        self.assertEqual(plume.slang_search_key("désolé"), plume.slang_search_key("desole"))

    def test_folds_case(self):
        self.assertEqual(plume.slang_search_key("BOF"), plume.slang_search_key("bof"))

    def test_folds_curly_apostrophe_to_straight(self):
        self.assertEqual(
            plume.slang_search_key("ça marche’s"), plume.slang_search_key("ça marche's")
        )

    def test_none_input_does_not_raise(self):
        self.assertEqual(plume.slang_search_key(None), "")


class TestSearchSlang(unittest.TestCase):
    def test_finds_by_raw_french_term(self):
        matches = plume.search_slang("bof")
        self.assertTrue(any(record[0] == "bof" for record in matches))

    def test_finds_by_english_meaning_accent_and_case_insensitive(self):
        matches = plume.search_slang("DESOLE")
        self.assertTrue(any(record[0] == "dsl" for record in matches))

    def test_finds_by_expansion(self):
        matches = plume.search_slang("rendez-vous")
        self.assertTrue(any(record[0] == "rdv" for record in matches))

    def test_multi_word_query_is_an_and_match(self):
        matches = plume.search_slang("tinker fix")
        self.assertTrue(any(record[0] == "bidouiller" for record in matches))

    def test_empty_query_returns_everything_in_catalogue_order(self):
        self.assertEqual(plume.search_slang(""), list(plume.SLANG_CATALOGUE))

    def test_category_filter_narrows_results(self):
        matches = plume.search_slang("", category="Greetings")
        self.assertTrue(matches)
        for record in matches:
            self.assertEqual(record[4], "Greetings")

    def test_unknown_category_yields_no_matches(self):
        self.assertEqual(plume.search_slang("", category="Not A Real Category"), [])

    def test_no_match_returns_empty_list(self):
        self.assertEqual(plume.search_slang("zzzznotaterm"), [])

    def test_finds_both_the_noun_and_the_phrase_sharing_a_root(self):
        # v1.42: "flemme" (the noun) and "j'ai la flemme" (the phrase) both
        # carry the same root and must both surface for one query.
        matches = plume.search_slang("flemme")
        ids = {record[0] for record in matches}
        self.assertIn("flemme", ids)
        self.assertIn("j-ai-la-flemme", ids)


class TestSlangInsertion(unittest.TestCase):
    def test_inserts_at_offset(self):
        candidate, caret = plume.slang_insertion("Bonjour !", 8, "bof", 100)
        self.assertEqual(candidate, "Bonjour bof!")
        self.assertEqual(caret, 11)

    def test_adds_space_only_between_two_alnum_characters(self):
        candidate, _caret = plume.slang_insertion("Salut", 5, "tkt", 100)
        self.assertEqual(candidate, "Salut tkt")

    def test_no_space_added_next_to_punctuation(self):
        candidate, _caret = plume.slang_insertion("Salut !", 6, "tkt", 100)
        self.assertEqual(candidate, "Salut tkt!")

    def test_insert_into_empty_text(self):
        candidate, caret = plume.slang_insertion("", 0, "bof", 100)
        self.assertEqual(candidate, "bof")
        self.assertEqual(caret, 3)

    def test_caret_math_survives_a_non_bmp_character_before_offset(self):
        # An emoji is one Python character but two UTF-16 code units; an
        # offset of 1 must land right after it, not one code unit short
        # (the bug a Tcl/Tk UTF-16-based index count would introduce).
        text = "\U0001F600!"
        candidate, caret = plume.slang_insertion(text, 1, "bof", 100)
        self.assertEqual(candidate, "\U0001F600bof!")
        self.assertEqual(caret, 4)

    def test_rejects_offset_out_of_range(self):
        with self.assertRaises(ValueError):
            plume.slang_insertion("hi", 99, "bof", 100)
        with self.assertRaises(ValueError):
            plume.slang_insertion("hi", -1, "bof", 100)

    def test_rejects_non_int_offset(self):
        with self.assertRaises(ValueError):
            plume.slang_insertion("hi", 1.0, "bof", 100)

    def test_rejects_empty_term(self):
        with self.assertRaises(ValueError):
            plume.slang_insertion("hi", 1, "", 100)

    def test_rejects_null_byte_in_term(self):
        with self.assertRaises(ValueError):
            plume.slang_insertion("hi", 1, "bo\x00f", 100)

    def test_rejects_insertion_exceeding_limit(self):
        with self.assertRaises(ValueError):
            plume.slang_insertion("hi", 1, "bof", 3)


class TestNormalisePhrasebookEntry(unittest.TestCase):
    def test_trims_both_fields(self):
        entry = plume.normalise_phrasebook_entry("  bof  ", "  meh  ")
        self.assertEqual(entry, {"source": "bof", "note": "meh"})

    def test_note_is_optional(self):
        entry = plume.normalise_phrasebook_entry("bof", "")
        self.assertEqual(entry, {"source": "bof", "note": ""})
        self.assertEqual(
            plume.normalise_phrasebook_entry("bof", None), {"source": "bof", "note": ""}
        )

    def test_rejects_empty_or_whitespace_source(self):
        self.assertIsNone(plume.normalise_phrasebook_entry("", "note"))
        self.assertIsNone(plume.normalise_phrasebook_entry("   ", "note"))
        self.assertIsNone(plume.normalise_phrasebook_entry(None, "note"))

    def test_rejects_null_byte_in_source(self):
        self.assertIsNone(plume.normalise_phrasebook_entry("bo\x00f", "note"))

    def test_rejects_oversized_source(self):
        long_source = "x" * (plume.PHRASEBOOK_MAX_SOURCE_CHARS + 1)
        self.assertIsNone(plume.normalise_phrasebook_entry(long_source, ""))

    def test_rejects_oversized_note(self):
        long_note = "x" * (plume.PHRASEBOOK_MAX_NOTE_CHARS + 1)
        self.assertIsNone(plume.normalise_phrasebook_entry("bof", long_note))

    def test_accepts_source_at_exact_limit(self):
        source = "x" * plume.PHRASEBOOK_MAX_SOURCE_CHARS
        entry = plume.normalise_phrasebook_entry(source, "")
        self.assertEqual(entry["source"], source)


class TestNormalisePhrasebooks(unittest.TestCase):
    def _book(self, **overrides):
        base = {"name": "ESO — Auridon", "entries": [{"source": "Auridon", "note": "Auridia"}]}
        base.update(overrides)
        return base

    def test_rejects_non_dict(self):
        self.assertIsNone(plume.normalise_phrasebook("not a dict"))

    def test_rejects_blank_name(self):
        self.assertIsNone(plume.normalise_phrasebook(self._book(name="   ")))

    def test_rejects_name_matching_unsaved_placeholder(self):
        self.assertIsNone(
            plume.normalise_phrasebook(self._book(name=plume.PHRASEBOOK_UNSAVED))
        )

    def test_name_truncated_to_max(self):
        clean = plume.normalise_phrasebook(self._book(name="x" * 60))
        self.assertEqual(len(clean["name"]), plume.PHRASEBOOK_NAME_MAX)

    def test_assigns_id_when_missing(self):
        clean = plume.normalise_phrasebook(self._book())
        self.assertTrue(clean["id"])

    def test_preserves_given_id(self):
        clean = plume.normalise_phrasebook(self._book(id="abc123"))
        self.assertEqual(clean["id"], "abc123")

    def test_entries_are_normalised(self):
        clean = plume.normalise_phrasebook(self._book(entries=[
            {"source": "  Auridon  ", "note": " Auridia "}, {"bad": "entry"},
        ]))
        self.assertEqual(clean["entries"], [{"source": "Auridon", "note": "Auridia"}])

    def test_entries_deduplicated_by_source_casefold(self):
        clean = plume.normalise_phrasebook(self._book(entries=[
            {"source": "Auridon", "note": "a"}, {"source": "auridon", "note": "b"},
        ]))
        self.assertEqual(len(clean["entries"]), 1)

    def test_entries_capped_at_max(self):
        many = [{"source": "term{}".format(i), "note": ""} for i in range(40)]
        clean = plume.normalise_phrasebook(self._book(entries=many))
        self.assertEqual(len(clean["entries"]), plume.PHRASEBOOK_MAX_ENTRIES)

    def test_missing_entries_defaults_to_empty_list(self):
        clean = plume.normalise_phrasebook({"name": "Empty book"})
        self.assertEqual(clean["entries"], [])

    def test_list_drops_malformed_entries(self):
        books = plume.normalise_phrasebooks([
            self._book(id="1"), {"bad": "entry"}, self._book(id="2", name="Other"),
        ])
        self.assertEqual(len(books), 2)

    def test_list_deduplicates_by_id(self):
        books = plume.normalise_phrasebooks([
            self._book(id="1"), self._book(id="1", name="Different name"),
        ])
        self.assertEqual(len(books), 1)

    def test_list_caps_at_max(self):
        many = [self._book(id=str(i), name="Book{}".format(i)) for i in range(20)]
        books = plume.normalise_phrasebooks(many)
        self.assertEqual(len(books), plume.MAX_PHRASEBOOKS)

    def test_list_rejects_non_list(self):
        self.assertEqual(plume.normalise_phrasebooks("not a list"), [])

    def test_list_repairs_duplicate_display_name(self):
        books = plume.normalise_phrasebooks([
            self._book(id="1", name="Chat"), self._book(id="2", name="Chat"),
        ])
        self.assertEqual(len(books), 2)
        names = sorted(b["name"] for b in books)
        self.assertEqual(names, ["Chat", "Chat (2)"])

    def test_list_repairs_name_colliding_with_placeholder(self):
        books = plume.normalise_phrasebooks([
            self._book(id="1", name=plume.PHRASEBOOK_UNSAVED),
        ])
        self.assertEqual(len(books), 0)  # name itself is rejected, not repaired

    def test_round_trip_through_save_config_shape(self):
        books = plume.normalise_phrasebooks([self._book(id="1")])
        payload = json.loads(json.dumps(books))
        self.assertEqual(plume.normalise_phrasebooks(payload), books)


class TestUseAsMain(unittest.TestCase):
    def test_adopt_main_translation_favours_non_empty_candidate(self):
        self.assertEqual(
            plume.adopt_main_translation("Bonjour.", "Salut."), "Salut."
        )

    def test_adopt_main_translation_keeps_current_when_candidate_blank(self):
        self.assertEqual(plume.adopt_main_translation("Bonjour.", "   "), "Bonjour.")
        self.assertEqual(plume.adopt_main_translation("Bonjour.", None), "Bonjour.")


class TestHistoryEntries(unittest.TestCase):
    def test_make_history_entry_captures_source_and_result(self):
        result = valid_result()
        result["language_note"] = "Language was slightly ambiguous."
        result["notes"] = ["Check the register."]
        entry = plume.make_history_entry("hello", result)
        self.assertEqual(entry["source_text"], "hello")
        self.assertEqual(entry["main_translation"], "Bonjour tout le monde")
        self.assertEqual(entry["source_language"], "English")
        self.assertEqual(entry["target_language"], "French")
        self.assertEqual(entry["language_confidence"], "high")
        self.assertEqual(entry["language_note"], "Language was slightly ambiguous.")
        self.assertEqual(entry["notes"], ["Check the register."])
        self.assertEqual(len(entry["variations"]), 5)
        self.assertFalse(entry["favourite"])
        self.assertTrue(entry["id"])
        self.assertTrue(entry["timestamp"])

    def test_make_history_entry_ids_are_unique(self):
        a = plume.make_history_entry("hello", valid_result())
        b = plume.make_history_entry("hello", valid_result())
        self.assertNotEqual(a["id"], b["id"])

    def test_make_history_entry_includes_situation_when_given(self):
        entry = plume.make_history_entry("hi", valid_result(), situation="a work email")
        self.assertEqual(entry["situation"], "a work email")

    def test_make_history_entry_situation_defaults_to_blank(self):
        entry = plume.make_history_entry("hi", valid_result())
        self.assertEqual(entry["situation"], "")

    def test_make_history_entry_favourite_defaults_to_false(self):
        entry = plume.make_history_entry("hi", valid_result())
        self.assertFalse(entry["favourite"])

    def test_make_history_entry_accepts_favourite_true(self):
        entry = plume.make_history_entry("hi", valid_result(), favourite=True)
        self.assertTrue(entry["favourite"])

    def test_prune_history_keeps_favourites_beyond_limit(self):
        entries = [{"id": str(i), "favourite": (i == 0)} for i in range(5)]
        pruned = plume.prune_history(entries, limit=2)
        ids = [e["id"] for e in pruned]
        self.assertIn("0", ids)  # favourite always kept
        self.assertEqual(len(ids), 3)  # 1 favourite + 2 most-recent non-favourites

    def test_set_favourite_toggles_matching_entry_only(self):
        entries = [{"id": "a", "favourite": False}, {"id": "b", "favourite": False}]
        plume.set_favourite(entries, "b", True)
        self.assertFalse(entries[0]["favourite"])
        self.assertTrue(entries[1]["favourite"])

    def test_remove_history_entry_drops_only_matching_id(self):
        entries = [{"id": "a"}, {"id": "b"}]
        remaining = plume.remove_history_entry(entries, "a")
        self.assertEqual([e["id"] for e in remaining], ["b"])

    def test_clear_history_keeps_only_favourites(self):
        entries = [{"id": "a", "favourite": True}, {"id": "b", "favourite": False}]
        remaining = plume.clear_history(entries)
        self.assertEqual([e["id"] for e in remaining], ["a"])

    def test_normalise_history_entry_preserves_valid_entry(self):
        entry = plume.make_history_entry("hello", valid_result(), situation="a text")
        entry["favourite"] = True
        clean = plume.normalise_history_entry(entry)
        self.assertIsNotNone(clean)
        self.assertEqual(clean["source_text"], "hello")
        self.assertEqual(clean["language_confidence"], "high")
        self.assertEqual(clean["situation"], "a text")
        self.assertTrue(clean["favourite"])

    def test_normalise_history_entry_drops_unusable_entry(self):
        self.assertIsNone(plume.normalise_history_entry({"main_translation": "Bonjour"}))
        self.assertIsNone(plume.normalise_history_entry({"variations": []}))

    def test_normalise_history_entry_keeps_favourite_with_fewer_alternatives(self):
        entry = plume.make_history_entry("hello", valid_result(), favourite=True)
        entry["variations"] = entry["variations"][:4]
        clean = plume.normalise_history_entry(entry)
        self.assertIsNotNone(clean)
        self.assertEqual(len(clean["variations"]), 4)
        self.assertTrue(clean["favourite"])

    def test_normalise_history_entry_still_drops_non_favourite_with_fewer_alternatives(self):
        entry = plume.make_history_entry("hello", valid_result(), favourite=False)
        entry["variations"] = entry["variations"][:4]
        self.assertIsNone(plume.normalise_history_entry(entry))


class TestHistorySearch(unittest.TestCase):
    def _entries(self):
        return [
            {
                "id": "1", "source_text": "Hello there",
                "main_translation": "Bonjour", "situation": "Close friend",
                "favourite": False,
            },
            {
                "id": "2", "source_text": "See you later",
                "main_translation": "À plus tard", "situation": "Guild raid chat",
                "favourite": True,
            },
            {
                "id": "3", "source_text": "Good morning",
                "main_translation": "Bonjour tout le monde", "situation": "",
                "favourite": False,
            },
        ]

    def test_matches_source_text(self):
        result = plume.filter_history_entries(self._entries(), query="hello")
        self.assertEqual([e["id"] for e in result], ["1"])

    def test_matches_main_translation_case_insensitively(self):
        result = plume.filter_history_entries(self._entries(), query="BONJOUR")
        self.assertEqual([e["id"] for e in result], ["1", "3"])

    def test_matches_situation(self):
        result = plume.filter_history_entries(self._entries(), query="guild raid")
        self.assertEqual([e["id"] for e in result], ["2"])

    def test_empty_query_returns_everything(self):
        result = plume.filter_history_entries(self._entries(), query="   ")
        self.assertEqual(len(result), 3)

    def test_no_match_returns_empty(self):
        result = plume.filter_history_entries(self._entries(), query="zzz-nope")
        self.assertEqual(result, [])

    def test_favourites_only_applies_before_search(self):
        result = plume.filter_history_entries(
            self._entries(), query="", favourites_only=True,
        )
        self.assertEqual([e["id"] for e in result], ["2"])

    def test_favourites_only_and_search_combine(self):
        result = plume.filter_history_entries(
            self._entries(), query="hello", favourites_only=True,
        )
        self.assertEqual(result, [])

    def test_search_blob_omits_variations_and_notes(self):
        entry = {
            "source_text": "a", "main_translation": "b", "situation": "c",
            "variations": [{"translation": "secret-alt"}],
            "notes": ["secret-note"],
        }
        blob = plume.history_search_blob(entry)
        self.assertNotIn("secret-alt", blob)
        self.assertNotIn("secret-note", blob)


class TestExportFavourites(unittest.TestCase):
    def _entry(self, **overrides):
        entry = plume.make_history_entry(
            "Bonjour", valid_result(), situation="a close friend", favourite=True
        )
        entry.update(overrides)
        return entry

    def test_tsv_export_has_one_line_per_entry(self):
        tsv = plume.export_history_to_tsv([self._entry(), self._entry()])
        self.assertEqual(len(tsv.splitlines()), 2)

    def test_tsv_export_front_has_source_and_situation(self):
        tsv = plume.export_history_to_tsv([self._entry()])
        front, _, back = tsv.partition("\t")
        self.assertIn("Bonjour", front)
        self.assertIn("a close friend", front)
        self.assertIn("Bonjour tout le monde", back)

    def test_tsv_export_back_lists_all_five_alternatives(self):
        tsv = plume.export_history_to_tsv([self._entry()])
        _, _, back = tsv.partition("\t")
        for variation in valid_result()["variations"]:
            self.assertIn(variation["translation"], back)

    def test_tsv_export_strips_embedded_tabs_and_newlines(self):
        entry = self._entry(source_text="Line one\twith a tab\nand a newline")
        tsv = plume.export_history_to_tsv([entry])
        self.assertEqual(len(tsv.splitlines()), 1)
        self.assertEqual(tsv.count("\t"), 1)  # only the front/back separator

    def test_tsv_export_empty_list_is_empty_string(self):
        self.assertEqual(plume.export_history_to_tsv([]), "")

    def test_markdown_export_includes_source_and_alternatives(self):
        md = plume.export_history_to_markdown([self._entry()])
        self.assertIn("Bonjour", md)
        self.assertIn("Situation:", md)
        self.assertIn("Bonjour tout le monde", md)
        for variation in valid_result()["variations"]:
            self.assertIn(variation["translation"], md)

    def test_markdown_export_one_section_per_entry(self):
        md = plume.export_history_to_markdown([self._entry(), self._entry()])
        self.assertEqual(md.count("## Bonjour"), 2)


class TestCurrentResultExport(unittest.TestCase):
    def test_includes_source_situation_and_main(self):
        md = plume.export_current_result_markdown(
            "Bonjour", valid_result(), situation="a close friend"
        )
        self.assertIn("Bonjour", md)
        self.assertIn("**Situation:** a close friend", md)
        self.assertIn("Bonjour tout le monde", md)

    def test_omits_situation_section_when_blank(self):
        md = plume.export_current_result_markdown("Bonjour", valid_result())
        self.assertNotIn("Situation:", md)

    def test_includes_all_alternatives(self):
        md = plume.export_current_result_markdown("Bonjour", valid_result())
        for variation in valid_result()["variations"]:
            self.assertIn(variation["translation"], md)

    def test_includes_a_diff_section(self):
        md = plume.export_current_result_markdown("Bonjour", valid_result())
        self.assertIn("## Diff", md)
        self.assertIn("```diff", md)

    def test_omits_diff_when_no_source_or_target(self):
        empty_result = valid_result(main="")
        empty_result["variations"] = []
        md = plume.export_current_result_markdown("", empty_result)
        self.assertNotIn("## Diff", md)


class TestTranslationDiffExport(unittest.TestCase):
    def test_reports_no_differences_for_identical_text(self):
        content = plume.export_translation_diff("same text", "same text")
        self.assertIn("No textual differences.", content)
        self.assertNotIn("```diff", content)

    def test_includes_a_fenced_diff_when_text_differs(self):
        content = plume.export_translation_diff("Hello there", "Bonjour la-bas")
        self.assertIn("```diff", content)
        self.assertIn("Hello there", content)
        self.assertIn("Bonjour la-bas", content)

    def test_ignores_final_newline_only_difference(self):
        content = plume.export_translation_diff("same text\n", "same text")
        self.assertIn("No textual differences.", content)

    def test_fence_is_longer_than_embedded_backtick_runs(self):
        content = plume.export_translation_diff("plain", "some ```` backticks")
        fence_line = content.splitlines()[-1]
        self.assertTrue(fence_line.startswith("`````"))

    def test_disclaims_accuracy_not_just_a_label(self):
        content = plume.export_translation_diff("a", "b")
        self.assertIn("not an assessment of translation accuracy", content.lower())


class TestMetrics(unittest.TestCase):
    def test_counts_characters_and_words(self):
        metrics = plume.text_metrics("one two three")
        self.assertEqual(metrics["characters"], 13)
        self.assertEqual(metrics["words"], 3)

    def test_empty_text_has_zero_reading_seconds(self):
        metrics = plume.text_metrics("")
        self.assertEqual(metrics["reading_seconds"], 0)

    def test_french_uses_slower_wpm(self):
        text = " ".join(["mot"] * 200)
        en_metrics = plume.text_metrics(text)
        fr_metrics = plume.text_metrics(text, language=plume.FRENCH)
        self.assertGreater(fr_metrics["reading_seconds"], en_metrics["reading_seconds"])

    def test_auto_detect_uses_english_rate(self):
        text = " ".join(["word"] * 200)
        self.assertEqual(
            plume.text_metrics(text, language=None)["reading_seconds"],
            plume.text_metrics(text, language=plume.ENGLISH)["reading_seconds"],
        )

    def test_format_label_reports_empty(self):
        label = plume.format_metrics_label(plume.text_metrics(""))
        self.assertIn("0 characters", label)
        self.assertIn("empty", label)

    def test_format_label_reports_seconds(self):
        label = plume.format_metrics_label({"characters": 10, "words": 2, "reading_seconds": 5})
        self.assertIn("~5 s to read", label)

    def test_format_label_reports_minutes(self):
        label = plume.format_metrics_label(
            {"characters": 1000, "words": 300, "reading_seconds": 90}
        )
        self.assertIn("min to read", label)


class TestFrenchTypography(unittest.TestCase):
    def test_adds_narrow_nbsp_before_punctuation_with_no_existing_space(self):
        out = plume.apply_french_typography("Bonjour!")
        self.assertEqual(out, "Bonjour !")

    def test_collapses_existing_space_to_narrow_nbsp(self):
        out = plume.apply_french_typography("Bonjour !")
        self.assertEqual(out, "Bonjour !")

    def test_handles_question_mark_and_colon(self):
        self.assertEqual(plume.apply_french_typography("Ça va?"), "Ça va ?")
        self.assertEqual(plume.apply_french_typography("Attention:"), "Attention :")

    def test_ellipsis_becomes_single_character(self):
        self.assertEqual(plume.apply_french_typography("Attends..."), "Attends…")

    def test_straight_quotes_become_guillemets(self):
        self.assertEqual(
            plume.apply_french_typography('Il a dit "bonjour" hier.'),
            "Il a dit « bonjour » hier.",
        )

    def test_does_not_touch_unrelated_text(self):
        self.assertEqual(plume.apply_french_typography("Bonjour tout le monde"), "Bonjour tout le monde")

    def test_empty_and_non_string_input_returned_unchanged(self):
        self.assertEqual(plume.apply_french_typography(""), "")
        self.assertIsNone(plume.apply_french_typography(None))

    def test_idempotent(self):
        text = 'Il a dit "bonjour !" Attends... ça va?'
        once = plume.apply_french_typography(text)
        twice = plume.apply_french_typography(once)
        self.assertEqual(once, twice)


class TestFormatFiveAlternatives(unittest.TestCase):
    def test_numbers_five_translations(self):
        result = valid_result()
        text = plume.format_five_alternatives(result)
        lines = text.splitlines()
        self.assertEqual(len(lines), 5)
        self.assertTrue(lines[0].startswith("1. "))
        self.assertTrue(lines[4].startswith("5. "))

    def test_omits_meaning_checks(self):
        result = valid_result()
        text = plume.format_five_alternatives(result)
        for variation in result["variations"]:
            self.assertNotIn(variation["english_meaning_check"], text)

    def test_skips_blank_translations(self):
        result = valid_result()
        result["variations"][2]["translation"] = "   "
        text = plume.format_five_alternatives(result)
        self.assertEqual(len(text.splitlines()), 4)

    def test_empty_variations_returns_empty_string(self):
        self.assertEqual(plume.format_five_alternatives({"variations": []}), "")

    def test_missing_variations_key_returns_empty_string(self):
        self.assertEqual(plume.format_five_alternatives({}), "")
        self.assertEqual(plume.format_five_alternatives(None), "")


class TestBuildCopyAllContent(unittest.TestCase):
    def test_empty_main_text_returns_empty_strings(self):
        self.assertEqual(
            plume.build_copy_all_content("Hi", "", valid_result(), ""), ("", "")
        )

    def test_none_result_returns_empty_strings(self):
        self.assertEqual(
            plume.build_copy_all_content("Hi", "", None, "Bonjour"), ("", "")
        )

    def test_plain_text_includes_all_sections(self):
        result = valid_result()
        plain, _html = plume.build_copy_all_content(
            "Hello everyone", "texting a friend", result, result["main_translation"],
        )
        self.assertIn("SOURCE", plain)
        self.assertIn("Hello everyone", plain)
        self.assertIn("SITUATION: texting a friend", plain)
        self.assertIn("LANGUAGE: English → French · detected with high confidence", plain)
        self.assertIn("MAIN TRANSLATION", plain)
        self.assertIn(result["main_translation"], plain)
        self.assertIn("ALTERNATIVES", plain)
        for variation in result["variations"]:
            self.assertIn(variation["translation"], plain)
            self.assertIn(variation["english_meaning_check"], plain)

    def test_situation_section_omitted_when_blank(self):
        result = valid_result()
        plain, fragment = plume.build_copy_all_content(
            "Hello", "", result, result["main_translation"],
        )
        self.assertNotIn("SITUATION", plain)
        self.assertNotIn("SITUATION", fragment)

    def test_html_fragment_escapes_and_marks_up_sections(self):
        result = valid_result(main="<Bonjour> & \"vous\"")
        plain, fragment = plume.build_copy_all_content(
            "<Hello> & \"you\"", "", result, result["main_translation"],
        )
        self.assertIn("&lt;Bonjour&gt; &amp; &quot;vous&quot;", fragment)
        self.assertIn("&lt;Hello&gt; &amp; &quot;you&quot;", fragment)
        self.assertIn("<strong>SOURCE</strong>", fragment)
        self.assertIn("<strong>MAIN TRANSLATION</strong>", fragment)
        self.assertIn("<strong>ALTERNATIVES</strong>", fragment)
        self.assertIn("<em>", fragment)
        # The plain-text side is never escaped.
        self.assertIn("<Bonjour> & \"vous\"", plain)

    def test_alternatives_without_meaning_check_omit_the_dash(self):
        result = valid_result()
        result["variations"][0]["english_meaning_check"] = ""
        plain, fragment = plume.build_copy_all_content(
            "Hi", "", result, result["main_translation"],
        )
        self.assertIn("1. {}".format(result["variations"][0]["translation"]), plain)
        self.assertNotIn(
            "1. {} —".format(result["variations"][0]["translation"]), plain
        )
        self.assertIn(
            "<p>1. {}</p>".format(result["variations"][0]["translation"]), fragment
        )

    def test_blank_translations_are_skipped(self):
        result = valid_result()
        result["variations"][2]["translation"] = "   "
        plain, _fragment = plume.build_copy_all_content(
            "Hi", "", result, result["main_translation"],
        )
        numbered_lines = [
            line for line in plain.splitlines()
            if line[:2] in ("1.", "2.", "3.", "4.", "5.")
        ]
        self.assertEqual(len(numbered_lines), 4)

    def test_typography_fn_applied_to_main_and_alternatives_only(self):
        result = valid_result(main='Il a dit "bonjour"')
        result["variations"][0]["translation"] = 'Elle a dit "salut"'
        plain, _fragment = plume.build_copy_all_content(
            "source", "situation: text", result, result["main_translation"],
            typography_fn=plume.apply_french_typography,
        )
        self.assertIn("« bonjour »", plain)
        self.assertIn("« salut »", plain)
        # Applied only to translation-bearing fields, never to the labels.
        self.assertIn("SITUATION: situation: text", plain)

    def test_no_typography_fn_leaves_text_unchanged(self):
        result = valid_result(main='Il a dit "bonjour"')
        plain, _fragment = plume.build_copy_all_content(
            "source", "", result, result["main_translation"],
        )
        self.assertIn('Il a dit "bonjour"', plain)


class TestCfHtml(unittest.TestCase):
    def _parse_offsets(self, payload: bytes) -> dict:
        header = payload.decode("utf-8", errors="ignore")
        offsets = {}
        for line in header.splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                if value.strip().isdigit():
                    offsets[key] = int(value)
        return offsets

    def test_offsets_point_to_correct_slices(self):
        payload = plume._build_cf_html("<b>hi</b>")
        offsets = self._parse_offsets(payload)
        fragment = payload[offsets["StartFragment"]:offsets["EndFragment"]]
        self.assertEqual(fragment.decode("utf-8"), "<b>hi</b>")
        whole = payload[offsets["StartHTML"]:offsets["EndHTML"]]
        self.assertTrue(whole.decode("utf-8").startswith("<html>"))

    def test_handles_multibyte_utf8_fragment(self):
        payload = plume._build_cf_html("<p>café — déjà vu</p>")
        offsets = self._parse_offsets(payload)
        fragment = payload[offsets["StartFragment"]:offsets["EndFragment"]]
        self.assertEqual(fragment.decode("utf-8"), "<p>café — déjà vu</p>")

    def test_non_windows_copy_returns_false(self):
        with mock.patch.object(plume.sys, "platform", "linux"):
            self.assertFalse(plume.copy_html_to_windows_clipboard("<p>hi</p>", "hi"))

    def test_missing_window_handle_returns_false(self):
        # v1.26: a real hwnd is required; OpenClipboard(None) establishes
        # no owner, so the function must refuse rather than fall back to
        # that, regardless of platform.
        self.assertFalse(plume.copy_html_to_windows_clipboard("<p>hi</p>", "hi"))
        self.assertFalse(plume.copy_html_to_windows_clipboard("<p>hi</p>", "hi", hwnd=0))

    def test_embedded_nul_in_plain_text_returns_false(self):
        self.assertFalse(
            plume.copy_html_to_windows_clipboard("<p>hi</p>", "hi\x00there", hwnd=12345)
        )


class TestHistoryPersistence(unittest.TestCase):
    def test_atomic_save_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, plume.HISTORY_FILENAME)
            with mock.patch.object(plume, "history_path", return_value=path):
                entries = [plume.make_history_entry("hello", valid_result())]
                plume.save_history(entries)
                loaded = plume.load_history()
                self.assertEqual(len(loaded), 1)
                self.assertEqual(loaded[0]["source_text"], "hello")

    def test_load_history_missing_file_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, plume.HISTORY_FILENAME)
            with mock.patch.object(plume, "history_path", return_value=path):
                self.assertEqual(plume.load_history(), [])

    def test_malformed_history_not_overwritten_by_automatic_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, plume.HISTORY_FILENAME)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{ this is not valid json ")
            with mock.patch.object(plume, "history_path", return_value=path):
                with self.assertRaises(plume.HistoryError):
                    plume.save_history([], force=False)
                with open(path, "r", encoding="utf-8") as fh:
                    self.assertIn("not valid json", fh.read())
                # An explicit recovery save replaces it.
                plume.save_history([], force=True)
                with open(path, "r", encoding="utf-8") as fh:
                    self.assertEqual(json.load(fh), [])

    def test_load_history_malformed_file_returns_empty_list_without_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, plume.HISTORY_FILENAME)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("not json")
            with mock.patch.object(plume, "history_path", return_value=path):
                self.assertEqual(plume.load_history(), [])
            with open(path, "r", encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "not json")  # untouched

    def test_load_history_drops_malformed_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, plume.HISTORY_FILENAME)
            entries = [
                plume.make_history_entry("hello", valid_result()),
                {"id": "bad", "main_translation": "Bonjour"},
            ]
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(entries, fh)
            with mock.patch.object(plume, "history_path", return_value=path):
                loaded = plume.load_history()
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["source_text"], "hello")


class TestEnglishCorrection(unittest.TestCase):
    def test_looks_like_english_plain(self):
        self.assertTrue(plume.looks_like_english("See you tomorrow"))

    def test_looks_like_english_rejects_diacritics(self):
        self.assertFalse(plume.looks_like_english("À demain"))

    def test_looks_like_english_rejects_blank(self):
        self.assertFalse(plume.looks_like_english("   "))

    def test_correction_prompt_forbids_paraphrase(self):
        prompt = plume.build_correction_prompt()
        self.assertIn("Do not paraphrase", prompt)
        self.assertIn("British English", prompt)

    def test_parse_correction_round_trip(self):
        raw = json.dumps({
            "corrected_text": "See you tomorrow.",
            "changes_made": True,
            "notes": [],
        })
        result = plume.parse_correction_result(raw)
        self.assertEqual(result["corrected_text"], "See you tomorrow.")
        self.assertTrue(result["changes_made"])

    def test_parse_correction_rejects_empty_text(self):
        raw = json.dumps({"corrected_text": "  ", "changes_made": False})
        with self.assertRaises(plume.TranslationValidationError):
            plume.parse_correction_result(raw)

    def test_parse_correction_rejects_non_json(self):
        with self.assertRaises(plume.TranslationValidationError):
            plume.parse_correction_result("not json at all")

    def test_parse_correction_rejects_list(self):
        with self.assertRaises(plume.TranslationValidationError):
            plume.parse_correction_result(json.dumps(["not", "a", "dict"]))

    def test_correct_english_restores_protected_terms(self):
        raw = json.dumps({
            "corrected_text": "See you at ⟦PH0⟧ tomorrow.",
            "changes_made": True,
            "notes": [],
        })
        with mock.patch.object(plume, "run_backend", return_value=raw):
            result = plume.correct_english(
                dict(plume.DEFAULT_CONFIG),
                "See you at test@example.com tomorrow.",
            )
        self.assertEqual(
            result["corrected_text"], "See you at test@example.com tomorrow."
        )
        self.assertEqual(result["notes"], [])

    def test_correct_english_warns_on_dropped_token(self):
        raw = json.dumps({
            "corrected_text": "See you tomorrow.",  # token silently dropped
            "changes_made": True,
            "notes": [],
        })
        with mock.patch.object(plume, "run_backend", return_value=raw):
            result = plume.correct_english(
                dict(plume.DEFAULT_CONFIG),
                "See you at test@example.com tomorrow.",
            )
        self.assertTrue(result["notes"])


class TestDocumentationShape(unittest.TestCase):
    def test_example_config_matches_default_config_keys(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        path = os.path.join(root, "plume_config.example.json")
        with open(path, "r", encoding="utf-8") as fh:
            example = json.load(fh)
        self.assertEqual(set(example), set(plume.DEFAULT_CONFIG))


if __name__ == "__main__":
    unittest.main(verbosity=2)
