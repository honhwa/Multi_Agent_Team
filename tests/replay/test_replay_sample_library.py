from __future__ import annotations

import json
from pathlib import Path


REQUIRED_FIELDS = {
    "case_id",
    "scenario",
    "baseline_type",
    "input",
    "context",
    "attachments",
    "expected_focus",
}


def test_replay_sample_library_has_required_schema_and_baseline_coverage() -> None:
    root = Path("evals/replay_samples")
    sample_paths = sorted(path for path in root.rglob("*.json") if path.is_file())

    assert sample_paths, "replay sample library should contain at least one sample"

    baseline_types: set[str] = set()
    for path in sample_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert REQUIRED_FIELDS.issubset(payload.keys())
        assert isinstance(payload["case_id"], str) and payload["case_id"].strip()
        assert isinstance(payload["scenario"], str) and payload["scenario"].strip()
        assert isinstance(payload["input"], dict)
        assert isinstance(payload["context"], dict)
        assert isinstance(payload["attachments"], list)
        assert isinstance(payload["expected_focus"], list) and payload["expected_focus"]
        baseline_type = str(payload["baseline_type"])
        assert baseline_type == path.parent.name
        baseline_types.add(baseline_type)

    assert baseline_types == {"office", "research", "swarm"}
