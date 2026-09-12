# Contributing (private repository)

Plume is a **private proprietary** Windows 11 French ↔ English conversation
helper owned by Mark Hawksworth. This is not an open-source contribution guide.

## Who edits this repo

Edits are for Mark and the agents team working on his behalf. Do not treat
issues or pull requests as a public contribution funnel.

## Working agreements

- **British English** in UI strings, docs, commit messages and PR text.
- Prefer the **smallest safe edit** that solves the stated problem.
- Do **not** change `plume.py`, tests, `LICENSE` or `COPYRIGHT` unless Mark
  explicitly asks for that change in the same task.
- Run tests before proposing code changes:

  ```
  python -m unittest discover -s tests -v
  ```

- Respect proprietary terms in [`LICENSE`](LICENSE) and [`COPYRIGHT`](COPYRIGHT).
  Do not copy Plume into other products or public forks.
- Follow [`AGENTS.md`](AGENTS.md) for agent roles, stewardship and safety notes.
- Product direction and deferred work live in [`ROADMAP.md`](ROADMAP.md).

## Pull requests

Use the repository PR template. Summarise the change, tick the test plan, and
confirm the copyright checklist. Docs-only PRs still need a clear summary.

## Issues

Use the Bug report or Enhancement templates when they fit. Keep reports free of
API keys and personal conversation content.

---

Copyright (c) 2026 Mark Hawksworth. All rights reserved.
