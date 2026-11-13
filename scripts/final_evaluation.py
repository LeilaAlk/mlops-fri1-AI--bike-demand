"""Week 5: score the held test ONCE, for the model already selected.

    uv run --locked python scripts/final_evaluation.py --decision decisions/<record>-eligible.json --bundle <folder with model.joblib>

The selection was made in Lab 7 on the validation window only. This script
never compares candidates: it scores the one accepted model on the held test
partition (2012-07-01..2012-12-31) and writes reports/final-evaluation.json.
It refuses to run a second time (the file already exists): a second look at
the test data would turn it into a selection set. The train-mean baseline is
scored on the same rows only as context for the number.

Checks before scoring: the bundle bytes match the committed decision, the data
snapshot matches the manifest, the features are the contract features.
"""

import argparse
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from sklearn.metrics import mean_absolute_error

from bike_demand.preflight import check_snapshot
from bike_demand.registry import IntegrityError, load_verified
from bike_demand.split import split_data
from bike_demand.validate import FEATURES, load_data

OUT = Path("reports/final-evaluation.json")


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    if OUT.exists():
        print(f"refused: {OUT.as_posix()} exists, the held test is scored once")
        return 1
    decision = json.loads(args.decision.read_text(encoding="utf-8"))
    if decision.get("outcome") != "eligible":
        print(f"refused: {args.decision.as_posix()} is not an eligible decision")
        return 1
    candidate = decision["candidate"]
    try:
        model, metadata = load_verified(args.bundle, candidate["model_sha256"])
    except IntegrityError as error:
        print(f"refused: {error}")
        return 1
    snapshot = check_snapshot(Path.cwd())
    partitions = split_data(load_data("data/raw/hour.csv"))
    train, test = partitions["train"], partitions["test"]
    features = list(FEATURES)
    predictions = model.predict(test.loc[:, features])
    mae = float(mean_absolute_error(test["cnt"], predictions))
    naive = float(
        mean_absolute_error(test["cnt"], np.full(len(test), train["cnt"].mean()))
    )
    result = {
        "scored_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "purpose": "single held-test evaluation of the model already selected "
        "on validation (Lab 7); not used to choose between models",
        "code_commit": git("rev-parse", "HEAD"),
        "decision_record": args.decision.as_posix(),
        "model_version": metadata["model_version"],
        "model_sha256": candidate["model_sha256"],
        "data_sha256": snapshot["sha256"],
        "test_window": [
            str(test["dteday"].min().date()),
            str(test["dteday"].max().date()),
        ],
        "test_rows": len(test),
        "metric": "MAE, bikes per hour",
        "test_mae": round(mae, 3),
        "test_mae_train_mean_baseline": round(naive, 3),
        "validation_mae_at_selection": round(decision["results"]["candidate_mae"], 3),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"written {OUT.as_posix()} (commit it; never rerun to get another number)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
