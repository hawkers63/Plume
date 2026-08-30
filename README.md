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
  style markers, so they survive translation unchanged.
- A copy button on every result, with a prominent **Copy main translation**.

---

## Prerequisites

- **Python 3.10 or later** (only needed to run from source).
- The single dependency:

  ```
  pip install -r requirements.txt
  ```

  That installs `customtkinter>=5.2.0`. Nothing else is required — Plume uses
  only the Python standard library for HTTP, JSON, threading and validation.

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
- **Paste** / **Clear** buttons, plus a per-row **Copy**.
- Reverse the direction before translating if auto-detection guesses wrong.

---

## Backends

### Claude (cloud)

Uses the Messages endpoint at `https://api.anthropic.com/v1/messages` with the
`x-api-key`, `anthropic-version` and `content-type` headers. The default model
is `claude-sonnet-4-6`; you can change it in Settings (for example to
`claude-sonnet-5`). The key is read from the config file if you deliberately
enter it, otherwise from the `ANTHROPIC_API_KEY` environment variable.

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
- Your API key is stored only if you deliberately enter it; otherwise Plume
  prefers `ANTHROPIC_API_KEY`. Settings shows the key **masked**.
- Plume does **not** log source messages, translated messages, headers or keys.
- Local history is **off** by default and is not stored in version 1.
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
| "did not contain exactly five alternatives" | A model slip — press Translate again, or switch backend. |
| Result shows "Generated for an earlier message" | You edited the input while a translation was in flight; the result is kept but flagged. |

---

## Version-1 limitations (deliberately deferred)

- No speech input/output, no messaging-service integration.
- No persistent history or cloud sync.
- French ↔ English only; other language pairs come later.
- Only *Neutral international French*; regional presets (France, Belgium,
  Quebec) come after native-speaker review.
- No dictionary-style word-by-word analysis — Plume is for fast conversation.

---

*Plume — “feather” / “quill”. Built to help you chat, not to lecture you.*
# Plume
