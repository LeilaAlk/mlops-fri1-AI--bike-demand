"""Lab 7 gate: blocked, rejected and eligible outcomes, and rejection keeps
the accepted state byte for byte."""

import json
import shutil
from pathlib import Path

import pytest
import yaml

from bike_demand.pipeline import EXIT, check, decide, run_pipeline
from bike_demand.registry import read_current, registry_root, snapshot, version_dir

pytestmark = pytest.mark.gate


def bootstrap(root: Path) -> dict:
    """Register the bootstrap bundle by hand (promotion has its own tests)."""
    decision = run_pipeline(root, Path("configs/baseline.yaml"), bootstrap=True)
    assert decision["outcome"] == "eligible", decision["reasons"]
    candidate = decision["candidate"]
    target = version_dir(registry_root(root), candidate["model_version"])
    shutil.copytree(root / candidate["run_dir"], target)
    current = {
        "model_version": candidate["model_version"],
        "model_sha256": candidate["model_sha256"],
        "decision_id": decision["decision_id"],
    }
    (registry_root(root) / "current.json").write_text(json.dumps(current))
    return decision


def test_missing_check_blocks_even_if_everything_else_passes():
    checks = [
        check("quality", "gain_vs_naive", "pass", 60, ">= 20"),
        check("quality", "gain_vs_accepted", "missing", "no accepted model", "req"),
    ]
    assert decide(checks)[0] == "blocked"


def test_integrity_failure_blocks_and_quality_failure_rejects():
    good = check("quality", "gain_vs_accepted", "pass", 1.0, ">= 0.5")
    assert decide([good, check("integrity", "frozen_data", "fail", "x", "=")])[0] == (
        "blocked"
    )
    assert decide([good, check("operation", "model_size", "fail", 500, "<=")])[0] == (
        "rejected"
    )
    assert decide([good])[0] == "eligible"


def test_no_accepted_model_is_blocked_not_passed(workspace, candidate):
    path = candidate(workspace, "first")
    decision = run_pipeline(workspace, path)
    assert decision["outcome"] == "blocked"
    assert EXIT["blocked"] == 4
    statuses = {c["name"]: c["status"] for c in decision["checks"]}
    assert statuses["gain_vs_accepted"] == "missing"
    assert not registry_root(workspace).exists()


@pytest.mark.parametrize(
    "change",
    [
        {"features": ["season", "yr"]},
        {"data": "data/raw/other.csv"},
        {"model": {"n_estimators": 10, "random_state": 7, "n_jobs": 1}},
        {"model": {"n_estimators": 10, "criterion": "poisson", "random_state": 42}},
    ],
)
def test_settings_guard_blocks_before_training(workspace, change, candidate):
    path = workspace / candidate(workspace, "guarded")
    config = yaml.safe_load(path.read_text())
    config.update(change)
    path.write_text(yaml.safe_dump(config))
    decision = run_pipeline(workspace, path.relative_to(workspace))
    assert decision["outcome"] == "blocked"
    assert not (workspace / decision["candidate"]["run_dir"] / "model.joblib").exists()


def test_rejection_leaves_the_accepted_state_unchanged(workspace, candidate):
    bootstrap(workspace)
    before = snapshot(registry_root(workspace))
    current = read_current(registry_root(workspace))
    weak = candidate(workspace, "weak", max_depth=2)
    decision = run_pipeline(workspace, weak)
    assert decision["outcome"] == "rejected"
    failed = [c["name"] for c in decision["checks"] if c["status"] == "fail"]
    assert failed == ["gain_vs_accepted"]
    assert snapshot(registry_root(workspace)) == before
    assert read_current(registry_root(workspace)) == current


def test_decision_record_names_policy_inputs_and_exact_bytes(workspace, candidate):
    bootstrap(workspace)
    decision = run_pipeline(workspace, candidate(workspace, "recorded"))
    record = json.loads((workspace / decision["record"]).read_text())
    assert record["policy"]["version"] == 1
    assert record["evaluation"]["window"] == "validation"
    assert record["results"]["validation_rows"] == 4358
    assert len(record["candidate"]["model_sha256"]) == 64
    assert record["accepted_before"]["model_version"].startswith("baseline-")
    assert not (workspace / "artifacts").exists()
