# Evaluation & Benchmarks

AudioBard includes an automated, hermetic benchmark suite to score dialogue attribution accuracy across various LLM backends against hand-labeled ground truth literature.

---

## The Gold Standard (`eval/gold_standard/`)

The gold standard dataset is located in `eval/gold_standard/` and contains hand-verified dialogue attribution for classic literature (e.g. *Pride and Prejudice*, Chapter 3).

### Scoring Metrics
- **Total Accuracy:** Percentage of lines correctly attributed to the true speaker.
- **Per-Character Precision & Recall:** Tracks performance on major characters vs minor one-line speakers.
- **Confusion Matrix:** Flags frequent misattributions between characters.

---

## Running the Benchmark

```bash
# Benchmark local Ollama model
audiobard benchmark --llm ollama --model qwen2.5:7b

# Benchmark Google Gemini Cloud model
export GEMINI_API_KEY="your-key"
audiobard benchmark --llm gemini --model gemini-2.0-flash

# Export benchmark results as structured JSON
audiobard benchmark --llm ollama --model qwen2.5:7b --json > results.json
```

---

## CI Regression Gate

AudioBard's CI pipeline enforces that any pull request modifying prompt templates (`src/audiobard/llm/prompts.py`) or parsing logic must not cause attribution accuracy to regress below **70%**.

