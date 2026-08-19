name: Pull request
description: Open a pull request against AudioBard
body:
  - type: markdown
    attributes:
      value: |
        Thanks for contributing! Please fill out the template below.

  - type: input
    id: related
    attributes:
      label: Related issue(s)
      description: Issue numbers this PR closes (e.g. `#42`, `#43`)
      placeholder: "#42"
    validations:
      required: false

  - type: dropdown
    id: type
    attributes:
      label: Type of change
      options:
        - feat (new feature)
        - fix (bug fix)
        - docs (documentation only)
        - refactor (no behavior change)
        - test (test additions)
        - chore (tooling, CI, deps)
    validations:
      required: true

  - type: textarea
    id: description
    attributes:
      label: What does this PR do?
      description: Describe the change in 2-3 sentences.
    validations:
      required: true

  - type: textarea
    id: testing
    attributes:
      label: How was it tested?
      description: Unit tests added, manual reproduction, benchmark output, etc.
    validations:
      required: true

  - type: textarea
    id: checklist
    attributes:
      label: Checklist
      description: |
        - [ ] Code follows the style guide
        - [ ] Tests added/updated
        - [ ] `ruff check .` passes
        - [ ] `mypy src/audiobard` passes
        - [ ] `pytest --cov` shows no coverage regression
        - [ ] If `prompts.py` modified: benchmark attached and shows no regression
        - [ ] Docs updated (if user-facing change)
    validations:
      required: false

  - type: dropdown
    id: ethics
    attributes:
      label: Does this PR touch ethics-sensitive areas?
      options:
        - no
        - yes (has `ethics-review` label approved)
    validations:
      required: true
