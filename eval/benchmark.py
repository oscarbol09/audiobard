#!/usr/bin/env python3
"""Attribution accuracy benchmark for AudioBard.

Runs the LLM dialog-attribution pipeline against the hand-labeled gold
standard (eval/gold_standard/p_and_p_ch3.json) and reports:

  - Overall accuracy  (matched / total dialog lines)
  - Per-character accuracy
  - A compact confusion matrix

Usage::

    python eval/benchmark.py
    python eval/benchmark.py --llm ollama --model qwen2.5:7b
    python eval/benchmark.py --llm gemini --model gemini-2.0-flash

The script is also registered as ``audiobard benchmark`` in the CLI.

Source text: Pride and Prejudice, Jane Austen (public domain, Project
Gutenberg EBook #1342).  The gold-standard labels in this directory were
created by hand and are the benchmark contract — do not edit them without
updating the hash in CONTRIBUTING.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLD_PATH = ROOT / "eval" / "gold_standard" / "p_and_p_ch3.json"

# ---------------------------------------------------------------------------
# Minimal inline text from P&P ch3 used as LLM input
# (public domain — Project Gutenberg EBook #1342)
# ---------------------------------------------------------------------------
_PP_CH3_TEXT = """
Chapter 3

Not all that Mrs. Bennet, however, with the assistance of her five daughters,
could ask on the subject was sufficient to draw from her husband any satisfactory
description of Mr. Bingley. They attacked him in various ways; with barefaced
questions, ingenious suppositions, and distant surmises; but he eluded the skill
of them all; and they were at last obliged to accept the second-hand intelligence
of their neighbour Lady Lucas.

"My dear Mr. Bennet," said his lady to him one day, "have you heard that
Netherfield Park is let at last?"

Mr. Bennet replied that he had not.

"But it is," returned she; "for Mrs. Long has just been here, and she told me
all about it."

Mr. Bennet made no answer.

"Do not you want to know who has taken it?" cried his wife impatiently.

"You want to tell me, and I have no objection to hearing it."

This was invitation enough.

"Why, my dear, you must know, Mrs. Long says that Netherfield is taken by a
young man of large fortune from the north of England; that he came down on
Monday in a chaise and four to see the place, and was so much delighted with it
that he agreed with Mr. Morris immediately; that he is to take possession before
Michaelmas, and some of his servants are to be in the house by the end of next
week."

"What is his name?"

"Bingley."

"Is he married or single?"

"Oh! single, my dear, to be sure! A single man of large fortune; four or five
thousand a year. What a fine thing for our girls!"

"How so? How can it affect them?"

"My dear Mr. Bennet," replied his wife, "how can you be so tiresome! You must
know that I am thinking of his marrying one of them."

"Is that his design in settling here?"

"Design! Nonsense, how can you talk so! But it is very likely that he may fall
in love with one of them, and therefore you must visit him as soon as he comes."

"I see no occasion for that. You and the girls may go, or you may send them by
themselves, which perhaps will be still better, for as you are as handsome as
any of them, Mr. Bingley might like you the best of the party."

"My dear, you flatter me. I certainly have had my share of beauty, but I do not
pretend to be any thing extraordinary now. When a woman has five grown up
daughters, she ought to give over thinking of her own beauty."

"In such cases, a woman has not often much beauty to think of."

"But, my dear, you must indeed go and see Mr. Bingley when he comes into the
neighbourhood."

"It is more than I engage for, I assure you."

"But consider your daughters. Only think what an establishment it would be for
one of them. Sir William and Lady Lucas are determined to go, merely on that
account, for in general, you know, they visit no new comers. Indeed you must go,
for it will be impossible for us to visit him if you do not."

"You are over-scrupulous, surely. I dare say Mr. Bingley will be very glad to
see you; and I will send a few lines by you to assure him of my hearty consent
to his marrying which ever he chuses of our daughters."

"How good it was in you, my dear Mr. Bennet! But I knew I should persuade you
at last. I was sure you could not have the heart to neglect your poor little
girls."

"Now, Kitty, you may cough as much as you chuse."

Sir William and Lady Lucas, and Mr. and Mrs. Gardiner, with their four children,
arrived at Longbourn before the party from Meryton, and Mr. Darcy had been
standing near the door to receive them. He looked at Elizabeth with a searching
gaze.

"She is tolerable; but not handsome enough to tempt me; and I am in no humour
at present to give consequence to young ladies who are slighted by other men."

"Come, Darcy," said he, "I must have you dance. I hate to see you standing
about by yourself in this stupid manner. You had much better dance."

"I certainly shall not. You know how I detest it, unless I am particularly
acquainted with my partner. At such an assembly as this, it would be
insupportable. Your sisters are engaged, and there is not another woman in the
room whom it would not be a punishment to me to stand up with."

"I would not be so fastidious as you are," cried Bingley, "for a kingdom!"

"You are dancing with the only handsome girl in the room."

"Oh! she is the most beautiful creature I ever beheld!"

"Did you not think, Mr. Darcy, that I expressed myself uncommonly well just now,
when I was teasing Colonel Forster to give us a ball at Meryton?"

"With great energy; but it is a subject which always makes a lady energetic."

"You are severe on us."
"""


def _load_gold() -> list[dict[str, object]]:
    """Load and return the gold-standard annotations."""
    with open(GOLD_PATH, encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


async def _run_attribution(llm_provider: str, model: str) -> list[str]:
    """Invoke the AudioBard LLM pipeline and return predicted speakers."""
    sys.path.insert(0, str(ROOT / "src"))
    from audiobard.config import AudioBardConfig
    from audiobard.models import AgeHint, Character, CharactersResult, GenderHint, Tone
    from audiobard.pipeline import create_llm_client

    config = AudioBardConfig(
        llm_provider=llm_provider,  # type: ignore[arg-type]
        llm_model=model,
    )
    client = create_llm_client(config)

    # Build a minimal character roster from the gold standard
    gold = _load_gold()
    speakers = sorted({str(d["speaker"]) for d in gold})
    characters = CharactersResult(
        characters=[
            Character(
                canonical_id=s,
                name=s,
                gender_hint=GenderHint.NEUTRAL,
                age_hint=AgeHint.ADULT,
                tone=Tone.NEUTRAL,
            )
            for s in speakers
        ]
    )

    result = await client.attribute_dialog(_PP_CH3_TEXT, characters)
    return [dl.speaker for dl in result.lines]


def _compute_metrics(
    gold: list[dict[str, object]], predictions: list[str]
) -> dict[str, object]:
    """Compute overall and per-character accuracy."""
    gold_speakers = [str(d["speaker"]) for d in gold]
    total = min(len(gold_speakers), len(predictions))
    if total == 0:
        return {"accuracy": 0.0, "per_character": {}, "confusion": {}}

    correct = sum(
        g == p
        for g, p in zip(gold_speakers[:total], predictions[:total], strict=True)
    )

    per_char: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for g, p in zip(gold_speakers[:total], predictions[:total], strict=True):
        per_char[g]["total"] += 1
        confusion[g][p] += 1
        if g == p:
            per_char[g]["correct"] += 1

    per_char_acc = {
        speaker: (
            f"{100 * v['correct'] / v['total']:.1f}%"
            f" ({v['correct']}/{v['total']})"
        )
        for speaker, v in sorted(per_char.items())
    }

    return {
        "accuracy": correct / total,
        "correct": correct,
        "total": total,
        "per_character": per_char_acc,
        "confusion": {k: dict(v) for k, v in confusion.items()},
    }


def _print_report(metrics: dict[str, object]) -> None:
    acc = float(str(metrics["accuracy"])) * 100
    correct = metrics.get("correct", "?")
    total = metrics.get("total", "?")
    print(f"\nAttribution Accuracy: {acc:.1f}% ({correct}/{total} lines)")
    print("\nPer-character:")
    per_char = metrics.get("per_character", {})
    assert isinstance(per_char, dict)
    for speaker, stat in per_char.items():
        print(f"  {speaker:<20} {stat}")
    print("\nConfusion matrix (gold -> predicted):")
    confusion = metrics.get("confusion", {})
    assert isinstance(confusion, dict)
    for gold_label, preds in sorted(confusion.items()):
        assert isinstance(preds, dict)
        parts = ", ".join(f"{p}:{n}" for p, n in sorted(preds.items()))
        print(f"  {gold_label:<20} -> {parts}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="AudioBard attribution benchmark (P&P ch3 gold standard)"
    )
    parser.add_argument(
        "--llm",
        default="ollama",
        choices=["ollama", "gemini", "openrouter"],
        help="LLM provider to benchmark (default: ollama)",
    )
    parser.add_argument(
        "--model",
        default="qwen2.5:7b",
        help="Model identifier (default: qwen2.5:7b)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON (for CI)",
    )
    args = parser.parse_args(argv)

    gold = _load_gold()
    print(
        f"Running attribution benchmark: provider={args.llm} model={args.model}"
        f" gold_lines={len(gold)}"
    )

    predictions = asyncio.run(_run_attribution(args.llm, args.model))
    metrics = _compute_metrics(gold, predictions)

    if args.json_output:
        print(json.dumps(metrics, indent=2))
    else:
        _print_report(metrics)

    accuracy = float(str(metrics["accuracy"]))
    if accuracy < 0.70:
        print(f"\nFAIL: accuracy {accuracy:.1%} is below the 70% threshold.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
