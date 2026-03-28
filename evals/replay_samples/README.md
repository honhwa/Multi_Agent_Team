# Replay Sample Library

This directory is the first lightweight replay sample library for quality gates and release regression.

## Directory Layout

- `evals/replay_samples/office/`: office baseline samples
- `evals/replay_samples/research/`: research-module samples
- `evals/replay_samples/swarm/`: research Swarm samples

## Required Fields

Each sample JSON file must include:

- `case_id`
- `scenario`
- `baseline_type` (`office`, `research`, or `swarm`)
- `input`
- `context`
- `attachments`
- `expected_focus`

## Intended Reuse

- gate/eval authors can promote stable replay scenarios into dedicated eval cases
- shadow/release workflows can reference representative samples instead of ad hoc payloads
- regression suites can add baseline-specific replay coverage without inventing new sample formats
