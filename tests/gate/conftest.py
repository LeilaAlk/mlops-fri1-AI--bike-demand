"""A throwaway project copy per test: the repository's runs/, decisions/ and
registry/ are never touched."""

import shutil
from pathlib import Path

import pytest
import yaml

from bike_demand.validate import FEATURES

ROOT = Path(__file__).resolve().parents[2]
COPIED = (
    "data/raw/hour.csv",
    "data/manifest.json",
    "configs/gate-policy.yaml",
    "configs/baseline.yaml",
    "tests/regression/baseline-expected.json",
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    for name in COPIED:
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, tmp_path / name)
    return tmp_path


def write_candidate(root: Path, name: str, **model) -> Path:
    """A small, fast candidate (10 trees) unless settings say otherwise."""
    settings = {"n_estimators": 10, "max_depth": 10, "random_state": 42, "n_jobs": 1}
    settings.update(model)
    path = root / "configs/candidates" / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    config = {
        "name": name,
        "data": "data/raw/hour.csv",
        "features": list(FEATURES),
        "model": settings,
    }
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    return path.relative_to(root)


@pytest.fixture
def candidate():
    return write_candidate
