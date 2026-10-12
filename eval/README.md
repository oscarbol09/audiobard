# eval/

Benchmark harness for the dialog-attribution pipeline — the project's
quality contract (see CONTRIBUTING "The benchmark bar").

- `gold_standard/` — hand-annotated references:
  - `p_and_p_ch3.json` (Pride and Prejudice, ch. 3, Gutenberg #1342).
  - `sherlock_ch1.json` (A Study in Scarlet, ch. 1, Gutenberg #244, 151 labeled lines with offsets).
  - `validate.py` (consistency and schema validator for gold standard datasets).
- `benchmark.py` — runs the pipeline over the gold standard and scores
  attribution accuracy.

## Usage

```bash
audiobard benchmark --llm ollama --model qwen2.5:7b
```

Any PR that changes prompts, parsers, or attribution logic must attach
benchmark output showing no regression. The gold standard itself changes
only through review — it is the yardstick, not a moving goal.