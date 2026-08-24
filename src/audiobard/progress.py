"""Pipeline progress reporting.

The pipeline is a long-running async operation. Without an explicit progress
hook, callers either block silently or fall back to polling a global state
they had no business holding. This module provides a tiny dataclass plus a
callback alias so any consumer (CLI Rich progress, FastAPI, Tauri events,
tests) can subscribe to stage transitions and percent updates without the
pipeline module growing transport concerns.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

ProgressCallback = Callable[["PipelineProgress"], None]


@dataclass(frozen=True)
class PipelineProgress:
    """A single progress update emitted by AudioBookPipeline.run().

    Attributes:
        stage: Human-readable stage identifier (parsing, characters,
            voice_assignment, synthesis, assembly, complete).
        percent: Integer 0-100 representing overall completion. The exact
            mapping between stage and percent is the pipeline's contract;
            consumers should treat it as monotonic and never assume a
            specific value at a specific stage boundary.
        message: Free-form human-readable status line. Localised strings
            are not required; the CLI wraps this in its Rich layout.
    """

    stage: str
    percent: int
    message: str

    def __post_init__(self) -> None:
        if not 0 <= self.percent <= 100:
            raise ValueError(f"percent must be in 0..100, got {self.percent}")
        if not self.stage:
            raise ValueError("stage must be a non-empty string")


__all__ = ["PipelineProgress", "ProgressCallback"]
