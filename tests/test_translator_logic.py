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
        entry = plume.make_history_entry("hello", valid_result())
        self.assertEqual(entry["source_text"], "hello")
        self.assertEqual(entry["main_translation"], "Bonjour tout le monde")
        self.assertEqual(entry["source_language"], "English")
        self.assertEqual(entry["target_language"], "French")
        self.assertEqual(len(entry["variations"]), 5)
        self.assertFalse(entry["favourite"])
        self.assertTrue(entry["id"])
        self.assertTrue(entry["timestamp"])

    def test_make_history_entry_ids_are_unique(self):
        a = plume.make_history_entry("hello", valid_result())
        b = plume.make_history_entry("hello", valid_result())
        self.assertNotEqual(a["id"], b["id"])

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
