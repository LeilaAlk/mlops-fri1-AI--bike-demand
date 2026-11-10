"""Same inputs, same outputs? Compare two probe runs request key by key.

    python scripts/compare_attempts.py <baseline-attempts.jsonl> <other-attempts.jsonl>

The replay cohort is fixed, so both runs sent the same features for each key.
If the predictions differ for the same key, the answering model (or its
configuration) changed, not the inputs. Standard library only.
"""

import json
import sys
from pathlib import Path


def good_predictions(path: Path) -> dict[str, tuple[float, str]]:
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        attempt = json.loads(line)
        if attempt["kind"] == "valid" and attempt["good"]:
            rows[attempt["key"]] = (attempt["prediction"], attempt["model_version"])
    return rows


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    first, second = Path(sys.argv[1]), Path(sys.argv[2])
    a, b = good_predictions(first), good_predictions(second)
    common = sorted(set(a) & set(b))
    same = [k for k in common if abs(a[k][0] - b[k][0]) <= 1e-9]
    deltas = [abs(a[k][0] - b[k][0]) for k in common]
    print(
        f"{first.name}: {len(a)} good predictions, versions "
        f"{sorted({v for _, v in a.values()})}"
    )
    print(
        f"{second.name}: {len(b)} good predictions, versions "
        f"{sorted({v for _, v in b.values()})}"
    )
    print(f"same keys compared: {len(common)}")
    print(f"identical predictions: {len(same)}   different: {len(common) - len(same)}")
    if deltas:
        print(f"max abs difference: {max(deltas):.3f} bikes/hour")
    if not common:
        print("no common key with a good prediction in both runs: no evidence")
    return 0


if __name__ == "__main__":
    sys.exit(main())
