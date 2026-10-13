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
- **Bug fix, found rebuilding and testing the frozen .exe:** the tray
  icon never actually appeared in a real build — `_icon_png_path()`
  (and the pre-existing, unrelated `_apply_window_icon()`, broken the
  same way since v1.1) located bundled files via
  `os.path.dirname(os.path.abspath(__file__))`, which does not reliably
  point at PyInstaller's extraction directory when frozen. Both silently
  treated the resulting "file not found" as "skip" — a generic window
  icon and a tray icon that never started, no error either way. Fixed
  with a new `resource_dir()` helper that uses `sys._MEIPASS` when
  frozen (distinct from `config_dir()`, which is a writable location,
  not a resource-lookup one). Confirmed only by actually launching the
  rebuilt frozen .exe and finding the tray icon missing from the real
  Windows notification area, including its overflow flyout — running
  from source, or even the app just starting without error, would never
  have surfaced this.

## v1.17 — Backend resilience (notes_011 Feature G)

- `_http_post_json` retries 429/502/503/504, dropped connections
  (`URLError`) and timeouts with bounded exponential backoff
  (`_backoff_delay`: `HTTP_BACKOFF_BASE` doubling per attempt, capped at
  `HTTP_BACKOFF_CAP`, plus up to 25% jitter so concurrent retries do not
  land together) — up to `HTTP_MAX_ATTEMPTS` (4) attempts total. A
  numeric `Retry-After` header is honoured outright, still capped.
  401/403/404 and other client errors are never retried; `HTTPError` is
  caught before `URLError` since it is a subclass. Both translation and
  Speak already run on a worker thread, so a blocking `time.sleep`
  between attempts is safe.
- **Streaming preparation, not streaming:** Claude's payload now sets
  `"stream": False` explicitly, and the response-parsing halves of
  `call_anthropic`/`call_ollama` are lifted into standalone
  `_anthropic_text_from_response()` / `_ollama_text_from_response()` —
  the same functions a later `_http_post_json` retry loop and a future
  SSE slice would both need, without changing today's JSON-only
  contract or adding any actual streaming/token-painting in this
  version.
- Verified against the live app: a real Claude translation still
  completed correctly after the refactor (unchanged behaviour, not a
  new capability — there was no transient failure to trigger a retry
  against the live API in this session).

## v1.18 — Explorer drag-and-drop (notes_011 Feature C) — attempted, reverted

- notes_011's `WindowsDropTarget` design (native `WM_DROPFILES` via a
  ctypes `SetWindowLongPtrW` subclass of the Tk toplevel's WndProc, no
  TkDND) was implemented in full: the subclass, `read_dropped_file()`
  (.txt/.md always, .docx behind a `DOCX_AVAILABLE` guard exactly like
  `TRAY_AVAILABLE`), extension filtering, and the "first supported file
  wins, extras ignored with one advisory" replace-not-merge behaviour.
- Two real bugs were found and fixed during testing: the note's own
  `DragFinish(hdrop)` call passed a 64-bit HDROP through ctypes with no
  `argtypes`, so ctypes assumed a 32-bit C `int` and raised
  `OverflowError` on every real handle — silently swallowed by the
  handler's own "fail closed" `except Exception: pass`, so the drop
  appeared to simply do nothing. Fixing the `argtypes` exposed a second,
  far more serious fault: **posting a real `WM_DROPFILES` message from
  an external process** (simulated by constructing a genuine `DROPFILES`
  structure via `GlobalAlloc`/`PostMessage` from a separate PowerShell
  process — mechanically the same delivery path Explorer itself uses,
  not a synthetic shortcut) **crashed the whole interpreter** with
  `Fatal Python error: PyEval_RestoreThread: the function must be called
  with the GIL held, but the GIL is released (the current Python thread
  state is NULL)`. Explicitly wrapping the drop handler in
  `ctypes.pythonapi.PyGILState_Ensure()`/`PyGILState_Release()` — the
  standard fix for calling into Python from a foreign thread context —
  did not change the crash at all, which points to a deeper conflict
  between raw `WNDPROC` subclassing and this Tcl/Tk build's own internal
  Windows message-pump/notifier implementation, not a simple missing-GIL
  bug in the handler itself.
- notes_011 itself named this "the most fragile slice" and prescribed
  failing closed (DragAcceptFiles off, no crash, Paste still works) if
  it misbehaved. A hard interpreter crash on a real Explorer drop is the
  opposite of failing closed, so this version was **reverted in full**
  (`git checkout --` back to the v1.17 tree) rather than shipped with a
  known crash path — a real user dragging a file onto Plume would hit
  the same asynchronous, cross-process delivery that crashed the test.
- Not scheduled for a specific future version. Revisiting this needs
  either real Tcl/Tk-on-Windows notifier expertise to find the actual
  conflict, or dropping the "no TkDND" constraint in favour of a
  maintained library (e.g. `tkinterdnd2`) that already solves this
  problem correctly, rather than further trial-and-error on hand-rolled
  ctypes subclassing.

## v1.19 — User conversation presets (notes_011 Feature D)

- A different object from the local-only Situation presets (v1.11): a
  named snapshot of the toolbar's five live controls (direction, French
  form, Me, You, situation), stored in `plume_config.json` as
  `conversation_presets` (capped at `MAX_CONVERSATION_PRESETS`, 12).
  `normalise_conversation_preset()`/`normalise_conversation_presets()`
  drop malformed entries and coerce unknown enum values to the same
  defaults `_coerce_choice` already uses elsewhere, so a hand-edited
  file cannot crash `load_config`.
- Toolbar UI (row 1, after You): a "Presets…" `OptionMenu` that applies
  a preset's controls immediately (in-memory only, matching the
  existing toolbar-wins-at-save rule), plus "Save preset…" (a
  `CTkInputDialog` for the name) and "Delete". Unlike the toolbar
  values themselves, the preset *list* is written to disk immediately
  on Save/Delete via `save_config`, so a named preset cannot vanish if
  Plume crashes before Settings is next saved.
- Verified end-to-end against the live app: saved a preset with a
  non-default direction and situation, confirmed it persisted to
  `plume_config.json` immediately, reset the toolbar, selected the
  preset from the menu and confirmed it restored both fields, then
  deleted it and confirmed the file and menu both went back to empty.

## v1.20 — Three-tone register combinator (notes_011 Feature E)

- Up to three register tones (`REGISTER_TONES`: Warm, Terse, Playful,
  Precise, Courteous, Direct, Reassuring) as three compact `OptionMenu`s
  under the Situation row on the input pane. The same class of
  information as Situation and just as non-authoritative:
  `build_tone_instruction()` explicitly forbids changing the JSON
  shape, adding facts, or outranking the source text.
- `validate_tones()` caps at three, drops unknown/`None` entries, and
  resolves the four fixed conflict pairs (Terse/Playful, Terse/Warm,
  Playful/Precise, Direct/Reassuring) by keeping whichever tone comes
  *later* in the given order. The three menus feed their values through
  in fixed left-to-right slot order on every change, so a newly-chosen
  conflicting tone always wins over an existing one and the resolved
  selection compacts left — simple and fully deterministic, at the cost
  of using slot position rather than true click-order as the "later"
  signal.
- Wired into both `build_translation_prompt` (a background-only clause
  appended after the Situation clause) and `build_user_envelope` (an
  omitted-when-empty "Tones: …" line), matching Situation's own
  omitted-when-blank pattern so existing callers and tests stay
  unaffected. `translate()` reads tones from `config_snapshot["tones"]`
  (set by `PlumeApp._translate()` from the three live menus), not from
  a separate parameter like Situation, since tones have no per-message
  free-text component.
- Reopening a history entry resets all three tone menus to None, the
  same as the finishing-touch and casual-sign-off pickers: history
  entries predate this version and carry no stored tone data, so
  resuming an old entry should not silently inherit today's live tones.
- Verified end-to-end against the live app: selecting Terse then a
  conflicting Playful correctly dropped Terse and compacted Playful
  into the first slot; a real Claude translation completed normally
  with a tone active.

## v1.21 — Current-result export, HTML clipboard, metrics (notes_011 Feature F)

- **Export**, next to Favourite on the primary card: writes a Markdown
  study sheet (`export_current_result_markdown`) with the source,
  situation, main translation, all five alternatives, and a fenced
  `difflib.unified_diff` of source vs. translation — a reading aid, not
  a claim the two texts match (they are different languages). Distinct
  from v1.13's Export favourites: this exports whatever is currently on
  screen, whether or not local history is enabled, via the same
  `_current_result` + `_current_main` ("Use this"-aware) pattern as
  Favourite.
- **Copy as HTML**, Windows only: puts a real `CF_HTML` clipboard
  payload alongside a plain-text fallback, via
  `copy_html_to_windows_clipboard()`. `_build_cf_html()` — the fiddly
  part, per Microsoft's HTML Clipboard Format — builds the header twice
  (placeholder offsets first, purely to measure its own byte length,
  then the real offsets), all as UTF-8 byte positions. Falls back to
  the existing plain-text `_copy()` on any non-Windows platform or if
  the clipboard write fails for any reason, so the button always does
  *something* useful. Unlike v1.18's WM_DROPFILES, this has no
  callback-into-Python re-entrancy (`OpenClipboard`/`SetClipboardData`
  are synchronous, same-thread, outward-only calls), so the GIL/thread-
  state hazard that sank v1.18 does not apply here.
- **Metrics**: the input pane's character count becomes "N characters
  · M words · ~Xs to read" (`text_metrics`/`format_metrics_label`).
  English ~200 wpm, French ~180 wpm; Auto-detect and a fixed
  English → French direction both use the English rate rather than
  running a model call just to pick a words-per-minute constant.
- Verified end-to-end against the live app: the metrics label updated
  correctly while typing; Export produced a correctly-formatted file
  (checked on disk) via the real native Save dialog; Copy as HTML was
  verified by reading the live Windows clipboard back afterwards
  (`System.Windows.Forms.Clipboard`, from PowerShell) — both the plain
  text and the `HTML Format` payload round-tripped correctly, with
  .NET's own independent reader confirming the byte offsets were exact.

## v1.22 — History race + stale Reopen (notes_012 C1, C2)

- **C1, History window clobbers concurrent saves:** `HistoryDialog` loaded
  `self._entries` once at construction and every mutation (`_toggle_favourite`,
  `_delete_entry`, `_clear_history`, `_export_favourites`) wrote that same
  in-memory snapshot back via `_persist`. A translation saved or favourited
  from the main window while the dialog was open, followed by any mutation
  in the dialog, silently discarded the main window's write — the exact
  "favourited items must not vanish" invariant the class docstring claimed
  to preserve. Fixed with `_reload_entries()`, called at the top of every
  mutation before touching `self._entries`, so this dialog and PlumeApp's
  own writers can never share a stale snapshot.
- **C2, Reopen doesn't supersede in-flight work:** `_reopen_history_entry`
  filled the input/result from a saved entry but never bumped `_request_id`/
  `_speech_request_id` or reset the Translate/Correct/Reply lock, unlike
  `_clear` and window-close. A translate or Speak request started before
  Reopen could complete afterwards and silently overwrite the reopened
  result. Fixed by giving Reopen the same opening `_clear()` uses (bump
  both ids, stop speech, re-enable the three buttons) without wiping the
  input/cards it is about to fill.
- Verified with a script that drives the real `PlumeApp`/`HistoryDialog`
  classes (not mocks) against an isolated temp config directory: a
  concurrent main-window save survives a stale-dialog favourite click, and
  a request issued before Reopen is correctly dropped as stale when it
  completes afterwards. Full suite: 213 tests pass.

## v1.23 — Source-snapshot integrity, textual diff export, favourite robustness (notes_012 M5/M10, notes_013 D1)

- **M5, Favourite/Export used the live input, not the rendered source:**
  `_favourite_current_result` and `_export_current_result` read
  `self._input_text()`/`self._situation_text()` at click time. If the input
  box was edited after a result rendered but before the user favourited or
  exported it (without re-translating), the saved/exported "source" no
  longer matched the text that actually produced the on-screen result —
  corrupting study data. Fixed with `self._result_source_text`/
  `self._result_situation`, captured once in `_deliver` (from the existing
  `snap_text`/`situation` parameters) and in `_reopen_history_entry` (from
  the history record), cleared in `_clear_results`; both methods now read
  the snapshot instead of the live widgets.
- **D1, textual diff export:** a new "Export diff…" button beside Favourite
  and Export, using `export_translation_diff()` — a `difflib.unified_diff`
  of source vs. translation in a Markdown fence sized longer than any
  backtick run already in the content, explicitly labelled as a textual
  comparison across languages rather than a claim of accuracy. Uses the
  same source snapshot as Export, so it is affected by the M5 fix as well.
- **M10, favourites with an atypical alternative count were silently
  deleted:** `normalise_history_entry` returned `None` — dropping the
  entry entirely on the next load — whenever a history record didn't have
  exactly `VARIATION_COUNT` (5) well-formed alternatives, with no exemption
  for favourites. A hand-edit, partial write, or future schema change could
  delete a favourite outright, violating the stated "favourited items must
  not vanish" invariant. Fixed so a favourite is kept with however many
  well-formed alternatives it has; a non-favourite is still dropped if it
  doesn't have exactly five (unchanged behaviour for ordinary history).
- 7 new unit tests (normalise_history_entry favourite/non-favourite
  variation-count cases, `export_translation_diff`'s no-difference/fenced/
  final-newline/backtick-fence/accuracy-disclaimer cases). Verified live
  against the real `PlumeApp` class (isolated temp config dir): editing the
  input after a result renders no longer changes what Favourite, Export or
  Export diff record as the source; Reopen and Clear correctly set/reset
  the snapshot; a 2-alternative favourite survives a save/load round trip.
  Full suite: 220 tests pass.

## v1.24 — Transactional presets with tones; recency-correct tone conflicts (notes_012 M1, notes_013 B1/B2/C)

- **Recency-correct tone conflicts (C):** `_on_tone_change` previously
  re-validated the three tone menus in fixed left-to-right slot order on
  every change, so a conflict was always resolved in favour of whichever
  slot happened to sit further right — not the tone the user had just
  clicked, which could silently revert if it lost to an untouched slot.
  Each menu's `command` now passes its own slot index; `_on_tone_change`
  moves that slot to the end of the list before calling `validate_tones`,
  so the choice just made always wins, regardless of position. An advisory
  now names any tone dropped this way, rather than letting it vanish
  silently.
- **Presets now persist tones (B1):** `normalise_conversation_preset`
  gained a `"tones"` key (existing presets without one default to `[]` on
  load); `_save_conversation_preset_dialog` snapshots the toolbar's live
  tones, and `_apply_conversation_preset` restores them.
- **Transactional preset save/delete (B2, M1's P1 reliability gap):**
  `_save_conversation_preset_dialog`/`_delete_conversation_preset`
  previously mutated the live config, then tried to save and silently
  swallowed a `ConfigError` (an `OSError` was not even caught) — the UI
  could claim a preset existed when it was never written. Both now go
  through a shared `_commit_presets()` that saves first and only updates
  in-memory state on success, showing a clear error and changing nothing
  otherwise. Saving also now refuses a duplicate name (casefold) or saving
  past the 12-entry cap outright, rather than letting Delete-by-name
  become ambiguous or the cap silently discard the newest preset.
  `normalise_conversation_presets` additionally repairs a duplicate
  display name deterministically (a "(2)", "(3)", ... suffix) for the
  defensive load-time case of a hand-edited file.
- **M1, Settings could revert a preset saved while it was open:**
  `SettingsDialog` takes a shallow copy of `config_data` at construction;
  saving a preset from the main window afterwards updates the *live*
  config but not that snapshot, so a subsequent Settings Save silently
  reverted the preset list. Fixed by having `SettingsDialog._save`
  re-read the live preset list from `master.config_data` immediately
  before its own save, the same pattern already used for the toolbar's
  five other "wins at save" fields.
- 8 new unit tests (preset tone validation/storage, duplicate-name and
  placeholder-name repair) plus a live-code verification script covering
  the recency fix in both directions, a preset's tones round-tripping
  through save/apply, duplicate-name and cap refusal, a failed save
  leaving memory unchanged, and the exact M1 reproduction (Settings held
  open across a preset save) now surviving. Full suite: 225 tests pass.

## v1.25 — Speak/TTS and correction-flow reliability (notes_012 M2, M3, M4, M6, M7, M12)

- **M2/M12, Speak could invalidate a previous in-flight request without
  actually starting a new one:** `_speak` bumped `_speech_request_id`
  *before* the missing-API-key and privacy-decline early returns. Clicking
  Speak with no key configured, or declining the privacy notice, still
  invalidated whatever TTS request was already playing, silently dropping
  its audio on delivery. The bump now happens only once Speak is actually
  going ahead.
- **M3, correction preservation notes were shown then immediately hidden:**
  `_deliver_correction` displayed `notes` (e.g. "kept 'Alex' as-is") on the
  advisory strip, then called `_translate()`, whose very next line hides
  the advisory unconditionally — so a failed keep-as-is round-trip during
  Correct English was never actually seen; auto-translate proceeded
  silently. Fixed by having `_translate()` capture (and clear)
  `self._pending_correction_notes` as the very first thing it does,
  regardless of which path it takes, and carrying that snapshot through to
  `_deliver`, which now merges it into the final result's advisory instead
  of the notes being overwritten. Capturing it per-call (not read later
  from shared state) also means a later, unrelated translate can never
  pick up notes left over from an earlier one that got superseded.
- **M4, a failed correction left "Use as input" dead:** `_correct_then_translate`
  disables `use_as_input_btn` alongside three other buttons; `_deliver_correction`'s
  error path restored the other three but not this one, matching `_deliver`'s
  own equivalent line, so a failed correction left the button disabled
  until the next successful translate even though the previous result was
  still on screen. Fixed to match `_deliver`.
- **M6, a locked TTS temp file was forgotten, not retried:** `_cleanup_tts_file`
  cleared `self._tts_temp_path` even when `os.remove` failed (Windows can
  briefly hold the handle right after `SND_PURGE`), leaking the WAV file
  in `%TEMP%` permanently rather than trying again on the next Speak/Clear/close.
  Now the path is only cleared on a successful remove.
- **M7, a new result didn't stop the previous one's audio:** Speaking an
  alternative, then starting a new translation, left the old audio playing
  over the new result. `_render_result` now calls `_stop_speech()` first,
  matching what `_clear_results` already did for the Clear path.
- Verified live against the real `PlumeApp` class (isolated temp config
  dir; `correct_english`/`translate` mocked to avoid network calls;
  background workers run synchronously via a fake `Thread` to sidestep
  this Tcl/Tk build's "main thread not in main loop" restriction on
  cross-thread Tk calls when no `mainloop()` is running — a scripted-test
  artefact, not a change to production threading). Full suite: 225 tests
  pass (no new pure-function unit tests this version; these are all GUI
  lifecycle fixes, covered by the live-code script instead).

## v1.26 — Clipboard ownership-safe rewrite (notes_012 M13, notes_013 D2)

- **M13, `OpenClipboard(None)`, an unchecked `GlobalLock`, and no
  `GlobalFree` on failure:** `copy_html_to_windows_clipboard` established
  no clipboard owner (Microsoft's own `SetClipboardData` documentation
  names this a failure case), never checked whether `GlobalLock`'s
  returned pointer was NULL before an unconditional `ctypes.memmove` into
  it (a real, if narrow, process-crash risk that no Python `except` clause
  can catch), and never freed a `GlobalAlloc` handle when
  `SetClipboardData` failed, leaking it. Rewritten: the function now
  requires a real window handle (refuses outright without one, rather than
  falling back to `None`), allocates and locks both payloads *before*
  `EmptyClipboard` runs (so a preparation failure never leaves the
  clipboard emptied with nothing published), checks every allocation,
  lock and transfer, and frees only the handles whose ownership did not
  actually transfer to the system. `_copy_current_result_as_html` now
  passes `self.winfo_id()` as that handle.
- 3 new unit tests (missing/zero handle refused, embedded NUL in the
  plain-text fallback refused). This is native ctypes code with no Python
  exception path for a genuine access violation, so — per the existing
  clipboard risk record — it was also verified against the real Windows
  clipboard: writing through the actual `PlumeApp._copy_current_result_as_html`
  call path (real `winfo_id()`), then reading both `HTML Format` and
  plain text back independently via .NET's `System.Windows.Forms.Clipboard`
  from a separate PowerShell process while the writing process stayed
  alive. Both formats round-tripped exactly, including accented and
  HTML-escaped characters. (An initial attempt that destroyed the Tk
  window immediately after copying showed the plain-text format missing
  on readback; keeping the window alive for even a moment afterward — the
  same as real usage, where the app stays open — showed both formats
  present via both a same-process ctypes readback and the independent
  .NET readback, so this was a test-script artefact, not an application
  bug.) Full suite: 227 tests pass.

## v1.27 — Backend resilience hardening (notes_012 M8, notes_013 E)

- **M8, an HTTPError's response body was never read or closed before a
  retry:** `_http_post_json`'s `HTTPError` branch inspected `Retry-After`
  and either slept-and-retried or raised, but never consumed the error
  response's body — urllib documents this as a potential socket leak, and
  four attempts under a busy session is enough to matter. Now `exc.read()`/
  `exc.close()` run unconditionally before either path.
- **Retry-After was capped/shortened rather than honoured, and only
  parsed as a plain integer:** a server-requested wait longer than
  `HTTP_BACKOFF_CAP` was silently shortened to 8 seconds — defeating the
  point of the header — and an HTTP-date value (RFC 9110's other
  permitted format) was silently ignored, falling back to exponential
  backoff. `_backoff_delay` now parses both numeric-seconds and HTTP-date
  forms and returns a Retry-After value as-is, uncapped; `_http_post_json`
  separately tracks accumulated wait against a new `max_retry_wait`
  budget (30s default) and gives up with a clear message if a single
  server-requested wait would blow it, rather than silently honouring an
  arbitrarily long pause or shortening a genuine minimum.
- **Jitter was added on top of the cap, not inside it:** the exponential
  path's `delay + jitter` could exceed `HTTP_BACKOFF_CAP` by up to 25%.
  Now jitter is applied inside the ceiling (a random point in its top
  25%), so the exponential path never exceeds `HTTP_BACKOFF_CAP`.
- **`IncompleteRead` was not treated as transient:** unlike
  `RemoteDisconnected` (already an `OSError` subclass, already retried),
  `http.client.IncompleteRead` descends from `HTTPException` and fell
  through to an unretried "unexpected error" instead of the existing
  transient-failure retry path. Added to the retried set explicitly.
- **Claude's 529 (overloaded) is now retryable, opted in only at the
  Claude call site:** a new `retryable_codes` parameter on
  `_http_post_json` (defaulting to the existing `HTTP_RETRYABLE_CODES`)
  lets `call_anthropic` add 529 without assuming every backend this app
  talks to shares that specific status code's meaning.
- Per-request cancellation (interrupting an in-progress backoff wait when
  Clear/close supersedes the request) was considered but left out of this
  version: the existing stale-request-id guard already prevents a
  superseded result from ever reaching the UI, so cancellation would only
  shave a worst-case few seconds off an already-doomed background wait,
  at the cost of threading a new parameter through `translate()`/
  `correct_english()`/`call_anthropic()`/`call_ollama()`/`_http_post_json`
  — real architectural churn for a latency nicety, not a correctness fix.
- 9 tests rewritten or added (HTTP-date parsing, jitter-never-exceeds-cap,
  wait-budget refusal, HTTPError body closed before retry, IncompleteRead
  retried, 529 excluded by default but retryable when opted in). The two
  changed-behaviour tests (Retry-After capping, exponential jitter shape)
  were rewritten to assert the new documented behaviour rather than
  patched to keep the old assertions passing. Verified against the real
  Claude API: one live translation completed correctly through the
  rewritten transport. Full suite: 234 tests pass.

## v1.28 — File import: Open file, text/Markdown only (notes_013 A2/A3, scoped down)

- **Open file…**, on the left pane's second button row (left-aligned
  beside Correct English/Translate, rather than a fifth button on the
  already-tight Paste/Clear/Copy source/Reply row): imports a `.txt` or
  `.md` file into the input box. Read off the UI thread, bounded to 2 MiB
  raw, accepting UTF-8 (including a BOM) or BOM-marked UTF-16 and refusing
  any other encoding rather than guessing one; content is never truncated
  to fit the configured character limit — an over-limit file is refused
  with the same message over-limit typed input already gets. If the input
  box isn't empty, asks before replacing it, and re-checks afterwards
  since the confirmation dialog runs its own nested event loop. An import
  whose result arrives after the input has changed is discarded with an
  advisory rather than silently overwriting newer typing.
- **Deliberately narrower than notes_013's full proposal, on purpose:**
  no native Explorer drag-and-drop (`WindowsFileDrop`/A1) — this app's
  Tcl/Tk build has a demonstrated, unresolved interpreter-crash risk under
  real cross-process `WM_DROPFILES` delivery (see v1.18), and the specific
  pointer/argtypes fixes notes_013 proposed do not address that root
  cause, per the standing native-integration risk record — and no `.docx`
  import path, kept out of scope so this version adds no new dependency.
  Revisiting drag-and-drop would need either genuine Tcl/Tk-on-Windows
  notifier expertise or a maintained library (`tkinterdnd2`) rather than
  another hand-rolled `ctypes` attempt.
- 11 new unit tests for `read_import_text` (UTF-8/BOM/UTF-16, unsupported
  extension, oversized file, over-character-limit refusal without
  truncation, CRLF normalisation, embedded NUL, invalid encoding, missing
  file, a directory given instead of a file). Verified live against the
  real `PlumeApp` class: import into an empty box (no prompt), import
  into a non-empty box (prompt shown, both accept and decline paths),
  an import superseded by a meanwhile-changed input (discarded, not
  applied), an unsupported extension (clear advisory, no crash), and the
  concurrent-import guard — plus a screenshot of the real running app
  confirming the new button doesn't crowd the layout (the exact class of
  regression a past version introduced and fixed). Full suite: 246 tests
  pass.

## v1.29 — Mode/Strength/Role writing profile (notes_013 B3)

- **An optional second preset phase**, layered on top of the existing
  Tones/Situation/conversation-preset system rather than replacing any of
  it: `WRITING_MODES` (Translate; Correct English then translate),
  `WRITING_STRENGTHS` (Source-led; Light; Balanced), `WRITING_ROLES`
  (General; Friend; Colleague; Customer). `normalise_writing_profile()`
  coerces each to one of a small fixed set — never an arbitrary
  system-prompt template, claimed identity or authority — matching how
  every other conversation-preset field is hardened.
- **One compact row**, not the three-row stacked block notes_013's own
  mockup showed: Mode/Strength/Role sit beneath Tones as label+dropdown
  pairs in a single horizontal row, matching the existing Tones/Situation
  rows' own layout rather than adding real vertical height to an already
  tight pane. Verified at both the default 1180×760 and the documented
  920×600 minimum: dropdown widths were tuned (and made to share extra
  space via `grid_columnconfigure(weight=1)`) so nothing is cut off at
  the minimum size — long values (e.g. "Correct English then translate")
  clip to fit the button, the same accepted tradeoff the Presets menu
  already makes for a long preset name.
- **Strength/Role only ever add a background prompt clause** — via
  `build_writing_profile_instruction()`, appended to the system prompt
  after the tone clause — **and only once Strength is raised above
  Source-led** (the default): selecting a Role alone changes nothing.
  The clause explicitly forbids assuming a relationship, identity,
  expertise or authority the source text doesn't itself establish, and
  states the source wins any conflict, mirroring the tone clause's own
  non-authoritative framing.
- **Mode changes which pipeline Translate/Ctrl+Enter dispatches to, but
  only on an explicit click:** `_run_selected_mode()` (the new command
  for both) runs `_correct_then_translate()` if Mode is set to correction,
  otherwise `_translate()` — the default Mode is always Translate, so
  behaviour is unchanged unless a user (or a preset) deliberately sets
  Mode to correction. Selecting a Mode, or applying a preset that
  restores one, never itself starts a request — only this explicit
  dispatch does. The separate, pre-existing Correct English button is
  unchanged: it always corrects, regardless of Mode.
- **Presets now carry a `"writing"` key** (`normalise_conversation_preset`),
  saved from and restored to the three live dropdowns exactly like tones
  already are. Reopening a history entry resets the writing profile to
  defaults, the same reasoning already applied to tones and finishing
  touches: history predates this version and carries no such data.
- 15 new unit tests (profile validation/defaults, prompt clause
  presence/absence, preset round-trip) plus a live-code verification
  script covering dispatch (both Modes), a preset with Mode set to
  correction never itself submitting, Reopen's reset, and `_translate()`'s
  snapshot carrying the live profile — plus screenshots of the real
  running app at both window sizes. Full suite: 259 tests pass.

## v1.30 — Compact layout tightening; a wider documented minimum

- **Prompted by a real, pre-existing bug found while checking the
  request:** the toolbar's second row (French form/Me/You/Presets/Save
  preset…/Delete) already didn't fit at the documented 920×600 minimum
  — Save preset… and Delete were rendered entirely off-screen, invisible
  and unreachable, not merely clipped. This had been true since Save/
  Delete were added in v1.19 and was never caught because minimum-size
  testing wasn't part of this project's verification habit until v1.29.
- **Padding tightened throughout the toolbar and both panes:** inter-
  element gaps (label→control, button→button) were reduced app-wide —
  toolbar rows, the left pane's button rows, and the right pane's
  Favourite/Export/Copy as HTML/Export diff… row — without shrinking any
  dropdown below what its actual field *values* need (only static
  button labels and already-accepted-clip fields like preset names
  were touched), so no real data becomes unreadable.
- **The documented minimum widened from 920×600 to 1000×600**, and the
  Strength/Role dropdowns (v1.29) were widened slightly (90/90 → 105/100)
  once the extra room existed — at 1000×600 every control, including
  "Source-led" and "General" in the writing-profile row, now displays
  its full text with no clipping at all, not just "nothing is missing."
  The 920×600 case this replaces was usable but visually cramped, per
  direct user feedback after reviewing screenshots at both sizes.
- Verified with real screenshots at both 1000×600 and the default
  1180×760 (a `ShowWindow` minimize/restore cycle was needed between
  resize and capture in this environment — a plain resize occasionally
  left a stale partial repaint in the screenshot, a capture artefact
  distinct from anything the app itself does wrong). Full suite: 259
  tests pass (no logic changed, layout-only version).

## v1.31 — MMORPG chat picker, glossed slang, Translation Glossary

- **MMORPG chat**, a third append-tag picker next to Emotes and Casual
  sign-off, for online-gaming chat: `dispo`, `rez`, `bj`, `osef`, `oklm`,
  `aïe`. Sourced from a user-supplied MMORPG slang reference and curated
  to the same bar v1.14 already applied to Casual sign-off: only terms
  that work as a general appendable tag regardless of the rest of the
  sentence. Excluded on that basis: domain nouns describing gear/content
  rather than a mood tag (`le stuff`, `l'aggro`, `les trash`, `HL`, `dj`,
  `voc`, `abo`, `kikimeter`) and callouts that are a complete standalone
  message or a comment on someone *else's* play rather than an appended
  flavour word (`bg`, `rede`, `ouai`/`wé`). `compose_finishing_touch` now
  joins all three pickers; existing two-argument callers are unaffected
  (the third parameter defaults to `None`).
- **Bracketed glosses on Casual sign-off and MMORPG chat:** each option
  now shows a short English meaning in the dropdown, e.g. "tkt (don't
  worry)" or "rez (resurrect me)". Only the raw term before the bracket
  is ever appended to the copied/spoken text or reaches the model — the
  gloss is a same-session, English-only reading aid
  (`casual_signoff_display`/`mmorpg_term_display` for the label,
  `..._raw_value` to recover the term).
- **Translation Glossary**, a new Settings feature distinct from Keep-as-is
  (v1.10): a Keep-as-is term is never translated at all (a name, a
  handle), whereas a glossary term should still be translated, just
  *consistently* — e.g. always "délai" for "deadline" rather than
  whichever equally valid alternative the model picks each time. Up to 20
  `term = translation` pairs (mirroring Keep-as-is's own textbox
  convention and 20-entry/40-character limits), normalised by
  `normalise_glossary_entries` (accepts the persisted list-of-dicts shape
  or the Settings textbox's line format) and turned into a background-only
  prompt clause by `build_glossary_instruction` — appended to the system
  prompt after the writing-profile clause, explicitly non-authoritative:
  it must not change the JSON shape, and the source text's own meaning
  always wins. New `translation_glossary` config key, present in
  `DEFAULT_CONFIG` and `plume_config.example.json`.
- 33 new unit tests (gloss display/round-trip for both pickers, the
  three-way `compose_finishing_touch`, glossary normalisation from both
  input shapes, prompt-clause presence/absence, config load-time
  coercion). Verified live against the real `PlumeApp`/`SettingsDialog`
  classes: the composed touch uses only raw terms even when the
  dropdown shows a gloss, Clear/Reopen reset both pickers, a glossary
  saved through Settings persists and reopens correctly, and
  `translate()` threads the live glossary into the prompt — plus
  screenshots of the real running app (main window and the scrolled
  Settings dialog). Full suite: 289 tests pass.

## v1.32 — Crash-safe file intake: argv, Send to, paste-as-path (notes_015 2.A)

- **Three routes into the existing v1.28 `read_import_text()` reader,
  none of them native drag-and-drop:** the v1.18 record stands — this
  Tcl/Tk build has a demonstrated, unresolved `WM_DROPFILES` crash risk,
  so a conversation helper still cannot catch an Explorer drop directly.
  Every other Windows 11 path that does not subclass a window procedure
  remains open:
  1. **Command line**, `--import "path"` or a bare `.txt`/`.md` argument
     (so a Send to shortcut can pass `%1` with no flag).
     `parse_import_path()` scans all of `argv` and returns the first
     candidate plus whether a second one was ignored, so multiple files
     are never silently merged — one advisory names the situation instead.
     Read on `PlumeApp.__init__`, after the tray starts, via the existing
     `_begin_file_import()` worker; an empty window always accepts it
     with no "replace?" prompt, same as importing into an empty box today.
  2. **Explorer "Send to Plume"**, a new disabled-by-default Settings
     checkbox next to the tray/autostart group (independent of
     `TRAY_AVAILABLE` — it is a plain `.cmd` file, not a pystray feature).
     `set_send_to_shortcut()` writes/removes
     `%APPDATA%\Microsoft\Windows\SendTo\Plume.cmd`, one line reusing
     `autostart_command()` minus `--start-minimised` (a file the user is
     actively sending should open a visible window) plus
     `--import "%~1"`. No `.lnk`, no `pywin32`, no COM.
  3. **Paste-as-path.** `looks_like_importable_path()` recognises a
     clipboard value that is one quoted/raw existing `.txt`/`.md` path;
     `_paste()` now offers "Open this file as source text?" before
     falling back to today's behaviour of inserting the clipboard text
     verbatim.
  All three still go through the unmodified v1.28 pipeline: bounded to
  2 MiB, UTF-8/UTF-16 only, never truncated, never auto-translated, and
  a stale-input race still discards a superseded import with an advisory.
- New `send_to_shortcut` config key (`DEFAULT_CONFIG` and
  `plume_config.example.json`), coerced to `bool` on load like every
  other toggle.
- 24 new unit tests (`parse_import_path` against `--import`, a bare
  path, other flags, no candidate, an ignored extra candidate, and a
  dangling `--import` with no value; `looks_like_importable_path`
  against a real quoted path, prose, a missing file and a wrong
  extension; `send_to_cmd_path`/`set_send_to_shortcut` create/remove
  against a temporary `APPDATA`; config coercion). Verified live against
  the real `PlumeApp`: `--import` against an isolated copy of the app
  loads an empty box with no prompt; pasting a quoted path to an
  existing file shows the Open file dialog, then (since the box was
  non-empty for that run) the existing v1.28 replace-confirmation, and
  the file's text lands correctly; the Settings checkbox renders
  correctly-placed and enabled in the scrolled dialog. The real
  `%APPDATA%\...\SendTo` folder was deliberately left untouched by this
  manual pass — that behaviour is covered by the mocked-`APPDATA` unit
  tests instead. Full suite: 307 tests pass.

## v1.33 — Correctness hardening: raw-value boundary, tone validator (notes_014 B, E)

- **Strict raw-value boundary for Casual sign-off and MMORPG chat.**
  `casual_signoff_raw_value()`/`mmorpg_term_raw_value()` previously fell
  back to returning an unrecognised input unchanged; a stale label left
  over from a since-changed catalogue could then reach the copied/spoken
  text, English gloss and all. Both now resolve anything that is not a
  currently-known display label or raw term — including a non-string —
  to that picker's `None` sentinel instead. Not a reproduced user-facing
  bug (the dropdowns only ever set a value they generated themselves),
  but a real data-boundary tightening ahead of any future path that could
  set these some other way.
- **`validate_tones()` no longer crashes on a malformed entry.** A
  hand-edited `plume_config.json` conversation preset whose `"tones"`
  list held a stray list or dict — `{"tones": ["Warm", ["nested"]]}` —
  raised an uncaught `TypeError` from the set-membership check
  (`item not in allowed`), crashing config load and the app with it. The
  loop now checks `isinstance(item, str)` first, so a malformed entry is
  dropped like any other unknown value rather than raising. Order/cap/
  conflict-resolution semantics are otherwise unchanged from v1.24.
- **Tone instruction now also guards against uninvited embellishment:**
  appended to the existing background-only register clause — "Preserve
  negation, quantities, attribution, uncertainty and obligations. Do not
  introduce reassurance, gratitude, apologies, availability or agreement
  that the source does not express. Source slang is content to translate
  faithfully, not permission to invent further slang.", applied to the
  main translation and all five alternatives alike. This is a prompt-text
  change, not a deterministic one: it constrains generation but cannot
  prove the absence of hallucination, and — per notes_014's own
  acceptance criteria — still wants a human bilingual calibration pass
  (negation, quantities, humour, uncertain deadlines) independently of
  this session's syntax/unit verification.
- 6 new/changed unit tests (unrecognised label, non-string input and a
  bare raw term for the raw-value boundary on both pickers; a stray
  list/dict tone member no longer raising; the new instruction clause's
  presence). One pre-existing test that asserted the old pass-through
  behaviour was updated to assert the new sentinel-fallback contract
  instead. No live screenshot pass for this version: both fixes tighten
  an internal fallback path the real dropdowns cannot reach (they only
  ever set a value they generated themselves), so a click-through would
  exercise unchanged UI rather than the actual change — the existing
  round-trip tests (`test_raw_value_reverses_display` for both pickers)
  already cover the path real clicks do take. Full suite: 312 tests pass.

## v1.34 — French slang reference: search, insert, local draft (notes_014 A/C/D)

- **A new "French slang…" button** beside the "Message to translate"
  heading (the heading is now its own two-column row so the button
  doesn't collide with the label — verified at the documented 1000x600
  minimum) opens a non-modal `SlangReferenceDialog`. Independent of the
  finishing-touch pickers (v1.2/v1.14/v1.31): these are full vocabulary/
  phrase entries, not every one works as an appended sentence suffix, so
  they are inserted deliberately rather than auto-appended.
- **`SLANG_CATALOGUE`**: 18 candidate records (id, raw term, expansion,
  English meaning, category, register, use note) across Texting,
  Greetings, Reactions, Relationships, Vocabulary and Phrases — the
  notes_014 first batch, editorially reviewed against Larousse for the
  two entries most likely to be misread: `bsr`/bonsoir is glossed "good
  evening" rather than a bare "goodbye" (it greets or parts depending on
  context), and `bof` is glossed "so-so / not especially" with a note
  that it conveys indifference/uncertainty, not a blanket "terrible".
  Pronunciation is deliberately omitted this release, per notes_014's
  own caution against the source attachment's unverified spellings.
  The wider 195-row attachment remains an editorial backlog, added in
  independently reviewed batches later — this version does not change
  the UI to accommodate it.
- **Search** (`slang_search_key`/`search_slang`): accent-, case- and
  curly-apostrophe-insensitive, matching the raw term, its expansion or
  the English meaning; an optional category filter; capped at 30
  rendered rows with an advisory to refine a broad query, since roughly
  200 records is comfortably a linear scan, not a case for a search
  index or worker thread.
- **Insert in source** (`_insert_slang_source`, `slang_insertion`): inserts
  the raw term at the input box's caret, adding a space only at a real
  word boundary (never rewriting punctuation or an existing selection),
  bounded by the existing character limit. Refused only for an English
  source direction (French text would land where the model expects
  English) — otherwise available regardless of an in-flight request,
  matching how typing directly into the box already behaves. Offsets use
  Python's own character count rather than Tcl's UTF-16 unit count, so
  an emoji before the caret cannot shift the insertion point.
- **Copy term** copies only the raw French, never the English gloss.
- **A separate local draft**, seeded once from the current French result
  plus its finishing touch when one exists (never taking English output
  and presenting it as French), with its own "Insert in draft", reusing
  `text_metrics`/`format_metrics_label` for its own reading-time label.
  "Copy draft" and "Copy draft as HTML" (the existing checked CF_HTML
  transfer with a plain-text fallback) operate on this draft alone — the
  main translation result, `_current_result` and config are never
  touched by anything in this dialog, and a new translation, Clear or
  Reopen does not overwrite an already-open draft.
- One small catalogue-data correction alongside: `bjr`/`bsr`'s register
  was normalised from a mismatched "Texting" to "Informal", consistent
  with the other two SMS-greeting entries (`slt`, `a+`) in the same
  category — a data-consistency fix, not a translation-content change.
- 26 new unit tests: catalogue shape/uniqueness, search (accent/case/
  apostrophe folding, category filter, unknown category, multi-word AND
  match), insertion (word-boundary spacing, an emoji before the offset,
  bounds/empty-term/null-byte/limit rejection). Verified live against
  the real `PlumeApp` at both the default and documented-minimum window
  sizes (no layout collision), then end to end: searching "bof" narrows
  to the one matching record; Insert in draft updates the draft and its
  metrics; Copy draft and Copy draft as HTML both land the correct
  plain/CF_HTML clipboard content; Insert in source lands the term in
  the real input box; switching to English → French and retrying Insert
  in source is correctly refused with an on-screen advisory rather than
  silently inserting nothing. Full suite: 338 tests pass.

## v1.35 — User Situation catalogue (notes_015 2.B)

- **User-defined Situation shortcuts**, alongside the five hard-coded
  presets: a "Save…"/"Delete" pair next to the existing Situation preset
  menu. Save stores the current Situation text as a reusable local-only
  entry (`user_situation_presets` in `plume_config.json`, up to 12
  entries, 80 characters each); Delete removes whichever one is
  currently selected in the menu. Closes the one inconsistency users
  would actually notice: conversation presets (v1.19) are already
  user-defined, but Situation itself was still hard-coded five options.
- **`normalise_user_situations`**: de-duplicated (casefold), length- and
  count-bounded, and a user entry that casefold-matches a built-in
  preset name (or the menu's own placeholder/heading text) is dropped on
  load — so a saved situation can never shadow a built-in or produce two
  identically-labelled menu rows. **`situation_menu_values`** builds the
  full menu: placeholder, the five built-ins, then — only when the user
  has saved at least one — a non-selectable "(My situations)" heading
  (CTkOptionMenu has no real separator; `_apply_situation_preset` treats
  a click on it as a no-op, the same as the placeholder) followed by the
  user's own entries.
- **Save is refused outright**, never silently discarded, on a name
  already used by a built-in preset, a duplicate of an existing saved
  entry, an oversized label, or a full list — matching the existing
  conversation-preset Save's own convention (v1.24). **Delete** likewise
  refuses with an explanation if the menu isn't currently showing one of
  the user's own entries, rather than deleting the wrong thing or doing
  nothing unexplained. Both use the same transactional
  save-then-publish pattern as conversation presets: `save_config()` is
  attempted first, and `config_data`/the menu are only updated on
  success.
- No prompt change: selecting a saved situation still just writes its
  text into `situation_entry`, exactly like a built-in preset already
  does.
- 14 new unit tests (normalisation: plain list and newline-separated
  string input, whitespace/blank handling, built-in/placeholder/heading
  reservation, case-insensitive de-duplication, oversized-entry and
  count-cap rejection, non-list/non-string input; menu construction:
  placeholder-then-built-ins ordering, heading omitted when empty,
  heading-and-entries appended when present; config load-time
  coercion). Verified live against the real `PlumeApp`: Save persists
  the entry to the actual config file and the menu updates to show it
  selected; reopening the menu shows the correct placeholder/built-ins/
  heading/user-entry order; selecting the saved entry fills Situation;
  Delete removes it from the config file and resets the menu; Delete
  with nothing valid selected shows the refusal advisory rather than
  deleting anything. Layout verified clean at both the default and
  documented 1000x600 minimum window sizes. Full suite: 352 tests pass.

## v1.36 — Sticky register defaults (notes_015 2.C)

- **A "Remember tones and profile" button**, its own row beneath Tones
  and Writing profile, saves the three live tone slots and the live
  Mode/Strength/Role as what a future launch restores
  (`default_tones`/`default_writing_profile` in `plume_config.json`).
  Restored automatically in `PlumeApp.__init__` once the widgets exist,
  so a session spent as Warm+Precise+Colleague no longer resets to
  None/Translate/Source-led/General every time the app reopens.
  MAX_TONES stays 3; the conflict-resolution/newest-slot-wins UI
  (v1.20/v1.24) is unchanged — this only changes what the menus start
  at, never how they behave once open.
- **Not tied to a fixed row placement by accident:** the button was
  first tried on the Tones row itself and, separately, appended to the
  Writing profile row — both were rejected after a live screenshot at
  the documented 1000x600 minimum: neither row has fixed-width slack to
  absorb another button, and Writing profile's three dropdowns visibly
  truncated ("Source-led" -> "Sourc", "General" -> "Gen") once forced to
  share space with it. A dedicated row avoids shrinking either.
- **Settings Save also carries these forward automatically**, extending
  the existing "toolbar is the single source of truth" rule already
  applied to direction/French form/gender/backend (same
  `hasattr(master, ...)` toolbar-wins block) — so closing Settings after
  a deliberate tone change persists it exactly like the five fields
  already did, without requiring a separate Remember click.
- **Applying a conversation preset still overrides these menus**; it
  does not rewrite the remembered defaults unless the user then clicks
  Remember (or saves Settings) — a preset restores a *named* snapshot,
  the defaults are "whatever I was last using".
- No prompt change: this only changes what the toolbar/menus are
  pre-filled with at launch.
- 4 new unit tests (config load-time coercion: a malformed
  `default_tones` entry still validates down to only the compatible
  members; `default_writing_profile` coercion and its Source-led/General
  fallback). Verified live against the real `PlumeApp`: setting Warm +
  Balanced and clicking Remember writes both keys to the real config
  file with the advisory shown; killing and relaunching the app restores
  Warm/Balanced automatically with Mode/Role left at their defaults;
  layout re-verified clean at the documented 1000x600 minimum after the
  row was moved. Full suite: 356 tests pass.

## v1.37 — Result export polish: metrics, copy-five, French typography (notes_015 2.D)

- **Result-pane metrics**, a small label under the primary translation
  showing the same reading-time estimate the input pane already has
  (`text_metrics`/`format_metrics_label` reused, not recalibrated), using
  the French words-per-minute constant when the working result's target
  is French. Refreshed by `_refresh_primary_display` — a new result,
  "Use this", or a finishing-touch change all keep it describing exactly
  what Copy main translation would copy.
- **"Copy five"** and **"Copy five as HTML"**, above the alternatives
  list: `format_five_alternatives()` gives numbered plain text of the
  five translation fields only — no meaning checks, no finishing touch —
  distinct from the existing study-sheet/diff export, which keeps both.
  The HTML sibling reuses the existing checked CF_HTML transfer with a
  plain-text fallback, the same as Copy as HTML on the main card.
- **Optional French typography, copy-time only, off by default**
  (`apply_french_typography()`, a new Settings checkbox). When the
  working result's target is French *and* the checkbox is on, Copy main
  translation / Copy five / Copy (five) as HTML run it after the
  finishing touch: a narrow no-break space before `; : ! ?`, `"..."` ->
  the single-character ellipsis, and short straight-quoted phrases ->
  guillemets. Idempotent by construction. Never sent to the model, never
  written into `_current_main`, never applied to the exported study-sheet/
  diff, and Speak still reads the raw translation — verified live that
  the on-screen card keeps its original straight quotes/"..." after a
  typographied copy, so nothing is silently mutated in place.
- 15 new unit tests (typography: adds a narrow space with and without an
  existing one, ellipsis, guillemets, idempotence, empty/non-string
  input, unrelated text untouched; five-alternatives: numbering, meaning
  checks omitted, blank entries skipped, empty/missing variations;
  config load-time bool coercion). Verified live end-to-end against the
  real `PlumeApp` with a scripted result (no live API call): the metrics
  label and both Copy-five buttons appear correctly enabled; Copy main
  translation with the Settings checkbox off copies the raw text
  unchanged; switching the checkbox on through the real Settings dialog
  and re-copying produces guillemets/ellipsis/narrow spaces in the real
  Windows clipboard (plain and CF_HTML) while the on-screen card stays
  untouched; layout re-verified clean at the documented 1000x600
  minimum. Full suite: 371 tests pass.

## v1.38 — Transport hardening, cooperative cancel, Ollama fallback (notes_014 G, notes_015 2.E)

- **Bounded response reads.** `_http_post_json` no longer reads a
  successful response fully into memory: capped at
  `HTTP_MAX_RESPONSE_BYTES` (2 MiB), raising a clear `BackendError`
  rather than accepting an unbounded body from a malfunctioning backend.
  An `HTTPError`'s body is no longer drained before `close()` either —
  retrying must not wait for a potentially unbounded error body, and
  `close()` alone already releases the connection.
- **SSL/TLS failures are never retried.** A bare `ssl.SSLError`, or a
  `URLError` wrapping one, now gets its own explicit handler with a
  dedicated message ("The secure connection could not be verified.")
  instead of falling through to the generic transient-`OSError` retry
  path (`ssl.SSLError` *is* an `OSError` subclass, so it was silently
  retried before this version) — retrying a certificate failure will not
  fix it and could mask a genuine MITM condition.
- **The generic network-failure message no longer echoes the raw
  exception reason**, matching the existing `HTTPError` path, which
  never displayed raw exception detail either.
- **Cooperative HTTP cancel.** Clear, closing the window, and the start
  of a newer `_translate`/`_correct_then_translate` now call
  `_new_http_cancel()`, which sets the previous request's
  `threading.Event` and installs a fresh one. `_http_post_json` (a new
  `cancel_event` parameter) checks it before each attempt, before
  sleeping in backoff, and once immediately after a request completes —
  so an abandoned request stops retrying and is not delivered once
  superseded. Honest limitation, stated in code and here: urllib cannot
  abort a blocked read portably without closing the socket, so a request
  already inside `urlopen()` may still finish; it simply will not be
  retried or delivered. Threaded through via `config_snapshot["_cancel_event"]`
  (already a private per-request copy) rather than a new parameter on
  every function in the call chain. ElevenLabs/Speak is explicitly out of
  scope this version (notes_015's own deferral) — its own direct
  `urlopen` call is untouched.
- **Opt-in one-shot local Ollama fallback**, a new Settings checkbox ("If
  Claude is unavailable, retry once with local Ollama",
  `fallback_to_ollama`, off by default). After Claude exhausts retries
  with a genuine `BackendError`, `run_backend` tries Ollama once — only
  when the checkbox is on, a non-blank `ollama_model` is configured, and
  the failure was not itself a cancellation. Never the other way round
  (Ollama is never retried against Claude). Marks
  `config_snapshot["_used_fallback"]` rather than changing
  `run_backend`'s return type; `translate()` appends a single, honest
  notes[] advisory ("Claude was unavailable; translated with local
  Ollama.") when that flag is set.
- 18 new unit tests (response-size bounding, HTTPError body never read
  before close, bare/wrapped SSL errors not retried, the raw URLError
  reason omitted from the message, cancellation before an attempt/during
  backoff/after a completed read, an uncancelled request still
  delivering normally, the fallback decision matrix — opted in, no
  model configured, a cancelled failure, Ollama never falling back to
  Claude — and translate()'s conditional advisory). Verified live: the
  real Settings checkbox renders correctly and persists
  `fallback_to_ollama` to the actual config file; a scripted check
  against the real `PlumeApp` (no live API calls) confirmed
  `_new_http_cancel()` genuinely invalidates the previous event object
  and that `_clear()`/`_translate()`/`_on_close_destroy()` all call it at
  the right point. Not exercised: cancelling a request against a real,
  slow-responding backend end-to-end — that would need a live Claude/
  Ollama endpoint deliberately made to hang, which this session did not
  have available; the mechanism itself is unit-tested directly instead.
  Full suite: 389 tests pass.

## v1.39 — History search, tray "Show and paste clipboard" (notes_015 2.F)

- **History search**, a new entry in the History window's header
  (between the "History" heading and "Favourites only"): casefold
  substring matching over source text, main translation and situation —
  not the alternatives or notes, the fields a user is actually likely to
  remember a past conversation by. Favourites-only narrows first, then
  search; an empty query shows everything, matching "today's list".
  `filter_history_entries`/`history_search_blob` are pure, reused as-is
  by `HistoryDialog._visible_entries`. The empty-list message now
  distinguishes "No history yet." (nothing saved at all) from "No
  matching entries." (a search/filter narrowed it to nothing).
- **Tray "Show and paste clipboard"**, a third tray menu item alongside
  Show Plume/Quit: deiconifies the window (the same `_show_window()` now
  shared with Show Plume, extracted rather than duplicated) and runs the
  existing `_paste()` — including the paste-as-path offer from v1.32 —
  never `_translate()`.
- 8 new unit tests (`filter_history_entries`/`history_search_blob`:
  matches by each of the three fields, case-insensitive, empty query,
  no-match, favourites-only applied before search and combined with it,
  alternatives/notes excluded from the search blob). Verified live
  against the real `PlumeApp` with a seeded local history file (three
  entries via the real `make_history_entry`/`save_history`): the search
  box renders in the header between the heading and the checkbox;
  typing narrows the list to the matching entry and only it, live, with
  the correct casefold match against source text and situation; a
  scripted check (no real system-tray click, which is a fiddly, small
  target to automate reliably — the underlying method was exercised
  directly instead) confirmed `_tray_paste()` genuinely restores a
  withdrawn/minimised window and pastes real clipboard text into the
  input box via the same `_paste()` path. Full suite: 397 tests pass.

## v1.40 — Slang reference window visibility fix (notes_018 2.A/3.A)

- **The SlangReferenceDialog (v1.34) could open and appear empty, or not
  appear at all**, for three compounding reasons, all fixed together:
  the transient window never synced its own `-topmost` flag with an
  always-on-top main window, so on Windows 11 it could map *behind* the
  parent; the term list was built synchronously inside `__init__` while
  CustomTkinter's scrollable-frame canvas could still report zero
  height, so cards were created but never laid out; and the catalogue
  row and the local-draft row shared equal grid weight, leaving the
  term list a sliver even when it did render. `_present()` (new) now
  runs on `after_idle`: it syncs `-topmost` from `config_data`, lifts
  and focuses the window, then builds the list, with a single 50ms
  retry if the frame still has no children afterwards. Reuse
  (`_open_slang_reference`'s existing-window path) re-syncs `-topmost`
  too, not just on first open. The catalogue row now gets triple the
  draft row's weight, with a bold "Catalogue" heading so an empty
  result set reads as an obvious empty state rather than a missing
  section.
- **Discoverability caption**: a one-line label under the main-window
  "French slang…" button — "Local slang reference — not the Settings
  glossary" — so it is not confused with the unrelated Settings
  Translation Glossary (`translation_glossary`, a preferred-terms list
  fed to the model, never slang).
- No new unit tests: this is a window-lifecycle/layout fix with no new
  pure-function surface. Verified live instead, both with
  `always_on_top` off and on: the dialog now raises above the parent
  and shows all 18 catalogue cards immediately on first open, and the
  reuse path (clicking the button again while it is already open) also
  re-raises correctly above an always-on-top parent. Full suite: 397
  tests pass (unchanged from v1.39).

## v1.41 — Append-tag catalogue expansions (notes_018 2.B/3.B)

- **Widened all three copy-time append pickers** past their first-ship
  minima: `FINISHING_TOUCHES` gains 7 more emotes (`:D`, `:/`, `:'(`,
  `:o`, `^^`, `<3`, `xo`); `CASUAL_SIGNOFF_CATALOGUE` gains 9 more terms
  (dsl, bof, nickel, tranquille, carrément, biz, a+, merci, trop bien);
  `MMORPG_TERM_CATALOGUE` gains 14 more (gg, gl, hf, afk, brb, sec, lag,
  gj, go, gn, cya, cyl, ttyl, ttys). All three catalogues stay pairwise
  disjoint and every casual/MMORPG entry keeps its bracketed English
  gloss. The two glossed dropdowns widened 170px -> 190px so more of the
  longer new glosses stay legible.
- **A deliberate trim against the source note's own proposal**: roughly
  a third of notes_018's proposed casual-sign-off/MMORPG additions are
  held out because they fail the project's own pre-existing
  curation-guard tests or the v1.2/v1.14/v1.31 admission bar (tone-only
  or a self-contained suffix; never a one-word verdict on a person or
  thing, a comment aimed at someone else's play, a question/greeting
  fragment, or vulgar address). Excluded from Casual sign-off: bg, sah,
  cheum, wesh, slt, pk, cv, stylé, mortel, gèrer, tu gères. Excluded
  from MMORPG: nt (a comment at an opponent), bb (reads as often as
  "baby" as "bye bye"), nul, relou, bouffon (plain verdicts on a
  person/thing). See the updated catalogue comments and the new
  banned-list test entries for the term-by-term reasoning.
- 3 new unit tests (the v1.41 expansion is present in each catalogue,
  the trimmed terms stay excluded, `compose_finishing_touch` joins one
  new term from each picker) plus extensions to the existing
  catalogue-membership and banned-list tests, which parametrise over
  the live tuples and so covered the new entries' disjointness and
  round-trip display/raw-value behaviour without any test changes.
  Verified live at both the default size and a resize to the documented
  1000x600 minimum: both dropdowns show every new entry fully, none
  clipped. Full suite: 400 tests pass.

## v1.42 — Second French slang-reference batch (notes_018 2.C/3.C)

- **`SLANG_CATALOGUE` grows from 18 to 33 entries**, the same 7-column
  shape as the v1.34 first batch: everyday vocabulary (mec, nana,
  flemme, boite, gosse, super, chouette, cool, frerot) and
  conversational phrases (n'importe quoi, c'est clair, vas-y, ça passe,
  j'ai la flemme, c'est bon), each still carrying a use note flagging
  context, register or regional caveats — dictionary-stable and
  learner-safe, not suffix-dumped. Still capped at
  `SLANG_MAX_VISIBLE_RESULTS = 30` visible rows per search. Everything
  notes_014 held back as pending (K29, wétu, unverified pronunciation,
  the grouped "Frérot, gros" entry, etc.) stays out, and the wider
  attachment beyond both batches remains editorial backlog, not shipped
  catalogue content.
- 2 new unit tests (the batch-2 ids are present and searchable;
  `search_slang("flemme")` surfaces both the noun and the "j'ai la
  flemme" phrase sharing its root) plus the existing catalogue tests
  (unique ids, seven columns, non-empty fields, full-catalogue search
  order), which parametrise over the live tuple and so already covered
  the new rows. Verified live: searching "flemme" in the slang window
  returns exactly the two matching entries. Full suite: 402 tests pass.

## v1.38 follow-up — Cooperative-cancel backoff wake + loopback integration tests (notes_017)

- **The backoff-wait cancellation gap notes_017 identified is closed.**
  `_http_post_json.wait_or_give_up` waited out its full computed delay with
  a plain `time.sleep(delay)` even when `cancel_event` was set moments
  into the wait — up to the whole backoff window (as much as the 30s
  `max_retry_wait` budget for a server-requested pause) could be wasted
  before a Clear/close/newer-request cancellation actually took effect.
  Replaced with `cancel_event.wait(delay)`, which wakes immediately when
  the event is set and otherwise behaves exactly like the old sleep for an
  uncancelled request; `cancel_event is None` still takes the plain-sleep
  path unchanged.
- **New `TestHttpLoopbackIntegration` test class**: a real
  `http.server.ThreadingHTTPServer` on an ephemeral loopback port, real
  threads and real `threading.Event`s — no mocked `urlopen` or clock, so
  backoff waiting and cancellation run exactly as they do in production.
  Covers notes_017's transport-level acceptance criteria: an uncancelled
  delayed request still succeeds; cancelling mid-backoff-wait against a
  real `Retry-After: 2` response wakes in well under a second (not the
  full 2s) with exactly one server request logged (no retry attempted);
  and a second, fresh request succeeds normally while an older one is
  cancelled mid-backoff — mirroring `PlumeApp._clear()`'s actual mechanism
  (`_new_http_cancel()` sets the old event, mints a new one) without
  needing a live window. The pre-existing
  `test_cancelled_during_backoff_wait_stops_retry` is renamed to
  `test_cancelled_before_backoff_wait_stops_retry` with a docstring
  explaining what it actually covers (cancellation observed before the
  wait starts, fully mocked) now that a genuinely-mid-wait test exists
  alongside it — notes_017 flagged the old name as overstating its
  coverage.
- **GUI-layer stale-request guard verified live** against the real
  `PlumeApp` (no `mainloop()`, isolated scratch config — same pattern as
  the v1.38 session): `_clear()` and `_on_close_destroy()` both bump
  `_request_id` and invalidate the in-flight request's `cancel_event` via
  `_new_http_cancel()`; a `_deliver()` call carrying the now-superseded
  request id is confirmed to be a clean no-op in both cases (via
  `result_is_stale` for Clear, via the `winfo_exists()`/`TclError` guard
  for close) rather than overwriting newer state or raising. Not added to
  the headless suite — driving a real background worker thread's own
  `winfo_exists()` call without an actual running `mainloop()` raises
  `RuntimeError: main thread is not in main loop`, a test-harness
  artifact of this verification style (confirmed not a production issue:
  a real `mainloop()` is always running in normal use), so this scenario
  was checked by calling `_clear`/`_on_close_destroy`/`_deliver` directly
  on the single thread that owns the Tk root, rather than through a real
  end-to-end async HTTP round trip.
- The bilingual tone-calibration benchmark notes_017 also specifies
  (v1.33) remains unactioned — it needs real Claude/Ollama outputs and a
  human bilingual reviewer's judgement, not a code change.
- Full suite: 405 tests pass (402 -> 405: three new loopback-integration
  tests).

## v1.43 — Per-conversation phrasebook (notes_019)

- **A new "Phrasebook" button** beside "French slang…" opens a second,
  independent local reference window: a free-form list of your own
  source -> note pairs, built as you go, rather than a curated catalogue.
  Add a phrase (with an optional note), **Insert** it into the message
  box at the caret, or **Delete** it — a duplicate source (casefold) is
  refused with an inline notice rather than silently added twice, and the
  list is capped at `PHRASEBOOK_MAX_ENTRIES = 30` entries of at most
  `PHRASEBOOK_MAX_SOURCE_CHARS`/`PHRASEBOOK_MAX_NOTE_CHARS = 80` characters
  each.
- **Deliberately ephemeral, per notes_019's own core proposal**: entries
  live only in `PlumeApp._phrasebook_entries` for the current session,
  reset when you press Clear, and are never written to
  `plume_config.json` or sent to the model — the same local-only
  guarantee the French slang reference makes. notes_019 also sketched two
  optional persistence designs (embedding in conversation presets, or a
  standalone `plume_phrasebooks.json`) as "a logical progression" for
  later; neither is implemented this version, staying scoped to the
  note's own core feature rather than its speculative follow-on.
- **Insertion reuses `slang_insertion`** (the same boundary-aware spacing
  French slang's "Insert in source" already uses) rather than a new
  bespoke insertion helper, just without that action's French-only
  direction guard — a phrasebook entry may be typed in either language.
- **Reuses the exact `-topmost`/`after_idle` fix v1.40 gave
  `SlangReferenceDialog`** (notes_018): `PhrasebookDialog` is the same
  kind of non-modal transient window, so it gets the same present-on-
  `after_idle` treatment up front rather than shipping a second dialog
  with the same latent behind-an-always-on-top-parent bug.
- **A real bug found and fixed during live testing, not by unit tests**:
  the first draft reset `self._phrasebook_entries = []` in `_clear()`,
  which rebinds the attribute to a new list rather than emptying the one
  an already-open `PhrasebookDialog` had captured a reference to at
  construction — the dialog kept showing stale entries after Clear even
  though the app's own list was empty. Fixed to `.clear()` (mutate in
  place), verified by reopening the dialog, adding an entry, pressing
  Clear on the main window, and confirming the still-open dialog now
  correctly shows "No entries yet."
- 7 new unit tests for `normalise_phrasebook_entry` (trims both fields,
  optional note, rejects empty/whitespace/null-byte/oversized source,
  rejects oversized note, accepts a source at the exact limit). No new
  tests for the dialog itself (UI-only, no new pure-function surface
  beyond the entry normaliser) — verified live instead: open, add, reject
  a case-insensitive duplicate, insert into the message box, delete, and
  the Clear-reset fix above, at both the default size and the documented
  1000x600 minimum (the new button row does not overflow at either).
  Full suite: 412 tests pass (405 -> 412).

## v1.44 — "Copy all" one-click clipboard bundle (notes_020)

- **A new "Copy all" button**, beside Copy five/Copy five as HTML,
  copies the whole translation package in one clipboard write: source
  text, situation (when set), the language-direction/confidence line,
  the main translation (finishing touch applied, same as Copy main
  translation) and all five alternatives with their English meaning
  checks. Both a plain-text version (clear section headings — SOURCE /
  SITUATION / LANGUAGE / MAIN TRANSLATION / ALTERNATIVES) and, on
  Windows, a rich HTML version go onto the clipboard via the existing
  CF_HTML infrastructure, with the same plain-text fallback every other
  copy action already uses off Windows or on a clipboard-write failure.
- **New pure helper `build_copy_all_content(source_text, situation,
  result, main_text, typography_fn=None)`**, returning `(plain_text,
  html_fragment)` — kept as a standalone function rather than inline in
  `PlumeApp`, per notes_020's own suggested refactor for testability.
  Distinct from both `format_five_alternatives` (no meaning checks, no
  language line) and `export_current_result_markdown` (a Markdown study
  sheet with a diff, written to a file, not a plain/HTML clipboard pair
  with the confidence line) — genuinely new content shape, not a
  duplicate of an existing export path.
- **French typography is applied here, not skipped**, when the
  Settings option is on and the result is French: `typography_fn` runs
  over the main translation and each alternative's translation only,
  never over the section labels or the source/situation text. notes_020
  itself suggested keeping Copy all "raw" for fidelity, but every other
  copy action (Copy main translation, Copy five, Copy as HTML) already
  applies this setting when enabled — a silent exception here would be
  a surprising inconsistency with no offsetting benefit, so this
  version follows the established pattern instead.
- **Placement is not where notes_020 sketched it** ("alongside the
  Favourite/Export options", i.e. the row with Favourite/Export/Copy as
  HTML/Export diff…): that row has no shrinkable columns and is already
  at its width budget at the documented 1000x600 minimum — adding a
  fifth fixed-width button there clipped visibly off the right edge in
  live testing. Placed instead next to Copy five/Copy five as HTML,
  which has ample width headroom; verified with a screenshot at 1000x600
  showing all three buttons fully visible.
- 9 new unit tests for `build_copy_all_content` (all sections present,
  situation omitted when blank, HTML escaping and markup, a meaning-less
  alternative omits the dash, a blank translation is skipped, typography
  applied only to translation-bearing fields and left untouched with no
  `typography_fn`, both empty-input guards). Full suite: 421 tests pass
  (412 -> 421).

## v1.45 — Glossary dialog for gaming/community terms (notes_021)

- **A new "Glossary" toolbar button**, in the main window's top-right
  button group alongside History/Settings, opens `GlossaryDialog`: a
  friendlier front-end for the existing `translation_glossary` config
  key, aimed at community/gaming terms a user wants translated
  consistently (e.g. Auridon <-> Auridia) without hand-writing
  "source = translation" lines in the Settings textbox. Contains a
  search box, Source term / Preferred rendering entry fields with an
  Add button, a live preview line, and a scrollable list of saved pairs
  with per-row Edit/Delete buttons — no raw JSON shown. Changes persist
  to `plume_config.json` immediately (unlike the ephemeral Phrasebook/
  French slang windows, which never touch disk).
- **The Settings textbox is kept, not replaced** (per notes_021's own
  suggested fallback option), with a one-line tip pointing to the new
  dialog. Since two live editors now exist for the same config key, an
  already-open Settings window is kept in step both ways: `GlossaryDialog`
  reads `master.config_data` fresh in every method rather than caching
  its own copy (so a concurrent Settings Save is always reflected), and
  a new `SettingsDialog._sync_glossary()` pushes a `GlossaryDialog`
  change into an already-open Settings window's textbox — otherwise
  saving that stale Settings window afterwards would silently revert
  whatever the Glossary dialog had just persisted. This is the same
  class of stale-reference bug the M1 conversation-presets fix and
  v1.43's Clear-reset fix both already addressed for this codebase, just
  arising here from a second editor rather than a shared mutable list.
- **`build_glossary_instruction()` now names elision explicitly**: the
  clause already told the model to adapt a preferred rendering
  grammatically rather than force it verbatim; notes_021's own worked
  example (Auridon/Auridia needing to surface as "d'Auridia") is now
  called out by name — "including French elisions and contractions
  where grammar requires them (for example, de/le/la contracting to
  d'/l' before a vowel sound)" — so a user only ever needs to save the
  base form, never the contracted one, matching notes_021's explicit
  warning against storing "Auridon = d'Auridia" as an entry.
- **Deliberately not implemented**: a `direction` field on glossary
  entries (notes_021's own "more explicit" alternative). The note itself
  recommends against it "unless the glossary expands significantly" —
  the existing flat, bidirectional two-line convention (Auridon =
  Auridia / Auridia = Auridon) already covers the worked example and
  matches every other flat config list in this project.
- 2 new unit tests for `build_glossary_instruction` (mentions "elision";
  covers a bidirectional gaming pair by name). No new tests for
  `GlossaryDialog` itself (UI-only, no new pure-function surface beyond
  the existing `normalise_glossary_entries`) — verified live instead:
  toolbar layout at 1180x760 and the documented 1000x600 minimum (no
  clipping), open/add/edit/delete/search, and a direct read of the
  isolated `plume_config.json` after each mutating action confirming
  real persistence, not just in-memory UI state. Full suite: 423 tests
  pass (421 -> 423).

## v1.46 — Persistent named phrasebooks; version number in the title bar (notes_022 2.A)

- **Title bar now shows the running version**: a new `APP_VERSION`
  constant is appended to the main window's title
  ("Plume — French ↔ English conversation helper — v1.46"), so it is
  easy to tell at a glance which build is running — the user's own
  standing request after finding a rebuilt `.exe` can go stale for days
  between rebuilds. `APP_VERSION` is bumped alongside each roadmap
  version from here on, the same way `ROADMAP.md` already numbers them.
- **Persistent named phrasebooks**: the per-conversation phrasebook
  (v1.43) stays the default working set — `Clear` still empties it, and
  it is still never sent to the model. This adds an opt-in second layer:
  "Save as…" snapshots the live list under a name into a new
  `phrasebooks` config key (`normalise_phrasebook`/`normalise_phrasebooks`,
  mirroring the existing `normalise_conversation_preset(s)` shape and
  its duplicate-name-repair/id-dedupe/cap rules — `MAX_PHRASEBOOKS = 8`,
  `PHRASEBOOK_NAME_MAX = 40`), so a named book survives `Clear` and a
  restart while a saved book is still never sent to the model.
- **UI lives inside the existing `PhrasebookDialog`** rather than adding
  a fourth button to the already-tight main-window heading row: a new
  book-selector row (a menu of saved books plus "This session
  (unsaved)", and a Load button) and an actions row (Save as… / Update /
  Delete book) sit above the existing add-entry row. "Load" warns via a
  confirm dialog when the live list differs from the book about to be
  loaded (compared by normalised source/note pairs) before replacing it
  — via slice assignment on the shared `master._phrasebook_entries` list,
  never a rebind, the same fix v1.43's Clear bug already established.
  "Delete book" removes a saved book only, never the live list. The
  dialog's caption now explains both layers: "The working list is local
  and cleared with Clear. Saved books live in plume_config.json and are
  never sent to the model." Pressing the main window's Clear also resets
  the dialog's book indicator back to "This session (unsaved)" via a new
  `_note_cleared()` hook, since the live list it was tracking just
  emptied.
- 17 new unit tests for `normalise_phrasebook`/`normalise_phrasebooks`
  (malformed/blank/oversized names, id dedupe, name-collision repair,
  entry normalisation/dedupe/cap, non-list rejection, a `save_config`
  JSON round-trip). `plume_config.example.json` updated with the new
  `phrasebooks: []` key. Full suite: 440 tests pass (423 -> 440).
  Verified live: Save as…/Update/Load (both the confirm-and-cancel and
  confirm-and-proceed paths)/Delete book all round-tripped correctly
  against a direct read of the isolated `plume_config.json`, and the
  title bar showed the version number, at the documented window size.

## v1.47 — Add-from-result: Glossary and Keep-as-is from a working translation (notes_022 2.B)

- **"Add to glossary…" and "Keep as-is"**, two new buttons on their own
  row beneath the five-alternatives area, let a user promote a name or
  term straight from a just-seen result instead of re-typing it into
  Settings or a separate dialog with empty fields. Neither makes a new
  backend request; both are disabled until a result is showing
  (`_current_result`), matching Copy five/Copy all's own gating.
- **"Add to glossary…"** opens (or raises) the existing `GlossaryDialog`
  pre-filled from the working result: the source term defaults to the
  input box's current text selection, or the whole source when it is
  short enough to be one term (`looks_like_single_term`); the preferred
  rendering defaults to the working main translation under the same
  test. Either field is left blank rather than guessing when its
  candidate is a full sentence. Saving still goes through the same
  `normalise_glossary_entries` + `save_config` path v1.45 already uses —
  no new persistence code.
- **"Keep as-is"** appends the current selection (or a short source) to
  `keep_as_is_terms` via `normalise_keep_as_is_terms` and `save_config`,
  refusing an empty/oversized candidate and reporting "Already in Keep
  as-is." for a casefold duplicate rather than saving a no-op silently.
  Feedback for both actions is shown on the existing advisory strip.
- **`SettingsDialog._sync_keep_as_is()`** (new): the same bug class
  `_sync_glossary` (v1.45) already guards against, now also covered for
  Keep-as-is now that it has a second writer — an already-open Settings
  window's textbox is pushed in step so a later stale Save there cannot
  silently revert what "Keep as-is" just persisted to disk.
- **Layout correction found during live testing, not left as filed
  debt**: the two new buttons were first placed in the existing "Copy
  five / Copy five as HTML / Copy all" row on the assumption (from
  v1.44's own comment) that it "has ample room" — true for three
  buttons, not five. At the documented 1000x600 minimum, "Keep as-is"
  clipped off the right edge. Fixed by giving Add-from-result its own
  row instead, verified clean at both 1000x600 and the 1180x760 default.
- 8 new unit tests for `looks_like_single_term` (single word, two words,
  three-plus words, blank/None, multiline, over/at the character limit,
  surrounding whitespace). No new tests for the two button handlers
  themselves (UI-only, driving pre-existing, already-tested pure
  functions) — verified live instead by populating a real result via
  `PlumeApp._render_result()` (this project's established technique for
  exercising result-dependent UI without a live backend call) and
  exercising both buttons for real: a full-sentence source correctly
  left blank while a short main translation pre-filled the rendering
  field, a text selection correctly fed Keep-as-is with a direct read of
  the isolated `plume_config.json` confirming the write, a repeat click
  correctly reported "Already in Keep as-is.", and both buttons stayed
  disabled on a fresh launch with no result yet. Full suite: 448 tests
  pass (440 -> 448).

## v1.48 — Local fidelity lint (notes_022 2.C)

- **`fidelity_notes(source, result, keep_as_is=())`** (new, pure and
  import-safe): a *local* second pass over the accepted result — the
  model already returns `notes`, but this catches a dropped detail even
  when the model stays silent, with no extra backend call. Checks, each
  tentative and never a verdict on translation quality ("does not
  appear", never "is wrong"):
  1. Decimal numbers/years in the source absent from every translation
     field (main plus all five alternatives), one line, French thin-
     space/NBSP thousands-grouping normalised before comparing so a
     correctly-rendered "1 500" isn't a false positive against a plain
     "1500" in the source.
  2. A source URL absent from every translation field, one line. No
     protected/unprotected distinction is needed here: by the time
     `_deliver()` runs, `restore_result_tokens` has already resolved
     placeholder tokens back to real text on both sides.
  3. Each `keep_as_is_terms` entry present in the source but absent from
     every translation field, one line per missing term, with the
     overall list still capped at `MAX_NOTES` so a source with many
     Keep-as-is terms cannot flood the advisory strip.
- **Wired into `_deliver()`**, appended onto the same `extra_notes` list
  as the existing "generated for an earlier message" warning, so it
  shows on the advisory strip alongside any other notice. Naturally
  never runs on a correction-only payload, since `_deliver_correction`
  (the standalone "Correct English" action) is a separate method that
  never calls this.
- **Deviates from the note's own draft snippet in one place** (the kind
  of judgement call notes_018/019 sessions already established this
  project expects, not a silent departure): the snippet's `_lint_haystack`
  read `result.get("translation")`, but this codebase's actual result
  contract keys the main translation as `"main_translation"` (confirmed
  against `_render_result`/`restore_result_tokens`) — using the note's
  key verbatim would have made every fidelity check compare against an
  always-empty haystack.
- 13 new unit tests (missing/present number in the main translation and
  in an alternative, thin-space normalisation, missing/present URL,
  missing/present/absent-from-source Keep-as-is term, the `MAX_NOTES`
  cap, a non-dict result tolerated without raising, blank source
  produces no notes). Full suite: 461 tests pass (448 -> 461). Verified
  live by driving `PlumeApp._deliver()` directly with a fake result
  missing a number, a URL and a Keep-as-is term all at once (this
  project's established technique for exercising delivery-path UI
  without a live backend call): the advisory strip showed all three
  notes correctly, each on its own bulleted segment.

## v1.49 — Tray completion notice (notes_022 2.D)

- **`PlumeApp._notify_tray(message)`** (new): a best-effort tray balloon
  for a finished request. Fires only while the main window is actually
  withdrawn (`winfo_viewable()` false) *and* a tray icon is running
  (`_tray_icon is not None`) — a visible window already shows the
  result, so a balloon there would be noise. Never includes source text
  (privacy): "Translation ready." on success, "Translation failed. Open
  Plume for the message." on error, generic either way. Missing pystray,
  a torn-down icon, or `notify()` raising are all swallowed silently —
  the result is still sitting on the window either way, so a balloon
  failure is never worth interrupting the user over.
- **Wired into `_deliver()` only** (not `_deliver_correction`, the
  speech/file-import deliveries, or the standalone Correct English
  action) — both its error-path return and its success-path end, exactly
  where notes_022 pointed. No new config key: off in practice whenever
  the tray isn't running, the same as every other tray feature.
- **No new unit tests** (UI/OS-integration behaviour, no new pure-
  function surface — matches the precedent already set for other
  UI-lifecycle-only versions such as v1.40). Verified live in two
  layers, since a Windows balloon itself resists automated screenshot
  verification the same way the v1.16 tray *icon* already did (see the
  project's own notes on that): (1) gating logic, by substituting a
  recording fake for `_tray_icon` and driving `_deliver()` directly
  through all four cases — visible window (no call), withdrawn+success
  ("Translation ready."), withdrawn+error (generic message, confirmed
  not leaking the real error detail), and no tray icon at all (no
  crash); (2) a real-`pystray.Icon` integration check — genuine tray
  icon started, window withdrawn, `_notify_tray` called for real —
  confirming the actual `notify()` call completes without raising. The
  balloon's on-screen appearance itself was not independently eyeballed
  this session.
- **v1.50 (global restore hotkey) intentionally not attempted this
  session.** notes_022 itself sequences it last and conditionally: "If
  implemented... If that isolated HWND still proves unsafe... drop the
  version rather than attaching anything to Tk." Per this project's own
  hard-won lesson from v1.18 (`WM_DROPFILES` raw `WNDPROC` subclassing
  crashed the interpreter under real async delivery), a `WM_HOTKEY`
  handler on a dedicated message-only HWND needs its own live,
  external-process-triggered safety test before it can be trusted — the
  same bar v1.18's revert was held to — rather than being implemented
  speculatively in the same pass as four already-scoped, lower-risk
  versions.

## v1.50 — Global restore hotkey (notes_022 2.E, notes_023 2.A)

- **Hard gate cleared first, exactly as required.** A throwaway,
  Plume-free harness (`ctypes` only, no Tk, no CustomTkinter) built the
  same message-only-HWND design and was run standalone. It registered
  Ctrl+Shift+P, received one genuine externally triggered `WM_HOTKEY`
  (a real key press, not a same-process `PostMessage`), and unregistered
  and tore down cleanly — no crash, no hang. This is the same bar v1.18's
  `WM_DROPFILES` revert was held to, now met on the safety property that
  actually matters: async delivery into a foreign-thread ctypes callback
  does not touch Tk and does not crash the interpreter. The harness's
  first draft did hit a real bug on the way — `CreateWindowExW`'s
  `hInstance` argument overflowed (`ArgumentError: int too long to
  convert`) because `GetModuleHandleW`'s 64-bit return was never given an
  explicit `restype` — the exact class of bug the project's own
  `DragFinish(hdrop)` lesson from v1.18 already warned about. Fixed by
  setting explicit `argtypes`/`restype` on every Win32 call, matching the
  pattern the v1.21 CF_HTML clipboard code already established.
- **`RestoreHotkey`** (new, Windows-only, import-safe): a message-only
  HWND (`HWND_MESSAGE`) on its own daemon thread with its own `WNDPROC`
  that understands only `WM_HOTKEY` and `WM_DESTROY` — everything else is
  `DefWindowProcW`. On `WM_HOTKEY` it only sets a `threading.Event`; it
  never calls into Tk. `start()` registers Ctrl+Shift+P
  (`MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT`, so a held chord cannot queue
  repeats) and returns an error string on failure (already in use by
  another application, or class/window creation failure) instead of
  raising. `stop()` posts a quit to the message-only window, unregisters,
  and joins the thread with a short timeout. Never subclasses Tk's own
  toplevel — the v1.18 class of risk stays out of scope entirely.
- **`PlumeApp._sync_restore_hotkey()` / `_poll_restore_hotkey()`** (new):
  the Tk thread never touches the hotkey thread directly. It polls
  `self._restore_hotkey.fired` every 200 ms via `after(...)` and, when
  set, clears it and calls the existing `_show_window()` — deiconify,
  lift, focus, honour always-on-top. Never auto-translates, never
  pastes; "Show and paste clipboard" stays a tray-menu-only action, as
  notes_023 required. A registration failure clears the config flag and
  surfaces the one-line reason on the existing `self.advisory` strip
  rather than leaving a checkbox silently on with nothing running.
- **Settings checkbox** "Restore Plume with Ctrl+Shift+P (does not paste
  or translate)", off by default, placed directly under "Close to the
  tray rather than quitting" — independent of `TRAY_AVAILABLE` (a user
  who never enables close-to-tray still wants the window back from a
  buried game), gated instead on its own `_restore_hotkey_available()`
  (Windows + a working user32/kernel32 ctypes bind), disabled with its
  own one-line caption otherwise.
- **New config key** `"restore_hotkey": false`, coerced with `bool()` on
  load like every other boolean flag; added to
  `plume_config.example.json`. Started/stopped from
  `PlumeApp.__init__` (after `_maybe_start_tray()`) and re-synced from
  `_apply_settings()` after every Settings save; stopped in
  `_on_close_destroy()` before `destroy()` so the thread and the
  registration never outlive the window.
- **No new unit tests** (Windows Win32 message-loop behaviour, no new
  pure-function surface — matches the precedent set for v1.16's tray
  icon and v1.49's tray notice). Verified live: the isolated harness
  (above); driving `PlumeApp` and `SettingsDialog` directly from an
  isolated copy of `plume.py` confirmed the checkbox toggles
  `config_data["restore_hotkey"]`, `_save()` actually starts the real
  `RestoreHotkey` thread, and `_on_close_destroy()` stops it cleanly
  (`_thread.is_alive()` False afterwards); a screenshot of the scrolled
  Settings body confirmed the new row sits directly under "Close to the
  tray..." with no clipping at 1180×760, and the existing 461 tests
  still pass unchanged. `APP_VERSION` is bumped to "1.50" in this same
  commit, ending the drift that had left it reading "1.46" since v1.47.

## v1.51 — Reply-thread previous exchange (notes_023 2.B)

- **`PlumeApp._previous_exchange`** (new, in-memory only, never persisted,
  never sent unless a working main translation exists): one remembered
  `{source, translation}` pair, installed by `_reply()` from
  `self._result_source_text` and `self._current_main` — the gesture the
  user already makes when a turn ends. Not a chat agent and not a rolling
  history dump: exactly one pair, overwritten by the next Reply, dropped
  by Clear, forgotten on close.
- **`normalise_previous_exchange(value)`** / **`build_previous_exchange_instruction(value)`**
  (new, pure, import-safe): the same shape as every other background-only
  clause (Situation, tones, the glossary) — bounded with
  `_safe_short_string(..., PREVIOUS_EXCHANGE_MAX_CHARS)`
  (`PREVIOUS_EXCHANGE_MAX_CHARS = 240`, the existing note cap), omitted
  entirely from both the prompt and the envelope when unset so every
  existing caller and test keeps today's shape, and explicit that the
  current source always wins on conflict. A missing or oversized field
  drops the whole pair rather than sending a half-remembered turn.
- **`build_translation_prompt(..., previous=None)`** and
  **`build_user_envelope(..., previous=None)`**: the clause sits next to
  the glossary clause in the prompt; the envelope gets two extra
  "Previous source:" / "Previous translation:" lines directly before
  "Text to translate:" only when a pair is present. `translate()` reads
  `config_snapshot.get("_previous_exchange")` and passes it through both.
- **`_reply()`** now also writes the pair (guarded on `self._current_main`
  being non-empty) and calls the new `_refresh_thread_label()`.
  **"Use as input" deliberately does not set it** — a different loop (the
  translation becomes the new source) that must not silently attach the
  old source as context. `_clear()` sets it back to `None`. `_translate()`'s
  snapshot carries `snapshot["_previous_exchange"] = self._previous_exchange`
  alongside the existing `tones`/`writing` overlay.
- **UI:** no new toolbar checkbox — Reply is the opt-in gesture. A
  grey caption under the Paste/Clear/Copy source/Reply row reads "Reply
  remembers this turn for the next translation. Clear ends the thread.",
  with a `self.thread_label` reading "Thread on" beside it
  (`grid_remove()` when no pair is set) — never echoing the remembered
  text itself. Its own row (row 9, pushing the Open file…/Correct
  English/Translate row down to row 10) rather than a fifth button on
  the four-button row, matching the reasoning v1.15 already established
  for keeping Translate off that row. The caption uses `wraplength=380`
  (the same pattern as the "Local reference tools" caption above it) —
  an early screenshot at the documented 1000×600 minimum caught the
  unwrapped caption running off the window's right edge before this was
  added.
- **12 new unit tests**: `normalise_previous_exchange` (non-dict, blank
  field, oversized-truncated-not-dropped, happy path);
  `build_previous_exchange_instruction` (empty when `None`, background-only
  wording with both strings present); the envelope omitting the pair by
  default and including both lines before "Text to translate" when
  present; the prompt omitting/including "Previous exchange (background
  only)"; and `translate()` actually passing a configured
  `_previous_exchange` through to both the system prompt and the user
  envelope via a mocked `run_backend`. Full suite: 472 tests pass (461 →
  472). Verified live by driving `PlumeApp` directly from an isolated
  copy of `plume.py`: rendered a fake cinema-invitation result, called
  `_reply()` and confirmed `_previous_exchange` was set and "Thread on"
  appeared; pasted "Oui, vers 19h" and drove `_translate()` with a mocked
  backend, confirming the previous exchange reached both the captured
  system prompt and user envelope; called `_clear()` and confirmed the
  pair and the label both cleared. Screenshotted at both 1000×600 and
  1180×760 with a pair active — no clipping at either size.

## v1.52 — Glossary reverse pair + glossary fidelity (notes_023 2.C)

- **`looks_like_proper_name(text)`** (new, pure): true only for one
  name-shaped token — a single word, or a hyphenated/apostrophe name
  (`Marie-Claire`, `O'Neill`) — never a phrase ("guardians of Auridon")
  and never an elided form (`d'Auridia` is grammar, not the saved base
  form, so it is explicitly excluded even though the character class
  alone would have matched it). Used only to default the glossary's new
  checkbox; never validated at Add time, so nothing already saved can
  become invalid retroactively.
- **`reverse_glossary_entry(entry)`** (new, pure): swaps term/translation
  and re-runs the result through `normalise_glossary_entries` so the
  reverse gets the exact same trimming/length rules as any other entry.
  Returns `None` for a malformed entry or when both sides casefold-equal
  (a no-op reverse that would just duplicate the forward entry).
- **GlossaryDialog "Also save the reverse pair (Auridon ↔ Auridia)"
  checkbox** (new row, between the Add row and the existing "Save base
  forms..." caption, pushing every row below it down by one):
  `_update_preview()` now *actively* sets it — on when not editing and
  both fields pass `looks_like_proper_name`, off otherwise — rather than
  only ever setting it `True`, so Cancel (blank fields, editing index
  already cleared) correctly lands back on unchecked instead of keeping
  a stale value from before the last edit. A small, deliberate departure
  from the note's own draft pseudocode, which only set the variable in
  one direction.
- **`GlossaryDialog._add_or_update()`**: after a successful forward
  persist, when the checkbox is on and this was a genuine Add (not an
  edit), `_add_reverse_pair()` appends the swapped entry — skipped with
  its own notice ("...Reverse pair skipped (already present)." /
  "...(glossary full).") rather than ever overwriting an existing
  reverse or deleting another entry to make room. First-wins stays the
  glossary's rule.
- **`glossary_fidelity_notes(source, haystack, glossary)`** and
  **`_haystack_without_elision(text)`** (new, pure), folded into
  `fidelity_notes(..., glossary=())` after the Keep-as-is lines (which
  stay first — a Keep-as-is promise is stronger, since the term was
  supposed to be copied verbatim) rather than a second advisory pass, so
  the existing `MAX_NOTES` cap still applies to the combined list. For
  each glossary pair whose term appears in the source, flags one
  tentative line if the preferred rendering is absent from the
  translations *after* stripping French elision prefixes
  (`d'`, `l'`, `n'`, `m'`, `t'`, `s'`, `j'`, `c'`, `qu'`) from the
  haystack — so a translation that correctly rendered "d'Auridia" is not
  flagged just because the bare form "Auridia" never appears verbatim.
  Same tentative voice as v1.48: "does not appear", never "is wrong",
  never a claim that the elision was grammatically required.
  `_deliver()` (7014-ish) now passes
  `glossary=self.config_data.get("translation_glossary") or []`.
  notes_021's declined direction field stays declined — two one-line
  pairs remain the shape; nothing here adds a third field.
- **12 new unit tests**: `looks_like_proper_name` (single token,
  hyphenated/apostrophe, rejects a phrase, rejects an elided form,
  rejects blank/`None`); `reverse_glossary_entry` (happy swap, identical
  sides → `None`, malformed → `None`, round-trips through
  `normalise_glossary_entries`); `glossary_fidelity_notes` folded into
  `fidelity_notes` (default `glossary=()` keeps every v1.48 test green,
  a present preferred rendering stays quiet, a missing one is flagged
  naming both the term and the preferred rendering). Full suite: 484
  tests pass (472 → 484). Verified live by driving `GlossaryDialog`
  directly from an isolated copy of `plume.py`: typing Auridon/Auridia
  auto-checked the box; Add wrote both pairs to `plume_config.json`
  ("Added, with reverse pair."); editing an existing row and then
  Cancel both left the checkbox correctly unchecked; adding a term whose
  reverse already existed showed the "already present" skip while still
  keeping the forward pair; filling the glossary to `GLOSSARY_MAX_ENTRIES`
  and adding one more showed the "glossary full" skip; and driving
  `_deliver()` with a fake result whose source contained a glossary term
  but whose translations omitted the preferred rendering showed the new
  advisory line. Screenshotted the checkbox row — no clipping.

## v1.53 — Undo last Clear (notes_023 2.D)

- **`PlumeApp._take_clear_snapshot()`** (new): captures input, situation,
  direction, the working result (`current_result`/`current_main`/
  `result_source_text`/`result_situation`), a *copy* of the phrasebook
  entries, and a copy of the v1.51 previous-exchange pair — everything
  `_clear()` is about to drop. In-memory only, never persisted, never
  sent anywhere. `_clear()` now takes this snapshot unconditionally,
  even when everything is already blank, so Undo is a true revert rather
  than a guess at "was there anything" — and enables the new button at
  the end.
- **`PlumeApp._undo_clear()`** (new): writes the snapshot's fields back;
  slice-assigns the phrasebook (`self._phrasebook_entries[:] = ...`,
  never rebinds — the exact v1.43 Clear bug this project already fixed
  once), refreshing an open PhrasebookDialog. Does not bump
  `_request_id`: no in-flight work is involved, and Undo Clear does not
  resurrect a cancelled request. One level — a second Clear before Undo
  simply replaces the snapshot with the newer one.
- **Real bug caught during live testing, not in the note's draft**:
  `_render_result(result)` itself resets `_current_main` from
  `result["main_translation"]`, but `_use_as_main` ("Use this") already
  diverges `_current_main` from `_current_result` without touching
  `_current_result` — so calling `_render_result()` and then setting
  `_current_main` in the order notes_023's own snippet used would have
  silently lost a "Use this" promotion on every Undo. Fixed by calling
  `_render_result()` first and re-applying the snapshotted
  `_current_main` plus `_refresh_primary_display()` afterwards, the same
  finishing sequence `_use_as_main` itself already uses. Caught live by
  promoting an alternative before Clear/Undo and checking the restored
  primary text, not by unit test (this is UI-lifecycle sequencing, no
  new pure-function surface).
- **`Undo Clear` button**, disabled until a snapshot exists, added to
  `translate_row` sharing column 0 with `Open file…` in their own
  left-anchored sub-frame (`left_actions`) — columns 1 and 2 of that row
  were already Correct English and Translate with no spare spacer
  column to reuse, unlike what the note's insertion map assumed for the
  live tree. **Ctrl+Shift+Z** is bound on the toplevel (not the input
  box, unlike Translate/Correct English's shortcuts) since Undo Clear is
  not text-editing-specific; plain Ctrl+Z is left untouched, staying the
  input box's own text-undo.
- **A second real clipping bug caught live**, the same class as v1.51's:
  `Open file…` (120) + `Undo Clear` (90) + `Correct English` (130) +
  `Translate` (140) overflowed the left pane by roughly 34px at the
  documented 1000×600 minimum, truncating "Undo Clear" mid-label
  (`Open file…`/`Undo Cl`) even though every button rendered its full
  text comfortably at 1180×760. Fixed by trimming three widths (120→105,
  90→80, 130→120) and two `padx` gaps (6→4), verified by re-screenshotting
  at both sizes rather than assuming the note's own draft widths were
  already tuned for this row's new fifth element.
- **No new unit tests** (UI-lifecycle state only, matching the
  precedent set for v1.40/v1.49/v1.50); full suite stays at 484 tests,
  unchanged. Verified live by driving `PlumeApp` directly from an
  isolated copy of `plume.py`: filled input, a result, a "Use this"
  promotion, two phrasebook rows and a v1.51 thread pair; Clear (button
  enables); Undo Clear — all five came back, including the promoted
  "Cinema tonight?" rather than the original main translation; a second
  Clear correctly took a fresh snapshot. Screenshotted at both 1000×600
  and 1180×760 after the width fix — no clipping at either size.

## v1.54 — About panel (notes_024 2.A)

- A compact `CTkFrame` ("About Plume — v{APP_VERSION}", the app's one-line
  description, and the copyright notice) sits inside `SettingsDialog`'s
  existing scrollable body, directly after the "Settings" heading and
  before the Backend selector — no new toolbar button or window.
- **`APP_COPYRIGHT`** (new module constant, beside `APP_NAME`/
  `APP_VERSION`): the short notice as release metadata, matching
  `COPYRIGHT`/`LICENSE` verbatim, not read from either file at runtime —
  so a frozen `.exe` never depends on an external file for its own
  About text. Review this constant against `COPYRIGHT`/`LICENSE`
  whenever attribution changes.
- Both body labels rebind their own `wraplength` on `<Configure>`, the
  same self-resizing pattern already used elsewhere in this dialog, so
  the panel wraps cleanly rather than clipping as Settings is resized
  down to its documented 480×480 minimum.
- No config schema, dependency, thread, or network call changed —
  implemented exactly as notes_024's own snippets (3.A/3.B), taken
  essentially verbatim. No new unit tests (static release metadata, no
  new pure-function surface); full suite stays at 484 tests. Verified
  live: launched from an isolated copy of `plume.py`, opened Settings,
  confirmed the panel reads "About Plume — v1.54" with the correct
  copyright line at both the default 560×780 size and the 480×480
  minimum (wraps without clipping; Save/Cancel stay reachable in the
  fixed footer at both sizes).

## v1.55 — Lowercase translations (notes_024 2.B)

- A "Lowercase translations" checkbox under the alternatives applies
  `str.lower()` (never `casefold()`, so `ß` stays `ß` rather than
  expanding to `ss`) at the display/clipboard boundary only.
  `format_translation_case()` (new pure function) is the single seam;
  `_display_translation()` calls it with the live `self.lowercase_var`.
  `_current_main`/`_current_result` are never touched, so Export,
  Export diff, Favourite, History and "Use as input" all keep their
  original casing exactly as before — only what is *shown* or *copied*
  as a translation changes. One in-memory `ctk.BooleanVar`, default
  off, reset on restart (no config/schema change — deliberately
  session-only, per the note).
- Wired through the existing seams rather than duplicating them: the
  primary display (`_refresh_primary_display`) and each alternative's
  label (`_build_variation_card`, refreshed in place by
  `_on_lowercase_change` without rebuilding cards or losing a "Use
  this" promotion) call `_display_translation()` directly;
  `_maybe_french_typography()` (the existing copy-time seam already
  used by Copy main/Copy five/Copy all/Copy as HTML) now also applies
  it first, so every one of those routes picks up the preference for
  free. `_copy_variation()` (individual alternative Copy) previously
  bypassed that seam entirely — routed through it now, which also
  makes it respect the pre-existing French-typography preference for
  the first time, a small deliberate consistency fix alongside the
  main feature. `build_copy_all_content()`'s existing `typography_fn`
  parameter means Copy all lowercases the main translation and
  alternatives only — source, situation, language line and meaning
  checks keep their original case, matching the note's scope matrix.
- 6 new headless tests (`TestFormatTranslationCase`) cover the pure
  formatter: disabled is a no-op, enabled lowercases English/French
  while keeping accents, `ß` is not expanded, empty stays empty, the
  default argument is disabled. 484 → 490 tests. The bound-method
  integration (the checkbox, the display/clipboard seams together) is
  UI-lifecycle wiring with no headless surface, matching the v1.40/
  v1.49/v1.50/v1.53 precedent — verified live instead: drove
  `PlumeApp` directly from an isolated copy of `plume.py` with a
  populated result containing accents, `ß` and mixed case, confirmed
  `_current_main`/`_current_result` stay raw after toggling, every
  clipboard route (Copy main, an individual alternative Copy, Copy
  five, Copy all) lowercases only the translation text, unchecking
  restores the original casing immediately, and toggling with an empty
  result raises no exception.
- **A real, pre-existing bug caught live, not caused by this note**:
  at the documented 1000×600 minimum, the Translation pane's stacked
  content already needed roughly 753px against ~456px actually
  available — confirmed byte-identical against v1.54 (before this
  checkbox existed) and reproduced with a short two-line result, so it
  was not specific to long alternatives or to the new checkbox. The
  alternatives list, the new checkbox and the advisory strip were all
  silently rendering below the visible window edge, unreachable, with
  no error and no scrollbar. Root cause: `right` (the whole Translation
  pane) was a plain `CTkFrame` with only `alts_frame` independently
  scrollable, so once the pane's fixed rows alone exceeded the
  available height, everything below simply overflowed the window.
  Fixed the same way `SettingsDialog` already solves this exact class
  of problem (v1.10's own comment there describes the identical
  symptom): `right` is now itself a `CTkScrollableFrame`, and
  `alts_frame` is a plain transparent `CTkFrame` again (a scrollable
  frame nested inside another one makes the mouse wheel behave
  inconsistently depending on which one last had it, which is worse,
  not better). Verified live at 1000×600 with a full five-alternative
  result: the pane now shows a scrollbar, and scrolling reaches every
  alternative, the checkbox and its help text, all fully functional
  (toggling lowercase from the scrolled position updates cards 3–5
  correctly). Re-verified the default 1180×760 size afterwards for any
  regression — content renders identically, scrolling only appears
  when content actually exceeds the pane.

## v1.56 — Lowercase translations follow-up (user feedback on v1.55)

Two fixes requested directly by the user after screenshotting v1.55 on
a large monitor and asking for the Lowercase checkbox to sit closer to
the top and to stay on until manually turned off.

- **Fixed a real, separate bug the user's screenshots exposed**: the
  empty-state `alts_frame` had no explicit height, so CustomTkinter's
  `CTkFrame` default of `width=200, height=200` applied — a ~200px
  dead floor above the checkbox whenever no result is showing, on top
  of v1.55's own scrollable-pane fix. Diagnosed with the same
  `winfo_reqheight()` technique as v1.55's overflow (confirmed
  `alts_frame.winfo_reqheight() == 200` with zero children, tracked to
  `CTkFrame`'s literal constructor default). Fixed by passing
  `height=1` explicitly; `grid_propagate` still lets it grow to fit
  real cards once a result renders (confirmed live: 5 populated cards
  still reach 580px), so this only removes the empty-state floor.
  Verified live at a large window (matching the user's own
  screenshots): the checkbox now sits directly under "Add to
  glossary…/Keep as-is" instead of far down the pane.
- **`lowercase_output` now persists across restarts**, not just across
  Clear/Undo Clear within a session — the follow-up notes_024 itself
  anticipated ("Should a remembered preference be required in the
  future..."). New `DEFAULT_CONFIG["lowercase_output"] = False`,
  loaded with the same `bool(config.get(...))` coercion every other
  boolean in this config already uses (deliberately not the stricter
  JSON-boolean-only check notes_024's draft suggested — consistency
  with every existing boolean field beat introducing a one-off
  exception for this one). `PlumeApp.__init__` seeds `lowercase_var`
  from it; `_on_lowercase_change` writes it straight back with
  `save_config()` on every toggle — a best-effort immediate persist,
  the same pattern already used for `elevenlabs_privacy_ack`, chosen
  over waiting for a Settings save so quitting without ever opening
  Settings still remembers the toggle.
- **A real dual-editor race, caught before it shipped, not after**:
  `SettingsDialog._save()` writes from `self._config`, a snapshot
  taken when Settings opened — exactly the class of bug this project
  has hit before (v1.43 Clear, M1 presets) whenever a value can also
  change from the main window while Settings stays open. Added
  `lowercase_var` to the same live-remirror block Settings already
  uses for `direction_var`/`backend_var`/etc., so a stale Settings
  Save can never revert a toggle made after Settings was opened.
  Verified live end-to-end: opened Settings, toggled Lowercase off
  from the main window (confirmed the immediate write landed on disk),
  clicked Save in the still-open, stale-snapshotted Settings dialog,
  and confirmed the file still read the live (off) value, not the
  stale (on) snapshot.
- 2 new headless tests (`lowercase_output` boolean coercion and
  default, mirroring the existing `french_typography`/
  `fallback_to_ollama` pattern exactly). 490 → 492 tests. The gap fix
  and the Settings-mirror are UI-lifecycle wiring verified live only,
  same precedent as v1.40/v1.49/v1.50/v1.53/v1.55.
- Deliberately kept the checkbox on the main window rather than moving
  it into Settings, per discussion with the user: something toggled
  "frequently" (the user's own framing) is better served by staying
  one click away than being buried behind Settings' open/toggle/Save
  round trip — and the gap fix above already closes most of the visual
  distance that prompted the Settings suggestion in the first place.

## v1.57 — Reply to this (incoming turn) + notes_025 M1/m1 fixes

First of a batch grounded in notes_026 ("Next-turn conversation
helpers"), which itself folds in notes_025's bug-hunt findings. Closes
the other half of the standing brief's "Reply to This": v1.9's Reply
already handled "my turn is over" (outgoing, English → French); this
adds "now draft my answer to that" (incoming, French → English).

- **`result_is_incoming_french(result)`** — a small pure predicate
  (`source_language == "French" and target_language == "English"`)
  keyed on the *accepted result*, not the toolbar, so a stale toolbar
  direction can't mislabel the button.
- **`_reply()` now branches on the working result.** Outgoing (an
  English → French result, or no incoming-French result showing) is
  unchanged: copy the composed translation, invert a fixed direction
  (no-op on Auto-detect), clear and focus the input, remember the pair.
  Incoming (French → English) does *not* copy — you are not sending
  English — and pins direction to English → French even from
  Auto-detect, so a short English draft ("Yes, around 7") can't be
  auto-detected as French and bounce back. Both branches install the
  same reply-thread `_previous_exchange` from the result snapshot
  (v1.51) and leave Situation untouched (the v1.9 rejection of a
  Situation auto-fill stands — see notes_026 §2.A for the restated
  reasoning). "Use as input" remains a different loop and still does
  not touch `_previous_exchange`.
- **One button, two labels/captions**, never echoing source text:
  `_refresh_reply_label()` sets `reply_btn` to "Reply to this"
  (width 110) with a matching caption ("Reply to this pins English →
  French and remembers this turn. Situation stays the scene, not the
  last message.") when the working result is incoming French, and back
  to "Reply" (width 80) with the original caption otherwise. Called
  from `_render_result` and `_clear_results`, so Reopening a history
  entry picks up the right label for free via `_render_result`.
- **notes_025 M1** (Undo Clear stays armed after a later
  Translate/Correct and can overwrite the newer result): `_translate`
  and `_correct_then_translate` now disarm Undo Clear
  (`_clear_snapshot = None`; `_set_undo_clear_enabled(False)`)
  immediately after their existing busy-guard, before any other
  validation — a new request supersedes a pre-existing Clear snapshot
  regardless of whether this particular call goes on to start a
  worker.
- **notes_025 m1** (`_reopen_history_entry` didn't call
  `_new_http_cancel()`, unlike `_clear`/`_on_close_destroy`): now it
  does, immediately after bumping the request/speech ids, so an
  in-flight retry/backoff wait stops promptly on Reopen instead of only
  being dropped later by the stale-id check at delivery.
- 4 new headless tests (`result_is_incoming_french`: FR→EN true, EN→FR
  false, missing-keys dict false, non-dict false). 492 → 496 tests. The
  button/caption relabelling, the direction-pin/no-copy behaviour, and
  the M1/m1 fixes are UI-lifecycle wiring verified live only (scripted
  `PlumeApp`, isolated temp config, no network), same precedent as
  v1.40/v1.49/v1.50/v1.53/v1.55/v1.56: screenshotted at 1000×600 and
  1180×760 for both the outgoing and incoming states (no clipping —
  "Reply to this" and its two-line caption both fit above the
  Open file…/Undo Clear/Correct English/Translate row at the
  documented 1000×600 floor), and driven directly (`_render_result` /
  `_reply()` / `_clear()` / `_reopen_history_entry()` against a
  constructed `PlumeApp`, no `mainloop()`) to confirm the clipboard is
  genuinely left untouched on the incoming path, direction is pinned,
  Situation survives both paths, and Undo Clear/the HTTP cancel event
  behave as M1/m1 describe.

## v1.58 — Speech rate menu + Speak source

Second of the notes_026 batch. The Slow checkbox (v1.12) could only ever
offer one fixed 0.75× rate; the standing brief asked for 0.75× *or*
0.8×, which a boolean cannot express. Also closes the other half of
"hear that French slowly": Speak previously only ever read the
translation aloud, with no one-click way to pronounce the *incoming*
French itself.

- **`SPEECH_RATES` (1.0 / 0.8 / 0.75) replace the boolean Slow
  checkbox** on the same `touch_row`, as a `CTkOptionMenu` showing
  "Normal" / "0.8×" / "0.75×". `normalise_speech_rate` does exact
  membership (not a clamp), so a hand-edited "0.8000001" in the config
  file falls back to Normal rather than silently becoming a third,
  unlabelled speed. `speech_sample_rate(factor)` is the single seam:
  `int(ELEVENLABS_SAMPLE_RATE * normalise_speech_rate(factor))`.
  `SLOW_SPEECH_RATE_FACTOR` stays as an alias for the slowest rate so
  the existing `test_slow_speech_rate_scales_frame_rate` test needed no
  change. `_speak` reads the menu once per click, so a rate change
  mid-playback never affects audio already in flight — the same
  snapshot discipline `_translate` already uses for its own config.
- **`speech_rate` persists across restarts**, seeded in
  `PlumeApp.__init__` and written back immediately on change
  (`_on_speech_rate_change`), the identical best-effort immediate-save
  pattern v1.56 established for `lowercase_output`. `SettingsDialog._save`
  remirrors the live menu into its snapshot first, so an open Settings
  window can't revert a rate change made from the main window while it
  was open — the same dual-editor race v1.56 already closed for
  `lowercase_output`.
- **Speak source**, a new button beside Copy source, speaks the result's
  source-text snapshot (or the live input, before a result exists) —
  raw text, never a finishing touch, through the same `_speak()`
  worker, privacy notice and stale `_speech_request_id` guard as Speak.
  This is the pronunciation-companion half of the standing brief: after
  translating incoming French you can hear *their* French at 0.8×
  without copying it into the input or swapping direction. No extra
  ElevenLabs call unless the button is actually clicked.
- **A real clipping bug caught before it shipped, not after**: adding
  Speak source to the Paste/Clear/Copy source/Reply row pushed its
  required width to 495px against the pane's ~458px available at the
  documented 1000×600 floor — "Reply to this" (v1.57) was cut off
  mid-word. Found with the same `winfo_reqwidth()` technique v1.53 used
  for this identical class of overflow, confirming it as a real,
  measured 37px gap rather than eyeballing a screenshot. Fixed by
  trimming five button widths (Paste/Clear 80→64, Copy source 95→88,
  Speak source 100→92, "Reply to this" 110→95) rather than wrapping to
  a third row — each new width still comfortably exceeds that button's
  actual rendered text width (measured with `tkinter.font.Font.measure`
  against the button's own font), so no label is truncated.
- 6 new headless tests (`normalise_speech_rate` exact-membership and
  fallback, `speech_sample_rate` scaling, label/`speech_rate_from_label`
  round-trip) plus 3 config-coercion tests (`speech_rate` normalised on
  load, defaults to Normal, hand-edited junk falls back). 496 → 505
  tests. The menu/button wiring, the immediate persistence, the
  Settings dual-editor guard and the width fix are UI-lifecycle
  verified live only, same precedent as v1.53/v1.56/v1.57: screenshotted
  at 1000×600 and 1180×760 for outgoing/incoming/cleared states (no
  clipping after the width fix), measured with `winfo_reqwidth()` before
  and after trimming, and driven directly against a constructed
  `PlumeApp` (mocking `call_elevenlabs_tts`/`pcm_to_wav_bytes` to avoid
  a real network call) to confirm each rate menu choice produces the
  right WAV frame rate, Speak source reads the source snapshot (not the
  translation) and falls back to the live input pre-translation,
  `speech_rate` reaches disk immediately, and a stale Settings snapshot
  cannot revert a live rate change.

## v1.59 — Retry visibility + ElevenLabs retry

Third of the notes_026 batch. `_http_post_json` already retried
429/502/503/504 (Claude also 529) with capped exponential backoff, but
the UI never heard about it: the status bar was set once at dispatch
and stayed there until delivery, so a 20-second run of retries looked
exactly like a hang. ElevenLabs Speak had no retry loop at all — a 429
was a user-facing error on the very first attempt.

- **`_http_post_json` grows an optional `on_retry` callback**, called as
  `on_retry(next_attempt_number, attempts)` immediately before each
  backoff wait — never on the final, non-retried failure. Any exception
  it raises is swallowed, so a status-bar failure can never abort a
  retry. `call_anthropic`/`call_ollama` pass
  `on_retry=config_snapshot.get("_on_retry")` straight through.
- **`_schedule_status(state)`** is the worker-thread-safe status update
  Translate/Correct/Speak's `_on_retry` callbacks use: `self.after(0,
  ...)` plus a `winfo_exists()` guard, the exact hop `_deliver_safe`
  already uses for delivering results. `_translate`,
  `_correct_then_translate` and `_speak` each install
  `snapshot["_on_retry"]` with a fixed template
  ("Retrying (2 of 4)…" / "Retrying speech (2 of 4)…") — never the
  submitted phrase, an exception message, or anything else dynamic.
- **ElevenLabs now retries** the same 429/502/503/504 set with the same
  bounded exponential backoff as the translation path — not routed
  through `_http_post_json` itself (that helper JSON-decodes the body;
  this one returns raw PCM), so `call_elevenlabs_tts` grew its own
  small retry loop mirroring `_http_post_json`'s shape, honouring
  Retry-After and closing a failed response without draining its body
  (v1.38). Speak does not share Translate's cancel event (notes_015
  already deferred that) — this version retries without cancellation,
  still guarded by the existing stale `_speech_request_id` check at
  delivery. Also dropped the raw exception reason from ElevenLabs'
  URLError message, which v1.38 had already dropped from the
  translation path — Speak was the one place that still leaked it.
- 8 new headless tests: `on_retry` fires before every retried wait and
  never on the final failure (`_http_post_json`), an exception inside
  `on_retry` doesn't abort the retry, `on_retry` is never called when
  nothing needs retrying; `call_elevenlabs_tts` retries 429 then
  succeeds, exhausts retries and raises, calls `on_retry` the right
  number of times, and no longer leaks a raw URLError reason; a status
  line carrying "Retrying (2 of 4)…" still excludes the submitted
  phrase (extends the existing privacy suite). 505 → 513 tests. The
  worker-thread status hop is UI-lifecycle wiring verified live only,
  same precedent as v1.53/v1.56/v1.57/v1.58: driven against a
  constructed `PlumeApp` under a real (briefly self-quitting)
  `mainloop()` — plain `update()` polling proved unreliable for a
  cross-thread `after(0, ...)` callback specifically, a harness-only
  limitation (production always has `mainloop()` running continuously)
  — confirming `_schedule_status` updates the status bar from a genuine
  background thread, and that `_translate`/`_correct_then_translate`/
  `_speak` each install a working, correctly-worded `_on_retry` that
  reaches the status bar through the real worker thread. Screenshotted
  live showing "Retrying (2 of 4)…" on the status bar with no other
  layout change (no new widgets this version).

## v1.60 — Quick translate

Last of the notes_026 batch's four main versions, closing the standing
brief's "clipboard in, French out": v1.39's tray paste and v1.50's
restore hotkey both deliberately refuse to translate, so getting a
Discord message in, translated, and back on the clipboard was still
four separate clicks.

- **`IsolatedHotkey`**: v1.50's `RestoreHotkey` (a message-only HWND on
  its own daemon thread, understanding only WM_HOTKEY/WM_DESTROY, never
  touching Tk directly — the design that replaced v1.18's WndProc
  subclass after that crashed the interpreter on a real cross-process
  message) is now a small base class parameterised by
  `(vk, mods, hotkey_id, window_class)`. `RestoreHotkey` is a thin
  subclass unchanged in behaviour; `QuickTranslateHotkey` is a second
  instance — Ctrl+Shift+T, its own hotkey id, its own window class
  `PlumeQuickTranslateHotkey` (`RegisterClassW` is keyed on the class
  name, so the two instances cannot collide).
- **A real, previously-shipped crash bug found and fixed**: a throwaway,
  Plume-free harness (registers both hotkeys, posts real WM_HOTKEY
  messages to each, per this note's own testing discipline — never
  attach either to the Tk toplevel to "just try it") crashed the
  interpreter with `STATUS_ILLEGAL_INSTRUCTION` the moment a hotkey was
  stopped and started a second time in the same process. Root cause:
  `RegisterClassW` returning `ERROR_CLASS_ALREADY_EXISTS` on a second
  `start()` was treated as "fine, reuse it" — but the reused
  registration's `lpfnWndProc` still pointed at the *first* run's
  `self._wndproc_ref` trampoline, which that run's own `start()` had
  already replaced with a new one, letting ctypes garbage-collect the
  old native trampoline. The next `CreateWindowExW` (or any message
  routed through the reused class) then called into freed trampoline
  memory. This bug already shipped in v1.50 — it just needed two
  `_sync_restore_hotkey()` calls in one session (Settings: turn the
  restore-hotkey checkbox off, save, on, save) to hit it, which nothing
  had exercised before this version's own harness did. Fixed with
  `UnregisterClassW` on every exit path of `_run()` (a `try/finally`,
  not just the clean message-loop exit), and the `ERROR_CLASS_ALREADY_EXISTS`
  branch now force-unregisters and retries fresh rather than ever
  trusting a "reuse". Stress-tested 10 stop/start cycles of both
  hotkeys interleaved, posting WM_HOTKEY each cycle, with no crash.
- **Two layers, one method** (`_quick_translate_from_clipboard`):
  window-level `<Control-Shift-t>`, bound on the toplevel like Undo
  Clear, always on — Plume is already focused, no Settings needed.
  System-wide Ctrl+Shift+T is opt-in (Settings, off by default,
  directly under the restore-hotkey checkbox), using
  `QuickTranslateHotkey`. The existing `_poll_restore_hotkey` loop
  polls both hotkeys' Events now; the system-wide one is skipped
  when Plume is already focused and mapped, since the window-level Tk
  binding will already have fired for that same keypress and
  `RegisterHotKey`'s chord fires regardless of focus — acting on both
  would run the pipeline twice. A 400ms debounce on
  `self._quick_last_ts` covers the same class of double-fire.
- **Pipeline**: show the window, read the clipboard (empty → stop), a
  file path offers the existing "Open this file?" confirmation instead
  of translating the path text, oversized text gets the existing
  generic advisory, otherwise the input box is *replaced* (not
  inserted-at-caret — Quick translate means "this is the new message"),
  `_auto_copy_on_deliver` is set, and `_run_selected_mode()` dispatches
  exactly like Ctrl+Enter, respecting the current Mode/direction. An
  already-running translation refuses a second worker with a status
  message rather than queueing one.
- **Auto-copy only on an accepted delivery that still matches**:
  `_deliver`'s success path copies the main translation and shows
  "Copied." only when `_auto_copy_on_deliver` is set *and* the input
  still equals what was submitted — exactly the existing "Generated for
  an earlier message" staleness check `_deliver` already had, reused
  rather than duplicated. `_auto_copy_on_deliver` resets to `False`
  after every delivery (success or error).
- **Six leak paths found and closed while wiring the flag through
  Correct-then-translate mode** (Quick translate respects whatever Mode
  is selected, including "Correct English then translate"): a
  correction refused by `_correction_is_allowed()` (e.g. Auto-detect
  sees French, not English), a correction's own oversized-input
  refusal, a declined privacy notice in either `_translate` or
  `_correct_then_translate`, and `_deliver_correction`'s error/stale-
  input paths all short-circuit *before* the chained `_translate()`
  call that would otherwise have cleared the flag on delivery — each
  now clears `_auto_copy_on_deliver` itself, or a stale `True` would
  silently auto-copy some later, unrelated manual Translate's result.
  Proved this mattered (not just plausible) by reproducing the leak
  scenario live before the fix and confirming a subsequent unrelated
  manual Translate did *not* touch the clipboard after it. Deliberately
  did **not** add a matching clear at the top of `_translate`/
  `_correct_then_translate`'s own busy-guards — Quick translate sets the
  flag and calls straight into one of them in the same synchronous call
  chain, so clearing it there would have erased the very intent it was
  just given (an early draft of this version did exactly that and was
  caught by the live delivery test, not read-through).
- Config: `quick_translate_hotkey: false` in `DEFAULT_CONFIG` and the
  example file, bool-coerced on load, persisted from Settings the same
  way `restore_hotkey` is (`and _restore_hotkey_available()` so a
  hand-edited `true` on Linux/macOS can't silently claim to be on).
- 4 new headless tests (`_hotkey_hint` letter-VK labels and the generic
  fallback; `quick_translate_hotkey` config coercion and default). 513 →
  517 tests. Everything else here is native/UI-lifecycle, verified live
  only, same precedent as v1.50/v1.53/v1.57/v1.58/v1.59: the throwaway
  hotkey harness and its 10-cycle stress test (see above), driving
  `PlumeApp` directly under a real briefly-self-quitting `mainloop()`
  (mocking `translate`/`correct_english`, never a real network call) to
  confirm the happy path, the 400ms debounce, the already-busy refusal,
  the file-path-offers-open-not-translate path, the input-changed-
  before-delivery skip, all six leak paths, and the Settings checkbox
  round trip through `SettingsDialog._save` → `_apply_settings` →
  `_sync_quick_hotkey` (including the exact stop/start/stop/start cycle
  that used to crash, now clean). Screenshotted Settings at 1000×600:
  the new checkbox sits directly under Restore, full text visible, no
  clipping.

## v1.61 — Texting chip strip

First of the two smaller notes_026 deltas. `stp`, `rdv` and `bcp` were
already in `SLANG_CATALOGUE` as in-sentence terms, reachable only
through the full French slang… dialog; `cad` (c'est-à-dire), `pcq`
(parce que) and `pk` (pourquoi) were missing from the catalogue
entirely.

- **`cad`/`pcq`/`pk` added to `SLANG_CATALOGUE`**, right after the
  existing `rdv` row, same seven-column shape, category Texting,
  register Abbreviation. Confirmed no pre-existing rows under these
  ids before adding (the note's own instruction).
- **`TEXTING_SHORTCUTS = ("stp", "rdv", "cad", "bcp", "pcq", "pk")`** —
  a curated subset of the wider catalogue, not a new vocabulary source:
  these are in-sentence abbreviations, not copy-time suffixes (a suffix
  of "rdv" or "cad" would read "On se voit demain rdv", which is
  wrong), so they get their own one-tap row rather than joining the
  Casual sign-off picker. `tkt`/`dsl`/`a+` are deliberately not
  duplicated here — they already live on that picker, and a second copy
  of the same term in two places is how catalogues drift.
- **A compact "Texting" chip row** under the input box (a new grid row
  in `_build_left`, between "Remember tones and profile" and the Paste/
  Clear/Copy source/Speak source/Reply row — `buttons`/`thread_row`/
  `translate_row` each shifted down one grid row to make space). Each
  chip calls the existing `_insert_slang_source` (via a small
  `_insert_texting_shortcut` wrapper that surfaces its English-
  direction `ValueError` on the advisory strip, the same pattern
  `SlangReferenceDialog._act` already uses) — no model traffic, no new
  insertion mechanism.
- 9 new headless tests: `cad`/`pcq`/`pk` present in the catalogue;
  `TEXTING_SHORTCUTS` is a subset of the catalogue's raw terms, is
  disjoint from the held-out harsher-register list (wesh, keuf, boloss,
  cheum, sah, relou) and from the Casual sign-off suffixes
  (tkt/dsl/a+), and each of its six terms still spaces correctly at a
  word boundary via the existing `slang_insertion`. 517 → 522 tests.
  The chip row itself is UI-lifecycle, verified live: screenshotted at
  1000×600 and 1180×760 (all six chips fully visible, no clipping, row
  order unaffected by the renumbering), and driven directly against a
  constructed `PlumeApp` to confirm a chip click inserts at the real
  caret with a boundary space, chains correctly across two consecutive
  chips, is refused (and shown on the advisory) on a forced English
  direction, and that every `TEXTING_SHORTCUTS` term has a real button
  in the widget tree.

## v1.62 — History "Export visible"

Second and last of the notes_026 batch. `export_history_to_tsv`
already matches the standing brief's Anki shape (Front: source +
situation; Back: main + five alternatives + meaning checks, `<br>`-
joined) — this version only widens *which entries* get exported, not
the export format itself.

- **"Export visible"** button in the History actions row, beside the
  existing "Export favourites". Exports `_visible_entries()` — whatever
  the current search box and favourites-only filter are showing —
  instead of always filtering to `favourite is True`.
- **`_write_history_export(entries, title)`** factors the shared save-
  dialogue + format-dispatch + write + success/error messaging out of
  `_export_favourites`, so both buttons now share one I/O path rather
  than duplicating it. The one deliberate behaviour change: the success
  message generalised from "Exported N favourite(s) to path" to
  "Exported N entry/entries to path", since "favourite(s)" no longer
  describes what "Export visible" exports.
- An empty visible set shows its own "No matching entries to export."
  advisory rather than writing a blank file — `_export_favourites` kept
  its own distinct empty-state message ("You have no favourited
  translations to export yet."), since the two buttons can be empty for
  different reasons.
- The two-column Anki TSV contract (Front/Back, no tags column) is
  unchanged — deliberately: a third column can break a two-field Basic
  note type on import, and notes_026 explicitly left that out of scope
  pending a future request.
- No new headless tests: `export_history_to_tsv`/
  `export_history_to_markdown` and `filter_history_entries`
  (`_visible_entries`'s underlying function) are already covered, and
  this version only wires two already-tested pieces together with no
  new format logic. Verified live instead, driving a constructed
  `HistoryDialog` directly (mocking `filedialog`/`messagebox`, no real
  file browser): confirmed "Export favourites" is byte-for-byte
  unaffected by the refactor (still only the starred entries), "Export
  visible" with a search filter active exports only the matching entry
  and nothing else, and an empty filter shows the info dialog and never
  opens a save dialog. Screenshotted History at 1000×600 — the three-
  button actions row (Clear history / Export favourites / Export
  visible) renders fully, no clipping.

## v1.63 — Reply keeps a draft, Quick translate arms Reply

First of the four notes_027 versions (draft-safe Reply, then a speech
cache, speech cancel and the texting/study gaps — shipped one at a time
so a reply regression and a playback regression never share a bisect).
Two corrections to how a French message you have just read hands over to
the English answer you are about to write.

- **Reply no longer wipes a real draft.** Reply and "Reply to this" used
  to clear the whole source box unconditionally, so an answer you had
  already started (or the other person's next message, pasted before you
  clicked) was lost. New pure helper
  `reply_should_keep_draft(input_text, result_source)`: the box is
  cleared only when it is blank or still exactly the text that was just
  translated; anything else is a draft, kept as it stands with the caret
  moved to its end. The comparison is exact (`_input_text()` does not
  strip), the helper never raises and never echoes either argument, and
  it ignores languages, so the incoming and outgoing paths share one
  rule.
- **`_apply_reply_turn(incoming)`** is the old `_reply` body plus that
  rule; `_reply` is now a thin wrapper that works out `incoming` from the
  result on screen. Otherwise unchanged: outgoing copies the composed
  translation and swaps a fixed direction; incoming pins English →
  French (even from Auto-detect) and does not copy; both install the
  reply-thread pair; Situation is never touched.
- **Quick translate of incoming French now arms "Reply to this" instead
  of copying the English.** v1.60 auto-copied whatever main translation
  arrived, which for a French → English result put the *English* on the
  clipboard, not something you paste into the chat. A second flag,
  `_quick_incoming_reply`, set beside `_auto_copy_on_deliver`, routes an
  accepted French → English delivery (input still equal to the snapshot,
  as before) through `_apply_reply_turn(True)`: direction pinned to
  English → French, the turn remembered, the source cleared, the
  clipboard left alone, status "Ready to reply.". An English → French
  Quick translate is unchanged: it still auto-copies the French and
  reads "Copied.".
- **The two flags always travel together.** `_clear_quick_followup()`
  replaces every former `_auto_copy_on_deliver = False` (Clear, Reopen,
  both correction paths, `_translate`'s refusals, error delivery and the
  success tail — including two sites in `_deliver_correction` that the
  note's insertion map did not list, found by searching for the
  assignment rather than trusting the list), and `_apply_reply_turn`
  ends with it, so a Quick translate intent can never ride in on the
  reply draft you are about to type.
- 7 new headless tests for `reply_should_keep_draft` (blank input, a
  shared trailing space, a one-character edit, no result on screen,
  non-strings, one rule for both shapes). 522 → 529 tests. The behaviour
  itself is UI-lifecycle, so it was verified live against a real
  `PlumeApp` under a virtual display with an isolated config directory
  and `translate` mocked (no network): 59 checks covering Reply with the
  source untouched / a draft typed / their next French line pasted / no
  result at all, Quick translate in both directions, a correction
  refusal, a backend error, a Clear while a request is pending, and text
  typed during the round trip (none arms, copies or pins, and both flags
  end cleared). The same scenarios run against v1.62 fail exactly where
  intended — Reply empties the draft and Quick translate copies the
  English without pinning.

## v1.64 — Speak remembers what it said

Second of the four notes_027 versions, kept out of the Reply change on
purpose. The comment beside the speech-rate constants says a slower
rate costs "no extra ElevenLabs call", but that only held for audio
already in flight: pressing Speak again, or changing the rate and
pressing Speak, synthesised the same sentence a second time (a second
charge, a second delay, and a second copy of the text leaving the
machine).

- **A small in-memory PCM cache.** Three pure helpers beside
  `speech_rate_from_label`: `speech_cache_key(voice_id, model_id, text)`
  (voice and model fall back to the shipped defaults, so a blank voice
  setting and the explicit default share one entry; the playback rate is
  deliberately *not* part of the key), `remember_speech_pcm(cache, key,
  pcm, limit=SPEECH_CACHE_LIMIT)` and `lookup_speech_pcm(cache, key)`.
  The list is newest-last and capped at eight clips; remembering returns
  a new list rather than mutating the one it was given, empty or
  non-bytes audio is never stored, and a repeated key takes one slot.
- **What is stored is the raw 16 kHz PCM**, not a WAV. The slow-rate
  trick is only a different WAV frame rate, so `_speak` re-wraps the
  cached PCM with `pcm_to_wav_bytes(…, sample_rate=speech_sample_rate(
  rate))` at whatever rate is selected *now* — a replay at 0.8× is the
  same audio as the first play, just labelled slower.
- **A hit happens before the API-key and privacy checks.** A replay
  sends nothing anywhere, so it needs neither a configured key nor the
  privacy notice; a miss still goes through both exactly as before
  (missing key → the same advisory, declined notice → no request). A hit
  bumps `_speech_request_id` so an older in-flight clip cannot land on
  top of it, and reports the fixed status "Speaking again.".
- **The worker now returns the PCM and the Tk thread wraps it.**
  `_deliver_speech` stores the clip, then plays it, so the cache is only
  ever mutated on the UI thread and needs no lock. A stale delivery
  (Clear, Reopen, close or a newer Speak happened first) is dropped
  before it can be stored, and an error stores nothing.
- **Clear, Reopen from History and closing the window empty the cache**
  next to the existing `_speech_request_id` bump, so audio never
  outlives the working session it belongs to. It is never written to
  disk, to the config or to history.
- **Privacy:** the key contains the spoken text, so the cache is never
  formatted into a status line, title, advisory or error; the only new
  string is the fixed "Speaking again.".
- 14 new headless tests (`TestSpeechCache`: the key has no rate input
  and falls back to the defaults, remembering does not mutate its input,
  the ninth distinct clip evicts the oldest, a repeated key keeps one
  slot, empty and non-bytes audio store nothing, malformed entries are
  ignored, a bad limit falls back, and cached PCM re-wraps at every
  offered rate without losing a frame). 529 → 543 tests. Verified live
  against a real `PlumeApp` under a virtual display with an isolated
  config directory, `call_elevenlabs_tts` replaced by a counting fake
  and playback recorded (61 checks): first Speak stores raw PCM; replays
  at 0.8×, 0.75× and Normal make no further call and carry the right
  frame rate; a replay works with no key and no privacy acknowledgement
  and shows no dialog; a miss without a key still shows the missing-key
  advisory; a different voice is a different clip; Clear, Reopen and
  close empty the cache; the ninth distinct text evicts the first; a
  stale delivery after Clear and an older clip superseded by a newer
  Speak are neither stored nor played; an error shows only the safe
  message and caches nothing. Run against v1.63 the same replay makes a
  second network call.

## v1.65 — Speak gets its own cancel

Third of the four notes_027 versions. `call_elevenlabs_tts` has honoured
a `_cancel_event` since v1.59 (it checks before every attempt and waits
with `Event.wait`, so a set event wakes a backoff at once), but `_speak`
never passed one, and the docstring said so. A Speak that hit a 429 with
a `Retry-After` therefore slept through the whole pause after Clear,
Reopen or close, and then made the next request anyway — one more call,
and one more copy of the text sent — before its result was thrown away
by the stale-id guard.

- **`self._speech_cancel` and `_new_speech_cancel()`**, beside
  `_http_cancel` / `_new_http_cancel()` and the same shape (set the old
  event, install and return a fresh one). Deliberately **independent**
  of `_http_cancel`: `_translate` and `_correct_then_translate` call
  `_new_http_cancel()` every time, so sharing one event would have
  cancelled a Speak whenever a translation started, and a translation
  whenever a Speak started.
- **Wired at the abandon paths:** right after the existing
  `_speech_request_id += 1` in `_clear`, `_on_close_destroy` and
  `_reopen_history_entry`; on a cache-hit replay (so an older Speak's
  backoff cannot deliver over the replay); and on the network path of
  `_speak`, where the request id is bumped, as
  `snapshot["_cancel_event"] = self._new_speech_cancel()`. A missing API
  key or a declined privacy notice still returns *before* any bump, so
  it does not cancel a Speak that is already in flight (the v1.59 M2
  rule, now covering the event as well as the id).
- **No new wording.** The retry status stays "Retrying speech (n of
  m)…", the cancelled worker's `BackendError("The request was
  cancelled.")` is dropped by `_deliver_speech`'s stale-id guard and never
  shown, and neither carries the spoken text. As with Translate, a
  `urlopen` already blocked in a read still runs to its timeout:
  cancellation stops the *next* retry and the clip being stored or
  played; it does not claim to abort a blocked socket.
- Stale text corrected: the comment in `_speak` and the
  `call_elevenlabs_tts` docstring both said Speak has no cancel event;
  `_reopen_history_entry`'s docstring now mentions both events.
- 6 new headless tests in `TestElevenLabsTTS`, the `_http_post_json`
  cancel tests' counterparts (event already set → no `urlopen` and the
  fixed message; set during an attempt → one request and no retry status;
  the message never contains the spoken text; an unset event changes
  neither the retry count nor the status callbacks; a real-clock
  loopback test where a `Retry-After: 2` backoff wakes in under a second
  with exactly one request; and a loopback test of the Speak-supersedes-
  Speak case, where the older call is cancelled mid-backoff while a newer
  one succeeds). 543 → 549 tests. Verified live against a real
  `PlumeApp` under a virtual display with an isolated config directory
  (52 checks): the worker receives `_speech_cancel`, never
  `_http_cancel`; Clear, Reopen, close, a newer Speak and a replay each
  set the previous Speak's event and leave the new one unset; a Translate
  and a Speak in flight at once complete independently in either order; a
  missing key or declined notice cancels nothing; and, with the real
  `call_elevenlabs_tts` and a 503 + `Retry-After: 5` server stand-in, the
  status reads "Retrying speech (2 of 4)…" and Clear returns the worker
  in well under a second with no second request, nothing played and no
  advisory. The same end-to-end Clear against v1.64 leaves the worker
  asleep.

## v1.66 — Shift-click chips insert the full form; Export meaning checks

Last of the four notes_027 versions, closing the two study/texting gaps
it left open. The texting chips only ever inserted the abbreviation
(`stp`, `cad`), although the friendly full forms (`s'il te plaît`,
`c'est-à-dire`) were already in `SLANG_CATALOGUE` and never reached the
caret. And a favourite's five alternatives and their English meaning
checks sat inside one Anki "Back" blob, so "what does this alternative
actually mean?" could not be drilled as a card of its own.

- **Shift-click on a chip inserts the full form.** New pure helper
  `texting_insert_text(term, expanded=False, catalogue=SLANG_CATALOGUE)`
  returns the raw term by default and the catalogue's stripped expansion
  when `expanded` is true: `stp` → `s'il te plaît`, `rdv` →
  `rendez-vous`, `cad` → `c'est-à-dire`, `bcp` → `beaucoup`, `pcq` →
  `parce que`, `pk` → `pourquoi`. An unknown, empty or non-string term
  raises `ValueError("Choose a catalogue term.")`, and an expanded
  request on a row with a blank expansion raises `"That shortcut has no
  expanded form."` — fixed text that never echoes the term.
  `_insert_texting_shortcut(term, expanded=False)` hands the result to
  the existing `_insert_slang_source`, so the English-direction refusal,
  the character limit and the word-boundary spacing apply to both forms
  unchanged: Shift does not let French into a forced English source.
- **The chips drop their `command=`.** Each chip now binds `<Button-1>`
  to `_on_texting_chip(event, term)`, which reads Shift from the Tk
  state bit (`event.state & 0x0001`), inserts, and returns `"break"`.
  CustomTkinter's `bind` adds to the button's own click handling rather
  than replacing it, so a chip that kept a `command=` as well would fire
  twice, and a Shift-click would insert the abbreviation and then the
  full form. Caps Lock, Ctrl and Alt on their own do not expand; Shift
  together with Ctrl or Caps Lock does. Shift-click needs a keyboard
  Shift: without one the chips behave exactly as in v1.61.
- **A grey "Shift: full form" hint** ends the same chip row, so there is
  no new row. Measured, not guessed: at the 1000×600 floor the left pane
  is 482 px wide (458 usable inside its padding) and the chip row
  requests 425 px, with the hint's right edge at 425, so neither
  fallback the note allowed (chips at width 40, then "Shift: full") was
  needed. At 1180×760 the pane is 572 px (548 usable) and the request is
  the same 425. Screenshots at both sizes show the row on one line with
  nothing clipped.
- **Export meaning checks.** Three pure helpers beside
  `export_history_to_markdown`. `iter_meaning_check_rows(entries)`
  yields `(translation, english_meaning_check)` for each usable
  alternative, in entry order then variation order, skipping a blank or
  non-string side and any malformed entry or variation. It never yields
  the main translation: the contract gives the main no meaning check,
  and inventing one would put the source phrase on the back of a card.
  There is no de-duplication — two starred conversations that share a
  line are two cards, and Anki's own duplicate check is the place to
  merge them. `export_meaning_checks_tsv(entries)` writes
  `front<TAB>back` per row through `_export_field`, so a tab or newline
  cannot break a note boundary: no header, no third column, no trailing
  newline. `export_meaning_checks_markdown(entries)` writes the heading
  `# Plume — meaning checks` and then `- front — *back*` lines.
  `export_history_to_tsv` and its `<br>` join are untouched, and a new
  byte-for-byte golden test pins that.
- **A fourth History button, on a second row.** "Export meaning checks"
  (width 180, row 1, column 0, `pady=(8, 0)`): row 0 already holds three
  buttons at 220, 160 and 140 px and is about as wide as the dialog's
  560 px minimum, so a fourth beside them would clip.
  `_export_meaning_checks` reloads history from disk first and uses
  **favourites only** — not the visible, filtered list: a search must
  not silently shrink a study deck (Export visible stays the filtered
  path for the full-card export). With nothing to export it says "You
  have no favourited meaning checks to export yet." and never opens the
  save dialog. Otherwise the dialog offers Anki TSV (`.tsv`, the
  default) or Markdown (`.md`) and the extension picks the writer; a
  failed write says only "Could not write the export file."; success
  says "Exported N meaning check(s) to <path>." — N counts cards, not
  entries, and the path is the one the user chose. No phrase appears in
  any title, message or status line. A favourite is kept by
  `normalise_history_entry` with whatever alternatives it has (even
  none), whereas a non-favourite needs exactly five clean ones or
  `load_history()` drops it, so the export can meet a favourite with
  fewer than five and simply contributes the pairs it has. Layout
  checked at 560×480 and 640×680: the new button sits at (16, 84),
  180×28, fully inside the dialog, and row 0 is where it was (Clear
  history at 16,48 · Export favourites 244,48 · Export visible 412,48).
- **One deliberate deviation from the note.** `texting_insert_text`
  sits after `slang_insertion`, not after `TEXTING_SHORTCUTS` as the
  insertion map says: its default argument is `SLANG_CATALOGUE`, which
  is defined further down the module, and a default is evaluated when
  the `def` runs, so the earlier spot would raise `NameError` on import.
- No example-config edit and no history-schema change. 24 new headless
  tests: `TestTextingInsertText` (10: the raw term by default for every
  chip, the six expansions pinned, fixed messages that never echo a
  planted term, a blank, whitespace or `None` expansion failing only
  when expanded, a custom catalogue honoured, boundary placement through
  `slang_insertion`), `TestMeaningCheckExport` (13: two columns with no
  header and no trailing newline, tabs and newlines flattened, the main
  translation, source and situation never present, entry-then-variation
  order, no de-dupe, unusable alternatives skipped, an atypical count
  contributing what it has, malformed input yielding nothing, no
  mutation, the Markdown form) and the TSV golden test in
  `TestExportFavourites`. 549 → 573 tests. Verified live against a real
  `PlumeApp` under a virtual display with an isolated config directory
  (82 checks): all six chips carry no command; plain and Shift clicks
  through both the label and the canvas, and a synthesised
  `<Shift-Button-1>`; the modifier combinations above; word-boundary
  spacing; the refusal in a forced English → French direction with its
  fixed advisory and nothing inserted; the character-limit refusal of
  the long form; no planted phrase on the advisory, status bar or any
  title; focus back in the message box; and, for the export, the empty,
  no-usable-pair, search-filter-ignored, TSV, Markdown, other-extension,
  cancelled, write-error and reload-before-export cases, with Export
  favourites and Export visible unchanged. The same script against v1.65
  fails every Shift, hint and no-command check (a Shift-click inserts
  `stp`) before stopping at the missing `_on_texting_chip`.

## v1.67 — Glossed emote menu; captions that finish

From notes_028. Casual sign-off and MMORPG chat already show an English
gloss in their dropdowns (`tkt (don't worry)`), but the emote picker
listed bare marks, so `mdr`, `ptdr` and `jpp` told an English reader
nothing. And the grey captions beside the two slang pickers ran off the
card: notes_028 saw them cut at "…meaning, not ju" and "…chat term,
app", and measured live at the 1000×600 floor the v1.66 rows ask for
543 px and 574 px of the 411 px the card gives them.

- **The emote menu carries a gloss.** `FINISHING_TOUCH_CATALOGUE`
  replaces the flat tuple with `(raw, gloss)` pairs, the shape Casual
  sign-off and MMORPG chat already use, and `FINISHING_TOUCHES` is now
  derived from it: still `None` plus the fourteen raw marks, in the same
  order, so nothing else that reads it changes. New
  `finishing_touch_display()` and `finishing_touch_raw_value()` are thin
  wrappers over the shared `_glossed_display` / `_glossed_raw_lookup`,
  with the same contract as the sign-off and MMORPG pairs: a mark or its
  full label resolves to the mark, and anything else — a bare gloss, a
  gloss on the wrong mark, a blank, a non-string — resolves to the
  "None" sentinel, so a gloss can never reach the clipboard. The
  glosses: `:)` smile, `:p` playful, `;)` wink, `xD` laughing, `mdr`
  LOL, `ptdr` ROFL, `jpp` had enough, `:D` big grin, `:/` unsure, `:'(`
  tearful, `:o` surprised, `^^` happy, `<3` love, `xo` kisses.
- **One seam on the copy path.** `_current_touch()` now passes the emote
  variable through `finishing_touch_raw_value()`, as it already did for
  the other two pickers. The primary card, Copy, Copy all, Copy HTML, a
  variation card's Copy and the diff export all read the touch there, so
  they all compose the bare mark; Speak reads the raw translation and
  never sees a touch. Clear and History reopen still reset the variable
  to "None", which is both the raw and the display value, so they needed
  no change. No gloss is stored in history or sent to either backend.
- **A fixed-width button.** `width=156, dynamic_resizing=False` (was
  110). CTkOptionMenu's default would grow the closed button to fit the
  chosen label — ":) (smile)" is wider than "None" — and shove the
  speech-rate menu along. The text area is now 119 px and the longest
  label, "jpp (had enough)", takes 96 px. The open list is a native Tk
  menu that sizes itself (131 px, was 101) and may cover Copy and Speak
  while it is open, which the note accepted. At the floor the row now
  asks for 382 px of 411 (was 336); the rate menu stays pinned to the
  right edge (x = 321, 90 px, "Normal" in full) with 37 px between the
  two menus.
- **Captions that finish.** `SIGNOFF_ROW_HINT = "Changes meaning"` and
  `MMORPG_ROW_HINT = "Game-chat tag"` replace the two sentences. At
  1000×600 the sign-off caption has 118 px and needs 102, and the MMORPG
  caption has 121 and needs 84; both rows fit at 1180×760 as well.
- **One deliberate deviation from the note.** The note proposed "Meaning,
  not just tone" for the sign-off caption, with a 24-character cap.
  Measured, that string needs 125 px of the 118 px the caption has at the
  floor, so it still clips by about 7 px. That fails the note's own
  acceptance check (fully visible at 1000×600), and a 24-character cap
  would admit other strings that clip too. "Changes meaning" keeps the
  point of the separate picker — a sign-off changes the meaning, not just
  the tone — and the tests cap both captions at 20 characters. The
  note's fallback was to drop the caption altogether; either way it is a
  one-line constant. Measured with CustomTkinter's bundled Roboto 13
  under a virtual display, not Windows ClearType, so the tighter caption
  keeps 16 px of slack for a rendering difference.
- No example-config edit and no history-schema change. 16 new headless
  tests in `TestGlossedFinishingTouch` (the display of three marks and of
  None; the flat tuple derived from the catalogue; a gloss on every mark
  with the mark leading its label; unique labels, at most 18 characters
  so they fit the fixed button; the raw value reversing the display,
  accepting a bare mark, and sending a bare gloss, a stale label, a
  gloss on the wrong mark, a blank and a non-string to None; only the
  mark composed and copied, never the gloss; captions at most 20
  characters; and neither old sentence being a constant or anywhere in
  `plume.py`). 573 → 589 tests. Verified live against a real `PlumeApp`
  under a virtual display with an isolated config directory (44 checks):
  the menu and the native list show the 15 glossed labels in order; for
  each of the 14 marks the closed button stays 156 px wide with the rate
  menu where it was and nothing clipped; and the primary card, Copy, a
  variation's Copy, Copy all, Copy HTML and Speak carry the bare mark
  (Speak: nothing appended) and never the gloss; all three pickers
  together copy `:) tkt gg`; a bare gloss and a gloss on the wrong mark
  resolve to nothing while a bare mark still works; Clear and History
  reopen put the menu back on "None", button text included; and both
  captions fit at 1000×600 and 1180×760. With
  `finishing_touch_raw_value` deliberately broken to pass the label
  through, 13 of the 44 fail.

## v1.68 — Quick translate protects drafts and the clipboard

From notes_029, whose six parts were each checked against the code first
(the note says it was written without source access). Reply to this,
slow pronunciation, Export favourites, the texting palette and bounded
retries all have earlier counterparts (v1.51/v1.57/v1.63,
v1.58/v1.64/v1.65, v1.13/v1.62/v1.66, v1.61/v1.66 and v1.27/v1.38/v1.59),
so a real gap in any of them is its own version. Quick translate
(v1.60/v1.63) existed too, but two of the protections the note asks for
did not: a different unsent draft was replaced without a word, and the
automatic copy ran whatever had happened in the seconds since the chord
— it overwrote something you had copied meanwhile, and copied a result
for a direction or Situation you had since changed.

- **An unsent draft is no longer replaced silently.** New pure helper
  `quick_translate_needs_confirm(input_text, result_source, clip)`, built
  on `reply_should_keep_draft`: blank is not a draft, the text of the
  result on screen is not a draft, and a draft that already equals the
  clipboard (ignoring surrounding whitespace) loses nothing. Anything
  else asks `messagebox.askyesno` before the box is replaced. The title,
  prompt and cancel status are fixed constants
  (`QUICK_REPLACE_DRAFT_TITLE`, `QUICK_REPLACE_DRAFT_PROMPT`,
  `QUICK_KEPT_DRAFT_STATUS`), so neither the draft nor the clipboard text
  reaches a dialog or the status bar. Yes carries on exactly as before;
  No keeps the draft, sends nothing, arms nothing and says "Quick
  translate cancelled. Your draft was kept.". `_quick_confirm_open`
  ignores a second press while the dialog is up: the system-wide chord
  is read by a Tk timer, which keeps firing under a modal dialog.
- **The automatic copy stands down when things moved on.** `_quick_clip`
  holds the text read at invocation. When the delivery arrives, after
  the existing stale-result guard (which already drops a request that
  was cleared, superseded or whose source was edited), `_deliver`
  re-reads the clipboard and asks the new pure
  `quick_copy_skip_reason(clip_at_invoke, clip_now, context_at_dispatch,
  context_now)`, where a context is `(direction, Situation)`. None
  copies as before and reads "Copied.". Otherwise nothing is written,
  the result still shows, and the status says "Translation ready.
  Clipboard changed; automatic copy skipped." (the note's wording) or
  "Translation ready. Direction or Situation changed; automatic copy
  skipped.". An empty or unreadable clipboard, or no baseline at all,
  counts as changed: Plume does not write over what it cannot show is
  still its own. A settings change is reported ahead of a clipboard
  change.
- **Direction comes from the dispatch snapshot.** `_translate` now hands
  `_deliver` the snapshot's `default_direction`. Reading `direction_var`
  at invocation instead would have skipped every Quick translate in
  Correct-then-translate mode, because `_deliver_correction` pins
  English → French between the chord and the dispatch.
- **Nothing leaks.** `_clear_quick_followup()` resets `_quick_clip` along
  with the other two flags, so a manual Translate never inherits a
  baseline, and Quick translating incoming French still arms Reply to
  this rather than copying.
- **Deliberate deviations from the note.** No `QuickCopyIntent` /
  `should_auto_copy` pair: the intent already is two request-scoped flags
  plus `_request_id` / `result_is_stale`, so one clipboard baseline and
  one pure comparison finish the job without a second mechanism to keep
  in step with the first. No new Ctrl+Shift+Enter binding: the note says
  to reuse an existing owner, Ctrl+Shift+T and the opt-in system-wide
  chord are that owner, and Ctrl+Shift+Enter already means Correct
  English. Refusing while a request runs, size validation, the
  path-to-Paste detour and the privacy gate were already in place
  (v1.60), and every refusal already clears the flags (v1.63). A
  successful copy still reads "Copied." rather than "Translation
  copied", which the note offered only as an example.
- No config or history-schema change. 18 new headless tests in
  `TestQuickTranslateProtections` (a blank box, the result on screen, a
  draft that differs from or equals the clipboard, case sensitivity, a
  blank or non-text clipboard, non-text input; the copy going ahead when
  nothing moved and standing down for a changed, empty or unread
  clipboard, a missing baseline, a direction change or a Situation
  change, with settings reported first; every reason being None or one
  of two fixed lines that never carry a clipboard or Situation sentinel;
  the fixed strings having no format fields; the note's clipboard
  wording; and the lines reaching the status bar unaltered). 589 → 607
  tests. Verified live against a real `PlumeApp` under a virtual display
  (Linux, customtkinter 5.2.2, not Windows) with an isolated config
  directory, `run_backend` mocked and `urlopen` poisoned, so nothing
  touched the network (45 checks): an empty box translates and copies
  with no dialog; a draft asks once, Yes replaces it, No keeps it with
  no request and the fixed status, and neither dialog text echoes the
  draft or the clipboard; a draft equal to the clipboard, or still equal
  to the last result's source, asks nothing; a second chord while the
  dialog is open adds no second dialog or request; a clipboard changed
  or emptied while the request runs is
  left alone with the skip status, as is the same after a direction
  flip, a Situation edit or a source edit; a manual Translate never
  touches the clipboard; incoming French still arms Reply; and nothing
  skips falsely — Correct-then-translate, a non-empty Situation, a fixed
  direction, a Situation typed and reverted, and a chord straight after
  a skipped one all copy. Against v1.67 the same scenarios show the
  draft replaced without a word and the clipboard overwritten; with
  both helpers neutralised, 13 of the 34 main checks fail. The
  system-wide chord's native thread was not exercised: both chords land
  in `_quick_translate_from_clipboard`, which the scenarios call
  directly.

## v1.69 — Exports write atomically and Markdown shows text as text

From notes_029, part 3 (Export Favourites). The feature itself exists
(v1.13 Anki TSV and Markdown, v1.62 Export visible, v1.66 Export meaning
checks) and history already keeps everything the note's adapter needs,
so there is no migration. Two of the note's safety requirements were not
met. Every export was written with a plain `open(path, "w")`, which
truncates the file first, so a failure part-way through (a full disk, a
crash) could leave a study deck empty or half-written. And the Markdown
exports wrote submitted phrases and model replies raw, so a phrase such
as `# Heading`, `[link](…)`, `<script>` or a code fence turned into a
heading, link, HTML or code block in the rendered sheet.

- **Exports are written atomically.** New `write_text_atomic(path,
  text)` writes UTF-8 to a temporary file beside the target, flushes and
  fsyncs it, then `os.replace`s it over the target: the same sequence as
  `save_config` and `save_history`. If the write, the fsync or the
  replace fails, the temporary file is removed and any existing file is
  exactly as it was. All four write sites use it, inside their existing
  `except OSError`, so the fixed messages ("Could not write the export
  file." and "Could not write the comparison file.") are unchanged and no
  path, phrase or exception text reaches the UI. The temporary name is
  `<path>.<8 hex>.tmp`, created with mode `"x"`, rather than
  `save_history`'s fixed `.tmp` sibling or `NamedTemporaryFile`: here the
  path is chosen by the user, so a fixed sibling could be a file of
  theirs (exclusive create refuses instead of overwriting it), and
  `NamedTemporaryFile` would give the exported file its private 0600 mode
  on POSIX. Text mode and newline handling are as before.
- **Markdown shows submitted and translated text as text.** New pure
  helper `markdown_safe(value, multiline=False)` puts a backslash before
  the characters CommonMark and GitHub-style Markdown give a meaning to
  (`` \ ` * _ [ ] < > # | ~ ``), before an `&` only where it would start an
  entity (`&amp;`, `&#35;`), and before a line-leading `-`, `+` or `=`, a
  bare table divider such as `:-:`, and the `.` or `)` of a leading
  `1.` / `1)`. Only those characters change, so ordinary French and
  English come back byte-for-byte (`1.5 kg`, `v1.2`, `Tom & Jerry`,
  `AT&T`, `:-)`, accents, non-breaking spaces, emoji). Single-line mode
  (headings, list items, labels) joins the stripped non-empty lines with a
  space; `multiline=True` (the study sheet's Source and Main translation)
  keeps each line and escapes it separately. The History sheet, the
  meaning-check sheet and the current-result sheet send every submitted or
  translated field through it — source, Situation, main translation, each
  alternative and its meaning check — and leave their own headings and
  labels alone.
- **The Diff section can no longer break out of its fence.** The
  current-result sheet fenced its Diff with a fixed three backticks, so a
  fence line that the source and the translation share (a context line in
  the diff) closed it early and what followed was no longer inside a code
  block. The standalone comparison (v1.23) already sized its fence longer
  than any backtick run it contains; that rule is now one helper,
  `_diff_fence`, used by both. The diff is still computed from the raw
  text, so it shows exactly what was submitted.
- **Deliberate deviations from the note.** The Anki TSV is unchanged. The
  note asks for "escaped HTML with `<br>` line breaks"; the `<br>` joins
  are v1.13's, and `export_history_to_tsv` is pinned byte-for-byte by a
  golden test. Escaping `&`, `<` and `>` there would change the Front of
  every phrase containing them, so re-importing an older deck would stop
  matching its notes and add duplicates, and it is only right when Anki
  imports the file with HTML enabled, which depends on the import
  dialog's "Allow HTML in fields" or an `#html:true` header. Anki's
  documentation could not be reached from this sandbox to settle that (the
  request was held for approval), so the TSV, and the `#separator` /
  `#html` / `#columns` headers, wait for a decision: if you import with
  HTML on and want phrases containing `<` or `&` to survive, that is a
  small version of its own. No worker thread: the files are a few
  kilobytes, and moving a write off the main thread would bring Tk's
  thread-safety rules (dialogs, status updates) for no visible gain. No
  preset filename such as `plume_favourites.tsv`: the save dialogs
  already ask before overwriting, and the extension chosen there selects
  TSV or Markdown, which a preset name would pre-empt. No "protected text
  blocks" in place of escapes: that would replace the sheets' existing
  shape, which tests and previously saved sheets rely on, and escaping
  meets the requirement that submitted markup cannot become a heading,
  link or embedded HTML element.
- **Residuals, stated plainly.** A GitHub-style viewer may auto-link a
  bare URL in a phrase (nothing is fetched, and the link can include our
  escape backslashes). A lone surrogate in the text raises
  `UnicodeEncodeError`, which the callers' `except OSError` does not
  catch; that was true before, but the old file now survives it. If the
  process is killed mid-write a stray `<path>.<8 hex>.tmp` can remain. On
  Windows, `os.replace` onto a file another program has open raises
  `PermissionError`, which lands on the existing fixed message.
- No config or history-schema change. 31 new headless tests (607 → 638):
  `TestWriteTextAtomic` (11: exact UTF-8 bytes, a newline round trip, an
  existing file replaced without a leftover temp, a failed fsync and a
  failed replace each keeping the old file and removing the temp, a
  directory in the way and a missing folder raising `OSError` with
  nothing created, a lone surrogate keeping the old file, an unrelated
  `out.md.tmp` neighbour left alone, a temp-name clash refusing rather
  than deleting the other file, and the temp sitting beside the target),
  `TestMarkdownSafe` (8: plain text unchanged, each special character
  escaped, Windows path backslashes doubled, only entity-like ampersands
  escaped, the line-start escapes, single-line joining, multiline mode,
  empty input) and `TestMarkdownExportSafety` (12: the three exporters
  byte-identical to v1.68 for ordinary text, exact hostile output for
  each, hostile phrases leaving the document skeleton the same as a
  plain-word control's, a marker present and escaped everywhere it is
  submitted, the diff fence never closed early, `_diff_fence` itself, the
  TSV exporters deliberately unescaped, and no input mutated). Ordinary
  text exports byte-for-byte as in v1.68 (30 Markdown comparisons, plus
  the TSV and the comparison export), and 13 of 13 deliberately broken
  variants of the helpers fail at least one new test. The three Markdown
  exporters were also run through markdown-it-py (CommonMark with tables
  and strikethrough, raw HTML on) and GitHub's cmark-gfm (raw HTML on):
  116 hostile phrases plus random strings of markup tokens, about 68,000
  to 89,000 checks per seed over eight seeds, none failing. For each
  phrase the document skeleton equals a plain-word control's and each
  field renders as its own text (cmark-gfm: skeleton only, with a bare
  URL allowed to become a link); the harness fails when the escaping is
  deliberately weakened. Verified live against a real `PlumeApp` and
  `HistoryDialog` under a virtual display (Linux, customtkinter 5.2.2,
  not Windows) with an isolated config directory, a stand-in save dialog
  and a fake backend (37 checks): the sheet and the comparison written
  with no temp file left; a hostile source inert before the Diff, with
  only the sheet's own headings; a forced `os.replace` failure at each of
  the four sites keeping the old file, showing the fixed message and
  leaving no temp; a missing folder; cancel; and all three History
  exports in both formats, written and failing safely. With a plain
  overwrite put back at the four sites, 13 of the 37 fail.

## v1.70 — A reply marked "do not retry" is not retried

From notes_029, part 5 (bounded backend retries). Nearly all of it has
shipped: v1.27 (capped exponential backoff, `Retry-After` honoured as a
minimum inside a total-wait budget, Claude's 529 opted in at its own
call site), v1.38 (a certificate failure never retried, error bodies not
drained, cooperative cancel) and v1.59 (a fixed "Retrying (2 of 4)…"
status line with no phrase, URL or exception text in it, and the same
retry for Speak). One line of the note's policy was not met: "Respect
x-should-retry: false." A 429, 502, 503, 504 or Claude 529 carrying that
header was retried up to three more times anyway, waiting out the
backoff between requests, and a 429 with `Retry-After: 30` was waited
out in full before the next one.

- **The header now ends the retrying.** New pure helper
  `_server_forbids_retry(headers)` is true only when `x-should-retry` is
  `false`, in any case and with surrounding whitespace ignored; a
  missing, empty, unreadable or any other value is false, and it never
  raises. `_http_post_json` reads it with `Retry-After`, before the error
  body is closed, and the retry condition gained one clause (`and not
  server_forbids_retry`). A marked response is requested once: no
  backoff wait, no `on_retry` call (so no "Retrying…" status), and its
  `Retry-After` is not waited out. Claude and Ollama share the
  transport, so both get it.
- **The message is unchanged.** The reply ends in the same fixed text
  for its status as an exhausted one (`_friendly_http_message`), so no
  header value, body, URL or phrase reaches the UI, and "Please retry"
  still reads rightly: the header says that repeating the request now
  will not help, not that the service is gone for good.
- **Only `false` counts.** `true` does not widen the retry set: a 401,
  404 or other client error is never retried whatever the header says,
  and a retryable status with no header, or any other value, is retried
  exactly as before.
- **Deliberate deviations from the note.** Three attempts from 0.5
  seconds: declined. Four attempts from 0.6 s (capped at 8 s, with 30 s
  of total waiting) and the "(2 of 4)" copy are v1.27/v1.59 behaviour
  with tests behind them, and the note names no failure the change would
  fix. An unhinted 429 is still retried: an ordinary rate limit is the
  common 429 and clears within seconds, the spend-cap 429 the note
  worries about is what the header is for (so it is now honoured instead
  of guessed at), and being wrong costs a few seconds before an error
  that was coming anyway. Timeouts are still retried like any dropped
  connection: Claude's socket timeout is 60 s and a reply here is five
  short variations, so a timeout looks more like a stalled connection
  than a long generation, and being wrong costs a repeated request,
  bounded by the attempt count and the wait budget, which Clear stops
  between attempts. If you would rather risk a missing translation than
  a repeated one, the note's "only when brief" rule is a small version
  of its own. The ElevenLabs Speak loop is untouched: the header is the
  Claude API's, and the note is about the translation transport.
- No config or history-schema change. 14 new headless tests (638 → 652)
  in `TestShouldRetryHeader`: the helper (any case or padding; every
  other value, a missing header and a `.get` that raises), a marked 503
  requested once with no sleep, no retry callback, the error body closed
  and the usual message free of the reply, a marked 429 ignoring its
  `Retry-After`, an unmarked or `true` 503 retried as before, the header
  name read case-insensitively from a real `HTTPMessage`, the opted-in
  529, a 401 unchanged with either value, only the marked response in a
  sequence stopping it, and four real-socket loopback tests (a marked
  and an unmarked 503 through `_http_post_json`, a marked and an
  unmarked 529 through `call_anthropic`). 12 of 12 deliberately broken
  variants (header ignored, helper always false, case-sensitive, padding
  not stripped, any value or any substring counting, inverted, the wrong
  header name, exceptions escaping, `true` widening the set, a 429 or a
  `Retry-After` exempted) fail at least one new test. Verified live
  against a real `PlumeApp` under a virtual display (Linux,
  customtkinter 5.2.2, not Windows) with an isolated config directory,
  Claude's and Ollama's endpoints pointed at a local server and any
  non-loopback request failing the run (32 checks): a marked 503 is
  requested once and shows the fixed message, no "Retrying" status and
  nothing from the reply; an unmarked 503 makes four attempts with the
  three retry statuses; two 503s then a success delivers the
  translation; a marked 429 with `Retry-After: 30` is one request and
  finishes inside three seconds; a marked 529 stops and an unmarked one
  does not;
  capitals and padding are honoured, `true` and an unknown value change
  nothing; a 401 is one request either way; and Ollama behaves the same.
  With the clause removed, 9 of the 32 fail: the marked cases, the 429
  among them still waiting.

## v1.71 — Touches stay with the result they were chosen for

From notes_029, part 4 (casual sign-offs and texting shortcuts). Most of
it has shipped: the texting chips work on the source before translating
and stand down on a forced EN→FR direction (v1.61, v1.66), and the
Casual sign-off picker has been a separate, labelled copy-time choice
since v1.14. The note's last paragraph was not met at copy time: "Allow
the French palette only when the selected translation belongs to a
validated French-target result. Reset the choice when a new result
appears; a transient default avoids accidentally carrying an apology or
reassurance into another conversation." The three finishing-touch
pickers (Emote, Casual sign-off, Game tag) were reset by Clear and by
Reopen from History (v1.2, v1.14) and by nothing else, so a "dsl" or
"tkt" picked for one message was still picked for the next: shown on its
card, copied with it and, because Quick translate copies for you, on the
clipboard before the result had been read. It also rode along on the
English reading of an incoming French message, and a French sign-off
could be composed onto an English-target result, where it means nothing.

- **A new result starts bare.** `_render_result`, the one place every
  result is drawn (a translation, a Quick translate, a Reply, Reopen
  from History, Undo Clear), now calls the new
  `_reset_finishing_touches()` just after it stops speech and before the
  card is drawn: all three pickers go back to None, so the card, Copy,
  Copy all, the exports and Quick translate's auto-copy start from the
  bare translation. Clear and Reopen from History keep their own call. A
  touch is still a copy-time choice and still never reaches Speak.
  "Use this" is not a new result, so the touch chosen for it stays on
  the variation adopted as the main translation, as before.
- **A sign-off needs a French-target result.**
  `signoff_applies_to(result)` is true only for a result whose
  `target_language` is French.
  `touch_for_result(result, emote, signoff, mmorpg_term=None)` is now
  the one place the app composes a touch, and for any other result it
  drops the sign-off, and only the sign-off. Picking one while the card
  holds an English reading, an older history entry with no stored target
  language (never guessed) or nothing at all is refused: the picker
  snaps back to None and the status bar says "Casual sign-offs apply to
  French translations only." That is a fixed sentence with no phrase in
  it, and transient like any status line: the next refresh, typing
  included, replaces it.
- **Deliberately not gated.** Emotes are language-neutral. Game tags are
  a mixed set typed as they are in French chat, and tagging each term
  with a language would be a catalogue change the note does not ask for.
  The row hint beside the sign-off picker ("Changes meaning") is
  untouched: that row is width-constrained, and the refusal says what it
  needs to in the status bar. The note's prefix and replace operations
  (tkt and dsl in front of the text, rdv and cad swapped in for a
  matching expression) stay declined for the reasons given in v1.61, and
  its drawer with a visible expansion is the glossed menu of v1.67.
- **One behaviour changes, and is easy to put back.** A touch picked
  *before* translating no longer survives into the translation: pick it
  once the result is on screen (the card and Copy follow at once). That
  is what the note asks for, and what stops a stale apology reaching the
  clipboard, but it does end "set it once and leave it". To restore it,
  remove the `_reset_finishing_touches()` call in `_render_result` (and
  the unit guard that pins it).
- No config or history-schema change. 19 new headless tests (652 → 671).
  `TestTouchForResult` (13): the gate true for French and false for
  English, for a missing, empty, odd or non-text target language and for
  a result that is not a dict; `touch_for_result` identical to
  `compose_finishing_touch` for a French result across all 3,780
  combinations of the three pickers; an English result losing only the
  sign-off, in every combination; the order emote, sign-off, game tag;
  real parsed results and history entries, a legacy one included; and
  the refusal note a short fixed sentence. `TestTouchWiring` (6 guards
  over the parsed source, since `PlumeApp` is not importable headlessly):
  `_render_result` resets before it draws the card, Clear and Reopen
  still reset, the reset sets all three pickers to their None values,
  only `touch_for_result` calls `compose_finishing_touch` and
  `_current_touch` calls it, the picker's handler checks the gate, snaps
  back once and reports through the status bar, and every picker change
  still refreshes the card. 35 of 35 deliberately broken variants fail
  at least one of them: the gate always or never true, inverted, loose
  about case, whitespace or substring, without its type check or reading
  the source language; `touch_for_result` keeping the sign-off, also
  dropping the emote or the game tag, ignoring the game-tag argument or
  swapping the order; the note emptied, unfinished or too long; the
  reset missing, late, partial or setting the wrong value; the copy path
  skipping the gate; and the picker's check, snap-back, refresh or note
  dropped, wrong or replaced with a literal. A first pass counted three
  of them killed only because the full-suite stage had errored on a file
  missing from the scratch copy; with both baselines asserted clean
  first they survived, and the guards were tightened until they died.
  Verified live against a real `PlumeApp` under a virtual display
  (Linux, customtkinter 5.2.2, not Windows) with an isolated config
  directory, a fake backend and any network request failing the run (57
  checks): a fresh result starts with the pickers on None and a bare
  card; a French result composes emote, sign-off and game tag in that
  order on the card and in Copy; a second French result starts bare
  again; the text Quick translate copies is bare after touches were
  chosen on the result before; an incoming French message's English
  reading is bare with nothing copied (Reply is armed instead), and the
  reply, translated in the direction Reply set, starts clean and then
  takes a French sign-off; an English result refuses a sign-off with the
  fixed note, leaves the emote and game tag alone, keeps its card and
  Copy bare and loses the note at the next keystroke, while choosing
  None is not a refusal; "Use this" keeps the touch; Clear, and Undo
  Clear, leave the pickers on None; Reopen from History takes a sign-off
  on a French entry and refuses it on an English one and on an older one
  with no target language; with nothing on screen an emote is harmless
  and a sign-off is refused; and every menu keeps all its options.
  Against the v1.70 code 26 of the 57 fail. Thirteen of the broken
  variants were also run against the same script and 11 fail it. The
  other two, the Reopen reset removed and the copy path skipping the
  gate, cannot be seen from the window, because the reset in
  `_render_result` and the picker's snap-back already stand in front of
  them; the headless guards are there for those.

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
