# Plume — Roadmap

Plume is a Windows 11 desktop French ↔ English conversation helper: one faithful
main translation plus five natural, same-tone alternatives, each with an English
meaning check. This roadmap is organised by version. It records what has landed
and what is planned, so each release has a clear, single-purpose scope.

Working conventions: British English throughout; `urllib` only (no `requests`,
no SDK); atomic JSON config; strict validated response contract; stale-callback
protection; changes reviewed and pushed manually per `AGENTS.md` (no auto-push).

---

## v1.1 — current baseline (released to GitHub)

- French gender agreement: separate **Me / You** controls (Feminine · Masculine ·
  Avoid where possible), carried through snapshot → prompt → envelope.
- Removed the "Five natural alternatives" heading to reclaim vertical space.
- Earlier bug fixes (Clear supersedes in-flight work, window-close guard,
  status-bar state, config coercion, backend hardening) and `.gitignore`.

## v1.2 — Essential Shortcuts + first console-less .exe  ✅ landed and pushed

- **Refactor (notes_006 §1):** extracted `PlumeApp._build_variation_card`, giving
  the alternative cards one seam for future button changes. No visual change.
- **Essential Shortcuts / finishing-touch picker (notes_004):** a curated,
  optional "Add a finishing touch" emote menu beneath the main translation
  (None · :) · :p · ;) · xD · mdr · ptdr · jpp). Applied *after* translation, at
  copy time; the translation itself is never altered and nothing extra is sent
  to the model. `Copy main translation` and each alternative's `Copy` append the
  selected touch; the picker resets on Clear.
- **.exe:** `plume.spec` already sets `console=False`, so a PyInstaller build
  suppresses the PowerShell window. Build step to be run on Windows.

## v1.3 — Selection + backend toggle  ✅ landed and pushed

- **"Use this" (notes_005):** `adopt_main_translation()` plus `_use_as_main`
  promote an alternative to the working main translation without a second API
  call; the five cards stay for comparison. Slotted into `_build_variation_card`
  as a two-button column (Use this / Copy).
- **Toolbar backend toggle (notes_006 §2):** `normalise_backend()` centralises
  the Ollama/Anthropic coercion; a Claude ⇄ Ollama segmented button on the
  toolbar mirrors into `config_data`, refreshes the status bar immediately, and
  follows the existing "toolbar wins at save" rule.

## v1.4 — Quick-swap direction + contextual prompting  ✅ landed and pushed

- **Quick-swap direction:** `swap_direction()` inverts English → French ⇄
  French → English (a no-op on Auto-detect); a "Swap" button sits on the
  toolbar between Direction and Backend.
- **Situation box:** an optional "Situation (optional)" field steers
  register/context. Wired through `translate()` and `build_user_envelope()`
  as a labelled line, bounded by the existing `_safe_short_string`. A
  dedicated system-prompt clause requires the model to treat it strictly as
  background context, never as an instruction — it cannot change the JSON
  output shape, add or remove fields, override the requested direction, or
  outrank the source text's own faithful meaning.

## v1.5 — Local History & Favourites  ✅ landed and pushed

- **Storage:** `plume_history.json`, atomic-write (mirrors `save_config`),
  malformed-file protection via `HistoryError`; gitignored alongside
  `plume_config.json` since it holds real conversation content.
- **Opt-in, automatic save:** every successful translation is saved via
  `_save_to_history`, gated on a new "Save translations to local history
  (stored on this device only)" checkbox in Settings — off by default.
- **Favourites:** `prune_history` keeps every favourite exempt from the
  200-entry rolling cap; "Clear history" removes only non-favourited entries.
- **History window:** a new toolbar button opens a separate dialog (same
  pattern as Settings) — scrollable list newest-first, per-entry
  Favourite/Copy/Delete, a "Favourites only" filter, and "Clear history
  (keeps favourites)" with a confirmation prompt.

## v1.6 — Voice (TTS via ElevenLabs)

- Spoken output for translations. Deferred last, once the typed workflow is
  thoroughly dependable, as the project spec advises.

---

### Notes on sequencing

- The v1.2 refactor was landed *with* the finishing-touch picker precisely so
  that v1.3's "Use this" and the picker's touch-aware Copy do not collide in a
  shared loop body — both now extend `_build_variation_card` in one place.
- Finishing touches deliberately ship only the safe "Emotes & Reactions" group.
  A "Casual sign-off / slang" group (tkt, grave, …) can follow in a later phase
  after the first experience proves satisfactory.
