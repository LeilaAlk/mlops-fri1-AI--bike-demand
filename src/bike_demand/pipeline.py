"""Lab 7 entry point: one candidate in, one decided candidate out.

    uv run --locked python -m bike_demand.pipeline --candidate configs/candidates/<name>.yaml

Stages (each consumes the previous stage's output; failure is an output too):

1. inputs    frozen data hash = policy, candidate settings inside the guard, split
2. train     fit on the 2011 rows only, write runs/<run_id>.partial/ then rename
3. evaluate  candidate, train-mean baseline and the accepted model on the same
             4,358 validation rows; model size and single-row predict time
4. decide    apply configs/gate-policy.yaml rule by rule
5. record    runs/<run_id>/decision.json and decisions/<utc>-<name>-<outcome>.json

The pipeline never writes artifacts/ or registry/: a candidate cannot become
serving state here. Promotion is a separate, reviewed step (bike_demand.promote).

Exit status (how CI or a script observes the outcome):
0 eligible, 3 rejected (a measured rule failed), 4 blocked (evidence missing or
invalid: repair, then rerun).
"""

import argparse
import json
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import joblib
import numpy as np
import pandas as pd
import sklearn
import yaml
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

from bike_demand.preflight import check_snapshot, sha256
from bike_demand.registry import (
    IntegrityError,
    load_verified,
    read_current,
    registry_root,
    version_dir,
)
from bike_demand.split import partition_summary, split_data
from bike_demand.train import DEFAULT_MODEL, compare_mean
from bike_demand.validate import FEATURES, load_data

EXIT = {"eligible": 0, "rejected": 3, "blocked": 4}
POLICY_PATH = Path("configs/gate-policy.yaml")
LAB2_RECORD = Path("tests/regression/baseline-expected.json")
MODEL_KEYS = {"n_estimators", "max_depth", "min_samples_leaf", "random_state", "n_jobs"}


class Blocked(ValueError):
    """Evidence is missing or invalid: no decision on quality is possible."""


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def load_policy(path: Path) -> dict:
    policy = yaml.safe_load(path.read_text())
    required = {
        "policy_version",
        "evaluation",
        "quality",
        "operation",
        "candidate_settings",
        "budget",
    }
    if not isinstance(policy, dict) or not required <= set(policy):
        raise Blocked(f"policy {path.as_posix()}: missing {sorted(required)}")
    return policy


def is_int(value) -> bool:
    return type(value) is int


def check_candidate(config: dict, policy: dict, bootstrap: bool) -> dict:
    """Settings guard: same data, same twelve ordered predictors, bounded settings."""
    if not isinstance(config, dict) or not {"data", "features", "model"} <= set(config):
        raise Blocked("candidate: require data, features and model")
    extra = set(config) - {"name", "data", "features", "model"}
    if extra:
        raise Blocked(f"candidate: unexpected keys {sorted(extra)}")
    if config["data"] != "data/raw/hour.csv":
        raise Blocked("candidate: use the frozen data/raw/hour.csv snapshot")
    if config["features"] != list(FEATURES):
        raise Blocked("candidate: require the twelve ordered contract predictors")
    model = config["model"]
    if not isinstance(model, dict) or set(model) - MODEL_KEYS:
        raise Blocked(f"candidate: model settings limited to {sorted(MODEL_KEYS)}")
    guard = policy["candidate_settings"]
    for key, value in guard["fixed"].items():
        if model.get(key) != value:
            raise Blocked(f"candidate: {key} must stay {value}")
    for key in ("n_estimators", "max_depth", "min_samples_leaf"):
        if key not in model or (key == "max_depth" and model[key] is None):
            continue
        low, high = guard[key]
        if not is_int(model[key]) or not low <= model[key] <= high:
            raise Blocked(f"candidate: {key} must be an integer in [{low}, {high}]")
    if bootstrap and model != DEFAULT_MODEL:
        raise Blocked("bootstrap: only the Lab 2 baseline settings can be bootstrapped")
    return config


def p95_nearest_rank(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, int(np.ceil(0.95 * len(ordered))) - 1)]


def predict_latency_ms(model, rows: pd.DataFrame) -> list[float]:
    durations = []
    for index in range(len(rows)):
        row = rows.iloc[[index]]
        start = time.perf_counter()
        model.predict(row)
        durations.append((time.perf_counter() - start) * 1000)
    return durations


def check(group: str, name: str, status: str, observed, rule: str) -> dict:
    return {
        "group": group,
        "name": name,
        "status": status,
        "observed": observed,
        "rule": rule,
    }


def passed(condition: bool) -> str:
    return "pass" if condition else "fail"


def decide(checks: list[dict]) -> tuple[str, list[str]]:
    """Blocked if any evidence is missing or any integrity check failed; then
    rejected if a measured rule failed; eligible only if every check passed."""
    missing = [c for c in checks if c["status"] == "missing"]
    integrity = [
        c for c in checks if c["group"] == "integrity" and c["status"] != "pass"
    ]
    failed = [c for c in checks if c["status"] == "fail" and c["group"] != "integrity"]
    reasons = [
        f"{c['group']}/{c['name']}: {c['status']} ({c['observed']}; rule {c['rule']})"
        for c in missing + integrity + failed
    ]
    if missing or integrity:
        return "blocked", reasons
    if failed:
        return "rejected", reasons
    return "eligible", ["all quality, operation and integrity checks passed"]


def evaluate(root: Path, config: dict, policy: dict, bootstrap: bool, run: Path):
    """Stages 1-3. Returns (checks, results, candidate, accepted)."""
    checks: list[dict] = []
    snapshot = check_snapshot(root)
    expected_data = policy["evaluation"]["data_sha256"]
    checks.append(
        check(
            "integrity",
            "frozen_data",
            passed(snapshot["sha256"] == expected_data),
            snapshot["sha256"][:12],
            f"= policy {expected_data[:12]}",
        )
    )
    partitions = split_data(load_data(root / config["data"]))
    train, validation = partitions["train"], partitions["validation"]
    features = list(FEATURES)
    # Stage 2: train on 2011 only. The held test partition is never used.
    model = RandomForestRegressor(**config["model"])
    model.fit(train.loc[:, features], train["cnt"])
    predictions = model.predict(validation.loc[:, features])
    candidate_mae = float(mean_absolute_error(validation["cnt"], predictions))
    _, naive_mae = compare_mean(train["cnt"], validation["cnt"])
    model_path = run / "model.joblib"
    joblib.dump(model, model_path)
    digest = sha256(model_path)
    reloaded = joblib.load(model_path).predict(validation.loc[:, features])
    checks.append(
        check(
            "integrity",
            "reload_same_predictions",
            passed(np.array_equal(predictions, reloaded)),
            f"max abs delta {float(np.max(np.abs(predictions - reloaded)))}",
            "saved bytes reproduce the evaluated predictions",
        )
    )
    checks.append(
        check(
            "integrity",
            "finite_nonnegative_predictions",
            passed(bool(np.isfinite(predictions).all() and (predictions >= 0).all())),
            f"min {float(predictions.min()):.3f}",
            "finite and >= 0",
        )
    )
    model_mb = model_path.stat().st_size / 1_000_000
    rows = validation.loc[:, features].head(policy["operation"]["latency_rows"])
    durations = predict_latency_ms(model, rows)
    p95 = p95_nearest_rank(durations)
    operation = policy["operation"]
    checks.append(
        check(
            "operation",
            "model_size",
            passed(model_mb <= operation["max_model_mb"]),
            f"{model_mb:.1f} MB",
            f"<= {operation['max_model_mb']} MB",
        )
    )
    checks.append(
        check(
            "operation",
            "p95_single_row_predict",
            passed(p95 <= operation["max_p95_predict_ms"]),
            f"{p95:.2f} ms over n={len(durations)}",
            f"<= {operation['max_p95_predict_ms']} ms",
        )
    )
    quality = policy["quality"]
    gain_naive = naive_mae - candidate_mae
    checks.append(
        check(
            "quality",
            "gain_vs_naive",
            passed(gain_naive >= quality["min_gain_vs_naive"]),
            f"{gain_naive:.3f} bikes/h (naive {naive_mae:.3f}, "
            f"candidate {candidate_mae:.3f})",
            f">= {quality['min_gain_vs_naive']}",
        )
    )
    accepted = None
    accepted_mae = None
    try:
        current = read_current(registry_root(root))
    except (IntegrityError, ValueError) as error:
        current = None
        checks.append(
            check("integrity", "accepted_record", "fail", str(error), "readable")
        )
    if bootstrap:
        record = json.loads((root / LAB2_RECORD).read_text())
        recorded = record["validation_mae"]["random_forest"]
        tolerance = record["tolerance_abs"]
        checks.append(
            check(
                "integrity",
                "registry_empty_for_bootstrap",
                passed(current is None),
                "empty" if current is None else current["model_version"],
                "bootstrap only before the first accepted version",
            )
        )
        checks.append(
            check(
                "quality",
                "matches_recorded_lab2_model",
                passed(abs(candidate_mae - recorded) <= tolerance),
                f"{candidate_mae:.6f} vs recorded {recorded:.6f}",
                f"within {tolerance} ({LAB2_RECORD.as_posix()})",
            )
        )
    elif current is None:
        checks.append(
            check(
                "quality",
                "gain_vs_accepted",
                "missing",
                "no accepted model in the registry",
                "an accepted model is required to compare with",
            )
        )
    else:
        try:
            directory = version_dir(registry_root(root), current["model_version"])
            accepted_model, _ = load_verified(directory, current["model_sha256"])
        except (IntegrityError, OSError) as error:
            checks.append(
                check("integrity", "accepted_bundle", "fail", str(error), "verified")
            )
        else:
            accepted = {
                "model_version": current["model_version"],
                "model_sha256": current["model_sha256"],
                "decision_id": current["decision_id"],
            }
            checks.append(
                check(
                    "integrity",
                    "accepted_bundle",
                    "pass",
                    current["model_sha256"][:12],
                    "bytes match the registry record before loading",
                )
            )
            accepted_predictions = accepted_model.predict(validation.loc[:, features])
            accepted_mae = float(
                mean_absolute_error(validation["cnt"], accepted_predictions)
            )
            gain = accepted_mae - candidate_mae
            checks.append(
                check(
                    "quality",
                    "gain_vs_accepted",
                    passed(gain >= quality["min_gain_vs_accepted"]),
                    f"{gain:.3f} bikes/h (accepted {accepted_mae:.3f}, "
                    f"candidate {candidate_mae:.3f}, same {len(validation)} rows)",
                    f">= {quality['min_gain_vs_accepted']}",
                )
            )
    results = {
        "validation_rows": len(validation),
        "naive_train_mean_mae": naive_mae,
        "candidate_mae": candidate_mae,
        "accepted_mae": accepted_mae,
        "model_mb": round(model_mb, 3),
        "p95_single_row_predict_ms": round(p95, 3),
        "latency_rows": len(durations),
        "partitions": partition_summary(partitions),
    }
    candidate = {"model_sha256": digest, "model_bytes": model_path.stat().st_size}
    return checks, results, candidate, accepted, snapshot


def run_pipeline(
    root: Path,
    candidate_path: Path,
    policy_path: Path = POLICY_PATH,
    bootstrap: bool = False,
) -> dict:
    run_id = uuid4().hex
    runs = root / "runs"
    partial = runs / f"{run_id}.partial"
    partial.mkdir(parents=True)
    policy_file = root / policy_path
    decision = {
        "decision_id": run_id,
        "created_at": utc_now(),
        "kind": "bootstrap" if bootstrap else "candidate",
        "code": {
            "commit": git(root, "rev-parse", "HEAD"),
            # Tracked files only: the run's own log files are untracked.
            "dirty": git(root, "status", "--porcelain", "--untracked-files=no")
            not in ("", "unavailable"),
        },
        "policy": {
            "path": policy_path.as_posix(),
            "sha256": sha256(policy_file) if policy_file.is_file() else None,
            "last_commit": git(
                root, "log", "-1", "--format=%H %cI", "--", policy_path.as_posix()
            ),
        },
        "candidate": {"config_path": candidate_path.as_posix()},
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "scikit_learn": sklearn.__version__,
        },
    }
    try:
        policy = load_policy(policy_file)
        decision["policy"]["version"] = policy["policy_version"]
        config = yaml.safe_load((root / candidate_path).read_text())
        check_candidate(config, policy, bootstrap)
        name = config.get("name") or candidate_path.stem
        decision["candidate"].update(
            name=name,
            config_sha256=sha256(root / candidate_path),
            settings=config["model"],
            model_version=f"{name}-{run_id[:12]}",
        )
        checks, results, candidate, accepted, _ = evaluate(
            root, config, policy, bootstrap, partial
        )
        decision["candidate"].update(candidate)
        decision["accepted_before"] = accepted
        decision["evaluation"] = {
            "data_sha256": policy["evaluation"]["data_sha256"],
            "window": policy["evaluation"]["window"],
            "metric": policy["evaluation"]["metric"],
        }
        decision["results"] = results
        decision["checks"] = checks
        outcome, reasons = decide(checks)
    except (Blocked, IntegrityError, OSError, ValueError, KeyError) as error:
        outcome, reasons = "blocked", [f"{type(error).__name__}: {error}"]
        decision.setdefault("checks", [])
    decision["outcome"] = outcome
    decision["reasons"] = reasons
    final = runs / run_id
    if "evaluation" in decision and (partial / "model.joblib").is_file():
        metadata = {
            "model_version": decision["candidate"]["model_version"],
            "model_sha256": decision["candidate"]["model_sha256"],
            "features": list(FEATURES),
            "decision_id": run_id,
            "training_commit": decision["code"]["commit"],
            "data_sha256": decision["evaluation"]["data_sha256"],
            "settings": decision["candidate"]["settings"],
        }
        (partial / "model-metadata.json").write_text(json.dumps(metadata, indent=2))
    decision["candidate"]["run_dir"] = final.relative_to(root).as_posix()
    text = json.dumps(decision, indent=2, allow_nan=False) + "\n"
    (partial / "decision.json").write_text(text)
    partial.rename(final)  # only complete runs lose the .partial suffix
    stamp = decision["created_at"].replace(":", "").replace("-", "")
    name = decision["candidate"].get("name", candidate_path.stem)
    record = root / "decisions" / f"{stamp}-{name}-{outcome}.json"
    record.parent.mkdir(exist_ok=True)
    record.write_text(text)
    decision["record"] = record.relative_to(root).as_posix()
    return decision


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=POLICY_PATH)
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="register the Lab 2 baseline as the first accepted model (empty registry)",
    )
    args = parser.parse_args()
    decision = run_pipeline(Path.cwd(), args.candidate, args.policy, args.bootstrap)
    print(f"decision: {decision['outcome'].upper()}  record: {decision['record']}")
    for check_item in decision["checks"]:
        print(
            f"  [{check_item['status']:7}] {check_item['group']}/{check_item['name']}: "
            f"{check_item['observed']}  (rule {check_item['rule']})"
        )
    for reason in decision["reasons"]:
        print(f"  reason: {reason}")
    return EXIT[decision["outcome"]]


if __name__ == "__main__":
    sys.exit(main())
