# Incident record: rejected model served on Cloud Run (Lab 8 drill)

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
| 19:16:22 | Andrea | **first signal** (watch-4): `ALERT MAE 102.236 > baseline 95.519 + 5` and `ALERT model_version not seen in baseline: shallow-trees-77df9d597f48`; valid statuses 200/200 (service answers, model changed) | `evidence/watch-4-summary.json` |
| by 19:23 | Andrea | checks: `/version` = `shallow-trees-77df9d597f48` (not in `releases.md`, the Lab 7 rejected candidate); 100% traffic on `bike-demand-drill-1`, created 19:15:38; same code `a9eda78`; 30/200 different outputs for identical inputs; `fc`: image and expected hash differ | `evidence/version-incident.json`, `evidence/traffic-incident.txt`, `evidence/revisions-incident.txt`, `evidence/compare-incident.txt`, `evidence/revision-old.txt`, `evidence/revision-new.txt` |
| 19:23 | Andrea | diagnosis written (section 4): A supported, B rejected, before any reveal (pushed in commit `8acbc3e`) | this file |
| 19:27 | Julia | fault revealed (section 6): rejected model deployed at 19:15:29 -> 19:16:19 | section 6 |

## 3. First signal

Signal `ALERT MAE 102.236 > baseline 95.519 + 5` and `ALERT model_version not seen
in baseline (shallow-trees-77df9d597f48)` at `19:16:22` UTC (watch-4), scope:
valid requests answered with HTTP 200 (200/200) but by an unknown model_version,
revision observed `bike-demand-drill-1` (100% of traffic, created 19:15:38),
model_version observed `shallow-trees-77df9d597f48`. Health stayed green: only
quality and identity changed. Raw: [`evidence/watch-4-summary.json`](evidence/watch-4-summary.json),
[`evidence/watch-4-attempts.jsonl`](evidence/watch-4-attempts.jsonl).

## 4. Hypotheses (written BEFORE the fault was revealed)

| | Hypothesis A: a new version (model) was deployed | Hypothesis B: inputs or demand changed, the service is the same |
| --- | --- | --- |
| Predicted observation | identity differs from `releases.md`; a new revision has the traffic; same inputs give different outputs | identity unchanged, same revisions; same inputs give the same outputs |
| Discriminating check | `/version` vs `releases.md`; traffic and revisions list; `fc` of the two revision specs; same-input comparison key by key (`compare_attempts.py` baseline vs watch-4) | same checks: the replay cohort is fixed, so if the service is unchanged the outputs must be identical key by key |
| Actual result | `/version` = `shallow-trees-77df9d597f48` (not in `releases.md`, the candidate rejected in Lab 7); 100% traffic on `bike-demand-drill-1` (created 19:15:38); same code `a9eda78`; 30/200 different outputs for identical inputs; `fc`: image and expected model hash differ | the cohort is fixed and identical, yet outputs changed for 30/200 keys and the identity changed |
| Conclusion | **supported** | **rejected** |
| Still uncertain | who authorised this deployment; whether other configuration changed (memory, max instances) | - |

Boundaries checked: service revision and image (new revision `bike-demand-drill-1`,
different image), model version and bytes (`shallow-trees-77df9d597f48`, different
expected hash), configuration (expected-hash variable differs), inputs (fixed
replay cohort, identical). Not checked: who authorised the deployment, other
settings (memory, max instances), real user traffic (only the replay cohort is
labelled).

## 5. Response

Why rollback fits: `<...>`. Target: revision `<...>`, model `<...>`, sha256
`<...>`, image `<digest>`, decision `<record>`. Compatibility checked: `<...>`.
Command and output: [`evidence/update-traffic.txt`](evidence/update-traffic.txt).

## 6. Fault revealed by the injector (after section 4)

Julia used option 1, "the wrong model is online". She deployed on our Cloud Run
service a rehearsal image (tag `drill-rejected`, digest
`sha256:b169f7ed7f4c5f2b74d48fb4467282c5de36938a436d9cc52a930b4cac6c053c`)
containing the candidate **rejected** in Lab 7, `shallow-trees-77df9d597f48`
(gain_vs_accepted -11.232 bikes/h), with the same code (commit `a9eda78`). The
image was built before the session from a temporary clone: the real registry,
the decisions, `releases.md` and the data were not touched.

Exact command (19:15:29 -> 19:16:19 UTC, then `bike-demand-drill-1` at 100% of traffic):

    gcloud run deploy bike-demand --image "europe-west1-docker.pkg.dev/bike-demand-ai/bike-demand/api:drill-rejected" --region europe-west1 --port 8000 --memory 1Gi --max-instances 2 --update-env-vars "BIKE_DEMAND_EXPECTED_MODEL_SHA256=1227415f1aee86e71b8f15fc3d624a22cc4dd79135ada959fe82851bfcfc72a3" --revision-suffix drill-1

Only the image and `BIKE_DEMAND_EXPECTED_MODEL_SHA256` changed; memory (1Gi),
max instances (2), port and code are identical to v2. This answers the open point
of hypothesis A ("other configuration changed?"): no.

Why it was reversible: the accepted revision `bike-demand-v2-deeper` stayed
available (as did `bike-demand-v1-baseline`). One traffic rollback
(`gcloud run services update-traffic --to-revisions bike-demand-v2-deeper=100`)
is enough, with no retraining and no registry change. Revision
`bike-demand-drill-1` is kept as evidence.

Did the diagnosis match? **Yes.** Hypothesis A (a new model was deployed) was
supported and B rejected before the reveal; the operator identified the exact
model (the Lab 7 rejected candidate), the new revision and its creation time
(19:15:38, within Julia's 19:15:29 -> 19:16:19 window). The first signal came at
19:16:22, 3 seconds after the deployment finished, on the next watch probe.

## 7. Three periods (same definitions)

| | Baseline | Incident | After rollback |
| --- | --- | --- | --- |
| Window (UTC) | 19:04:15 -> 19:04:38 | `<watch-4 window>` | |
| Revision / model_version | `bike-demand-v2-deeper` / `deeper-trees-e024f62d651a` | `bike-demand-drill-1` / `shallow-trees-77df9d597f48` | |
| Valid success | 200/200 | 200/200 | |
| Invalid 4xx | 20/20 | `<..>` | |
| p50 / p95 ms (n) | 91.76 / 203.73 (200) | `<..>` | |
| MAE bikes/h (coverage) | 95.519 (200/200) | 102.236 (`<..>`) | |
| Evidence | `baseline-summary.json` | `watch-4-summary.json` | |

What improved: `<...>`. What remains unknown: `<...>`. What would falsify the
recovery claim: `<...>`.

## 8. Follow-up

| Action | Owner | Verified by |
| --- | --- | --- |
| `<e.g. alert also on /version vs releases.md>` | `<name>` | `<how>` |