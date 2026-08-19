# data/

Local data lives here. **Nothing in this folder is committed except what
the guards allow.**

- `books/` — source books. **Public-domain samples only.** The guards
  allowlist (tools/guards.py `ALLOWED_DATA_BOOK_FILES`) decides what may be
  tracked; anything else stays in a fork or local. Copyrighted books and
  user uploads must never be committed.
- `personas.local.json`, `voice_mapping.local.json` — per-user voice and
  persona overrides. Gitignored by contract; never commit these.

Your private books go in a directory outside the repo (the CLI accepts a
path), or in a private fork you never merge.