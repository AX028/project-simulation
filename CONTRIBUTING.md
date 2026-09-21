# Contributing

Use Python 3.11 or newer and install the `dev` extra.

Before opening a pull request, run the same repeated quality gate used by CI:

```bash
python scripts/validate.py --repetitions 3
```

This runs pytest, Ruff, and strict mypy three times each. New simulation content must be
deterministic under supplied seeds, include focused tests, and include at least one invariant or
stress test when the system has state that can accumulate over time.

Do not bypass world knowledge boundaries: NPCs should only gain information through explicit
perception, communication, memory, or world-event routes.

This repository currently has no license. Opening a contribution does not change that status.
