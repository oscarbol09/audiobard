"""Unit tests for the attribution benchmark script."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import patch

import pytest
from eval.benchmark import _compute_metrics, _load_gold, main


def test_load_gold() -> None:
    """Test loading gold standard file returns expected format."""
    gold = _load_gold()
    assert isinstance(gold, list)
    assert len(gold) > 0
    assert "text" in gold[0]
    assert "speaker" in gold[0]


def test_compute_metrics() -> None:
    """Test compute_metrics calculation logic."""
    gold: list[dict[str, object]] = [
        {"speaker": "Elizabeth"},
        {"speaker": "Darcy"},
        {"speaker": "Narrator"},
    ]
    predictions = ["Elizabeth", "Elizabeth", "Narrator"]

    metrics = _compute_metrics(gold, predictions)
    assert metrics["accuracy"] == pytest.approx(2 / 3)
    assert metrics["correct"] == 2
    assert metrics["total"] == 3

    per_char = cast(dict[str, str], metrics["per_character"])
    assert per_char["Elizabeth"] == "100.0% (1/1)"
    assert per_char["Darcy"] == "0.0% (0/1)"

    confusion = cast(dict[str, dict[str, int]], metrics["confusion"])
    assert confusion["Darcy"]["Elizabeth"] == 1


@patch("eval.benchmark._run_attribution")
def test_benchmark_runner_success(mock_run: Any) -> None:
    """Test main benchmark runner script execution on success."""
    # Mock predictions that match the gold standard length
    gold = _load_gold()
    mock_run.return_value = [str(d["speaker"]) for d in gold]

    # Run with json output to check result
    with patch("sys.stdout"):
        rc = main(["--llm", "ollama", "--model", "dummy", "--json"])
        assert rc == 0


def test_load_sherlock_gold() -> None:
    """Test loading Sherlock Holmes Chapter 1 gold standard dataset."""
    from eval.benchmark import ROOT

    sherlock_path = ROOT / "eval" / "gold_standard" / "sherlock_ch1.json"
    assert sherlock_path.is_file()
    lines = _load_gold(sherlock_path)
    assert isinstance(lines, list)
    assert len(lines) >= 150
    assert lines[0]["text"] == "Whatever have you been doing with yourself, Watson?"
    assert lines[0]["speaker"] == "Character_C"
    assert "source" in lines[0]


def test_validate_gold_standards() -> None:
    """Test that all repository gold standards pass validation checks."""
    from eval.benchmark import ROOT
    from eval.gold_standard.validate import validate_gold_standard

    gold_dir = ROOT / "eval" / "gold_standard"
    p_and_p = gold_dir / "p_and_p_ch3.json"
    sherlock = gold_dir / "sherlock_ch1.json"

    assert validate_gold_standard(p_and_p) == []
    assert validate_gold_standard(sherlock) == []


def test_validate_gold_standard_invalid(tmp_path: Any) -> None:
    """Test validation errors on missing files and malformed entries."""
    from eval.gold_standard.validate import validate_gold_standard

    # Non-existent
    assert "File not found" in validate_gold_standard(tmp_path / "nonexistent.json")[0]

    # Empty file
    invalid_file = tmp_path / "bad.json"
    invalid_file.write_text("{", encoding="utf-8")
    assert "Invalid JSON" in validate_gold_standard(invalid_file)[0]

    # Missing lines
    invalid_file.write_text(
        '{"book": "Test", "chapter": 1, "lines": [{"index": 1, "text": "", "speaker": "Invalid"}]}',
        encoding="utf-8",
    )
    errors = validate_gold_standard(invalid_file)
    assert any("index mismatch" in err for err in errors)
    assert any("'text' must be a non-empty string" in err for err in errors)
    assert any("does not match canonical schema" in err for err in errors)
