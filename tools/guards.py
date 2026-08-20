#!/usr/bin/env python3
"""Supply-chain and data-hygiene guards for AudioBard's riskiest surfaces.

Run from anywhere: python tools/guards.py

This package ships provider code that executes on the user's machine and a
data/ tree meant to hold books. These guards make the dangerous changes LOUD,
not impossible: a PR that intentionally needs one of them must update the
allowlists in this file in the same diff, so the change is explicit and
reviewable rather than buried.

Checks:
1. secrets — no literal API keys or tokens anywhere in tracked files under
   src/, tools/, or the repo root (env-file references are fine).
2. .gitignore — the personal-data rules must all still be present, and no
   un-allowlisted negation (!pattern) may re-include them. Catches weakening
   that would silently commit user books, audio output, or .env files.
3. data/books — only allowlisted filenames may be tracked (e.g. a
   .gitkeep or a public-domain sample). Catches committing copyrighted books.
4. audio output — *.mp3 / *.m4b / *.wav must never be tracked.

Stdlib only. Exit 0 on success, 1 with a failure list otherwise.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
errors: list[str] = []

# .env and env-file references are the sanctioned way to hold secrets. A
# literal value for any of these shapes in a tracked file is a failure.
SECRET_PATTERNS = [
    re.compile(r"\b(?:AIza[0-9A-Za-z_-]{35}|sk-[0-9A-Za-z]{20,}|gh[pousr]_[0-9A-Za-z]{30,})\b"),
    re.compile(r"\b(?:GEMINI|OPENROUTER|NVIDIA)_API_KEY\s*=\s*['\"]?[^'\"]{8,}"),
    re.compile(r"\bapi[_-]?key\s*[:=]\s*['\"][^'\"]{16,}['\"]", re.IGNORECASE),
]
# Files that are allowed to look like they contain secrets (docs/tests may
# discuss shapes without holding real keys).
SECRET_EXEMPT_PATHS = [
    "tools/guards.py",
    "tests/test_guards.py",
    "README.md",
    "AudioBard_DevPlan.md",
    "SECURITY.md",
    ".github/",
    "docs/",
]

# Personal-data ignore rules that must never disappear from .gitignore.
REQUIRED_IGNORE_RULES = [
    ".env",
    ".env.*",
    "data/books/*",
    "!data/books/.gitkeep",
    "data/personas.local.json",
    "data/voice_mapping.local.json",
    "*.mp3",
    "*.m4b",
    "*.wav",
    "*.onnx",
    "*.onnx.json",
]

# Negation (re-include) rules the template legitimately ships. .gitignore is
# order-sensitive: a later `!pattern` re-includes a path an earlier rule
# excluded, so a rule can be physically present in REQUIRED_IGNORE_RULES yet
# no longer ignored (e.g. adding `!data/books/*`). Set membership on the
# required rules cannot see that. Any negation outside this allowlist is a
# failure - add an intentional one here in the same PR.
ALLOWED_IGNORE_NEGATIONS = {
    "!data/books/.gitkeep",
}

# Files that may be tracked inside data/books/. Public-domain samples only;
# anything else (copyrighted books, user uploads) belongs in a fork or local.
ALLOWED_DATA_BOOK_FILES = {".gitkeep"}

# Audio output must never be tracked, wherever it lands.
AUDIO_EXTENSIONS = {".mp3", ".m4b", ".wav", ".flac", ".ogg"}


def check_secrets() -> None:
    """Scan tracked files for literal secret material."""
    tracked = _tracked_files()
    for path in tracked:
        rel = path.relative_to(ROOT).as_posix()
        exempt = any(
            rel.startswith(ex) or rel.endswith("/" + ex.rstrip("/"))
            for ex in SECRET_EXEMPT_PATHS
        )
        if exempt:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pattern in SECRET_PATTERNS:
            match = pattern.search(text)
            if match:
                errors.append(
                    f"{rel}: possible API key/secret literal ({pattern.pattern!r}). "
                    "Secrets must live in .env (gitignored) or be read from the environment. "
                    "If this is a test fixture, move it to SECRET_EXEMPT_PATHS in "
                    "tools/guards.py in the same PR."
                )
                break


def check_gitignore() -> None:
    try:
        ignore_text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        lines = [line.strip() for line in ignore_text.splitlines()]
    except OSError as exc:
        errors.append(f".gitignore: unreadable: {exc}")
        return
    rules = set(lines)
    for rule in REQUIRED_IGNORE_RULES:
        if rule not in rules:
            errors.append(
                f".gitignore: required personal-data rule missing: {rule!r}. "
                "These rules keep users from committing books, audio output, or secrets. "
                "If the rule moved or was renamed intentionally, update REQUIRED_IGNORE_RULES "
                "in tools/guards.py in the same PR."
            )
    for line in lines:
        if line.startswith("!") and line not in ALLOWED_IGNORE_NEGATIONS:
            errors.append(
                f".gitignore: negation rule not in the reviewed allowlist: {line!r}. "
                "A negation re-includes a path an earlier rule excluded and can silently "
                "re-expose personal data. If this negation is intentional, add it to "
                "ALLOWED_IGNORE_NEGATIONS in tools/guards.py in the same PR."
            )


def check_data_books() -> None:
    """Only allowlisted files may be tracked under data/books/."""
    for path in _tracked_files():
        rel = path.relative_to(ROOT)
        parts = rel.parts
        if "data" in parts and "books" in parts:
            name = rel.name
            if name not in ALLOWED_DATA_BOOK_FILES:
                errors.append(
                    f"{rel.as_posix()}: file is not in the allowlisted data/books set "
                    f"({sorted(ALLOWED_DATA_BOOK_FILES)}). Copyrighted books must never be "
                    "committed - keep samples in a fork or local. If this file is a "
                    "public-domain sample that must ship, add it to ALLOWED_DATA_BOOK_FILES "
                    "in tools/guards.py in the same PR."
                )


def check_audio_output() -> None:
    """Audio output must never be tracked, wherever it lands."""
    for path in _tracked_files():
        if path.suffix.lower() in AUDIO_EXTENSIONS:
            errors.append(
                f"{path.relative_to(ROOT).as_posix()}: audio output must not be tracked. "
                "Generated audiobooks belong in local output directories or CI artifacts, "
                "never in the repository."
            )


def _tracked_files() -> list[Path]:
    """List files git would track, without requiring a git binary at runtime."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        errors.append(f"git ls-files failed: {exc}")
        return []
    return [ROOT / name for name in result.stdout.split("\0") if name]


def main() -> int:
    check_secrets()
    check_gitignore()
    check_data_books()
    check_audio_output()
    if errors:
        print(f"guards: {len(errors)} failure(s)")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("guards: OK (secrets, gitignore rules, data/books allowlist, audio output)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
