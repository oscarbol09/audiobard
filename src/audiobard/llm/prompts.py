"""Versioned prompt templates for AudioBard's LLM calls.

## Rules (from AGENTS.md)
- **Never edit a constant in place.**  To improve a prompt, add a new version
  (``EXTRACT_CHARACTERS_V2``, ``ATTRIBUTE_DIALOG_V2``) and switch the default
  builder function.  Any prompt change requires a benchmark run with no
  regression before merging.
- Schema is injected at call time so it stays in sync with Pydantic models
  automatically.
- Few-shot examples are hardcoded here (not in a separate file) so the version
  is fully self-contained.
"""

from __future__ import annotations

import json

from audiobard.models import AttributionResult, CharactersResult

# ---------------------------------------------------------------------------
# Version sentinel — bump when adding a new prompt version.
# ---------------------------------------------------------------------------
PROMPT_VERSION = "v1"

# ---------------------------------------------------------------------------
# V1 — Character extraction
# ---------------------------------------------------------------------------

_EXTRACT_CHARACTERS_SYSTEM_V1 = """\
You are a literary character-extraction expert.
Your ONLY output is a single valid JSON object matching the schema below.
Do NOT use markdown code fences. Do NOT add commentary. Do NOT invent \
characters not present in the text.

Schema:
{schema}

Rules:
- Assign exactly one canonical_id per unique character: "Narrator" for the \
narrative voice, "Character_A" through "Character_Z" for other speakers.
- "name" is the most common name used for this character in the text.
- "aliases" lists alternative names or pronouns used for the same character.
- "tone" captures the character's dominant voice quality.
- "gender_hint" and "age_hint" are best-effort estimates from context clues.
- If the text contains NO dialog (pure narration), return \
{{"characters": [{{"canonical_id": "Narrator", "name": "Narrator", \
"aliases": [], "tone": "neutral", "gender_hint": "neutral", \
"age_hint": "adult"}}]}}.
"""

_EXTRACT_CHARACTERS_EXAMPLES_V1 = [
    {
        "role": "user",
        "content": (
            'TEXT:\n"I have told you so already," said Elizabeth impatiently.\n'
            '"Then you will have a charming mother-in-law," said Mrs Bennet.\n'
            'Mr Darcy said nothing.'
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "characters": [
                    {
                        "canonical_id": "Narrator",
                        "name": "Narrator",
                        "aliases": [],
                        "tone": "neutral",
                        "gender_hint": "neutral",
                        "age_hint": "adult",
                    },
                    {
                        "canonical_id": "Character_A",
                        "name": "Elizabeth",
                        "aliases": ["Elizabeth", "Eliza", "Lizzy"],
                        "tone": "agitated",
                        "gender_hint": "female",
                        "age_hint": "young",
                    },
                    {
                        "canonical_id": "Character_B",
                        "name": "Mrs Bennet",
                        "aliases": ["Mrs Bennet", "Mother"],
                        "tone": "cheerful",
                        "gender_hint": "female",
                        "age_hint": "adult",
                    },
                    {
                        "canonical_id": "Character_C",
                        "name": "Mr Darcy",
                        "aliases": ["Mr Darcy", "Darcy"],
                        "tone": "cold",
                        "gender_hint": "male",
                        "age_hint": "adult",
                    },
                ]
            },
            ensure_ascii=False,
        ),
    },
    {
        "role": "user",
        "content": (
            "TEXT:\nThe night was perfectly still. Snow lay on the rooftops\n"
            "and the street was empty. I walked alone."
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "characters": [
                    {
                        "canonical_id": "Narrator",
                        "name": "Narrator",
                        "aliases": [],
                        "tone": "melancholic",
                        "gender_hint": "neutral",
                        "age_hint": "adult",
                    }
                ]
            },
            ensure_ascii=False,
        ),
    },
]

# ---------------------------------------------------------------------------
# V1 — Dialog attribution
# ---------------------------------------------------------------------------

_ATTRIBUTE_DIALOG_SYSTEM_V1 = """\
You are a literary dialog-attribution expert.
Your ONLY output is a single valid JSON object matching the schema below.
Do NOT use markdown code fences. Do NOT add commentary.

Schema:
{schema}

Rules:
- Emit one DialogLine entry for every line of dialog or direct speech in the \
text. Narration that is not direct speech is attributed to "Narrator".
- "speaker" MUST be one of the canonical_ids provided in the character roster.
- "text" is the verbatim line of dialog (without surrounding quotes or dashes).
- "emotion" is your best estimate of the speaker's emotional state.
- When the speaker is ambiguous, prefer the most recently mentioned character \
who is physically present in the scene. If truly indeterminate, use "Narrator".
- Do NOT output lines for pure narration (descriptive passages with no speech).

Character roster:
{roster}
"""

_ATTRIBUTE_DIALOG_EXAMPLES_V1 = [
    # Example 1 — clear attribution
    {
        "role": "user",
        "content": (
            'TEXT:\n"I never saw such a woman!" cried Mrs Bennet.\n'
            '"You quite alarm me," said Elizabeth.\n'
            "Mr Darcy turned away without reply."
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "lines": [
                    {
                        "text": "I never saw such a woman!",
                        "speaker": "Character_B",
                        "emotion": "angry",
                    },
                    {
                        "text": "You quite alarm me.",
                        "speaker": "Character_A",
                        "emotion": "fearful",
                    },
                ]
            },
            ensure_ascii=False,
        ),
    },
    # Example 2 — ambiguous speaker
    {
        "role": "user",
        "content": (
            "TEXT:\nThe young man looked out at the canal.\n"
            '— What do you see? — someone asked.\n'
            "— Nothing worth seeing.\n"
            "He said it quietly and went back inside."
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "lines": [
                    {
                        "text": "What do you see?",
                        "speaker": "Narrator",
                        "emotion": "neutral",
                    },
                    {
                        "text": "Nothing worth seeing.",
                        "speaker": "Character_A",
                        "emotion": "sad",
                    },
                ]
            },
            ensure_ascii=False,
        ),
    },
    # Example 3 — narration only
    {
        "role": "user",
        "content": (
            "TEXT:\nThe sun had long since set. The streets were deserted\n"
            "and the wind drove the fallen leaves in circles."
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps({"lines": []}, ensure_ascii=False),
    },
]

# ---------------------------------------------------------------------------
# Builder functions — these are what the rest of the codebase calls.
# ---------------------------------------------------------------------------


def build_extract_characters_prompt(text: str) -> str:
    """Return the full prompt string for character extraction (V1).

    The schema is injected at call time from the live Pydantic model, so it
    stays in sync automatically.
    """
    schema_json = json.dumps(CharactersResult.model_json_schema(), ensure_ascii=False, indent=2)
    system = _EXTRACT_CHARACTERS_SYSTEM_V1.format(schema=schema_json)

    # Flatten examples + the actual user request into a single string so it
    # works with providers that only accept a single prompt string (Ollama).
    parts = [f"SYSTEM:\n{system}\n"]
    for msg in _EXTRACT_CHARACTERS_EXAMPLES_V1:
        role = msg["role"].upper()
        parts.append(f"{role}:\n{msg['content']}\n")
    parts.append(f"USER:\nTEXT:\n{text}\n")
    parts.append("ASSISTANT:")
    return "\n".join(parts)


def build_attribute_dialog_prompt(text: str, characters: CharactersResult) -> str:
    """Return the full prompt string for dialog attribution (V1)."""
    schema_json = json.dumps(AttributionResult.model_json_schema(), ensure_ascii=False, indent=2)
    roster_lines = [
        f"  {c.canonical_id}: {c.name} (aliases: {', '.join(c.aliases) or 'none'})"
        for c in characters.characters
    ]
    roster = "\n".join(roster_lines)
    system = _ATTRIBUTE_DIALOG_SYSTEM_V1.format(schema=schema_json, roster=roster)

    parts = [f"SYSTEM:\n{system}\n"]
    for msg in _ATTRIBUTE_DIALOG_EXAMPLES_V1:
        role = msg["role"].upper()
        parts.append(f"{role}:\n{msg['content']}\n")
    parts.append(f"USER:\nTEXT:\n{text}\n")
    parts.append("ASSISTANT:")
    return "\n".join(parts)
