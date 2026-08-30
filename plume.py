#!/usr/bin/env python3
"""
Plume — French <-> English conversation helper.

A small Windows 11 desktop application that translates conversational French
and English in either direction. For every submitted phrase it returns one
faithful main translation plus exactly five natural, same-tone alternatives,
each with a short English "meaning check".

The module follows Scriptorium's practical engineering style: a dark,
native-feeling CustomTkinter interface, British English wording, explicit
privacy information, a strict validated response contract, atomic configuration
saving, and stale-callback protection for background work.

It is deliberately a single, well-sectioned module. Sections:

    1. Application constants and configuration paths.
    2. Defaults and load/save configuration functions.
    3. Input protection and small deterministic validation helpers.
    4. Prompt construction and structured-result parsing.
    5. Claude and Ollama backend functions.
    6. Settings dialogue.
    7. Main CustomTkinter application and UI callbacks.
    8. main() entry point.

The deterministic functions in sections 1-5 are import-safe: the GUI toolkit is
imported defensively so that tests\test_translator_logic.py can import this
module and exercise the logic without a display or CustomTkinter installed.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import urllib.error
import urllib.request

# --- Defensive GUI import ---------------------------------------------------
# CustomTkinter/Tkinter are only needed to actually run the window. Importing
# them defensively keeps the deterministic logic testable in a headless
# environment. On Mark's Windows machine customtkinter is a hard requirement.
try:  # pragma: no cover - exercised only when the GUI is present
    import tkinter as tk
    from tkinter import messagebox
    import customtkinter as ctk

    GUI_AVAILABLE = True
except Exception:  # pragma: no cover
    tk = None
    messagebox = None
    ctk = None
    GUI_AVAILABLE = False


# ===========================================================================
# 1. Application constants and configuration paths
# ===========================================================================

APP_NAME = "Plume"
APP_TITLE = "Plume \u2014 French \u2194 English conversation helper"
CONFIG_FILENAME = "plume_config.json"

# Allowed language identifiers used throughout the data contract.
ENGLISH = "English"
FRENCH = "French"
ALLOWED_LANGUAGES = (ENGLISH, FRENCH)

# Direction display strings (also stored in config).
DIR_AUTO = "Auto-detect"
DIR_EN_FR = "English \u2192 French"
DIR_FR_EN = "French \u2192 English"
DIRECTIONS = (DIR_AUTO, DIR_EN_FR, DIR_FR_EN)

# Maps a forced direction to the (source, target) it demands. Auto-detect -> None.
_FORCED_DIRECTION = {
    DIR_EN_FR: (ENGLISH, FRENCH),
    DIR_FR_EN: (FRENCH, ENGLISH),
    DIR_AUTO: None,
}

# French address form (tu/vous) preference.
FORM_INFORMAL = "Informal (tu)"
FORM_FORMAL = "Formal (vous)"
FORM_AUTO = "Let Plume decide"
FORMALITIES = (FORM_INFORMAL, FORM_FORMAL, FORM_AUTO)

# Regional French variant. Only a neutral option ships in version 1.
VARIANT_NEUTRAL = "Neutral international French"
VARIANTS = (VARIANT_NEUTRAL,)

# Confidence values the model may report for language detection.
CONFIDENCE_VALUES = ("high", "medium", "low")

VARIATION_COUNT = 5
DEFAULT_MAX_INPUT_CHARS = 2000
MAX_NOTE_CHARS = 240
MAX_NOTES = 6

# Placeholder token format, e.g. the first protected item becomes the token
# below with 0 substituted for its index.
PH_TOKEN = "\u27e6PH{}\u27e7"  # renders as: PH0 wrapped in white square brackets
_PH_TOKEN_RE = re.compile(r"\u27e6PH\d+\u27e7")

# --- Backend constants ---
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
ANTHROPIC_MAX_TOKENS = 2000
ANTHROPIC_TIMEOUT = 60

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_CHAT_PATH = "/api/chat"
OLLAMA_TAGS_PATH = "/api/tags"
DEFAULT_OLLAMA_MODEL = "llama3.1:8b"
OLLAMA_TIMEOUT = 120

APPEARANCE_MODE = "dark"
COLOR_THEME = "blue"


def config_dir() -> str:
    """Return the directory the live configuration file lives in.

    When frozen with PyInstaller the executable runs from a temporary folder,
    so configuration is written to %LOCALAPPDATA%\\Plume instead. When running
    from source the file sits beside this module, matching Scriptorium.
    """
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, APP_NAME)
    return os.path.dirname(os.path.abspath(__file__))


def config_path() -> str:
    return os.path.join(config_dir(), CONFIG_FILENAME)


# ===========================================================================
# 2. Defaults and load/save configuration functions
# ===========================================================================

DEFAULT_CONFIG = {
    "backend": "anthropic",
    "anthropic_api_key": "",
    "anthropic_model": DEFAULT_ANTHROPIC_MODEL,
    "ollama_model": DEFAULT_OLLAMA_MODEL,
    "privacy_ack": False,
    "default_direction": DIR_AUTO,
    "default_french_formality": FORM_INFORMAL,
    "default_french_variant": VARIANT_NEUTRAL,
    "protect_placeholders": True,
    "save_local_history": False,
    "max_input_chars": DEFAULT_MAX_INPUT_CHARS,
}


class ConfigError(Exception):
    """Raised when configuration cannot be saved safely."""


def _is_existing_file_malformed(path: str) -> bool:
    """True if a file exists at *path* but does not parse as a JSON object."""
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return True
    return not isinstance(data, dict)


def load_config():
    """Load configuration, merged over DEFAULT_CONFIG.

    Returns (config, load_error) where *load_error* is None on success or a
    short human-readable string when an existing file was malformed. A malformed
    file is never silently repaired here; the caller decides how to proceed and
    an automatic save will refuse to overwrite it.
    """
    path = config_path()
    config = dict(DEFAULT_CONFIG)
    if not os.path.exists(path):
        return config, None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        return config, "The configuration file could not be read ({}).".format(
            exc.__class__.__name__
        )
    if not isinstance(data, dict):
        return config, "The configuration file was not a JSON object."
    for key, value in data.items():
        if key in DEFAULT_CONFIG:
            config[key] = value
    return config, None


def save_config(config, force: bool = False) -> None:
    """Atomically write *config* to disk.

    Uses Scriptorium's atomic-save pattern: write a temporary sibling file,
    flush and fsync it, then replace the old file. If an existing file is
    malformed this refuses unless *force* is True, so that an automatic save
    can never clobber a file the user might still want to recover.
    """
    path = config_path()
    if not force and _is_existing_file_malformed(path):
        raise ConfigError(
            "The existing configuration file appears to be damaged. It was not "
            "overwritten. Use the Settings window's recovery save to replace it."
        )
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    tmp_path = path + ".tmp"
    payload = json.dumps(config, indent=2, ensure_ascii=False)
    with open(tmp_path, "w", encoding="utf-8") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_path, path)


# ===========================================================================
# 3. Input protection and deterministic validation helpers
# ===========================================================================

# Trailing/leading punctuation that should be ignored when comparing two
# phrasings for uniqueness. Superficial only; the visible text is never altered.
_SUPERFICIAL_PUNCT = " \t\r\n.!?\u2026;:,\u00b7"


def normalise_for_uniqueness(text) -> str:
    """Case-fold, collapse whitespace and drop superficial terminal punctuation.

    Used only to decide whether two variations are meaningfully distinct. It is
    never used to change the text shown to the user.
    """
    if not isinstance(text, str):
        return ""
    folded = text.casefold()
    collapsed = re.sub(r"\s+", " ", folded).strip()
    return collapsed.strip(_SUPERFICIAL_PUNCT)


# Placeholder protection patterns, applied in priority order. Earlier patterns
# win, so URLs and paths are masked before looser handle/number patterns.
_PROTECT_PATTERNS = [
    re.compile(r"https?://[^\s<>()]+", re.IGNORECASE),          # URLs
    re.compile(r"www\.[^\s<>()]+", re.IGNORECASE),              # bare www URLs
    re.compile(r"[A-Za-z]:\\[^\s<>|?*\"]+"),                    # Windows paths
    re.compile(r"\\\\[^\s<>|?*\"]+"),                            # UNC paths
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+", re.IGNORECASE),      # e-mail addresses
    re.compile(r"(?<![\w.])@[A-Za-z0-9_]{2,}"),                 # @handles
    re.compile(r"\{[^{}\n]{1,60}\}"),                            # {template} markers
    re.compile(r"\[[^\[\]\n]{1,60}\]"),                          # [bracketed] markers
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),                        # ISO dates
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),                 # dd/mm/yyyy dates
]


def protect_text(text: str, enabled: bool = True):
    """Replace protected material with ordered tokens.

    Returns (masked_text, mapping) where *mapping* maps each token to the exact
    original substring it replaced. When *enabled* is False the text is returned
    unchanged with an empty mapping.
    """
    if not enabled or not text:
        return text, {}
    mapping = {}
    counter = [0]

    def _sub(match):
        token = PH_TOKEN.format(counter[0])
        counter[0] += 1
        mapping[token] = match.group(0)
        return token

    masked = text
    for pattern in _PROTECT_PATTERNS:
        masked = pattern.sub(_sub, masked)
    return masked, mapping


def restore_tokens(text: str, mapping: dict) -> str:
    """Replace every token in *mapping* with its original substring."""
    if not mapping or not isinstance(text, str):
        return text
    for token, original in mapping.items():
        text = text.replace(token, original)
    return text


def restore_result_tokens(result: dict, mapping: dict):
    """Restore protected tokens throughout a validated result.

    Returns (result, warnings). A single generic warning is added if any
    expected token is missing from the model's output, which can happen if the
    model altered or dropped a protected item. The warning never echoes the
    original value, so no submitted content leaks into the interface.
    """
    warnings = []
    if not mapping:
        return result, warnings

    blob_parts = [result.get("main_translation", "")]
    for variation in result.get("variations", []):
        blob_parts.append(variation.get("translation", ""))
        blob_parts.append(variation.get("english_meaning_check", ""))
    blob = "\n".join(blob_parts)

    if any(token not in blob for token in mapping):
        warnings.append(
            "One or more protected items (such as a name, link, date or "
            "placeholder) may not have been reproduced exactly. Please check "
            "the result before sending it."
        )

    result["main_translation"] = restore_tokens(result["main_translation"], mapping)
    for variation in result["variations"]:
        variation["translation"] = restore_tokens(variation["translation"], mapping)
        variation["english_meaning_check"] = restore_tokens(
            variation["english_meaning_check"], mapping
        )
    return result, warnings


def validate_source_size(text: str, limit: int = DEFAULT_MAX_INPUT_CHARS):
    """Return (ok, message). Empty or over-long input is reported, not sent."""
    if text is None or not text.strip():
        return False, "Please type a phrase to translate."
    length = len(text)
    if length > limit:
        return False, (
            "The message is {} characters, which is longer than the current "
            "limit of {}. Please shorten it or raise the limit in Settings."
        ).format(length, limit)
    return True, ""


def _safe_short_string(value, limit: int = MAX_NOTE_CHARS) -> str:
    """Coerce arbitrary model output into a short, single-line safe string."""
    if not isinstance(value, str):
        return ""
    cleaned = re.sub(r"\s+", " ", value).strip()
    if len(cleaned) > limit:
        cleaned = cleaned[: limit - 1].rstrip() + "\u2026"
    return cleaned


def _safe_string_list(value, limit: int = MAX_NOTES):
    """Coerce a value into a short list of safe strings."""
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        text = _safe_short_string(item)
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


# ===========================================================================
# 4. Prompt construction and structured-result parsing
# ===========================================================================

# The exact JSON contract, embedded verbatim in the prompt. Kept as a plain
# (non-f) string so the braces need no escaping.
_SCHEMA_HINT = """{
  "source_language": "English" or "French",
  "target_language": the opposite language,
  "language_confidence": "high" | "medium" | "low",
  "language_note": "" or a short note explaining any uncertainty,
  "main_translation": "the single closest natural translation",
  "variations": [
    { "translation": "...", "english_meaning_check": "..." },
    ... exactly five objects in total ...
  ],
  "notes": [ "optional short notes" ]
}"""


def build_translation_prompt(direction=DIR_AUTO,
                             french_formality=FORM_INFORMAL,
                             french_variant=VARIANT_NEUTRAL,
                             protect_tokens: bool = True) -> str:
    """Build the system prompt. Pure function: same inputs -> same output.

    The prompt states the requested direction, the French address form and
    regional variant, the placeholder-token policy, the requirement for exactly
    five distinct alternatives each with an English meaning check, and the
    JSON-only output contract.
    """
    if direction == DIR_AUTO:
        direction_clause = (
            "Determine whether the source text is English or French, then "
            "translate it into the other language. If the language is genuinely "
            "ambiguous, choose the more likely one but lower the "
            "'language_confidence' value and explain briefly in 'language_note'."
        )
    else:
        forced = _FORCED_DIRECTION[direction]
        direction_clause = (
            "The direction is fixed by the user: the source is {} and the target "
            "is {}. Set 'source_language' and 'target_language' accordingly and "
            "do not change them."
        ).format(forced[0], forced[1])

    if french_formality == FORM_INFORMAL:
        formality_clause = (
            "When the target is French, use the informal 'tu' address form "
            "unless the source clearly demands otherwise."
        )
    elif french_formality == FORM_FORMAL:
        formality_clause = (
            "When the target is French, use the formal 'vous' address form "
            "unless the source clearly demands otherwise."
        )
    else:
        formality_clause = (
            "When the target is French and the source gives no clear basis for "
            "'tu' versus 'vous', choose the least presumptive natural form and "
            "record one short note rather than guessing."
        )

    if protect_tokens:
        token_clause = (
            "Some items may already be replaced with placeholder tokens of the "
            "form \u27e6PH0\u27e7, \u27e6PH1\u27e7 and so on. Treat each token as an opaque "
            "unit: reproduce it exactly and in a natural position, and never "
            "translate, alter, remove or invent tokens."
        )
    else:
        token_clause = (
            "Preserve any names, numbers, dates, URLs, handles, code and quoted "
            "content exactly as written; do not translate or alter them."
        )

    return (
        "You are a precise conversational translator between English and "
        "French.\n"
        + direction_clause
        + "\nTranslate faithfully and naturally. Preserve meaning, level of "
        "certainty, emotional tone, register, conversational rhythm and "
        "punctuation. Preserve directness, politeness, hedging, slang and "
        "ellipses when they are material. Do not add facts, soften or intensify "
        "commitments, introduce flirtation, sarcasm or offence, invent context, "
        "or explain the translation inside the translated text.\n"
        + formality_clause
        + " Respect the requested French regional variant: "
        + french_variant
        + ". Do not manufacture regional slang.\n"
        "Avoid gender-dependent French wording where possible. When it cannot "
        "be avoided, use neutral phrasing or an inclusive form such as "
        "'content(e)', and never guess the user's gender.\n"
        + token_clause
        + "\n\nReturn one primary translation and exactly five distinct, "
        "idiomatic alternatives in the target language. The five alternatives "
        "must keep the source's tone and formality and must differ meaningfully "
        "in word choice, idiom or word order rather than only in punctuation. "
        "Do not repeat the primary translation among the alternatives. Each "
        "alternative must include a concise English 'meaning check': for an "
        "English source this is a plain-English gloss of the French; for a "
        "French source it is the natural English rendering.\n"
        "When formality, gender or language detection is genuinely uncertain, "
        "choose the least presumptive natural wording and record one short "
        "note.\n\n"
        "Return only one valid JSON object matching this shape, with no Markdown "
        "fences and no prose before or after it:\n"
        + _SCHEMA_HINT
    )


def build_user_envelope(text: str,
                        direction=DIR_AUTO,
                        french_formality=FORM_INFORMAL,
                        french_variant=VARIANT_NEUTRAL) -> str:
    """Wrap the (already masked) user text in a small labelled envelope."""
    return (
        "Requested direction: {}\n"
        "French address preference: {}\n"
        "French variant: {}\n"
        "Text to translate:\n"
        "{}"
    ).format(direction, french_formality, french_variant, text)


class TranslationValidationError(Exception):
    """Raised when a model response does not satisfy the data contract.

    These are retryable: the interface invites the user to try again, shorten
    the message, or switch backend. The message never contains submitted text.
    """


def _strip_code_fence(raw: str) -> str:
    """Remove a single surrounding Markdown code fence, if present.

    Tolerated only as a wrapper; the JSON inside must still be valid. Random
    prose around a JSON fragment is not accepted.
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop the opening fence (optionally ```json) and a closing fence.
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def parse_translation_result(raw, forced_direction=DIR_AUTO) -> dict:
    """Validate a raw model response against the full data contract.

    Returns a clean, safe result dict on success. Raises
    TranslationValidationError for any malformed response: invalid JSON, a
    scalar or list at the top level, a missing or empty primary translation, a
    variations list that is not exactly five well-formed objects, duplicate
    alternatives after harmless normalisation, a primary duplicated among the
    alternatives, or a direction that contradicts a forced selection.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise TranslationValidationError("The model returned an empty response.")

    text = _strip_code_fence(raw)
    try:
        data = json.loads(text)
    except ValueError:
        raise TranslationValidationError(
            "The model did not return valid JSON. Please try again."
        )

    if not isinstance(data, dict):
        raise TranslationValidationError(
            "The model response was not a single JSON object."
        )

    source = data.get("source_language")
    target = data.get("target_language")
    if source not in ALLOWED_LANGUAGES or target not in ALLOWED_LANGUAGES:
        raise TranslationValidationError(
            "The response did not identify a valid source and target language."
        )
    if source == target:
        raise TranslationValidationError(
            "The source and target languages must be different."
        )

    forced = _FORCED_DIRECTION.get(forced_direction)
    if forced is not None:
        want_source, want_target = forced
        if source != want_source or target != want_target:
            raise TranslationValidationError(
                "The translation direction did not match your manual selection."
            )

    main = data.get("main_translation")
    if not isinstance(main, str) or not main.strip():
        raise TranslationValidationError(
            "The response had no usable main translation."
        )
    main = main.strip()

    variations = data.get("variations")
    if not isinstance(variations, list) or len(variations) != VARIATION_COUNT:
        raise TranslationValidationError(
            "The response did not contain exactly {} alternatives.".format(
                VARIATION_COUNT
            )
        )

    clean_variations = []
    for item in variations:
        if not isinstance(item, dict):
            raise TranslationValidationError(
                "One of the alternatives was not in the expected form."
            )
        translation = item.get("translation")
        meaning = item.get("english_meaning_check")
        if not isinstance(translation, str) or not translation.strip():
            raise TranslationValidationError(
                "An alternative was missing its translated text."
            )
        if not isinstance(meaning, str) or not meaning.strip():
            raise TranslationValidationError(
                "An alternative was missing its English meaning check."
            )
        clean_variations.append(
            {
                "translation": translation.strip(),
                "english_meaning_check": meaning.strip(),
            }
        )

    # Uniqueness: no alternative may duplicate another or the main translation
    # once superficial punctuation and casing are ignored.
    seen = {normalise_for_uniqueness(main)}
    for variation in clean_variations:
        key = normalise_for_uniqueness(variation["translation"])
        if key in seen:
            raise TranslationValidationError(
                "The alternatives were not all distinct from each other and "
                "the main translation."
            )
        seen.add(key)

    confidence = data.get("language_confidence")
    if confidence not in CONFIDENCE_VALUES:
        confidence = "low"

    return {
        "source_language": source,
        "target_language": target,
        "language_confidence": confidence,
        "language_note": _safe_short_string(data.get("language_note", "")),
        "main_translation": main,
        "variations": clean_variations,
        "notes": _safe_string_list(data.get("notes", [])),
    }


# ===========================================================================
# 5. Claude and Ollama backend functions
# ===========================================================================

class BackendError(Exception):
    """Friendly, recoverable network / HTTP / backend failure.

    Messages are safe to display and never contain the submitted phrase.
    """


def _http_post_json(url, payload, headers, timeout):
    """POST *payload* as JSON and return the decoded JSON response."""
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")
        except Exception:
            detail = ""
        raise BackendError(_friendly_http_message(exc.code, detail))
    except urllib.error.URLError as exc:
        raise BackendError(
            "Could not reach the translation backend. Please check your "
            "connection and try again. ({})".format(_reason_text(exc))
        )
    except (TimeoutError, OSError):
        raise BackendError(
            "The translation backend did not respond in time. Please try again."
        )
    try:
        return json.loads(body)
    except ValueError:
        raise BackendError("The backend returned a response that could not be read.")


def _reason_text(exc) -> str:
    reason = getattr(exc, "reason", None)
    return str(reason) if reason is not None else exc.__class__.__name__


def _friendly_http_message(code, detail) -> str:
    if code in (401, 403):
        return (
            "The Claude API rejected the request. Please check your API key in "
            "Settings."
        )
    if code == 404:
        return (
            "The requested model was not found. Please check the model name in "
            "Settings."
        )
    if code == 429:
        return "The Claude API is rate limiting requests. Please wait and retry."
    if 500 <= code < 600:
        return "The translation service reported a temporary error. Please retry."
    return "The request failed (HTTP {}). Please try again.".format(code)


def call_anthropic(config_snapshot, system_prompt, user_text):
    """Send a translation request to the Claude Messages endpoint."""
    api_key = (config_snapshot.get("anthropic_api_key") or "").strip()
    if not api_key:
        api_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not api_key:
        raise BackendError(
            "No Claude API key is set. Add one in Settings, or set the "
            "ANTHROPIC_API_KEY environment variable."
        )
    model = config_snapshot.get("anthropic_model") or DEFAULT_ANTHROPIC_MODEL
    headers = {
        "content-type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
    }
    payload = {
        "model": model,
        "max_tokens": ANTHROPIC_MAX_TOKENS,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_text}],
    }
    data = _http_post_json(ANTHROPIC_URL, payload, headers, ANTHROPIC_TIMEOUT)
    parts = []
    for block in data.get("content", []):
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    text = "".join(parts).strip()
    if not text:
        raise BackendError("The Claude API returned an empty message.")
    return text


def call_ollama(config_snapshot, system_prompt, user_text):
    """Send a translation request to a local Ollama instance."""
    model = config_snapshot.get("ollama_model") or DEFAULT_OLLAMA_MODEL
    url = OLLAMA_BASE_URL + OLLAMA_CHAT_PATH
    headers = {"content-type": "application/json"}
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
    }
    try:
        data = _http_post_json(url, payload, headers, OLLAMA_TIMEOUT)
    except BackendError as exc:
        # Give a more specific hint for the common "Ollama not running" case.
        message = str(exc)
        if "Could not reach" in message:
            raise BackendError(
                "Could not reach Ollama on {}. Is the Ollama application "
                "running?".format(OLLAMA_BASE_URL)
            )
        raise
    message = data.get("message") or {}
    text = (message.get("content") or "").strip()
    if not text:
        raise BackendError("Ollama returned an empty message.")
    return text


def list_ollama_models(base_url=OLLAMA_BASE_URL):
    """Return the names of locally installed Ollama models."""
    url = base_url + OLLAMA_TAGS_PATH
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError:
        raise BackendError(
            "Could not reach Ollama on {}. Is it running?".format(base_url)
        )
    except (ValueError, OSError):
        raise BackendError("Ollama returned a model list that could not be read.")
    names = []
    for model in data.get("models", []):
        name = model.get("name") if isinstance(model, dict) else None
        if name:
            names.append(name)
    return names


def run_backend(config_snapshot, system_prompt, user_text):
    """Dispatch to the configured backend using a copied config snapshot."""
    backend = config_snapshot.get("backend", "anthropic")
    if backend == "ollama":
        return call_ollama(config_snapshot, system_prompt, user_text)
    return call_anthropic(config_snapshot, system_prompt, user_text)


def translate(config_snapshot, text):
    """End-to-end deterministic pipeline used by the worker thread.

    Masks placeholders, builds the prompt and envelope, calls the backend,
    parses and validates the result, restores tokens, and merges any
    preservation warnings into the notes. Raises BackendError or
    TranslationValidationError on failure.
    """
    direction = config_snapshot.get("default_direction", DIR_AUTO)
    formality = config_snapshot.get("default_french_formality", FORM_INFORMAL)
    variant = config_snapshot.get("default_french_variant", VARIANT_NEUTRAL)
    protect = bool(config_snapshot.get("protect_placeholders", True))

    masked, mapping = protect_text(text, enabled=protect)
    system_prompt = build_translation_prompt(direction, formality, variant, protect)
    user_envelope = build_user_envelope(masked, direction, formality, variant)

    raw = run_backend(config_snapshot, system_prompt, user_envelope)
    result = parse_translation_result(raw, forced_direction=direction)
    result, warnings = restore_result_tokens(result, mapping)
    if warnings:
        result["notes"] = warnings + result.get("notes", [])
    return result


# ===========================================================================
# Status / label formatting (pure, tested for privacy)
# ===========================================================================

def format_status(config, char_count, state="ready") -> str:
    """Build the status-bar line. Never includes the submitted phrase."""
    backend = config.get("backend", "anthropic")
    if backend == "ollama":
        model = config.get("ollama_model") or DEFAULT_OLLAMA_MODEL
        left = "Backend: Ollama \u00b7 {} (local) \u2014 stays on this machine".format(model)
    else:
        model = config.get("anthropic_model") or DEFAULT_ANTHROPIC_MODEL
        left = "Backend: Claude \u00b7 {} \u2014 text is sent to Anthropic".format(model)
    right = state if state else "ready"
    if char_count is not None:
        right = "{} characters".format(char_count)
    return "{} | {}".format(left, right)


def format_language_label(result) -> str:
    """Build the small 'English -> French - detected with high confidence' line."""
    source = result.get("source_language", "")
    target = result.get("target_language", "")
    confidence = result.get("language_confidence", "low")
    return "{} \u2192 {} \u00b7 detected with {} confidence".format(
        source, target, confidence
    )


def mask_api_key(key) -> str:
    """Return a masked form of an API key for display in Settings."""
    if not key:
        return "(none)"
    key = key.strip()
    if len(key) <= 8:
        return "\u2022" * len(key)
    return key[:4] + "\u2022" * (len(key) - 8) + key[-4:]


def result_is_stale(result_request_id, current_request_id) -> bool:
    """True if a delivered result belongs to a superseded request."""
    return result_request_id != current_request_id


# ===========================================================================
# 6. Settings dialogue
# ===========================================================================

if GUI_AVAILABLE:

    class SettingsDialog(ctk.CTkToplevel):
        """Modal-ish settings window. Applies changes to the next request."""

        def __init__(self, master, config, on_save):
            super().__init__(master)
            self._on_save = on_save
            self._config = dict(config)
            self.title("{} \u2014 Settings".format(APP_NAME))
            self.geometry("560x620")
            self.minsize(520, 560)
            self.transient(master)
            self.grid_columnconfigure(0, weight=1)

            pad = {"padx": 16, "pady": 8}
            row = 0

            heading = ctk.CTkLabel(
                self, text="Settings", font=ctk.CTkFont(size=18, weight="bold")
            )
            heading.grid(row=row, column=0, sticky="w", **pad)
            row += 1

            # Backend selector
            ctk.CTkLabel(self, text="Backend").grid(row=row, column=0, sticky="w", padx=16)
            row += 1
            self.backend_var = ctk.StringVar(value=self._config.get("backend", "anthropic"))
            backend_row = ctk.CTkSegmentedButton(
                self,
                values=["anthropic", "ollama"],
                variable=self.backend_var,
            )
            backend_row.grid(row=row, column=0, sticky="ew", **pad)
            row += 1

            # Claude key
            ctk.CTkLabel(self, text="Claude API key").grid(row=row, column=0, sticky="w", padx=16)
            row += 1
            self.key_entry = ctk.CTkEntry(self, show="\u2022", placeholder_text="sk-ant-...")
            self.key_entry.grid(row=row, column=0, sticky="ew", **pad)
            existing_key = self._config.get("anthropic_api_key", "")
            if existing_key:
                self.key_entry.insert(0, existing_key)
            row += 1
            self.key_label = ctk.CTkLabel(
                self,
                text="Stored key: {}".format(mask_api_key(existing_key)),
                text_color="gray70",
            )
            self.key_label.grid(row=row, column=0, sticky="w", padx=16)
            row += 1

            # Claude model
            ctk.CTkLabel(self, text="Claude model").grid(row=row, column=0, sticky="w", padx=16)
            row += 1
            self.model_entry = ctk.CTkEntry(self)
            self.model_entry.insert(0, self._config.get("anthropic_model", DEFAULT_ANTHROPIC_MODEL))
            self.model_entry.grid(row=row, column=0, sticky="ew", **pad)
            row += 1

            # Ollama model + detect
            ctk.CTkLabel(self, text="Ollama model").grid(row=row, column=0, sticky="w", padx=16)
            row += 1
            ollama_frame = ctk.CTkFrame(self, fg_color="transparent")
            ollama_frame.grid(row=row, column=0, sticky="ew", **pad)
            ollama_frame.grid_columnconfigure(0, weight=1)
            self.ollama_entry = ctk.CTkEntry(ollama_frame)
            self.ollama_entry.insert(0, self._config.get("ollama_model", DEFAULT_OLLAMA_MODEL))
            self.ollama_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
            self.detect_btn = ctk.CTkButton(
                ollama_frame, text="Detect", width=90, command=self._detect_models
            )
            self.detect_btn.grid(row=0, column=1)
            row += 1

            # French defaults
            ctk.CTkLabel(self, text="Default French address form").grid(
                row=row, column=0, sticky="w", padx=16
            )
            row += 1
            self.formality_var = ctk.StringVar(
                value=self._config.get("default_french_formality", FORM_INFORMAL)
            )
            ctk.CTkOptionMenu(
                self, values=list(FORMALITIES), variable=self.formality_var
            ).grid(row=row, column=0, sticky="ew", **pad)
            row += 1

            # Toggles
            self.protect_var = ctk.BooleanVar(
                value=bool(self._config.get("protect_placeholders", True))
            )
            ctk.CTkCheckBox(
                self, text="Protect names, links and placeholders", variable=self.protect_var
            ).grid(row=row, column=0, sticky="w", **pad)
            row += 1

            self.privacy_var = ctk.BooleanVar(
                value=bool(self._config.get("privacy_ack", False))
            )
            ctk.CTkCheckBox(
                self,
                text="I understand Claude sends text to Anthropic",
                variable=self.privacy_var,
            ).grid(row=row, column=0, sticky="w", **pad)
            row += 1

            self.status_label = ctk.CTkLabel(self, text="", text_color="gray70")
            self.status_label.grid(row=row, column=0, sticky="w", padx=16)
            row += 1

            button_row = ctk.CTkFrame(self, fg_color="transparent")
            button_row.grid(row=row, column=0, sticky="ew", **pad)
            button_row.grid_columnconfigure(0, weight=1)
            ctk.CTkButton(button_row, text="Cancel", command=self.destroy,
                          fg_color="gray30").grid(row=0, column=1, padx=(0, 8))
            ctk.CTkButton(button_row, text="Save", command=self._save).grid(row=0, column=2)

        def _detect_models(self):
            self.detect_btn.configure(state="disabled", text="\u2026")
            self.status_label.configure(text="Contacting Ollama\u2026")

            def worker():
                try:
                    names = list_ollama_models()
                    msg = "Found: " + ", ".join(names) if names else "No local models found."
                except BackendError as exc:
                    names, msg = [], str(exc)
                self.after(0, lambda: self._finish_detect(names, msg))

            threading.Thread(target=worker, daemon=True).start()

        def _finish_detect(self, names, msg):
            if names:
                self.ollama_entry.delete(0, "end")
                self.ollama_entry.insert(0, names[0])
            self.status_label.configure(text=msg)
            self.detect_btn.configure(state="normal", text="Detect")

        def _save(self):
            self._config["backend"] = self.backend_var.get()
            self._config["anthropic_api_key"] = self.key_entry.get().strip()
            self._config["anthropic_model"] = self.model_entry.get().strip() or DEFAULT_ANTHROPIC_MODEL
            self._config["ollama_model"] = self.ollama_entry.get().strip() or DEFAULT_OLLAMA_MODEL
            self._config["default_french_formality"] = self.formality_var.get()
            self._config["protect_placeholders"] = bool(self.protect_var.get())
            self._config["privacy_ack"] = bool(self.privacy_var.get())
            try:
                save_config(self._config)
            except ConfigError as exc:
                answer = messagebox.askyesno(
                    "Damaged configuration",
                    str(exc) + "\n\nReplace the damaged file now?",
                )
                if answer:
                    save_config(self._config, force=True)
                else:
                    return
            self._on_save(self._config)
            self.destroy()


# ===========================================================================
# 7. Main CustomTkinter application and UI callbacks
# ===========================================================================

if GUI_AVAILABLE:

    class PlumeApp(ctk.CTk):
        def __init__(self):
            super().__init__()
            config, load_error = load_config()
            self.config_data = config
            self._request_id = 0
            self._active_snapshot = None
            self._variation_cards = []

            ctk.set_appearance_mode(APPEARANCE_MODE)
            ctk.set_default_color_theme(COLOR_THEME)

            self.title(APP_TITLE)
            self.geometry("1180x760")
            self.minsize(920, 600)

            self.grid_columnconfigure(0, weight=1)
            self.grid_rowconfigure(1, weight=1)

            self._build_toolbar()
            self._build_body()
            self._build_status_bar()
            self._bind_shortcuts()

            self._refresh_status()

            if load_error:
                messagebox.showwarning(
                    "Configuration",
                    load_error
                    + "\n\nDefaults are in use for now. Your existing file has "
                    "not been changed; use Settings to save a fresh one.",
                )

        # --- construction -------------------------------------------------

        def _build_toolbar(self):
            bar = ctk.CTkFrame(self)
            bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
            for i in range(6):
                bar.grid_columnconfigure(i, weight=0)
            bar.grid_columnconfigure(5, weight=1)

            self.direction_var = ctk.StringVar(
                value=self.config_data.get("default_direction", DIR_AUTO)
            )
            ctk.CTkLabel(bar, text="Direction").grid(row=0, column=0, padx=(10, 6), pady=8)
            ctk.CTkSegmentedButton(
                bar, values=list(DIRECTIONS), variable=self.direction_var,
                command=self._on_direction_change,
            ).grid(row=0, column=1, padx=6, pady=8)

            self.formality_var = ctk.StringVar(
                value=self.config_data.get("default_french_formality", FORM_INFORMAL)
            )
            ctk.CTkLabel(bar, text="French form").grid(row=0, column=2, padx=(16, 6))
            ctk.CTkOptionMenu(
                bar, values=list(FORMALITIES), variable=self.formality_var, width=170
            ).grid(row=0, column=3, padx=6)

            ctk.CTkButton(
                bar, text="Settings", width=110, command=self._open_settings
            ).grid(row=0, column=5, sticky="e", padx=10)

        def _build_body(self):
            body = ctk.CTkFrame(self, fg_color="transparent")
            body.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)
            body.grid_columnconfigure(0, weight=1, uniform="cols")
            body.grid_columnconfigure(1, weight=1, uniform="cols")
            body.grid_rowconfigure(0, weight=1)

            self._build_left(body)
            self._build_right(body)

        def _build_left(self, parent):
            left = ctk.CTkFrame(parent)
            left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
            left.grid_columnconfigure(0, weight=1)
            left.grid_rowconfigure(1, weight=1)

            ctk.CTkLabel(
                left, text="Message to translate",
                font=ctk.CTkFont(size=15, weight="bold"),
            ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

            self.input_box = ctk.CTkTextbox(left, wrap="word", font=ctk.CTkFont(size=15))
            self.input_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=4)
            self.input_box.bind("<KeyRelease>", self._on_input_change)

            self.char_label = ctk.CTkLabel(left, text="0 characters", text_color="gray70")
            self.char_label.grid(row=2, column=0, sticky="w", padx=12)

            ctk.CTkLabel(
                left, text="Ctrl+Enter to translate", text_color="gray60"
            ).grid(row=3, column=0, sticky="w", padx=12)

            buttons = ctk.CTkFrame(left, fg_color="transparent")
            buttons.grid(row=4, column=0, sticky="ew", padx=12, pady=(8, 12))
            buttons.grid_columnconfigure(3, weight=1)
            ctk.CTkButton(buttons, text="Paste", width=90, command=self._paste,
                          fg_color="gray30").grid(row=0, column=0, padx=(0, 8))
            ctk.CTkButton(buttons, text="Clear", width=90, command=self._clear,
                          fg_color="gray30").grid(row=0, column=1, padx=(0, 8))
            self.translate_btn = ctk.CTkButton(
                buttons, text="Translate", width=140, command=self._translate
            )
            self.translate_btn.grid(row=0, column=4, sticky="e")

        def _build_right(self, parent):
            right = ctk.CTkFrame(parent)
            right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
            right.grid_columnconfigure(0, weight=1)
            right.grid_rowconfigure(3, weight=1)

            ctk.CTkLabel(
                right, text="Translation",
                font=ctk.CTkFont(size=15, weight="bold"),
            ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

            # Primary translation card
            self.primary_card = ctk.CTkFrame(right)
            self.primary_card.grid(row=1, column=0, sticky="ew", padx=12, pady=4)
            self.primary_card.grid_columnconfigure(0, weight=1)
            self.primary_text = ctk.CTkLabel(
                self.primary_card, text="Your main translation will appear here.",
                justify="left", anchor="w", wraplength=460,
                font=ctk.CTkFont(size=16),
            )
            self.primary_text.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
            self.copy_main_btn = ctk.CTkButton(
                self.primary_card, text="Copy main translation",
                command=lambda: self._copy(self._current_main),
                state="disabled",
            )
            self.copy_main_btn.grid(row=1, column=0, sticky="ew", padx=12, pady=(4, 12))

            self.language_label = ctk.CTkLabel(right, text="", text_color="gray70")
            self.language_label.grid(row=2, column=0, sticky="w", padx=12)

            # Five alternatives (scrollable)
            self.alts_frame = ctk.CTkScrollableFrame(
                right, label_text="Five natural alternatives"
            )
            self.alts_frame.grid(row=3, column=0, sticky="nsew", padx=12, pady=6)
            self.alts_frame.grid_columnconfigure(0, weight=1)

            # Advisory strip (hidden until needed)
            self.advisory = ctk.CTkLabel(
                right, text="", text_color="#e0a000", justify="left", anchor="w",
                wraplength=460,
            )
            self.advisory.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 10))
            self.advisory.grid_remove()

            self._current_main = ""

        def _build_status_bar(self):
            self.status_label = ctk.CTkLabel(self, text="", anchor="w", text_color="gray70")
            self.status_label.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 10))

        def _bind_shortcuts(self):
            self.bind_all("<Control-Return>", self._translate_shortcut)

        # --- small helpers ------------------------------------------------

        def _input_text(self):
            return self.input_box.get("1.0", "end-1c")

        def _on_direction_change(self, _value=None):
            self.config_data["default_direction"] = self.direction_var.get()

        def _on_input_change(self, _event=None):
            self.char_label.configure(text="{} characters".format(len(self._input_text())))
            self._refresh_status()

        def _refresh_status(self, state=None):
            self.status_label.configure(
                text=format_status(self.config_data, len(self._input_text()), state)
            )

        def _paste(self):
            try:
                clip = self.clipboard_get()
            except Exception:
                return
            self.input_box.insert("insert", clip)
            self._on_input_change()

        def _clear(self):
            self.input_box.delete("1.0", "end")
            self._clear_results()
            self._on_input_change()

        def _clear_results(self):
            self.primary_text.configure(text="Your main translation will appear here.")
            self.copy_main_btn.configure(state="disabled")
            self.language_label.configure(text="")
            self._current_main = ""
            for card in self._variation_cards:
                card.destroy()
            self._variation_cards = []
            self.advisory.grid_remove()

        def _copy(self, text):
            if not text:
                return
            self.clipboard_clear()
            self.clipboard_append(text)

        def _open_settings(self):
            SettingsDialog(self, self.config_data, self._apply_settings)

        def _apply_settings(self, new_config):
            # Applies to the next request; a request already in flight keeps its snapshot.
            self.config_data = new_config
            self.formality_var.set(new_config.get("default_french_formality", FORM_INFORMAL))
            self._refresh_status()

        # --- translation lifecycle ---------------------------------------

        def _translate_shortcut(self, event):
            self._translate()
            return "break"  # suppress the newline Ctrl+Enter would insert

        def _translate(self):
            text = self._input_text()
            limit = int(self.config_data.get("max_input_chars", DEFAULT_MAX_INPUT_CHARS))
            ok, message = validate_source_size(text, limit)
            if not ok:
                self.advisory.configure(text=message)
                self.advisory.grid()
                return

            # Snapshot config + input so later Settings changes do not affect this run.
            snapshot = dict(self.config_data)
            snapshot["default_direction"] = self.direction_var.get()
            snapshot["default_french_formality"] = self.formality_var.get()

            if snapshot.get("backend") == "anthropic" and not snapshot.get("privacy_ack"):
                proceed = messagebox.askokcancel(
                    "Privacy notice",
                    "Claude translates in the cloud, so the text you submit is "
                    "sent to Anthropic. Ollama, by contrast, keeps everything on "
                    "this machine.\n\nContinue with Claude?",
                )
                if not proceed:
                    return
                self.config_data["privacy_ack"] = True
                snapshot["privacy_ack"] = True
                try:
                    save_config(self.config_data)
                except ConfigError:
                    pass

            self._request_id += 1
            rid = self._request_id
            self._active_snapshot = (rid, text)

            self.translate_btn.configure(state="disabled", text="Translating\u2026")
            self.advisory.grid_remove()
            self._refresh_status(state="translating\u2026")

            def worker():
                try:
                    result = translate(snapshot, text)
                    payload = ("ok", result)
                except (BackendError, TranslationValidationError) as exc:
                    payload = ("error", str(exc))
                except Exception as exc:  # pragma: no cover - defensive
                    payload = ("error", "An unexpected error occurred: {}".format(
                        exc.__class__.__name__))
                self.after(0, lambda: self._deliver(rid, text, payload))

            threading.Thread(target=worker, daemon=True).start()

        def _deliver(self, rid, snap_text, payload):
            # Ignore any result whose request has been superseded (later request,
            # Clear, or close). This is the stale-callback guard.
            if result_is_stale(rid, self._request_id):
                return
            self.translate_btn.configure(state="normal", text="Translate")

            kind, data = payload
            if kind == "error":
                self.advisory.configure(text=data)
                self.advisory.grid()
                self._refresh_status(state="ready")
                return

            self._render_result(data)

            # If the input changed since this request began, keep the result but
            # flag it clearly rather than overwriting the source text.
            if self._input_text() != snap_text:
                self.advisory.configure(
                    text="Generated for an earlier message. Your input has "
                         "changed since this translation was requested."
                )
                self.advisory.grid()
            self._refresh_status(state="ready")

        def _render_result(self, result):
            self._current_main = result["main_translation"]
            self.primary_text.configure(text=self._current_main)
            self.copy_main_btn.configure(state="normal")
            self.language_label.configure(text=format_language_label(result))

            for card in self._variation_cards:
                card.destroy()
            self._variation_cards = []

            for index, variation in enumerate(result["variations"], start=1):
                card = ctk.CTkFrame(self.alts_frame, border_width=1)
                card.grid(row=index, column=0, sticky="ew", pady=6, padx=4)
                card.grid_columnconfigure(0, weight=1)

                ctk.CTkLabel(
                    card, text="{}. {}".format(index, variation["translation"]),
                    justify="left", anchor="w", wraplength=430,
                    font=ctk.CTkFont(size=14),
                ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))

                ctk.CTkLabel(
                    card, text="[{}]".format(variation["english_meaning_check"]),
                    justify="left", anchor="w", wraplength=430, text_color="gray65",
                ).grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 4))

                ctk.CTkButton(
                    card, text="Copy", width=80,
                    command=lambda t=variation["translation"]: self._copy(t),
                ).grid(row=0, column=1, rowspan=2, padx=8, pady=8)

                self._variation_cards.append(card)

            notes = result.get("language_note", "")
            extra = result.get("notes", [])
            advisory_bits = [n for n in ([notes] + extra) if n]
            if advisory_bits:
                self.advisory.configure(text="  \u2022  ".join(advisory_bits))
                self.advisory.grid()
            else:
                self.advisory.grid_remove()


# ===========================================================================
# 8. main() entry point
# ===========================================================================

def main():
    if not GUI_AVAILABLE:
        sys.stderr.write(
            "Plume needs CustomTkinter to run its window. Install it with:\n"
            "    pip install customtkinter>=5.2.0\n"
        )
        return 1
    app = PlumeApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
