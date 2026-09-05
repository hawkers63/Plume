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
