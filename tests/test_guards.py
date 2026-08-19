"""Tests for tools/guards.py.

Each test builds a minimal repo tree the guards pass on, then breaks exactly
one thing, and asserts on real exit codes and messages - the same way CI
invokes the script (subprocess from a temp tree).

Pinned with the same philosophy as the repo's other contract tests: presence
checks cannot see semantic drift (a rule present in .gitignore but
re-included by a later negation), so the negation and data/books cases are
tested through real `git check-ignore` semantics where it matters.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GUARD_SCRIPT = REPO_ROOT / "tools" / "guards.py"

sys.path.insert(0, str(REPO_ROOT / "tools"))
import guards  # noqa: E402  (imported for its allowlist constants)


def run_guards(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(root / "tools" / "guards.py")],
        capture_output=True,
        text=True,
    )


def git_init_and_commit_all(root: Path) -> None:
    """Track every file in root so guards.py's `git ls-files` sees it.

    Uses `git add -f` deliberately: the scenarios the guards must catch are
    files committed *despite* being gitignored (someone force-added a book or
    an mp3), so the fixture has to replicate that bypass.
    """
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "add", "-Af"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "fixture", "--allow-empty"],
        check=True,
        capture_output=True,
    )


class GuardRepoFixture(unittest.TestCase):
    """Builds a minimal repo tree the guards pass on, then breaks one thing per test."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

        (self.root / "tools").mkdir()
        shutil.copy(GUARD_SCRIPT, self.root / "tools" / "guards.py")

        # .gitignore with the full required set
        (self.root / ".gitignore").write_text(
            "\n".join(guards.REQUIRED_IGNORE_RULES) + "\n", encoding="utf-8"
        )

        # data/books with an allowlisted .gitkeep
        (self.root / "data" / "books").mkdir(parents=True)
        (self.root / "data" / "books" / ".gitkeep").write_text("", encoding="utf-8")

        # benign source file
        (self.root / "src").mkdir()
        (self.root / "src" / "audiobard").mkdir()
        (self.root / "src" / "audiobard" / "__init__.py").write_text(
            '"""Fixture package."""\n', encoding="utf-8"
        )

        git_init_and_commit_all(self.root)

    def add_tracked_file(self, relpath: str, content: str = "") -> Path:
        path = self.root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        # -f: the file may match a gitignore rule (that is the point of the
        # guard); we track it anyway to simulate a force-add.
        subprocess.run(["git", "-C", str(self.root), "add", "-Af"], check=True, capture_output=True)
        return path


class CleanTreeTests(GuardRepoFixture):
    def test_clean_tree_passes(self):
        result = run_guards(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("guards: OK", result.stdout)


class SecretGuardTests(GuardRepoFixture):
    def test_gemini_key_literal_fails(self):
        key_line = 'GEMINI_API_KEY = "AIzaSyDummyKey1234567890abcdefghijklmno"\n'
        self.add_tracked_file("src/audiobard/client.py", key_line)
        result = run_guards(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("possible API key", result.stdout)
        self.assertIn("client.py", result.stdout)

    def test_openai_style_key_fails(self):
        self.add_tracked_file("config.py", 'api_key = "sk-abcdef1234567890abcdef1234567890"\n')
        result = run_guards(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("possible API key", result.stdout)

    def test_env_reference_is_allowed(self):
        self.add_tracked_file("src/audiobard/config.py", 'key = os.environ["GEMINI_API_KEY"]\n')
        result = run_guards(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_dotenv_load_is_allowed(self):
        self.add_tracked_file("src/audiobard/config.py", 'load_dotenv()  # reads .env\n')
        result = run_guards(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class GitignoreGuardTests(GuardRepoFixture):
    def test_each_missing_personal_data_rule_fails(self):
        for rule in guards.REQUIRED_IGNORE_RULES:
            with self.subTest(rule=rule):
                remaining = [r for r in guards.REQUIRED_IGNORE_RULES if r != rule]
                (self.root / ".gitignore").write_text("\n".join(remaining) + "\n", encoding="utf-8")
                result = run_guards(self.root)
                self.assertEqual(result.returncode, 1)
                self.assertIn("required personal-data rule missing", result.stdout)
                self.assertIn(rule, result.stdout)
        rules_text = "\n".join(guards.REQUIRED_IGNORE_RULES) + "\n"
        (self.root / ".gitignore").write_text(rules_text, encoding="utf-8")

    def test_negation_reincluding_books_fails(self):
        # `!data/books/*` after `data/books/*` re-includes the directory, so
        # the required rule is still present but no longer takes effect. Set
        # membership on the required rules cannot see this.
        (self.root / ".gitignore").write_text(
            "\n".join(list(guards.REQUIRED_IGNORE_RULES) + ["!data/books/*", ""]) + "\n",
            encoding="utf-8",
        )
        result = run_guards(self.root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("negation rule not in the reviewed allowlist", result.stdout)
        self.assertIn("!data/books/*", result.stdout)

    def test_allowlisted_negations_pass(self):
        rules = list(guards.REQUIRED_IGNORE_RULES) + sorted(guards.ALLOWED_IGNORE_NEGATIONS)
        text = "\n".join(rules) + "\n"
        (self.root / ".gitignore").write_text(text, encoding="utf-8")
        result = run_guards(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class DataBooksGuardTests(GuardRepoFixture):
    def test_copyrighted_book_fails(self):
        self.add_tracked_file("data/books/white_nights.txt", "Chapter 1\n")
        result = run_guards(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("allowlisted data/books set", result.stdout)
        self.assertIn("white_nights.txt", result.stdout)

    def test_allowlisted_file_passes(self):
        # Mutate the *copied* guard script (subprocess runs its own module,
        # so mutating the imported one here would not reach it) — the same
        # pattern the upstream-style guard tests use to exercise an allowlist
        # addition that must land in the same PR as the file it admits.
        guard = self.root / "tools" / "guards.py"
        guard.write_text(
            guard.read_text(encoding="utf-8").replace(
                'ALLOWED_DATA_BOOK_FILES = {".gitkeep"}',
                'ALLOWED_DATA_BOOK_FILES = {".gitkeep", "sample_public_domain.txt"}',
            ),
            encoding="utf-8",
        )
        self.add_tracked_file("data/books/sample_public_domain.txt", "Public domain text.\n")
        result = run_guards(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class AudioOutputGuardTests(GuardRepoFixture):
    def test_tracked_mp3_fails(self):
        self.add_tracked_file("output/audiobook.mp3", "")
        result = run_guards(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("audio output must not be tracked", result.stdout)

    def test_tracked_m4b_fails(self):
        self.add_tracked_file("out/book.m4b", "")
        result = run_guards(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("audio output must not be tracked", result.stdout)


class RealRepoTests(unittest.TestCase):
    def test_guards_pass_on_this_repo(self):
        # The live check CI runs: the actual repo tree must satisfy its own guards.
        result = run_guards(REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
