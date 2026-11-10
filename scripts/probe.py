"""Lab 8 probe: replay a fixed cohort against the live service and measure it.

Standard library only (like check_deployment.py): it observes the service from
outside, as a caller does. One run = one observation window.

    python scripts/probe.py --url <service url> --period baseline --out reports/incidents/evidence/baseline
    python scripts/probe.py --url <service url> --period watch-3 --baseline reports/incidents/evidence/baseline-summary.json --out ...

Writes two files and never edits them afterwards:
  <out>-attempts.jsonl  one raw line per attempt (UTC time, request id, status,
                        latency, model_version, prediction)
  <out>-summary.json    the signals below, with population, window and counts

Signals (same definitions in every period):
  valid_success     good / eligible. Eligible = every attempt of a known-valid
                    replay request, timeouts and connection errors included.
                    Good = HTTP 200 with a finite prediction >= 0 and a
                    model_version. Zero eligible attempts = no evidence (null).
  invalid_rejected  4xx / invalid attempts: deliberate bad inputs, reported
                    separately (a correct 422 is not a failure).
  latency           p50 / p95 (nearest rank) of successful valid attempts, ms,
                    measured by the caller; failed attempts listed apart.
  quality           MAE in bikes/hour of good predictions against the replay
                    labels (validation period only), with coverage = matched /
                    eligible. Service health and predictive quality are
                    separate claims.
  identity          /version before and after the window, and the
                    model_version counts seen in /predict responses.

With --baseline, the alert rules below compare this window to the baseline
window and the exit status is 1 when one fires (0 otherwise):
  valid_success < 0.99, MAE above baseline + 5 bikes/hour,
  p95 latency above 3 x baseline, or a model_version not seen in the baseline.
"""

import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path

INVALID = (
    ("hr=24", {"hr": 24}),
    ("temp=1.5", {"temp": 1.5}),
    ("weathersit=5", {"weathersit": 5}),
    ("missing windspeed", {"windspeed": None}),
)
MIN_SUCCESS = 0.99
MAX_MAE_INCREASE = 5.0
MAX_P95_FACTOR = 3.0


def utc(moment: float | None = None) -> str:
    stamp = datetime.fromtimestamp(moment or time.time(), UTC)
    return stamp.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def call(url: str, method: str = "GET", body: dict | None = None, request_id=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if request_id:
        request.add_header("X-Request-ID", request_id)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read() or b"null")
            status = response.status
    except urllib.error.HTTPError as error:
        status = error.code
        try:
            payload = json.loads(error.read() or b"null")
        except json.JSONDecodeError:
            payload = None
    except (urllib.error.URLError, OSError) as error:
        status, payload = 0, {"error": str(error)}
    return status, payload, round((time.perf_counter() - start) * 1000, 2)


def nearest_rank(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)]


def good_prediction(status: int, body) -> bool:
    if status != 200 or not isinstance(body, dict):
        return False
    value = body.get("prediction")
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
        and isinstance(body.get("model_version"), str)
    )


def run(args) -> dict:
    base = args.url.rstrip("/")
    cohort = [
        json.loads(line)
        for line in args.replay.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][: args.limit]
    if not cohort:
        raise SystemExit(f"{args.replay.as_posix()}: no replay rows")
    attempts = []
    window_start = utc()
    version_before = call(f"{base}/version")
    health_before = call(f"{base}/health")
    for row in cohort:
        request_id = f"probe-{args.period}-{uuid.uuid4().hex[:8]}"
        status, body, ms = call(f"{base}/predict", "POST", row["features"], request_id)
        body = body if isinstance(body, dict) else {}
        attempts.append(
            {
                "utc": utc(),
                "period": args.period,
                "kind": "valid",
                "key": row["key"],
                "request_id": request_id,
                "status": status,
                "latency_ms": ms,
                "good": good_prediction(status, body),
                "prediction": body.get("prediction"),
                "model_version": body.get("model_version"),
                "label_cnt": row["label_cnt"],
                "error": None
                if status == 200
                else body.get("detail", body.get("error")),
            }
        )
    for index in range(args.invalid):
        label, change = INVALID[index % len(INVALID)]
        features = {**cohort[index % len(cohort)]["features"], **change}
        features = {k: v for k, v in features.items() if v is not None}
        request_id = f"probe-{args.period}-bad-{uuid.uuid4().hex[:8]}"
        status, body, ms = call(f"{base}/predict", "POST", features, request_id)
        attempts.append(
            {
                "utc": utc(),
                "period": args.period,
                "kind": "invalid",
                "key": label,
                "request_id": request_id,
                "status": status,
                "latency_ms": ms,
                "good": 400 <= status < 500,
            }
        )
    version_after = call(f"{base}/version")
    window_end = utc()

    valid = [a for a in attempts if a["kind"] == "valid"]
    good = [a for a in valid if a["good"]]
    invalid = [a for a in attempts if a["kind"] == "invalid"]
    errors = [abs(a["prediction"] - a["label_cnt"]) for a in good]
    statuses: dict[str, int] = {}
    for attempt in valid:
        statuses[str(attempt["status"])] = statuses.get(str(attempt["status"]), 0) + 1
    versions: dict[str, int] = {}
    for attempt in good:
        versions[attempt["model_version"]] = (
            versions.get(attempt["model_version"], 0) + 1
        )
    success_ms = [a["latency_ms"] for a in good]
    summary = {
        "period": args.period,
        "url": base,
        "window_utc": [window_start, window_end],
        "cohort": f"{args.replay.as_posix()} (first {len(cohort)} validation hours)",
        "valid_success": {
            "good": len(good),
            "eligible": len(valid),
            "ratio": round(len(good) / len(valid), 4) if valid else None,
            "status_counts": statuses,
        },
        "invalid_rejected": {
            "rejected_4xx": sum(1 for a in invalid if a["good"]),
            "invalid": len(invalid),
        },
        "latency_ms_successful": {
            "n": len(success_ms),
            "p50": nearest_rank(success_ms, 0.50),
            "p95": nearest_rank(success_ms, 0.95),
            "method": "nearest rank, caller-side",
        },
        "latency_ms_failed": [a["latency_ms"] for a in valid if not a["good"]],
        "quality": {
            "mae_bikes_per_hour": round(sum(errors) / len(errors), 3)
            if errors
            else None,
            "matched": len(errors),
            "eligible": len(valid),
            "coverage": round(len(errors) / len(valid), 4) if valid else None,
        },
        "identity": {
            "version_before": {"status": version_before[0], "body": version_before[1]},
            "health_before": {"status": health_before[0], "body": health_before[1]},
            "version_after": {"status": version_after[0], "body": version_after[1]},
            "predict_model_versions": versions,
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    attempts_path = out.with_name(out.name + "-attempts.jsonl")
    with attempts_path.open("w", encoding="utf-8", newline="\n") as stream:
        for attempt in attempts:
            stream.write(json.dumps(attempt) + "\n")
    summary["raw_attempts"] = attempts_path.as_posix()
    return summary


def alerts(summary: dict, baseline: dict) -> list[str]:
    fired = []
    ratio = summary["valid_success"]["ratio"]
    if ratio is None:
        fired.append("no eligible valid attempts: no evidence")
    elif ratio < MIN_SUCCESS:
        fired.append(f"valid_success {ratio} < {MIN_SUCCESS}")
    mae, base_mae = summary["quality"]["mae_bikes_per_hour"], None
    base_mae = baseline["quality"]["mae_bikes_per_hour"]
    if mae is not None and base_mae is not None and mae > base_mae + MAX_MAE_INCREASE:
        fired.append(f"MAE {mae} > baseline {base_mae} + {MAX_MAE_INCREASE}")
    p95 = summary["latency_ms_successful"]["p95"]
    base_p95 = baseline["latency_ms_successful"]["p95"]
    if p95 is not None and base_p95 and p95 > MAX_P95_FACTOR * base_p95:
        fired.append(f"p95 {p95} ms > {MAX_P95_FACTOR} x baseline {base_p95} ms")
    known = set(baseline["identity"]["predict_model_versions"])
    new = sorted(set(summary["identity"]["predict_model_versions"]) - known)
    if new:
        fired.append(f"model_version not seen in baseline: {new}")
    return fired


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", required=True)
    parser.add_argument("--period", required=True, help="baseline, watch-1, after...")
    parser.add_argument("--out", required=True, help="path prefix for the two files")
    parser.add_argument(
        "--replay", type=Path, default=Path("examples/replay-validation.jsonl")
    )
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--invalid", type=int, default=20)
    parser.add_argument("--baseline", type=Path, help="baseline -summary.json")
    args = parser.parse_args()
    summary = run(args)
    fired = []
    if args.baseline:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        fired = alerts(summary, baseline)
        summary["compared_with"] = args.baseline.as_posix()
    summary["alerts"] = fired
    summary_path = Path(args.out).with_name(Path(args.out).name + "-summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    valid, quality = summary["valid_success"], summary["quality"]
    latency, identity = summary["latency_ms_successful"], summary["identity"]
    print(
        f"period {summary['period']}  window {summary['window_utc'][0]} -> "
        f"{summary['window_utc'][1]}"
    )
    print(
        f"valid success   {valid['good']}/{valid['eligible']} = {valid['ratio']}  "
        f"statuses {valid['status_counts']}"
    )
    print(
        f"invalid 4xx     {summary['invalid_rejected']['rejected_4xx']}/"
        f"{summary['invalid_rejected']['invalid']}"
    )
    print(
        f"latency ok (ms) p50 {latency['p50']}  p95 {latency['p95']}  n={latency['n']}"
    )
    print(
        f"quality MAE     {quality['mae_bikes_per_hour']} bikes/h  coverage "
        f"{quality['matched']}/{quality['eligible']}"
    )
    print(f"model_version   {identity['predict_model_versions']}")
    after = identity["version_after"]["body"] or {}
    print(
        f"/version after  {after.get('model_version')}  "
        f"sha {str(after.get('model_sha256'))[:12]}  "
        f"revision {str(after.get('service_revision'))[:12]}"
    )
    for alert in fired:
        print(f"ALERT {alert}")
    print(f"files {summary['raw_attempts']}  {summary_path.as_posix()}")
    return 1 if fired else 0


if __name__ == "__main__":
    sys.exit(main())
