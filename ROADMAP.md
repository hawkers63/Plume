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

## v1.2 — Essential Shortcuts + first console-less .exe  ✅ landed (pending your review/push)

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

## v1.3 — Selection + backend toggle

- **"Use this" (notes_005):** promote an alternative to the working main
  translation without a second API call; the five cards stay for comparison.
  Slots cleanly into `_build_variation_card`.
- **Toolbar backend toggle (notes_006 §2):** a Claude ⇄ Ollama segmented button
  on the toolbar, mirroring the existing "toolbar wins at save" rule.

## v1.4 — Quick-swap direction + contextual prompting

- A one-click direction-swap (English → French ⇄ French → English).
- An optional "situation" box to steer register/context without weakening the
  strict JSON contract.

## v1.5 — Local History & Favourites

- Opt-in, on-disk history and favourites UI, behind explicit consent. Off by
  default, honouring the version-1 privacy stance.

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
