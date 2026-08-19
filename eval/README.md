# eval/

Benchmark harness for the dialog-attribution pipeline — the project's
quality contract (see CONTRIBUTING "The benchmark bar").

- `gold_standard/` — hand-annotated reference: `p_and_p_ch3.json` (Pride
  and Prejudice, ch. 3, public domain). Structure and scoring rules are
  defined in AudioBard_DevPlan.md (Phase 4).
- `benchmark.py` — runs the pipeline over the gold standard and scores
  attribution accuracy.

## Usage

```bash
audiobard benchmark --llm ollama --model qwen2.5:7b
```

Any PR that changes prompts, parsers, or attribution logic must attach
benchmark output showing no regression. The gold standard itself changes
only through review — it is the yardstick, not a moving goal.