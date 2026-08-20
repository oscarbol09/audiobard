# Prompt Engineering & Model Evaluation Guide

AudioBard relies on structured prompt engineering to extract characters and attribute dialogues with high accuracy from public-domain literature.

This document details:
1. **The Prompt Versioning Contract**
2. **Dynamic JSON Schemas & Few-Shot Construction**
3. **Benchmarking & Testing New Models**

---

## 1. The Prompt Versioning Contract

All prompts live in `src/audiobard/llm/prompts.py` as versioned constants (`PROMPT_V1`, `PROMPT_V2`, etc.).

### Hard Rules:
- **Never edit a versioned prompt in place.** Once a prompt version is published and used in a benchmark, it is immutable.
- To improve a prompt, create `PROMPT_V<N+1>` and change the default version reference:
  ```python
  DEFAULT_PROMPT_VERSION = "v2"
  ```
- Any prompt change **must include benchmark results showing no regression in attribution accuracy**:
  ```bash
  audiobard benchmark --llm ollama --model qwen2.5:7b
  ```

---

## 2. Dynamic JSON Schemas & Few-Shot Construction

AudioBard enforces Pydantic schemas on LLM outputs using structured generation (e.g. Ollama JSON mode, Gemini responseSchema).

### Character Extraction (`extract_characters`)
- Extracts all speaking or named characters from a book opening sample (~5000 words).
- Injects character metadata: `canonical_id`, `name`, `aliases`, `gender_hint`, `age_hint`, and `tone`.

### Dialog Attribution (`attribute_dialog`)
- Receives text chunks (default 1500 words) and the extracted character roster.
- Attributes each line of dialog to a character or `"Narrator"`.
- Assigns emotional delivery (`happy`, `sad`, `angry`, `fearful`, `surprised`, `whisper`, `sarcastic`, `neutral`) which maps directly to TTS prosody modifiers.

---

## 3. Benchmarking New Models

Before introducing a new model or switching default models, verify its performance against the gold standard:

```bash
# Run benchmark with local Ollama
audiobard benchmark --llm ollama --model qwen2.5:7b

# Run benchmark with Gemini Cloud
export GEMINI_API_KEY="your-api-key"
audiobard benchmark --llm gemini --model gemini-2.0-flash

# Run benchmark with JSON output for automated pipelines
audiobard benchmark --llm ollama --model qwen2.5:7b --json
```

### Benchmark Metrics Reported:
- **Overall Accuracy**: Total correct character attributions. Must be $\ge 70\%$.
- **Per-character Accuracy**: Accuracy broken down per speaker (e.g. Elizabeth, Darcy, Mr. Bennet).
- **Confusion Matrix**: Identifies common misattributions (e.g. Mrs. Bennet misattributed as Jane).
