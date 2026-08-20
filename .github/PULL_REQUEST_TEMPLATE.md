<!--
Thanks for contributing to AudioBard! Please fill out this template -
issue-form YAML syntax (type: dropdown, etc.) isn't supported in PR
templates, so this is plain Markdown. Delete this comment block once done.
-->

## Related issue(s)

<!-- Issue numbers this PR closes, e.g. Closes #42, Relates to #43 -->

## Type of change

<!-- Check one -->

- [ ] feat (new feature)
- [ ] fix (bug fix)
- [ ] docs (documentation only)
- [ ] refactor (no behavior change)
- [ ] test (test additions)
- [ ] chore (tooling, CI, deps)

## What does this PR do?

<!-- Describe the change in 2-3 sentences. -->

## How was it tested?

<!-- Unit tests added, manual reproduction, benchmark output, etc. -->

## Checklist

- [ ] Code follows the style guide
- [ ] Tests added/updated
- [ ] `ruff check .` passes
- [ ] `mypy src/audiobard` passes
- [ ] `pytest --cov` shows no coverage regression
- [ ] If `prompts.py` or `parser/` modified: the `Benchmark` CI check ran
      on this PR and passed (it runs automatically — see the checks below
      this description)
- [ ] Docs updated (if user-facing change)

## Does this PR touch ethics-sensitive areas?

<!-- Check one. "Yes" = voice cloning, real-person impersonation, or similar -
     see CONTRIBUTING.md "Adding a provider" for the ethics-review RFC requirement. -->

- [ ] No
- [ ] Yes (has `ethics-review` label approved)
