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
