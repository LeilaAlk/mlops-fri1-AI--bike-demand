"""Lab 6 regression: retrain the Lab 2 baseline on the frozen snapshot and
compare with the recorded result. Catches silent changes in data, split,
features, model settings or library versions."""

import json
import shutil
from pathlib import Path

import pytest

from bike_demand.train import train_baseline

pytestmark = pytest.mark.recompute
ROOT = Path(__file__).resolve().parents[2]
EXPECTED = json.loads((Path(__file__).parent / "baseline-expected.json").read_text())


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    """Train once in a throwaway copy: the repository's reports/ stay untouched."""
    work = tmp_path_factory.mktemp("recompute")
    (work / "data/raw").mkdir(parents=True)
    (work / "configs").mkdir()
    for name in ("data/raw/hour.csv", "data/manifest.json", "configs/baseline.yaml"):
        shutil.copyfile(ROOT / name, work / name)
    return train_baseline(work, work / "configs/baseline.yaml")


def test_same_frozen_data(result):
    assert result["data_sha256"] == EXPECTED["data_sha256"]


def test_same_chronological_split(result):
    rows = {name: part["rows"] for name, part in result["partitions"].items()}
    assert rows == EXPECTED["partition_rows"]


@pytest.mark.parametrize("predictor", ["naive_train_mean", "random_forest"])
def test_validation_mae_matches_recorded_result(result, predictor):
    observed = result["validation_mae"][predictor]
    expected = EXPECTED["validation_mae"][predictor]
    assert observed == pytest.approx(expected, abs=EXPECTED["tolerance_abs"]), (
        f"{predictor}: recomputed MAE {observed} differs from recorded {expected}"
    )


def test_test_period_is_never_scored(result):
    assert "test_mae" not in json.dumps(result)
