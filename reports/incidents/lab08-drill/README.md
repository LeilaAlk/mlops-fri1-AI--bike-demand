# Incident record: <short name> (Lab 8 drill)

Status: <resolved / mitigated, monitoring>. Service `bike-demand` on Cloud Run,
region `europe-west1`. All times UTC. Raw evidence: [`evidence/`](evidence/).

| Role | Person |
| --- | --- |
| Operator (investigates, makes the agreed change) | Andrea |
| Injector (one reversible fault, revealed after the diagnosis) | Julia |
| Recorder (this timeline) | Talia |
| Coordinator, baseline and monitoring | Leila |

## 1. Normal, recorded before the injection

| | Value |
| --- | --- |
| Workload | `scripts/probe.py`, cohort `examples/replay-validation.jsonl` (200 valid validation-period hours) + 20 invalid requests, from Leila's laptop |
| Environment | Cloud Run `bike-demand`, `europe-west1`, 1 GiB, max 2 instances |
| Identity | revision `bike-demand-v2-deeper`, model `deeper-trees-e024f62d651a`, sha256 `94f4f4b8f348…`, code `a9eda78` (= `reports/releases.md`, line `serving 100%`) |
| Window, n | `19:04:15` -> `19:04:38` UTC, 200 valid + 20 invalid |
| Signals | valid success `200/200`, invalid 4xx `20/20`, p50/p95 `91.76/203.73` ms (n=200), MAE `95.519` bikes/h (coverage 200/200) |
| Evidence | [`evidence/baseline-summary.json`](evidence/baseline-summary.json), [`evidence/baseline-attempts.jsonl`](evidence/baseline-attempts.jsonl), [`evidence/traffic-baseline.txt`](evidence/traffic-baseline.txt) |

## 2. Timeline (written as it happened, never rewritten)

| UTC | Who | What was observed or done | Evidence |
| --- | --- | --- | --- |
| 19:01 | Talia | incident branch `lab08/incident` opened (commit `c820fcd`) | this file |
| 19:03:45 | Leila | baseline started (traffic recorded first) | `evidence/traffic-baseline.txt` |
| 19:04:52 | Leila | baseline probe done: 200/200, 20/20, MAE 95.519, model deeper-trees-e024f62d651a | `evidence/baseline-summary.json` |
| 19:08 | Andrea | watch loop started (one probe every 2 min, alert vs baseline) | `evidence/watch-*-summary.json` |

## 3. First signal

Signal `<alert line>` at `<UTC>`, scope `<all valid requests / one model_version>`,
revision observed `<...>`, model_version observed `<...>`. Raw:
[`evidence/watch-<n>-summary.json`](evidence/), first affected request id `<...>`.

## 4. Hypotheses (written BEFORE the fault was revealed)

| | Hypothesis A: a release changed the model or its configuration | Hypothesis B: inputs or demand changed, the service is the same |
| --- | --- | --- |
| Predicted observation | identity differs from `releases.md`; a new revision has the traffic; same inputs give different outputs (or 503) | identity unchanged, same revisions; same inputs give the same outputs |
| Discriminating check | `<...>` | `<...>` |
| Actual result | `<...>` | `<...>` |
| Conclusion | `<supported / rejected>` | `<supported / rejected>` |
| Still uncertain | `<...>` | `<...>` |

Boundaries checked: service revision and image `<...>`, model version and bytes
`<...>`, configuration `<...>`, inputs `<...>`. Not checked: `<...>`.

## 5. Response

Why rollback fits: `<...>`. Target: revision `<...>`, model `<...>`, sha256
`<...>`, image `<digest>`, decision `<record>`. Compatibility checked: `<...>`.
Command and output: [`evidence/update-traffic.txt`](evidence/update-traffic.txt).

## 6. Fault revealed by the injector (after section 4)

`<what Julia changed, exact command, UTC time, how it was reversible>`.
Did the diagnosis match? `<yes / partly / no, and why>`.

## 7. Three periods (same definitions)

| | Baseline | Incident | After rollback |
| --- | --- | --- | --- |
| Window (UTC) | 19:04:15 -> 19:04:38 | | |
| Revision / model_version | `bike-demand-v2-deeper` / `deeper-trees-e024f62d651a` | | |
| Valid success | 200/200 | | |
| Invalid 4xx | 20/20 | | |
| p50 / p95 ms (n) | 91.76 / 203.73 (200) | | |
| MAE bikes/h (coverage) | 95.519 (200/200) | | |
| Evidence | `baseline-summary.json` | | |

What improved: `<...>`. What remains unknown: `<...>`. What would falsify the
recovery claim: `<...>`.

## 8. Follow-up

| Action | Owner | Verified by |
| --- | --- | --- |
| `<e.g. alert also on /version vs releases.md>` | `<name>` | `<how>` |