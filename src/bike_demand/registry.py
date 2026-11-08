"""Accepted-model store: immutable versions plus one 'current' reference.

Layout (kept out of Git, see .gitignore):

    registry/versions/<model_version>/model.joblib
    registry/versions/<model_version>/model-metadata.json
    registry/versions/<model_version>/decision.json
    registry/current.json      which accepted version is current, and the one it replaced
    registry/history.jsonl     one line per promotion, never rewritten

A version folder is never modified after promotion; promotion only moves the
'current' reference. Only bike_demand.promote writes here.
"""

import json
import os
from pathlib import Path

import joblib

from bike_demand.preflight import sha256
from bike_demand.validate import FEATURES

REGISTRY_ENV = "BIKE_DEMAND_REGISTRY"
DEFAULT_REGISTRY = "registry"
BUNDLE_FILES = ("model.joblib", "model-metadata.json")


class IntegrityError(ValueError):
    """A bundle's bytes or metadata do not match the trusted record."""


def registry_root(root: Path) -> Path:
    return root / os.environ.get(REGISTRY_ENV, DEFAULT_REGISTRY)


def read_current(registry: Path) -> dict | None:
    """The current accepted reference, or None before the first acceptance."""
    path = registry / "current.json"
    if not path.is_file():
        return None
    current = json.loads(path.read_text())
    for key in ("model_version", "model_sha256", "decision_id"):
        if not current.get(key):
            raise IntegrityError(f"registry/current.json: missing {key}")
    return current


def version_dir(registry: Path, model_version: str) -> Path:
    if not model_version or "/" in model_version or "\\" in model_version:
        raise IntegrityError(f"invalid model_version {model_version!r}")
    return registry / "versions" / model_version


def verify_bundle(directory: Path, expected_sha256: str) -> dict:
    """Check the files before any pickle is loaded; return the metadata."""
    for name in BUNDLE_FILES:
        if not (directory / name).is_file():
            raise IntegrityError(f"{directory.as_posix()}: missing {name}")
    metadata = json.loads((directory / "model-metadata.json").read_text())
    digest = sha256(directory / "model.joblib")
    if digest != metadata.get("model_sha256"):
        raise IntegrityError(
            f"{directory.as_posix()}: model.joblib sha256 {digest[:12]} differs "
            f"from its metadata {str(metadata.get('model_sha256'))[:12]}"
        )
    if digest != expected_sha256:
        raise IntegrityError(
            f"{directory.as_posix()}: model.joblib sha256 {digest[:12]} differs "
            f"from the trusted record {expected_sha256[:12]}"
        )
    if list(metadata.get("features", [])) != list(FEATURES):
        raise IntegrityError(f"{directory.as_posix()}: feature order differs")
    return metadata


def load_verified(directory: Path, expected_sha256: str):
    """Verify, then load. Only our own retained bundles are ever loaded."""
    metadata = verify_bundle(directory, expected_sha256)
    return joblib.load(directory / "model.joblib"), metadata


def snapshot(registry: Path) -> dict:
    """Hashes of everything in the registry: used to prove what did not change."""
    if not registry.exists():
        return {}
    return {
        path.relative_to(registry).as_posix(): sha256(path)
        for path in sorted(registry.rglob("*"))
        if path.is_file()
    }
