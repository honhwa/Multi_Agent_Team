# Evals

This directory has two tiers.

## Stable Gate Suites

- `evals/gate_cases.json`
  - purpose: office/helper baseline gate
- `evals/research_gate_cases.json`
  - purpose: research-module gate
- `evals/swarm_gate_cases.json`
  - purpose: research Swarm gate

Run them with:

```bash
python scripts/run_evals.py --cases evals/gate_cases.json --output artifacts/evals/regression-summary.json
python scripts/run_evals.py --cases evals/research_gate_cases.json --output artifacts/evals/research-gate-summary.json
python scripts/run_evals.py --cases evals/swarm_gate_cases.json --output artifacts/evals/swarm-gate-summary.json
```

## Full Exploratory Suite

- file: `evals/cases.json`
- purpose: broader regression and investigation coverage
- expectation: useful for analysis, not necessarily suitable as a hard branch gate while legacy paths are still being retired

Run it with:

```bash
python scripts/run_evals.py --cases evals/cases.json --output artifacts/evals/full-summary.json
```

## Replay Samples

- directory: `evals/replay_samples/`
- purpose: lightweight baseline corpus for replay, gate promotion, and release regression seeding
