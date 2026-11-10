# Runbook: bike-demand on Cloud Run

Last verified: 2026-11-10 19:32-19:36 UTC by Andrea, after the Lab 8 drill
rollback, on revision `bike-demand-v2-deeper` (model `deeper-trees-e024f62d651a`,
sha256 `94f4f4b8f3482d034c10cec68cd65e66fdb91b0aac4119c61979f8bd2de9f857`,
code `a9eda78d66c42d08b84a325cfcf5eac86bda4ebc`). Revise after every drill or
incident; a step nobody has verified is marked UNVERIFIED.

Service `bike-demand`, project `bike-demand-ai`, region `europe-west1`,
URL `https://bike-demand-6zxggmsv2a-ew.a.run.app`. Owners: Leila, Julia, Talia,
Andrea. Escalate to: Leila (project owner: IAM, billing, quotas).

```powershell
$URL = "https://bike-demand-6zxggmsv2a-ew.a.run.app"; $REGION = "europe-west1"; $SVC = "bike-demand"
$E = "reports\incidents\<new-record>\evidence"   # one folder per incident
New-Item -ItemType Directory -Force $E
gcloud config set project bike-demand-ai
```

## 0. Access you need before an incident (checked in the Lab 8 drill)

| Role | Why |
| --- | --- |
| `roles/run.developer` | list and describe revisions, move traffic |
| `roles/iam.serviceAccountUser` | act as the service's runtime account when traffic changes |
| `roles/artifactregistry.reader` | **moving traffic also checks that you can read the image**: without it `update-traffic` fails with `PERMISSION_DENIED ... artifactregistry.repositories.downloadArtifacts` (happened in the drill, 19:28 UTC) |
| `roles/logging.viewer` | read the Cloud Run logs |

Check it calmly, not during an incident: `gcloud run revisions list --service $SVC --region $REGION`.

## 1. Symptom and scope

| You see | It can mean |
| --- | --- |
| Probe ALERT `valid_success < 0.99`, `/health` 503 | no usable model: missing bundle, checksum or expected-sha mismatch |
| Probe ALERT `MAE above baseline` with valid success 1.0 | a different model is answering: HTTP 200 does not mean the right model (the Lab 8 drill: 200/200 but MAE 102.2 instead of 95.5) |
| Probe ALERT `model_version not seen in baseline` | the serving identity changed |
| Probe ALERT `p95` | slower revision, cold starts, or more demand |

Write the first signal down before acting: UTC time, alert line, revision
observed, path to the `-summary.json` file.

## 2. First checks (cheapest first, do not change anything yet)

1. Identity vs the retained record:
   `curl.exe -s "$URL/version"` and compare with the `serving 100%` line of
   [`reports/releases.md`](reports/releases.md).
2. Which revision receives traffic, and since when:
   `gcloud run services describe $SVC --region $REGION --format="yaml(status.traffic)"`
   `gcloud run revisions list --service $SVC --region $REGION` (DEPLOYED and DEPLOYED BY columns)
3. What differs between the serving revision and the expected one (save both,
   then compare; in the drill only the image digest and
   `BIKE_DEMAND_EXPECTED_MODEL_SHA256` differed):
   `cmd /c "gcloud run revisions describe <serving revision> --region $REGION --format=yaml(spec) > $E\revision-new.txt 2>&1"`
   `cmd /c "gcloud run revisions describe bike-demand-v2-deeper --region $REGION --format=yaml(spec) > $E\revision-old.txt 2>&1"`
   `fc.exe $E\revision-old.txt $E\revision-new.txt`
4. Is the served model a known one? Search `decisions/` for the
   `model_version` shown by `/version` (in the drill it was the rejected
   candidate `shallow-trees-77df9d597f48`).
5. Same inputs, different outputs? Replay the fixed cohort and compare with
   the baseline attempts key by key:
   `uv run --locked python scripts/probe.py --url $URL --period check --baseline <baseline-summary.json> --out $E\check`
   `uv run --locked python scripts/compare_attempts.py <baseline-attempts.jsonl> $E\check-attempts.jsonl`
   Same key, different prediction = the model changed, not the inputs.
6. What the service logged (save the raw output):
   `gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=bike-demand' --freshness=2h --limit 300 --format=json | Out-File -Encoding utf8 $E\cloud-run-logs.json`
   then `Select-String -Path $E\cloud-run-logs.json -Pattern "model_loaded|model_unavailable" | Select-Object -First 10`

## 3. Decide

| Evidence | Action |
| --- | --- |
| The serving revision is not the `serving 100%` line of `releases.md` (model or env differs), and the expected revision is still listed | **rollback** (section 4) |
| Serving identity = expected, but inputs or demand changed | no rollback: contain, open an issue, investigate (rollback cannot fix the world) |
| Expected revision missing, or its image digest differs from `releases.md` | do not route traffic to it; escalate |

## 4. Safe action: route traffic back to the retained accepted revision

1. Name the target from `releases.md` before acting. Today:
   `bike-demand-v2-deeper`, model `deeper-trees-e024f62d651a`, sha256
   `94f4f4b8f348...`, image `sha256:59c317ef019e3fee5b6354890c2671ed73e087f163c4bf4d7da28018c6689b59`,
   decision `decisions/20261108T215758Z-deeper-trees-eligible.json`.
2. Compatibility: the target's image digest must equal `releases.md`:
   `gcloud run revisions describe bike-demand-v2-deeper --region $REGION --format="value(spec.containers[0].image)"`
3. One controlled change (keep the output):
   `cmd /c "gcloud run services update-traffic $SVC --region $REGION --to-revisions bike-demand-v2-deeper=100 > $E\update-traffic.txt 2>&1"`
4. Check that the routing changed:
   `gcloud run services describe $SVC --region $REGION --format="yaml(status.traffic)"`
   Traffic is now pinned to that revision (no `latestRevision: true`): a later
   deploy does not take traffic until someone routes it.

If step 3 fails with `PERMISSION_DENIED`, nothing changed: read the missing
permission in the message, ask Leila for that role (section 0), wait one
minute, retry into a new output file. Never retrain as a recovery action.
Never load or relabel a bundle whose checksum does not match its decision record.

## 5. Verify with fresh evidence (all three must agree)

The retained revision had no traffic, so Cloud Run has to start it again
(cold start, model of 37 MB): **the first call after a rollback can time out**
(drill: `check_deployment.py` -> `The read operation timed out` at 19:32 UTC).
Wait 30 seconds and run the check again into a new file before concluding.

1. Identity (expectation from the committed decision, not from the service):
   ```powershell
   $D = Get-Content (Get-ChildItem decisions\*-deeper-trees-eligible.json)[0].FullName -Raw | ConvertFrom-Json
   @{ model_version = $D.candidate.model_version; model_sha256 = $D.candidate.model_sha256 } | ConvertTo-Json | Set-Content -Encoding ascii $E\expected-accepted.json
   uv run --locked python scripts/check_deployment.py --url $URL --expected-metadata $E\expected-accepted.json --expected-revision a9eda78d66c42d08b84a325cfcf5eac86bda4ebc
   ```
   Expected: 8/8 ok, exit 0.
2. Behaviour: `uv run --locked python scripts/probe.py --url $URL --period after --baseline <baseline-summary.json> --out $E\after`
   (no ALERT, same MAE as baseline) and `compare_attempts.py` -> 200 identical.
3. Signals: Cloud Run logs after the change (step 2.6 query, new file) show
   request lines `probe-after-...` with the expected `model_version`.

Keep observing for 10 minutes before closing.

## 6. Escalate when

- the retained target is missing, its digest differs, or it fails step 5;
- `gcloud` reports a permission or quota error you cannot fix with section 0 (owner: Leila);
- the symptom continues after rollback (the cause is not the release).

## Known limits

The probe measures from one laptop (network latency included). Labels exist
only for the validation replay cohort, not for real traffic. A drill of a few
minutes says nothing about long-term reliability. The drill revision
`bike-demand-drill-1` is kept as evidence (`rehearsal only` in `releases.md`);
it must never receive traffic again.
