# Incident record: rejected model served on Cloud Run (Lab 8 drill)

Status: **resolved**. Traffic back on the accepted revision `bike-demand-v2-deeper`,
verified from three sources at 19:36:42 UTC. Service `bike-demand` on Cloud Run,
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
| 19:28:17 | Andrea | rollback attempt 1 **refused**: `PERMISSION_DENIED`, permission `artifactregistry.repositories.downloadArtifacts` missing on Artifact Registry repository `bike-demand` for the operator account; traffic stayed 100% on `bike-demand-drill-1` (recorded after the fact from Andrea's report) | `evidence/update-traffic.txt` |
| ~19:29 | Leila | granted `roles/artifactregistry.reader` on project `bike-demand-ai` to Andrea's account; Andrea waited about 1 min | Andrea's report |
| 19:30 | Talia | precision after reading the raw files: the watch-4 window (19:15:53 -> 19:16:22) straddled the switch; 170 answers came from `deeper-trees-e024f62d651a`, 30 from `shallow-trees-77df9d597f48`. The 30 different outputs are exactly the 30 answered by the rejected model; the incident MAE 102.236 mixes both models | `evidence/watch-4-summary.json` (`predict_model_versions`), `evidence/compare-incident.txt` |
| 19:30:57 | Andrea | rollback retry: `Routing traffic... done`, 100% `bike-demand-v2-deeper` | `evidence/update-traffic-retry.txt`, `evidence/traffic-after.txt` |
| 19:32:47 | Andrea | identity check 1 **failed** for the script (`read operation timed out`, 7/8 FAIL): Cloud Run received request `check-ec5e5760` and answered 200, but too late (cold start of `bike-demand-v2-deeper`) | `evidence/check-after.txt`, `evidence/cloud-run-logs-checks.json` |
| 19:32:47 -> 19:33:11 | Andrea | after probe: no ALERT, 200/200, 20/20, MAE 95.519, p95 135.59 ms; 200/200 predictions identical to baseline | `evidence/after-summary.json`, `evidence/compare-after.txt` |
| 19:34:46 | Andrea | identity check 2: 8/8 ok, exit 0 (request `check-6a55c62a`; deeper-trees-e024f62d651a, sha 94f4f4b8f348, commit a9eda78) | `evidence/check-after-2.txt`, `evidence/cloud-run-logs-checks.json` |
| 19:36:42 | Andrea | verification done: Cloud Run logs show the `probe-after` requests with the expected model; observation window 19:32:47 -> 19:36:42 | `evidence/cloud-run-logs-after.json` |

## 3. First signal

Signal `ALERT MAE 102.236 > baseline 95.519 + 5` and `ALERT model_version not seen
in baseline (shallow-trees-77df9d597f48)` at `19:16:22` UTC (watch-4, window
19:15:53 -> 19:16:22). Scope: all 200 valid requests got HTTP 200, but the last
30 of the window (after the switch at 19:16:19) were answered by the unknown
model `shallow-trees-77df9d597f48`; the first 170 still came from
`deeper-trees-e024f62d651a`. Revision observed `bike-demand-drill-1` (100% of
traffic, created 19:15:38); `/version` after the window reported
`shallow-trees-77df9d597f48`, sha256 `1227415f1aee…`. Health stayed green: only
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

Why rollback fits: hypothesis A was supported (a release changed the model) and
the accepted revision is still listed and retained; a traffic switch restores the
accepted model in one controlled change, with no retraining and no registry change.
A rollback could not fix hypothesis B, which was rejected.

Target (from the `serving 100%` line of [`reports/releases.md`](../../releases.md)):
revision `bike-demand-v2-deeper`, model `deeper-trees-e024f62d651a`, sha256
`94f4f4b8f3482d034c10cec68cd65e66fdb91b0aac4119c61979f8bd2de9f857`, image
`sha256:0f643f971c168b85b1007789b598dffe721ab00122dfcaabef44c25b980fc59b`,
decision `decisions/20261108T215758Z-deeper-trees-eligible.json`.
Compatibility: same code commit (`a9eda78`) and same API contract as the drill
revision and the last verified release.

Command: `gcloud run services update-traffic bike-demand --region europe-west1 --to-revisions bike-demand-v2-deeper=100`.

- Attempt 1 (19:28:17): **refused**, `PERMISSION_DENIED` on
  `artifactregistry.repositories.downloadArtifacts` (repository `bike-demand`)
  for the operator account; nothing changed (traffic still 100% on `drill-1`):
  [`evidence/update-traffic.txt`](evidence/update-traffic.txt).
- Unblocked by Leila (project owner): `roles/artifactregistry.reader` on project
  `bike-demand-ai` granted to Andrea's account; about 1 minute wait.
- Attempt 2 (19:30:57): done, 100% on `bike-demand-v2-deeper`:
  [`evidence/update-traffic-retry.txt`](evidence/update-traffic-retry.txt),
  [`evidence/traffic-after.txt`](evidence/traffic-after.txt).
- Time from first signal (19:16:22) to traffic restored (19:30:57): about 15 minutes,
  of which about 3 minutes lost on the missing permission.

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
`bike-demand-drill-1` is kept as evidence and recorded as `rehearsal only` in
`reports/releases.md`.

Did the diagnosis match? **Yes.** Hypothesis A (a new model was deployed) was
supported and B rejected before the reveal; the operator identified the exact
model (the Lab 7 rejected candidate), the new revision and its creation time
(19:15:38, within Julia's 19:15:29 -> 19:16:19 window). The first signal came at
19:16:22, 3 seconds after the deployment finished, at the end of the watch probe
that was running during the switch.

## 7. Three periods (same definitions)

| | Baseline | Incident | After rollback |
| --- | --- | --- | --- |
| Window (UTC) | 19:04:15 -> 19:04:38 | 19:15:53 -> 19:16:22 (watch-4, straddles the switch at 19:16:19) | 19:32:47 -> 19:33:11 |
| Revision / model_version | `bike-demand-v2-deeper` / `deeper-trees-e024f62d651a` (200) | `bike-demand-drill-1` / `shallow-trees-77df9d597f48` (30) + `deeper-trees-e024f62d651a` (170) | `bike-demand-v2-deeper` / `deeper-trees-e024f62d651a` (200) |
| Valid success | 200/200 | 200/200 | 200/200 |
| Invalid 4xx | 20/20 | 20/20 | 20/20 |
| p50 / p95 ms (n) | 91.76 / 203.73 (200) | 110.84 / 255.40 (200) | 105.51 / 135.59 (200) |
| MAE bikes/h (coverage) | 95.519 (200/200) | 102.236 (200/200), mixed: 30 answers from the rejected model | 95.519 (200/200) |
| Same inputs vs baseline | - | 170 identical, 30 different, max abs diff 217.401 bikes/h | 200 identical, 0 different, max abs diff 0.000 |
| Alerts | - | MAE, unknown model_version | none |
| Evidence | `baseline-summary.json` | `watch-4-summary.json`, `compare-incident.txt` | `after-summary.json`, `compare-after.txt`, `check-after-2.txt`, `cloud-run-logs-after.json` |

What improved: the accepted model answers again (identity 8/8 against the decision
record), the MAE is back to the baseline value exactly (95.519), and all 200
predictions are identical to the baseline key by key. Health was green in all
three periods: the incident was a quality and identity problem, not an
availability problem.

What remains unknown: the MAE of the rejected model on the full 200-row cohort
(the incident window mixes both models; only 30 answers came from it); behaviour
on real user traffic (only the replay cohort is labelled); who authorised the
deployment (no approval is required by Cloud Run itself); long-term reliability
(the after window is a few minutes).

What would falsify the recovery claim: a later probe or `/version` showing a
`model_version` other than `deeper-trees-e024f62d651a`; any key with a different
output than the baseline for the same input; traffic not at 100% on
`bike-demand-v2-deeper`.

## 8. Follow-up

| Action | Owner | Verified by |
| --- | --- | --- |
| Keep `roles/artifactregistry.reader` for the operator (needed by `update-traffic`), and write it in the runbook prerequisites | Leila (project owner) | Andrea reruns a traffic change in the next drill without `PERMISSION_DENIED` |
| Runbook: after a traffic change, expect a cold start; wait and retry `check_deployment.py` before concluding (first check at 19:32:47 timed out although Cloud Run answered 200) | Andrea (`RUNBOOK.md`) | Julia's peer attempt on the runbook |
| Alert also when `/version` differs from the `serving 100%` line of `releases.md`, not only on MAE | Leila (`scripts/probe.py`) | a probe against the retained drill revision raises the identity alert |
| Restrict who can deploy to `bike-demand` (any deploy goes live at 100% immediately) | Leila | IAM policy reviewed in a PR |