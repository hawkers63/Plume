# Plume — French ↔ English conversation helper

Plume is a small Windows 11 desktop application that translates conversational
French and English in either direction. For every phrase it returns **one
faithful main translation** plus **exactly five natural alternatives in the same
tone**, each with a short English *meaning check* in brackets so you can see what
a French phrasing says before you send it.

It is built in the same practical style as Scriptorium: a dark, native-feeling
CustomTkinter interface, British English throughout, explicit privacy
information, no silent rewriting, and a choice of a cloud (Claude) or local
(Ollama) backend.

---

## What it does

- **Auto-detect** the input language, or force **English → French** /
  **French → English** for short or ambiguous phrases (`non`, `merci`, names,
  quotations, mixed-language messages).
- One primary translation that preserves meaning, register, tone, punctuation
  and intent — it never adds facts, softens commitments, or invents context.
- Five genuinely distinct alternatives (different word choice, idiom or word
  order — not punctuation-only variants), each with its English meaning check.
- **tu / vous** consistency and a language-confidence indicator.
- **French gender agreement** for both people in the conversation: separate
  **Me** (speaker) and **You** (addressee) controls on the toolbar, each
  *Feminine* / *Masculine* / *Avoid where possible*. Woman-to-woman chat is the
  default (Feminine / Feminine); explicit gender in the source always wins, and
  French → English never invents gender in the English.
- Placeholder protection for names, links, dates and `[Name]` / `{amount}`
  style markers, so they survive translation unchanged. A **Keep as-is** list
  in Settings extends this to your own names or terms (up to 20, 40
  characters each), matched longest-first so e.g. "Marie-Claire" is not
  swallowed by "Marie".
- A **Glossary** in Settings (up to 20 pairs) for terms that *should* be
  translated, just consistently — e.g. always "délai" for "deadline" —
  unlike Keep as-is, which never translates a term at all. A background-
  only prompt hint, same as tones/situation: the source text still wins.
- A copy button on every result, with a prominent **Copy main translation**;
  alternatives can be promoted with **Use this**, and the current result can
  be re-sent as new input with **Use as input**.
- Three optional, independent **finishing touches** appended only at copy
  time — never sent to the model, so the translation itself stays faithful:
  an **Emotes & Reactions** picker (`:)` `:p` `;)` `xD` `mdr` `ptdr` `jpp`),
  a **Casual sign-off** picker (`tkt`, `grave`) labelled as changing
  register and meaning, not just tone, and an **MMORPG chat** picker
  (`dispo`, `rez`, `bj`, `osef`, `oklm`, `aïe`) for online-gaming chat.
  Both slang pickers show an English gloss in brackets (e.g. "tkt (don't
  worry)") — only the term itself is ever appended, never the gloss.
- A **French slang…** reference window: search a local, curated catalogue
  of French terms and phrases (bilingual, accent/case-insensitive) by
  category, insert one straight into the message at your caret, copy just
  the raw French, or build a separate, freely editable **local draft**
  (with its own reading-time metrics and plain/HTML copy) for a
  translation whose subtleties don't fit a one-click picker — e.g. `bof`
  conveying indifference rather than a flat "terrible", or `bonsoir`
  greeting or parting depending on context. Nothing here is sent to the
  model or changes the translation itself.
- **Copy source** and **Situation presets** (Close friend, Formal work
  email, Neighbour, Appointment, Dating/chat) for faster back-and-forth,
  plus up to 12 of your own **saved situations** (Save…/Delete beside the
  menu) for a shortcut the built-in list doesn't cover, e.g. "Guild raid
  chat" or "School gate".
- **Open file…** imports a `.txt` or `.md` file (up to 2 MiB, UTF-8 or
  UTF-16) straight into the input box, asking before it replaces anything
  already there. Three more crash-safe ways in, none of them native
  Explorer drag-and-drop: `--import "path"` on the command line, an
  optional "Send to Plume" entry in Explorer's right-click menu (off by
  default, in Settings), and pasting a clipboard value that is itself a
  `.txt`/`.md` file path, which offers to open the file rather than
  inserting the path as text. No Word import either — a plain file
  picker was the safer, dependency-free choice for this app's Tcl/Tk
  build (see `ROADMAP.md`'s v1.18/v1.28/v1.32 entries).
- Optional local history with favourites — including a one-click
  **☆ Favourite** on the main panel — per-entry **Copy** / **Reopen** /
  **Delete**, "clear history" preserving favourited entries, and
  **Export favourites** to an Anki TSV deck or Markdown study sheet.
- Optional ElevenLabs **Speak** buttons for pronunciation help, with a
  **Stop** button and a **Slow** playback toggle (a slower, lower-pitched
  playback rate — not studio-quality time-stretching, but a genuine aid
  for catching liaisons and elisions).
- **Correct English** (Ctrl+Shift+Enter) fixes spelling, grammar and
  necessary punctuation in a quickly-typed English draft — never
  paraphrasing, translating or changing register — then automatically
  translates the corrected text into French, so typos are never
  faithfully carried into the French output.
- Optional **sign-in autostart** and a **system tray icon** (needs
  `pystray` and `Pillow`): launch quietly at Windows sign-in, start
  minimised, and close-to-tray instead of quitting — a conversation
  helper that doesn't need to be relaunched and re-parked every session.
- **Conversation presets:** save the toolbar's direction, French form,
  Me/You gender agreement, situation and tones as a named preset (a
  "Presets…" menu plus Save/Delete beside the toolbar's You control) —
  switch between a few regular conversations in one click. A save is
  refused outright (with an explanation) on a duplicate name or past the
  12-preset cap, rather than silently discarding anything.
- **Register tones:** up to three background tones (Warm, Terse,
  Playful, Precise, Courteous, Direct, Reassuring) beneath Situation,
  the same non-authoritative background context, never overriding the
  source text's own meaning. Conflicting tones (e.g. Terse + Playful)
  resolve automatically, keeping whichever one you just chose.
- **Writing profile** (Mode / Strength / Role), beneath Tones: an
  optional second layer on top of presets. Strength (Source-led / Light /
  Balanced) and Role (General / Friend / Colleague / Customer) add a
  background register/relationship hint only once Strength is raised
  above Source-led — never assuming an identity or authority the source
  text doesn't establish. Mode (Translate / Correct English then
  translate) changes which pipeline Translate/Ctrl+Enter runs, but only
  on an explicit click — selecting a Mode, or applying a preset that
  restores one, never itself starts a request. Saved on conversation
  presets alongside direction, form, tones and situation.
- **Remember tones and profile**, beneath Writing profile: a one-click
  way to make your current Tones and Mode/Strength/Role the defaults a
  future launch starts with, instead of resetting to None/Translate/
  Source-led/General every time. Applying a conversation preset still
  overrides these menus without changing what Remember last saved.
- **Export** the current result to a Markdown study sheet (source,
  situation, all alternatives, a diff view), **Export diff…** for a
  standalone textual source/translation comparison, and **Copy as HTML**
  (Windows) for pasting formatted text into email or documents — all
  next to Favourite on the primary card. All three (plus Favourite) use
  the exact text that produced the on-screen result, even if you've since
  edited the input box.
- The input pane shows a reading-time estimate alongside the character
  and word count.

---

## Prerequisites

- **Python 3.10 or later** (only needed to run from source).
- The single dependency:

  ```
  pip install -r requirements.txt
  ```

  That installs `customtkinter>=5.2.0`. Nothing else is required — Plume uses
  only the Python standard library for HTTP, JSON, threading and validation.
  Optionally, `pip install pystray Pillow` enables the tray icon, sign-in
  autostart and close-to-tray; without them Plume runs exactly as before
  and the tray checkboxes in Settings are simply disabled.

- **One backend**, either:
  - a **Claude API key** (cloud), or
  - a running **Ollama** instance with a capable multilingual model (local).

---

## Running from source

```
py -3 plume.py
```

or simply double-click **`Plume.bat`**.

On first use of Claude, Plume shows a one-time privacy notice explaining that
submitted text is sent to Anthropic. Open **Settings** to enter your key or
switch to Ollama.

Keyboard and mouse:

- **Ctrl+Enter** — translate the current input.
- **Ctrl+Shift+Enter** — correct the input's English, then translate it
  (disabled for a fixed French → English direction).
- **Paste** / **Clear** buttons, plus per-row **Use this**, **Copy** and
  **Speak**.
- Use **Swap** to reverse a fixed direction before translating if
  auto-detection guesses wrong.
- **Reply** copies the main translation, swaps direction and clears the
  input in one click, ready for the incoming message — the previous
  result stays visible for reference. Situation is left untouched, since
  it describes the scene, not the last message.
- Open **History** to revisit, favourite, copy, delete or reopen saved local
  translations when history is enabled.

---

## Backends

### Claude (cloud)

Uses the Messages endpoint at `https://api.anthropic.com/v1/messages` with the
`x-api-key`, `anthropic-version` and `content-type` headers. The default model
is `claude-sonnet-4-6`; you can change it in Settings (for example to
`claude-sonnet-5`). The key is read from the config file if you deliberately
enter it, otherwise from the `ANTHROPIC_API_KEY` environment variable.

Transient failures (rate limiting, a temporary 502/503/504, or a dropped
connection) are retried automatically with a short exponential backoff
before Plume shows an error — no action needed, and nothing is retried
for a rejected key or a missing model.

### Ollama (local, privacy-first)

Talks to `http://localhost:11434` using `/api/chat` with `stream: false` and
`format: "json"`. The Settings **Detect** button lists locally installed models
via `/api/tags`.

> **Note on local quality.** Local models vary a lot in French quality and in
> reliable JSON compliance. Plume validates strictly: if a local result fails
> validation it shows a retryable error rather than displaying fewer than five
> options or made-up fields. A capable multilingual model is recommended.

---

## Privacy

- **Claude** processes text in the cloud: what you submit is sent to Anthropic.
- **Ollama** keeps everything on this machine, subject to your own Ollama setup.
- **ElevenLabs Speak** sends only the selected text to ElevenLabs when you use
  a Speak button and have configured an ElevenLabs key.
- API keys are stored only if you deliberately enter them; otherwise Plume
  prefers `ANTHROPIC_API_KEY` for Claude. Settings shows stored keys **masked**.
- Plume does **not** log source messages, translated messages, headers or keys.
- Local history is **off** by default. When enabled, it is stored only on this
  device in `plume_history.json`.
- The status line, window title and error messages never contain your phrase.

---

## Configuration

Settings are saved to `plume_config.json` (generated from defaults on first
save). See `plume_config.example.json` for the shape. Do **not** commit your
live file — it may contain an API key.

- Running **from source**: the file sits beside `plume.py`.
- Running the **frozen executable**: it is written to `%LOCALAPPDATA%\Plume`,
  not the temporary extraction folder.

Saving is atomic (temp file → flush → replace). If an existing file is damaged,
an automatic save will **refuse to overwrite it**; use the Settings window's
recovery prompt to replace it deliberately.

Settings also controls placeholder protection (including the Keep as-is
term list), local history, maximum message length, optional ElevenLabs voice
configuration, and whether Plume stays on top of other windows.

---

## Building a Windows executable (optional)

```
pip install pyinstaller
pyinstaller plume.spec
```

This produces `dist\Plume.exe`, bundling the CustomTkinter assets and the icon.
Confirm on a real Windows profile that configuration is written to
`%LOCALAPPDATA%\Plume`.

---

## Tests

The deterministic logic (config safety, placeholder round trips, prompt
construction, the full response contract, privacy of diagnostics and the
stale-request guard) is covered by unit tests that run headless:

```
python -m unittest discover -s tests -v
```

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| "No Claude API key is set" | Enter a key in Settings, or set `ANTHROPIC_API_KEY`. |
| "The Claude API rejected the request" | Wrong or expired key — check Settings. |
| "The requested model was not found" | Fix the model name in Settings. |
| "Could not reach Ollama … Is it running?" | Start the Ollama app; try **Detect**. |
| "No ElevenLabs API key is set" | Add an ElevenLabs key in Settings before using **Speak**. |
| "did not contain exactly five alternatives" | A model slip — press Translate again, or switch backend. |
| Result shows "Generated for an earlier message" | You edited the input while a translation was in flight; the result is kept but flagged. |

---

## Version-1 limitations (deliberately deferred)

- No speech input, messaging-service integration or live voice agent.
- No cloud sync; local history remains device-only and opt-in.
- French ↔ English only; other language pairs come later.
- Only *Neutral international French*; regional presets (France, Belgium,
  Quebec) come after native-speaker review.
- No dictionary-style word-by-word analysis — Plume is for fast conversation.

---

*Plume — “feather” / “quill”. Built to help you chat, not to lecture you.*
# Plume
