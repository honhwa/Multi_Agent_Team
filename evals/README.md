# Evals

This directory has two tiers.

## Stable Gate Suite

- file: `evals/gate_cases.json`
- purpose: CI gate on push and pull request
- expectation: every case must stay green

Run it with:

```bash
python scripts/run_evals.py --cases evals/gate_cases.json --output artifacts/evals/regression-summary.json
```

## Full Exploratory Suite

- file: `evals/cases.json`
- purpose: broader regression and investigation coverage
- expectation: useful for analysis, not necessarily suitable as a hard branch gate while legacy paths are still being retired

Run it with:

```bash
python scripts/run_evals.py --cases evals/cases.json --output artifacts/evals/full-summary.json
```
