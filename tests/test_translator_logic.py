"""Unit tests for Plume's deterministic logic.

These tests exercise only the pure functions (configuration, placeholder
protection, prompt construction, response parsing, status formatting and the
stale-request guard). They do not require CustomTkinter or a display, so they
run headless in CI.

Run from the project root:

    python -m unittest discover -s tests -v
"""

import io
import json
import os
import sys
import tempfile
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
                read=lambda: b'{"ok": true}',
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
                read=lambda: b'{"ok": true}',
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
                read=lambda: b'{"ok": true}',
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
                read=lambda: b'{"ok": true}',
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
                read=lambda: b'{"ok": true}',
            )

        with mock.patch.object(plume, "time"), \
                mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            data = plume._http_post_json(
                "https://x", {}, {"content-type": "application/json"}, 5,
                retryable_codes=plume.HTTP_RETRYABLE_CODES | {529},
            )
        self.assertEqual(data, {"ok": True})


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
        for mark in (":)", ":p", ";)", "xD", "mdr", "ptdr", "jpp"):
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

    def test_catalogue_excludes_wider_slang_and_greetings(self):
        # Curation guard: v1.14 ships only the two terms notes_004 named as
        # safe examples. Greetings, in-sentence abbreviations, nouns, and
        # harsher or more culturally loaded slang must never appear here,
        # even though several are listed in Essential Shortcuts.txt.
        banned = (
            "slt", "bjr", "rdv", "bcp", "mtn", "jsp", "oklm",
            "wesh", "meuf", "keuf", "boloss", "bg", "sah", "askip", "frr",
            "s/o", "chelou", "ouf", "relou", "stylé", "kiffer", "chanmé",
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

    def test_raw_value_falls_back_to_input_if_unrecognised(self):
        self.assertEqual(plume.casual_signoff_raw_value("not a real label"), "not a real label")

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

    def test_catalogue_excludes_domain_nouns_and_standalone_replies(self):
        # Same curation bar as Casual sign-off: gaming NOUNS describing
        # gear/content (not an appendable mood tag) and standalone replies/
        # comments about someone else's play stay out.
        banned = (
            "le stuff", "l'aggro", "les trash", "HL", "dj", "voc", "abo",
            "kikimeter", "bg", "rede", "wé", "ouai",
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

    def test_compose_joins_all_three_pickers(self):
        composed = plume.compose_finishing_touch(":)", "tkt", "rez")
        self.assertEqual(composed, ":) tkt rez")

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
