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
| Workload | `scripts/probe.py`, cohort `examples/replay-validation.jsonl` (200 valid validation-period hours) + 20 invalid requests, from `<who>`'s laptop |
| Environment | Cloud Run `bike-demand`, `europe-west1`, 1 GiB, max 2 instances |
| Identity | revision `<...>`, model `<...>`, sha256 `<...>`, code `<...>` (= `reports/releases.md`) |
| Window, n | `<start>` -> `<end>`, 200 valid + 20 invalid |
| Signals | valid success `<g>/<n>`, invalid 4xx `<r>/20`, p50/p95 `<..>/<..>` ms, MAE `<..>` bikes/h (coverage 200/200) |
| Evidence | [`evidence/baseline-summary.json`](evidence/baseline-summary.json), [`evidence/baseline-attempts.jsonl`](evidence/baseline-attempts.jsonl) |

## 2. Timeline (written as it happened, never rewritten)

| UTC | Who | What was observed or done | Evidence |
| --- | --- | --- | --- |
| `<...>` | Leila | baseline probe done | `evidence/baseline-summary.json` |
| `<...>` | Andrea | watch loop started (one probe every 2 min) | `evidence/watch-*-summary.json` |
| `<...>` | Andrea | **first signal**: `<ALERT line>` | `evidence/watch-<n>-summary.json` |
| `<...>` | Andrea | `<check>` -> `<result>` | `<file>` |
| `<...>` | Andrea | diagnosis written (section 4) | this file |
| `<...>` | Andrea | traffic -> `<revision>`=100 | `evidence/update-traffic.txt` |
| `<...>` | Andrea | verification done | `evidence/after-summary.json`, `evidence/check-after.txt` |
| `<...>` | Julia | fault revealed | section 6 |

## 3. First signal

Signal `<alert line>` at `<UTC>`, scope `<all valid requests / one model_version>`,
revision observed `<...>`, model_version observed `<...>`. Raw:
[`evidence/watch-<n>-summary.json`](evidence/), first affected request id `<...>`.

## 4. Hypotheses (written BEFORE the fault was revealed)

| | Hypothesis A: <a release changed the model or its configuration> | Hypothesis B: <inputs or demand changed, the service is the same> |
| --- | --- | --- |
| Predicted observation | `<identity differs from releases.md; same inputs give different outputs>` | `<identity unchanged; same inputs give the same outputs>` |
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
| Window (UTC) | | | |
| Revision / model_version | | | |
| Valid success | | | |
| Invalid 4xx | | | |
| p50 / p95 ms (n) | | | |
| MAE bikes/h (coverage) | | | |
| Evidence | | | |

What improved: `<...>`. What remains unknown: `<...>`. What would falsify the
recovery claim: `<...>`.

## 8. Follow-up

| Action | Owner | Verified by |
| --- | --- | --- |
| `<e.g. alert also on /version vs releases.md>` | `<name>` | `<how>` |
