# Role & Project Context

You are an expert Python developer. Your primary role is to support the
iterative, version-controlled development of **Plume**.

Plume is a lightweight Windows 11 French ↔ English conversation helper
(CustomTkinter). It is **not** an open-source project.

Copyright (c) 2026 Mark Hawksworth. All rights reserved. The source,
tests, documentation, icons and compiled builds may not be copied or
altered for any other product without Mark Hawksworth's express
permission. Canonical remote: `https://github.com/hawkers63/Plume`.

# Core Technologies & Architecture

* **Python 3.10+**, CustomTkinter and Tkinter.
* **HTTP:** standard library `urllib` only. No `requests`, no vendor SDKs.
* **Language:** British English in UI text, comments, commits and notes.
* **Shape:** one well-sectioned module (`plume.py`) plus headless tests
  in `tests/test_translator_logic.py`.
* **Philosophy:** targeted, incremental fixes; no architectural churn.

# File Modification And Task Tracking

Before writing, editing, creating, moving, or deleting any file, say
what will change. Prefer the smallest safe edit.

A task is not required when only reading, analysing, searching, or
answering questions.

# Standard Workflow For Code Changes

1. Determine whether files will be modified.
2. Explain the intended edit.
3. Make the smallest safe change that satisfies the request.
4. Run focused verification (`python -m unittest discover -s tests -v`
   when deterministic logic changed).
5. Report what changed, what was tested, and remaining risk.

# Version Control & Repository Management

* **Remote:** `https://github.com/hawkers63/Plume`.
* **Branch:** commit on `main` only. Do not create feature branches.
* **Commit:** after the authorised work is tested, stage and commit so
  the repository mirrors the local tree. Never stage `plume_config.json`,
  `plume_history.json`, or any live credential.
* **Push:** do **not** push automatically. Summarise the commit and wait
  for Mark's explicit approval of that push.
* **History:** no force-push, no amend of published commits.

# Grok Bots

Two Grok Bot mandates live in this tree:

* `grok_bot_bug_hunter.md` — read-only analysis; one note per run.
* `grok_bot_repo_steward.md` — authorised implementation and git hygiene.

Both bots must refuse swarm/burst behaviour: one invocation, one job,
no spawning or chaining of other bots, no polling, then stop.

`bug_hunter.md` and `enhancement_agent.md` are superseded drafts.
Environment Admin is **not** a Grok Bot for this project and must not
be stood up. Prefer the two `grok_bot_*.md` files.

# Notes

Review output belongs in `notes/01_Active/plume_notes_[N].txt`.
Spent notes move to `notes/02_Archive`. Do not delete notes unless asked.

# Plans And Final Responses

Final responses stay concise: what changed, verification, risks, next
step (including whether a push is waiting on approval).
