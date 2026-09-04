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

## v1.6 — Voice (TTS via ElevenLabs)  ✅ landed and pushed

- Spoken output for translations, via a "Speak" button on the primary card
  and each of the five alternatives — a pronunciation aid, not a chat
  feature. `urllib`-only REST call to ElevenLabs' one-shot Text-to-Speech
  endpoint (`POST /v1/text-to-speech/{voice_id}`), not the Conversational-AI
  SDK: this is "read this exact text aloud", never a live voice agent.
  Off by default (no API key configured) and gated behind the same
  privacy-notice pattern already used for the Claude cloud backend.

## v1.7 — History polish (notes_007)  ✅ landed and pushed

- **Toolbar refactor:** replaced the toolbar's hand-counted literal column
  numbers with a running counter, so future controls (already three-for-three
  on needing a renumber: Backend in v1.3, Swap in v1.4, History in v1.5)
  stop taxing every unrelated widget after the insertion point. Verified
  pixel-identical to the pre-refactor layout.
- **Situation on history entries:** `make_history_entry()` now takes and
  stores `situation`, threaded through `_translate`/`_deliver`/
  `_save_to_history`; the History card shows an italicised "Situation: …"
  line only when one was given, so pre-existing entries render unchanged.
- **Reopen from History:** a "Reopen" button per history card loads a past
  source phrase, its situation and its five alternatives back into the
  working translator with no network request, reusing `_render_result`
  exactly as it already exists. One accepted cosmetic quirk (flagged in
  notes_007): a reopened entry always shows "detected with low confidence"
  since `language_confidence` isn't stored in history — fixed in v1.8.

## v1.8 — Hardening pass (bug detection & repair)  ✅ landed locally

- No new feature surface. Implemented the hardening findings from
  notes_008: result advisories now render independently of opt-in history
  saving, so low-confidence language notes and placeholder-preservation
  warnings are visible for default users.
- History entries now preserve `language_confidence`, `language_note` and
  `notes`, and history loading normalises entry shape so malformed local
  records cannot crash Reopen.
- Speak/TTS delivery now has its own stale-request guard and temp-file cleanup,
  mirroring the existing translation worker protection.
- Shared HTTP diagnostics are service-aware, so Ollama HTTP failures no longer
  show Claude-specific wording.
- Settings exposes the existing `max_input_chars` limit, and
  `plume_config.example.json` is kept in parity with `DEFAULT_CONFIG`.
- README text was brought up to date for local history, Reopen, and
  ElevenLabs Speak.

## v1.9 — Reply loop + Always on top (notes_009, notes_010)  ✅ landed locally

- **Reply** (notes_009 §1 and notes_010 Feature 1, merged): both notes
  proposed the same "end your turn" button independently, which is
  itself a good sign, but their designs disagree on two points and
  this scope has to pick one rather than build both. Mechanism follows
  notes_009 throughout: reuses the existing `swap_direction()` helper
  rather than notes_010's hard-coded English → French, so it stays
  correct when Auto-detect is selected and for either direction of a
  reply chain; and the right-hand result stays visible rather than
  being cleared, since the point of the button is to keep what was
  just sent on screen while the incoming reply is pasted. The working
  main translation (if any) is copied exactly as `Copy main
  translation` already does, and the input box is cleared and
  focused — the one piece both notes agreed on. notes_010's other
  idea, auto-filling Situation with a quoted "In reply to: …" snippet,
  is deliberately **not** adopted: Situation is a persistent scene/
  register descriptor ("formal work email") that v1.4 designed to
  survive across a thread, and notes_009 argued for leaving it alone
  for exactly that reason. Overwriting it every Reply click would
  destroy that context each turn, which is a regression rather than
  an improvement — a per-turn quoted snippet and a persistent scene
  description are two different kinds of information and do not
  belong in the same field. Disabled alongside `translate_btn` while
  a request is in flight.
- **Always on top** (notes_009 §3): a "Keep Plume on top of other
  windows" Settings checkbox, off by default, backed by a new
  `always_on_top` config key and the Tk `-topmost` attribute. Applied
  at start-up and immediately on Settings save, no restart required.

## v1.10 — Keep as-is (notes_009 §2)  ✅ landed locally

- A short local list of names/terms (max 20, 40 characters each) that
  the existing placeholder-protection pipeline masks before sending
  text to the model and restores afterwards, applied longest-first so
  "Marie-Claire" is not swallowed by "Marie". Stored as
  `keep_as_is_terms` in `plume_config.json` (local only, already
  gitignored). Scoped as its own version rather than folded into
  v1.9: it changes `protect_text()`'s signature and needs the four
  dedicated tests notes_009 sets out (mask/restore, longest-term-wins,
  no over-matching, normalisation/cap/dedupe), unlike the two
  Settings-only, no-parsing additions in v1.9.
- `protect_text()` gained an `extra_terms` parameter, applied
  longest-first ahead of the built-in URL/date/handle patterns via a
  new `keep_as_is_pattern()` (case-sensitive, `\w`-boundary match) so a
  user term cannot be swallowed by a later built-in match. Existing
  callers that omit `extra_terms` are unaffected.
  `normalise_keep_as_is_terms()` sanitises both the Settings textbox
  (newline/comma/semicolon-separated) and a hand-edited config list:
  strips, drops empty/oversized/case-insensitive-duplicate entries,
  caps at 20. `translate()` passes the config snapshot's terms through
  it before masking; when `protect_placeholders` is off, extra terms
  are skipped too, since it remains one privacy/protection switch.
- Settings gained a "Keep as-is" textbox (one term per line) beside
  the other privacy controls, reusing the existing dialog's pack/grid
  pattern; `plume_config.example.json` stays in parity with
  `DEFAULT_CONFIG`.

## v1.11 — Live-loop polish (notes_008 backlog)  ✅ landed locally

Three of the five lightweight feature candidates notes_008 raised
alongside its hardening findings, not picked up by v1.8 because that
release was fixes-only. Grouped together as small, self-contained
button/menu additions that reuse existing helpers with no config
schema impact beyond one constants tuple:

- **Situation presets:** a `SITUATION_PRESETS` tuple (Close friend,
  Formal work email, Neighbour, Appointment, Dating/chat) backs a
  `CTkOptionMenu` beside the Situation field; picking one writes it
  straight into the existing entry via `_apply_situation_preset()`, so
  it is still freely editable afterwards and reuses the same prompt
  pathway as a hand-typed situation.
- **Copy source:** a "Copy source" button beside Paste/Clear, for
  chat back-and-forth, backed by `_copy_source()`.
- **Re-translate using current output as input:** a "Use as input"
  button that copies the main translation into the input box, swaps
  the fixed direction if applicable (reusing `swap_direction()`), and
  clears results — the sibling case to v1.9's Reply for when the
  reply arrives as spoken/typed French rather than being pasted.
  `_use_main_as_input()` always sends the raw main translation (never
  a finishing touch, matching Speak's convention) and is disabled
  alongside Translate/Reply while a request is in flight, guarding
  against a stale delivery landing on top of the fresh input.

## v1.12 — Voice extensions (notes_008 backlog, notes_010 Feature 2)  ✅ landed locally

- **Stop speech button** (notes_008 candidate #3): a "Stop" button next
  to Speak on the primary card, wired to the existing `_stop_speech()`.
  Left always enabled rather than tracked against playback state, since
  `winsound.PlaySound(None, SND_PURGE)` is already a safe no-op when
  nothing is playing.
- **Slow pronunciation mode** (notes_010 Feature 2): a "Slow" checkbox
  beside the finishing-touch picker. `SLOW_SPEECH_RATE_FACTOR = 0.75`
  scales `pcm_to_wav_bytes()`'s `sample_rate` argument at Speak time —
  no extra ElevenLabs call, reuses the already-synthesised PCM. Read
  once per Speak click, so it applies uniformly whether Speak was
  clicked on the main card or an alternative. Scoping note: this also
  drops the pitch, the way a slowed record does, since it is a
  playback-rate trick rather than true time-stretching. Accepted for
  v1.12 (it is still a genuine pronunciation aid and stays
  zero-dependency); the UI label and README say "slow" rather than
  implying studio-quality time-stretch, so it is not read as a bug
  later.

## v1.13 — History & study export (notes_008 backlog, notes_010 Feature 3)  ✅ landed locally

- **Favourite current result from the main panel** (notes_008
  candidate #4): a "☆ Favourite" button on the primary card. Builds a
  fresh history entry via `make_history_entry(..., favourite=True)`
  from the last rendered result rather than searching for one
  `_save_to_history` may already have written, so it works whether
  local history was on or off when the translation ran; if it was
  off, a prompt offers to turn it on first (declining changes
  nothing). Uses the currently displayed main translation (honouring
  a "Use this" promotion) with the alternatives/metadata from the
  last full result. Resets to un-starred whenever the working main
  translation changes, so a stale favourite can never silently apply
  to different text; reopening an already-favourited history entry
  shows "★ Favourited" (disabled) immediately, rather than allowing a
  duplicate entry.
- **Export favourites** (notes_010 Feature 3): an "Export favourites"
  button in the History window. `export_history_to_tsv()` builds an
  Anki-style deck (Front: source + situation, Back: main translation
  + all five alternatives, joined with `<br>` so each note stays on
  one physical line — a hard requirement for Anki's TSV importer) and
  `export_history_to_markdown()` builds a dated study sheet; a single
  save dialogue picks the format from the chosen file extension
  (`.tsv` vs `.md`). Local file only (`tkinter.filedialog`), no new
  dependency.
- **Settings dialog bug fix, found while testing this release:**
  `SettingsDialog` had grown to 27 stacked controls (most recently the
  v1.10 Keep as-is box) on a fixed-height, non-scrolling window;
  launching it now clipped the status line and Cancel/Save below the
  window's bottom edge with no way to reach them. Fixed by moving the
  form into a `CTkScrollableFrame` — the same pattern already used for
  the alternatives list and the History window — with the status label
  and Cancel/Save pinned as a fixed footer outside the scroll area, so
  they stay visible without scrolling and the dialog no longer needs a
  pixel-perfect height retuned every time a future control is added.

## v1.14 — Casual sign-off / slang finishing touches (notes_004, revisited)  ✅ landed locally

- The second finishing-touch phase notes_004 originally proposed
  alongside v1.2's emote group (tkt, grave, and similar slang), held
  back deliberately until the emote group had been "lived with" —
  notes_009 confirmed as recently as this note round that it judged
  the group "not due yet". With v1.3 through v1.8 now shipped and in
  use, this is the natural point to schedule it rather than leave it
  permanently deferred. Unlike the Emotes & Reactions group, slang
  terms change register and meaning, not just tone, so this needs its
  own review of prompt-safety wording before landing, not a copy of
  the v1.2 mechanism.
- **Not a copy of the v1.2 mechanism, concretely:** a new
  `CASUAL_SIGNOFFS = (CASUAL_SIGNOFF_NONE, "tkt", "grave")` catalogue
  gets its own "Casual sign-off" picker, separate from "Add a
  finishing touch", with a plain-language caption ("Changes register
  and meaning, not just tone") next to it — a slang term never sits
  unlabelled beside a tone-only emote. Kept to exactly the two terms
  notes_004 named as safe examples; every other entry in Essential
  Shortcuts.txt is a greeting, an in-sentence abbreviation, a
  standalone reply, a noun, or carries a harsher or more culturally
  loaded connotation (`wesh`, `meuf`, `keuf`, `boloss`, …), and stays
  out — a curation-guard test pins the exclusion.
- The two pickers are independent and compose: a new pure
  `compose_finishing_touch(emote, signoff)` space-joins whichever of
  the two is selected (either, both, or neither) into one string,
  which then feeds unchanged into the existing, already-tested
  `append_finishing_touch()`. `PlumeApp._current_touch()` becomes the
  single call site for both pickers, so `_refresh_primary_display()`,
  `_copy_main()` and `_copy_variation()` needed no changes. Both
  pickers reset to "None" on Clear and on Reopen from History, mirroring
  the existing finishing-touch reset.

## v1.15 — Correct English, then translate to French (notes_011 Feature A)

- **Correct English** button, right-aligned next to Translate on its own
  row beneath Paste / Clear / Copy source / Reply (a sixth fixed-width
  button on the original single row pushed Translate off-screen at the
  default 1180px width — split into two rows instead of widening the
  window, mirroring the Settings dialog's Cancel/Save spacer pattern),
  plus a Ctrl+Shift+Enter shortcut on the input box. A dedicated, narrower
  model call (`build_correction_prompt` / `parse_correction_result` /
  `correct_english`) fixes spelling, grammar and necessary punctuation only
  — no paraphrasing, register change, or translation — then overwrites the
  input box with the corrected English and immediately runs the existing
  Translate pipeline. Two separate calls, not one combined prompt: the user
  always sees the exact English that was actually translated, and history
  records the corrected text as the source.
- Enabled for English → French or Auto-detect (guarded by the conservative
  `looks_like_english()` diacritic check, which prefers a false refusal
  over silently English-correcting a French message); refused for
  French → English with an explanation in the advisory strip. Auto-detect
  is pinned to English → French after a successful correction so a short
  corrected phrase cannot bounce back into French → English.
- Same in-flight lock, stale-request guard and Claude privacy notice as
  Translate. If the input changes while correction is running, the result
  is discarded rather than overwriting newer text (matching `_deliver`'s
  existing "generated for an earlier message" discipline).

## v1.16 — Sign-in autostart, minimised to the tray (notes_011 Feature B)

- **Sign-in autostart:** a "Launch Plume when I sign in to Windows"
  checkbox in Settings writes a quoted command (always including
  `--start-minimised`) to the current user's
  `HKCU\...\CurrentVersion\Run` key via `winreg`; unchecking deletes the
  value. `set_launch_at_sign_in()` refuses to *enable* it outright on a
  non-Windows machine or when the tray extras are missing — the command
  always passes `--start-minimised`, so without a tray to hide into, the
  window would just flash at every sign-in instead of sitting quietly.
- **Tray icon, feature-gated:** `pystray` + `Pillow` are optional
  (`TRAY_AVAILABLE`); Plume imports and runs exactly as before when
  either is missing, and the three tray checkboxes in Settings are shown
  disabled with a one-line caption rather than hidden without
  explanation. The tray menu offers Show and Quit; the tray thread
  marshals every UI action back to the Tk thread via `self.after(0, …)`,
  the same discipline already used for Speak and Correct English
  delivery.
- **Start minimised to the tray** withdraws the window right after
  construction (or immediately on Settings save, if just enabled) and
  again whenever launched with `--start-minimised` on argv — the flag
  the autostart command always passes.
- **Close to the tray rather than quitting** replaces the destroy-on-X
  behaviour with `withdraw()` when a tray icon is running; the tray's
  Show item restores geometry, `deiconify()`, `lift()`, `focus_force()`
  and re-applies Always on top (v1.9) so a hidden-then-shown window
  never silently loses that flag. Quit (from the tray menu, or a real
  close when close-to-tray is off) is the only path that stops the tray
  icon and invalidates in-flight work via the existing `_on_close`
  teardown. Single-instance enforcement is deliberately out of scope —
  a second launch just opens a second window.
- Verified end-to-end against the live app: enabling "Start minimised to
  the tray" and "Close to the tray" and saving withdrew the running
  window immediately; a fresh launch with those settings saved withdrew
  on startup; sending the window a close request (the X-button path)
  hid it rather than exiting, with the process staying alive throughout.
  "Launch at sign-in" itself was verified only via mocked-registry unit
  tests, not exercised for real, so as not to write a persistent
  autostart entry to the developer's own Windows account during testing.

---

### Notes on sequencing

- The v1.2 refactor was landed *with* the finishing-touch picker precisely so
  that v1.3's "Use this" and the picker's touch-aware Copy do not collide in a
  shared loop body — both now extend `_build_variation_card` in one place.
- Finishing touches shipped the safe "Emotes & Reactions" group first (v1.2).
  A "Casual sign-off / slang" group (tkt, grave) was left for a later phase
  after the first experience proved satisfactory; that phase landed as v1.14,
  as its own picker rather than folded into the emote one.
- notes_009 and notes_010 both proposed an end-of-turn "Reply" button
  independently; v1.9 merges them into one feature rather than shipping two,
  following notes_009's mechanism throughout and declining notes_010's
  Situation auto-fill as a regression against v1.4's design — see v1.9 above
  for the reasoning.
