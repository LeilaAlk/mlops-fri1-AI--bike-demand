"""Check a running bike-demand service from outside, over HTTP.

Every claim has an expected value (from the model record and the Git commit you
built) and an observed value (from the running service). One mismatch fails the
whole check with exit status 1. Standard library only: no project code is
imported, so this checks the container, not the laptop code.

Example:
  python scripts/check_deployment.py --url http://127.0.0.1:8000 \
      --expected-metadata expected-model.json --expected-revision <git sha>
"""

import argparse
import json
import math
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

VALID = {
    "season": 3,
    "yr": 1,
    "mnth": 7,
    "hr": 17,
    "holiday": 0,
    "weekday": 3,
    "workingday": 1,
    "weathersit": 1,
    "temp": 0.7,
    "atemp": 0.65,
    "hum": 0.5,
    "windspeed": 0.2,
}


def call(url: str, method: str = "GET", body: dict | None = None, request_id=None):
    """Return (status, json body or None, headers); status 0 if unreachable."""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if request_id:
        request.add_header("X-Request-ID", request_id)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read() or b"null"), response
    except urllib.error.HTTPError as error:
        try:
            payload = json.loads(error.read() or b"null")
        except json.JSONDecodeError:
            payload = None
        return error.code, payload, error
    except (urllib.error.URLError, OSError) as error:
        return 0, {"error": str(error)}, None


def short(value) -> str:
    text = str(value)
    return text if len(text) <= 24 else text[:21] + "..."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--expected-metadata",
        type=Path,
        required=True,
        help="model-metadata.json copied out of the image before starting it",
    )
    parser.add_argument(
        "--expected-revision", required=True, help="git rev-parse HEAD you built"
    )
    parser.add_argument("--report", type=Path, help="also write the results as JSON")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    expected = json.loads(args.expected_metadata.read_text(encoding="utf-8-sig"))

    claims = []

    def claim(name, want, seen, ok=None):
        passed = (want == seen) if ok is None else ok
        claims.append(
            {"claim": name, "expected": want, "observed": seen, "ok": bool(passed)}
        )

    status, health, _ = call(f"{base}/health")
    claim("ready (/health)", 200, status)

    status, info, _ = call(f"{base}/version")
    info = info if status == 200 and isinstance(info, dict) else {}
    claim("model_version", expected.get("model_version"), info.get("model_version"))
    claim("model_sha256", expected.get("model_sha256"), info.get("model_sha256"))
    claim("service_revision", args.expected_revision, info.get("service_revision"))

    request_id = f"check-{uuid.uuid4().hex[:8]}"
    status, body, response = call(f"{base}/predict", "POST", VALID, request_id)
    body = body if isinstance(body, dict) else {}
    prediction = body.get("prediction")
    valid_number = isinstance(prediction, (int, float)) and math.isfinite(prediction)
    claim(
        "valid input -> 200",
        "200, finite >= 0",
        f"{status}, {prediction}",
        status == 200 and valid_number and prediction >= 0,
    )
    claim(
        "prediction model_version",
        expected.get("model_version"),
        body.get("model_version"),
    )
    echoed = response.headers.get("X-Request-ID") if response is not None else None
    claim("request id echoed", request_id, echoed)

    status, _, _ = call(f"{base}/predict", "POST", {**VALID, "hr": 24})
    claim("invalid hr=24 -> 422", 422, status)

    print(f"{'claim':26} {'expected':26} {'observed':26} result")
    for item in claims:
        result = "ok" if item["ok"] else "FAIL"
        print(
            f"{item['claim']:26} {short(item['expected']):26} "
            f"{short(item['observed']):26} {result}"
        )
    failed = [item["claim"] for item in claims if not item["ok"]]
    print(
        f"exit status {1 if failed else 0}" + (f" (failed: {failed})" if failed else "")
    )
    if args.report:
        report = {"url": base, "claims": claims, "passed": not failed}
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
