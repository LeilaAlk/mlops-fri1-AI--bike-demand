"""Lab 7 promotion: only eligible, unchanged bytes; the replaced version is
kept; a refused promotion changes nothing."""

import json
from pathlib import Path

import pytest

from bike_demand.pipeline import run_pipeline
from bike_demand.promote import PromotionRefused, promote
from bike_demand.registry import (
    IntegrityError,
    read_current,
    registry_root,
    snapshot,
    version_dir,
)

pytestmark = pytest.mark.gate


@pytest.fixture
def accepted(workspace) -> Path:
    decision = run_pipeline(workspace, Path("configs/baseline.yaml"), bootstrap=True)
    promote(workspace, Path(decision["record"]), "reviewer", reviewed=False)
    return workspace


def eligible(root: Path, candidate) -> dict:
    # 50 unlimited-depth trees beat the 50-tree depth-10 baseline by > 0.5.
    path = candidate(root, "better", n_estimators=50, max_depth=None)
    decision = run_pipeline(root, path)
    assert decision["outcome"] == "eligible", decision["reasons"]
    return decision


def test_promotion_moves_current_and_keeps_the_previous_version(accepted, candidate):
    registry = registry_root(accepted)
    previous = read_current(registry)
    decision = eligible(accepted, candidate)
    record = promote(accepted, Path(decision["record"]), "reviewer", reviewed=False)
    current = read_current(registry)
    assert current["model_sha256"] == decision["candidate"]["model_sha256"]
    assert current["previous"]["model_version"] == previous["model_version"]
    assert version_dir(registry, previous["model_version"]).is_dir()
    assert record["approved_by"] == "reviewer"
    lines = (registry / "history.jsonl").read_text().splitlines()
    assert len(lines) == 2


def test_rejected_decision_is_refused_and_nothing_changes(accepted, candidate):
    registry = registry_root(accepted)
    before = snapshot(registry)
    weak = run_pipeline(accepted, candidate(accepted, "weak", max_depth=2))
    with pytest.raises(PromotionRefused, match="only 'eligible'"):
        promote(accepted, Path(weak["record"]), "reviewer", reviewed=False)
    assert snapshot(registry) == before


def test_changed_candidate_bytes_are_refused(accepted, candidate):
    registry = registry_root(accepted)
    before = snapshot(registry)
    decision = eligible(accepted, candidate)
    model = accepted / decision["candidate"]["run_dir"] / "model.joblib"
    model.write_bytes(model.read_bytes() + b"tampered")
    with pytest.raises(IntegrityError):
        promote(accepted, Path(decision["record"]), "reviewer", reviewed=False)
    assert snapshot(registry) == before


def test_stale_decision_is_refused_after_another_promotion(accepted, candidate):
    first = eligible(accepted, candidate)
    second = run_pipeline(
        accepted,
        candidate(accepted, "other", n_estimators=60, max_depth=None),
    )
    assert second["outcome"] == "eligible", second["reasons"]
    promote(accepted, Path(first["record"]), "reviewer", reviewed=False)
    with pytest.raises(PromotionRefused, match="changed since this decision"):
        promote(accepted, Path(second["record"]), "reviewer", reviewed=False)


def test_versions_are_never_overwritten(accepted, candidate):
    decision = eligible(accepted, candidate)
    target = version_dir(
        registry_root(accepted), decision["candidate"]["model_version"]
    )
    target.mkdir(parents=True)
    with pytest.raises(PromotionRefused, match="immutable"):
        promote(accepted, Path(decision["record"]), "reviewer", reviewed=False)
    assert read_current(registry_root(accepted))["model_version"].startswith("baseline")


def test_bootstrap_is_refused_once_a_model_is_accepted(accepted, candidate):
    decision = run_pipeline(accepted, Path("configs/baseline.yaml"), bootstrap=True)
    assert decision["outcome"] == "blocked"
    record = json.loads((accepted / decision["record"]).read_text())
    failed = [c["name"] for c in record["checks"] if c["status"] == "fail"]
    assert "registry_empty_for_bootstrap" in failed
