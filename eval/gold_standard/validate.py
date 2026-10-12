#!/usr/bin/env python3
"""Validation utility for AudioBard gold-standard dialog datasets.

Checks consistency of hand-labeled evaluation benchmarks:
  - Valid JSON formatting and top-level schema.
  - Sequential, zero-based line indices.
  - Non-empty dialog text and canonical speaker formatting.
  - Standardized emotion labels adhering to AudioBard's Emotion enum.
  - Verifiable raw-text source offset citations.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_SPEAKER_PATTERN = re.compile(r"^(Narrator|Character_[A-Za-z0-9_]+)$")
_VALID_EMOTIONS = {
    "neutral",
    "happy",
    "sad",
    "angry",
    "fearful",
    "surprised",
    "whisper",
    "sarcastic",
}


def validate_gold_standard(path: Path) -> list[str]:
    """Validate a gold standard JSON file and return a list of error strings."""
    errors: list[str] = []

    if not path.is_file():
        return [f"File not found: {path}"]

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        return [f"Invalid JSON syntax in {path}: {exc}"]

    # Determine format: top-level dict (new standard) or list (legacy p_and_p_ch3)
    if isinstance(data, dict):
        if "lines" not in data or not isinstance(data["lines"], list):
            errors.append("Dataset dictionary missing 'lines' list")
            return errors
        lines = data["lines"]
        if "book" in data and not isinstance(data["book"], str):
            errors.append("'book' attribute must be a string")
        if "chapter" in data and not isinstance(data["chapter"], int):
            errors.append("'chapter' attribute must be an integer")
    elif isinstance(data, list):
        lines = data
    else:
        return [f"Unexpected root type in {path}: expected dict or list, got {type(data).__name__}"]

    if not lines:
        errors.append("Dataset contains 0 dialogue lines")
        return errors

    # Check each dialogue line
    for i, line in enumerate(lines):
        if not isinstance(line, dict):
            errors.append(f"Line {i}: expected dict, got {type(line).__name__}")
            continue

        # Index check (if present)
        if "index" in line and (not isinstance(line["index"], int) or line["index"] != i):
            errors.append(f"Line {i}: index mismatch, expected {i}, got {line.get('index')}")

        # Text check
        text = line.get("text")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"Line {i}: 'text' must be a non-empty string")

        # Speaker check
        speaker = line.get("speaker")
        if not isinstance(speaker, str) or not speaker.strip():
            errors.append(f"Line {i}: 'speaker' must be a non-empty string")
        elif not _SPEAKER_PATTERN.match(speaker) and isinstance(data, dict):
            # Strict enforcement for new gold standards (dict format)
            errors.append(
                f"Line {i}: 'speaker' ('{speaker}') does not match canonical schema "
                r"r'^(Narrator|Character_[A-Za-z0-9_]+)$'"
            )

        # Emotion check (if present)
        if "emotion" in line:
            emotion = line["emotion"]
            if not isinstance(emotion, str) or emotion.lower() not in _VALID_EMOTIONS:
                valid_list = ", ".join(sorted(_VALID_EMOTIONS))
                errors.append(f"Line {i}: invalid emotion '{emotion}'. Valid: {valid_list}")

        # Source citation check (if new standard dict format)
        if isinstance(data, dict) and "source" in line:
            source = line["source"]
            if not isinstance(source, str) or not source.strip():
                errors.append(f"Line {i}: 'source' citation must be a non-empty string")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate AudioBard gold standard datasets.")
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Path(s) to gold standard JSON file(s). Defaults to all files in eval/gold_standard/",
    )
    args = parser.parse_args(argv)

    target_files = args.files
    if not target_files:
        default_dir = Path(__file__).resolve().parent
        target_files = sorted(default_dir.glob("*.json"))

    if not target_files:
        print("No gold standard files found to validate.", file=sys.stderr)
        return 1

    total_errors = 0
    for target in target_files:
        errors = validate_gold_standard(target)
        if errors:
            print(f"[FAIL] {target.name} ({len(errors)} errors):", file=sys.stderr)
            for err in errors[:10]:
                print(f"  - {err}", file=sys.stderr)
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more errors", file=sys.stderr)
            total_errors += len(errors)
        else:
            print(f"[PASS] {target.name} is valid and consistent.")

    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
