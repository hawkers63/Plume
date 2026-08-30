"""Unit tests for Plume's deterministic logic.

These tests exercise only the pure functions (configuration, placeholder
protection, prompt construction, response parsing, status formatting and the
stale-request guard). They do not require CustomTkinter or a display, so they
run headless in CI.

Run from the project root:

    python -m unittest discover -s tests -v
"""

import json
import os
import sys
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
