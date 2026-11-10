# Bike Demand: Week 1 starter

Teams of 3–4 use one private GitHub repository throughout the course. Lab 1 is
repository setup, Git workflow and quality checks. Lab 2 adds validated data,
chronological splitting, a baseline comparison and local MLflow tracking.
Week 2 (Lab 3) adds a Docker image: see "Lab 3: build and rerun
in a container" below.

## Setup: Lab 1

Install Git and [uv](https://docs.astral.sh/uv/getting-started/installation/)
(`>=0.12.19,<0.13`). Python **3.12** is required; uv can download it. From the
`bike-demand/` root:

```bash
uv python install 3.12
uv sync --locked
uv run --locked python -m bike_demand.preflight
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest -q -m infra
uv run --locked pytest -q -m lab1
```

First setup requires internet for Python and the locked dependencies, unless
these exact distributions are already cached. The frozen UCI CSV ships here;
preflight does not download/repair it. `uv.lock` is shared across platforms;
that is not evidence that every OS has been tested. macOS setup has been checked;
Windows and Linux remain unverified. Remote CI is unavailable until a permitted
repository is configured and a workflow actually runs on the checked revision.
Do not regenerate the lock just to bypass an installation failure.

## Expected failure and exercise: Lab 1

`pytest -m infra` must pass immediately. `pytest -m lab1` has **one intentional
behavior failure** in `src/bike_demand/team.py`: the helper
`normalize_team_slug` does not yet meet the contract in `tests/lab1/test_team.py`
(trim, lowercase, join whitespace with hyphens, reject blank names with
`ValueError`). Read the assertion, diagnose the cause, make a small repair and add
one useful test of your own. Do not weaken assertions, skip tests or disable
checks. Sync or import errors, or failures outside `lab1`, are setup problems:
diagnose them separately.

Fill in `WORKING-AGREEMENT.md`. Use a task branch, open a pull request, and get a
review from another member before merging. Rotate driver/reviewer roles and the
main PR author between labs. Keep actual evidence in `reports/lab-01.md` and
`reports/week-01-team.md`; templates contain no pre-filled results.

## Expected failures: Lab 2

The student export has bounded TODOs in `src/bike_demand/`:

| File | Your task |
| --- | --- |
| `validate.py` | Categorical domains, finite normalised ranges, nonnegative counts, date windows |
| `split.py` | Chronological nonempty/disjoint/complete partitions; sort `(dteday, hr, instant)` |
| `train.py` | Ordered predictors, train-mean comparator, RF fit and validation MAE |

`NotImplementedError("TODO(Week 1, Lab 2): ...")` and failing exercise tests are
**expected before implementation**, not environment failures. Infra must pass
immediately. Do not skip/mute exercise tests or fabricate metrics to get green.
Tracking, metadata/history, configuration and input parsing are already supplied.
Read the failing test, inspect the contract, implement one TODO, and rerun:

```bash
uv run --locked pytest -q -m exercise
uv run --locked python -m bike_demand.validate --data data/raw/hour.csv
uv run --locked python -m bike_demand.train --config configs/baseline.yaml
uv run --locked pytest -q
```

Keep `data/raw/hour.csv` unchanged; use copies and `tests/fixtures/` for deliberate
faults. `missing-temp.csv` is the worked Fault A; design your own Fault B by
breaking exactly one contract rule or split boundary on a tiny copy, with a valid
control and a test of your own. The supplied `hum-out-of-range.csv` is another
worked example, not your Fault B. Missing hours are valid. Features and splits are fixed in the config and
code. Fit only on 2011 training rows; compare both predictors on the same
2012 January–June validation rows. Hold July–December 2012 test rows throughout
Weeks 1–4; do not compute test metrics. MAE is rentals/hour, not accuracy, and
RF is not required to beat the comparator. The task uses supplied weather;
it does not forecast future weather or station-level demand.

## Outputs and readback

Each successful train execution creates two separate MLflow runs, a saved
`artifacts/model.joblib` and `model-metadata.json`, latest `reports/metrics.json`,
and one appended `reports/metrics-history.jsonl` line. Metadata records feature
order, data identity, model version and run ID. A commit is recorded when Git is
available; `working_tree_dirty` prevents uncommitted code being mistaken for a
committed revision. Train reloads the trusted local model and verifies validation
MAE/metadata and logged artifact bytes. Never load untrusted joblib files.
Optional stretch, only after the core is complete and reviewed: run train again
unchanged and compare both run IDs and observed MAEs/history. Do not promise
byte-identical models across systems/library versions.

Viewer is optional; training does not depend on it:

```bash
uv run --locked mlflow server --backend-store-uri sqlite:///tracking/mlflow.db --default-artifact-root tracking/artifacts --no-serve-artifacts --host 127.0.0.1 --port 5000 --workers 1
```

`artifacts/`, `tracking/` and `.venv/` are ignored by Git. Team metrics may be
committed as evidence; never commit credentials or individual private reports.
CI currently checks only infrastructure/quality; expand it in Week 3.

## Lab 3: build and rerun in a container
The image installs exactly `uv.lock` and reruns the Lab 2 baseline away from
your laptop.
**Prerequisites:** Docker Desktop running (`docker run --rm hello-world`
works) and a clean checkout of `main`.
**What goes into the image** (allowlist in `.dockerignore`):
`pyproject.toml`, `uv.lock`, `.python-version`, `src/`, `configs/`, `data/`,
`tests/`, plus `README.md`, `reports/week-01-team.md` and
`.github/workflows/ci.yml`, which preflight requires. Everything else stays
out: `.git`, `.venv`, `.env`, `artifacts/`, `tracking/`, caches and
screenshots.
**Build, run and test** (from the repository root, bash or PowerShell):
docker build --build-arg GIT_COMMIT=$(git rev-parse HEAD) -t bike-demand:lab3 .
docker image inspect bike-demand:lab3 --format '{{.Id}} {{json
.Config.Labels}}'
docker run --name lab3-run --network none bike-demand:lab3
docker cp lab3-run:/app/reports/metrics.json ./container-metrics.json
docker rm lab3-run
docker run --rm --network none bike-demand:lab3 uv run --locked pytest -q
**Expected:** validation MAE 154.23 (train mean) and 86.85 (random forest),
the same as Lab 2; tests `51 passed`.
**Normal differences:** inside the container `training_commit` is
`unavailable` and `working_tree_dirty` is `null`, because `.git` is not
copied; the commit is recorded in the image label
`org.opencontainers.image.revision`. Run IDs, `timestamp`, `model_version`
and possibly `model_sha256` change on every run.
**Lock:** both `uv sync` steps use `--locked`. A missing or stale `uv.lock`
stops the build; never run `uv lock` just to make it pass.
**CI:** GitHub Actions checks the lock and the tests but does not build the
image; container runs are local evidence.

## Lab 4: request validation

The `/predict` request is one flat JSON object with exactly the twelve training
features. Unknown fields are rejected (`extra="forbid"` in
`src/bike_demand/schemas.py`), including the targets `cnt`, `casual` and
`registered`, so the target can never be sent to the API. A request with a
missing, extra or out-of-range field returns HTTP 422 before any prediction is
made.


## Lab 4: prediction API

The image ships the saved, evaluated baseline model and serves it with FastAPI.
The model is trained once **at image build time** (`docker build`), then the
service only loads `artifacts/model.joblib` and `artifacts/model-metadata.json`
at startup. It never trains at startup or per request.

**Endpoints** (both read the same model-availability state):

| Request | Model loaded | Answer |
| --- | --- | --- |
| `GET /health` | yes | `200 {"status": "ok", "model_version": "..."}` |
| `GET /health` | no | `503 {"detail": "model unavailable: ..."}` |
| `POST /predict`, valid body | yes | `200 {"prediction": <finite, >= 0>, "model_version": "..."}` |
| `POST /predict`, invalid body | yes or no | `422` (FastAPI validation), before any inference |
| `POST /predict`, valid body | no | `503`, never a guessed number |

`model_version` is read from the artifact's own `model-metadata.json`, not hard-coded.
At startup the service also checks that `model.joblib` matches the SHA-256 and the
feature order recorded in its metadata; otherwise it reports 503.

**Input contract:** one flat JSON object with exactly the twelve training features.
`season` 1-4, `yr` 0-1, `mnth` 1-12, `hr` 0-23, `holiday` 0-1, `weekday` 0-6,
`workingday` 0-1, `weathersit` 1-4 (integers); `temp`, `atemp`, `hum`, `windspeed`
finite numbers in [0, 1] (normalised, not Celsius or percentages).
**Extra fields are rejected with 422**, including `cnt`, `casual` and `registered`.
Types are strict: `"17"`, `17.5` or `true` are not accepted for an integer field.
Example body: [`examples/predict-request.json`](examples/predict-request.json).

**Build and run** (repository root; in Windows PowerShell use `curl.exe`, not `curl`):

    docker build --build-arg GIT_COMMIT=$(git rev-parse HEAD) -t bike-demand:lab4 .
    docker run -d --name lab4-api -p 127.0.0.1:8000:8000 bike-demand:lab4
    curl.exe -s -i http://127.0.0.1:8000/health
    curl.exe -s -i -X POST http://127.0.0.1:8000/predict -H "Content-Type: application/json" --data "@examples/predict-request.json"
    docker stop lab4-api
    docker rm lab4-api

The OpenAPI page is at http://127.0.0.1:8000/docs while the container runs.
The port is published on `127.0.0.1` only (your own machine).

**Tests inside the image** (normal, invalid and missing-model cases, no server needed):

    docker run --rm --network none bike-demand:lab4 uv run --locked pytest -q

**Missing model on purpose** (the service starts but answers 503):

    docker run -d --name lab4-nomodel -p 127.0.0.1:8001:8000 -e BIKE_DEMAND_MODEL_DIR=/app/no-model bike-demand:lab4
    curl.exe -s -i http://127.0.0.1:8001/health
    docker rm -f lab4-nomodel

**Lab 3 rerun with this image:** the default command is now the API, so run the
baseline explicitly:

    docker run --rm --network none bike-demand:lab4 uv run --locked python -m bike_demand.train --config configs/baseline.yaml

**Local run without Docker** (needs `artifacts/` from a local `train` run):

    uv run --locked uvicorn bike_demand.api:app --host 127.0.0.1 --port 8000

## Lab 5: deploy and check the service

**What "deployed" means for this team:** the image built from a known commit is
started with the command below, `scripts/check_deployment.py` passes against the
running container (exit status 0), and the request log lines show which model
and code answered. A running container alone is not a verified deployment. The
final check is run by someone who did not write the start-up code, from a fresh
clone, following only this section.

### Start it

From the repository root (Windows PowerShell; on macOS/Linux replace `curl.exe`
by `curl` and the `$VAR =` lines by `VAR=`):

    $SHA = git rev-parse HEAD
    docker build --build-arg GIT_COMMIT=$SHA -t bike-demand:lab5 .
    docker create --name lab5-expect bike-demand:lab5
    docker cp lab5-expect:/app/artifacts/model-metadata.json expected-model.json
    docker rm lab5-expect
    docker run -d --name lab5-api -p 127.0.0.1:8000:8000 bike-demand:lab5
    docker logs lab5-api

Settings are passed with `-e NAME=value` at `docker run` time; nothing secret is
baked into the image:

| Setting | Default | Effect |
| --- | --- | --- |
| `BIKE_DEMAND_MODEL_DIR` | `artifacts` | Folder with `model.joblib` + `model-metadata.json` |
| `BIKE_DEMAND_EXPECTED_MODEL_SHA256` | unset | If set and different from the loaded model, the service stays not ready (503) |
| `BIKE_DEMAND_LOG_LEVEL` | `INFO` | Log level of the JSON service logs. Keep `INFO` for a deployment: at `WARNING` the `model_loaded` line and the request lines disappear, so the logs no longer show which model and code answer (found in the Lab 5 README review) |
| `SERVICE_REVISION` | commit from `--build-arg GIT_COMMIT` | Code identity reported by `/version` and in every log line |

### Check it from outside

    uv run --locked python scripts/check_deployment.py --url http://127.0.0.1:8000 --expected-metadata expected-model.json --expected-revision $SHA

The script only talks HTTP to the container (no project code imported). It checks
eight claims: `/health` is 200; `/version` reports the expected `model_version`,
`model_sha256` and `service_revision`; a valid request returns 200 with a finite
non-negative prediction and the expected `model_version`; the `X-Request-ID`
sent is returned; `hr: 24` returns 422. Any mismatch prints `FAIL` and exits 1.
Add `--report check.json` to keep the results as a file.

    curl.exe -s -i http://127.0.0.1:8000/version
    docker logs lab5-api
    docker rm -f lab5-api

### Endpoints added

`GET /version` (always 200): `{"service_revision": "...", "model_version": "...",
"model_sha256": "...", "ready": true|false}`. Existing `/health` and `/predict`
requests and responses are unchanged; every response now carries an
`X-Request-ID` header (the caller's id if it is short and safe, otherwise a new one).

### Log line

One JSON line per request on stdout (`docker logs`), for example:

    {"ts": "...", "level": "INFO", "event": "request", "request_id": "check-383b9880", "method": "POST", "path": "/predict", "status": 200, "outcome": "predicted", "duration_ms": 16.9, "service_revision": "<commit>", "model_version": "baseline-...", "model_sha256": "d24c050e..."}

plus one start-up line, `model_loaded` or `model_unavailable` with the `reason`.
`outcome` is `predicted`, `rejected` (422), `unavailable` (503), `ok` or `error`.
Uvicorn's plain access log is disabled (`--no-access-log`) so there is exactly
one line per request.

### Decisions (our choice, the option we rejected, and why)

| Question | Our answer | Rejected | Why |
| --- | --- | --- | --- |
| Settings: what changes between laptop and container? | Model folder, expected model hash, log level and code revision, all read from the environment at start-up | Hard-coded paths or a config file baked into the image | The same image must run on a laptop, in CI and on a host; only settings change |
| Model: where does it come from at start-up? | Trained once at `docker build`, shipped in the image (`artifacts/`), only loaded by the service | Mounting a model folder at `docker run` | One image = one code + one model, easy to identify; the cost is a rebuild for a new model. `BIKE_DEMAND_MODEL_DIR` still allows a mount if needed |
| Ready: when is the service ready? | Only after load + checks pass (files present, SHA-256 and feature order match the metadata, optional expected hash); `/health` is 200 only then | "Ready as soon as the process listens" | A listening process can still have no usable model |
| Broken: what does it say if the model is missing? | `/health` and `/predict` answer 503 with the reason; `/version` says `"ready": false`; a `model_unavailable` log line gives the reason | Crash at start-up, or a default prediction | An honest 503 is better than a confident wrong answer, and the container stays inspectable |
| Log line: what must one request tell an operator? | Request id, method, path, status, outcome, duration, code revision, model version and hash | Free-text messages | Searchable fields answer "what happened, how long, which model and code" |
| Secrets: what must never appear in a log? | Request bodies (feature values), headers, tokens, environment values | Logging the full request for debugging | Logs are kept and shared; only metadata with a stated purpose is logged |
| Identity: which id shows which model is running? | `model_sha256` (exact file) with `model_version` (training run); `service_revision` for the code | Image tag such as `lab5` | A tag can be moved; a hash and a commit cannot |
| Expected: who knows the expected model, and when? | Whoever builds: the commit is known before `docker build`, the model record is copied out of the image (`docker cp`) before the service starts | Asking the running service what it expects | The expectation must come from outside the thing being checked |
| Promise: what does "deployed" promise to others? | See the definition at the top of this section | "The container is up" | Running is not verified |
| Failure: break it once, what does it leave behind? | See the team report (Lab 5): starting with a wrong `BIKE_DEMAND_EXPECTED_MODEL_SHA256` gives 503, a `model_unavailable` log line naming both hashes, and a failing check (exit 1) | — | A stranger can find the cause from the logs and the check output |

## Lab 6: continuous integration

Two workflows run on a clean GitHub runner for every pull request into `main` or
`develop`, every push to those branches, and on demand (*Actions* -> *Run workflow*).
Nothing from a laptop is on the runner: no `.venv`, no `artifacts/` or `tracking/`
(ignored by Git), no secrets. Everything is installed from `uv.lock`.

| Workflow / job | Runs | Why | Fails when |
| --- | --- | --- | --- |
| `CI` / `infrastructure` (first, cheapest) | `uv lock --check`, `uv sync --locked`, preflight, `ruff check`, `ruff format --check` | Stop early on a stale lock, a changed data snapshot or a style error | Lock out of date, snapshot checksum differs, lint/format error |
| `CI` / `tests` (needs `infrastructure`) | Guard: every test has a registered marker; then `-m infra`, `-m lab1`, `-m exercise`, `-m api` | Code and contract defects, in groups with readable failures | A test fails, or a new test has no marker and would never run |
| `CI` / `recompute` (needs `infrastructure`) | `-m recompute`: retrains the baseline on the frozen snapshot | Catches silent changes to data, split, features, model settings or libraries | Recomputed validation MAE differs from the recorded one by more than the tolerance |
| `Container` / `container` (last, most expensive) | Build the image from this commit, `pytest` inside it, start it, `scripts/check_deployment.py` from outside | Prove the thing we would ship: identity, prediction, rejection | Build fails, a test fails in the image, or a deployment claim fails |

Each run says what it checked: the job summary prints the commit, the image ID and
the model version; the container job uploads `check.json`, the container logs and
the expected model as an artifact (kept 30 days).

**Required to merge (team agreement):** all four checks green. Branch protection on
`main` requires a review and the `infrastructure` check; the team also waits for
`tests`, `recompute` and `container` before clicking *Merge*.

### Reproduce a failure locally (same locked commands)

    uv sync --locked
    uv run --locked pytest -q -m api          # or infra / lab1 / exercise / recompute
    uv run --locked pytest -q -x --lf         # rerun only what failed last time
    docker build --build-arg GIT_COMMIT=$(git rev-parse HEAD) -t bike-demand:ci .
    docker run --rm --network none bike-demand:ci uv run --locked pytest -q -m "not recompute"

Then follow "Lab 5: deploy and check the service" for the deployment check. Read a
failing run from the first red step upwards, and save the raw log as text in
`reports/logs/lab-06/` (run pages expire after 90 days).

### Which defect each test catches

| Defect (a believable mistake) | Caught by | Shown failing |
| --- | --- | --- |
| Lock not updated after a dependency change | `infrastructure`: `uv lock --check` | Lab 3 (`lock-stale.log`) |
| Raw data snapshot edited | `infrastructure`: preflight; `infra` tests; `recompute::test_same_frozen_data` | `infra` test `test_snapshot_tampering_is_rejected` |
| Split boundary moved (validation leaks into test) | `exercise` split tests; `recompute::test_same_chronological_split` and MAE tests | local mutation, 5 tests red |
| Model trained on the wrong target (`registered` instead of `cnt`) | only `recompute::test_validation_mae_matches_recorded_result[random_forest]` | Lab 6 break-it PR |
| Request contract loosened (extra field, wrong range, wrong type) | `api` tests (`test_api.py`, `test_schemas.py`) | Lab 4 review (`le=23` -> `le=24`, 2 tests red) |
| Wrong or tampered model served | `api` tests (checksum, feature order, expected hash) | Lab 5 review (wrong expected hash -> 503) |
| `/version` field renamed or removed | `api::test_startup.py`; container deployment check | Lab 6 break-it PR |
| Request body leaked into logs | `api::test_logging.py::test_request_body_is_never_logged` | local mutation |
| Image no longer reports its commit (`SERVICE_REVISION` lost) | only `Container` / deployment check (`service_revision`) | Lab 6 break-it PR |
| New test added without a marker (silently never run) | `tests` guard step | Lab 6 break-it PR |

### Decisions (our choice, the option we rejected, and why)

| Question | Our answer | Rejected | Why |
| --- | --- | --- | --- |
| Coverage: what do the checks not cover yet? | Other operating systems (CI is Linux only), load and latency, model quality on the held-out test period, drift on new data, the Cloud Run deployment, pinning `actions/checkout` by commit SHA (it uses the `v6` tag; `setup-uv` is pinned by SHA) | Claiming "all green = correct" | Green means: this commit, this runner, these checks |
| Machine: what does a clean runner not have? | No `.venv`, no `artifacts/` or `tracking/`, no secrets, no laptop files; the model is produced on the runner (recompute job, image build) | Committing a model file to make CI pass | CI evidence must be produced by the runner |
| Trigger: which changes start which checks? | Every PR and push to `main`/`develop` starts both workflows; manual start for reruns | Path filters (docs-only changes skip CI) | Simple and safe; a README change can still break the documented commands |
| Order: which check fails first, and why? | Lock and style first (seconds), then tests and recompute in parallel, container last (minutes) | One big job | A typo should not cost a container build; failures name their group |
| Evidence: what can CI claim about the model? | That this commit, installed from the lock, retrains to the recorded validation MAE within 1e-6, and that the image built from it serves the model whose version and hash it reports | Citing laptop MLflow runs as CI evidence | Local and CI evidence are separate claims |
| Defects: which bug does each test catch? | See the table above | Tests without a named defect | A test is worth what it can catch |
| Failing: can you make each test fail? | Yes: the break-it PRs and local mutations listed above, with red logs saved | Trusting a test that has never failed | A test that cannot fail proves nothing |
| Tolerance: where does the number come from? | `1e-6` rentals/hour: 5 runs on Windows and Linux gave the same MAE to all printed digits (`tests/regression/baseline-expected.json`) | A loose tolerance chosen to turn red green | Changing it is a reviewed change with a reason |
| Repair: did you fix the cause or hide it? | Each red run was repaired by reverting or fixing the defect on the same PR; no `continue-on-error`, `|| true`, skip or loosened assertion | Rerunning until green | A green rerun without a repair is not a repair |
| Records: what is still readable in 3 months? | Failing logs saved as text in `reports/logs/lab-06/`, the team report, the commits and PR conversations | Links to run pages only | Run logs and artifacts expire |

## Lab 7: pipeline and gate

One command turns one declared candidate into a **decided** candidate. A
separate, reviewed command promotes it. Nothing a candidate run writes can be
served until a person promotes it from reviewed `main`.

| What | Where |
| --- | --- |
| Gate policy (committed before any candidate was evaluated) | [`configs/gate-policy.yaml`](configs/gate-policy.yaml) |
| Declared candidates (budget: 3) | [`configs/candidates/`](configs/candidates/) |
| Decision records, one per run, committed | [`decisions/`](decisions/) |
| Raw run outputs, rejected-state proof | [`reports/logs/lab-07/`](reports/logs/lab-07/) |
| Accepted versions, Cloud Run revisions, image digests | [`reports/releases.md`](reports/releases.md) |
| Candidate bundles, accepted store (out of Git) | `runs/`, `registry/` on the release machine |

### Run it (clean checkout)

```powershell
uv sync --locked
uv run --locked python -m bike_demand.pipeline --candidate configs/candidates/deeper-trees.yaml
uv run --locked python -m bike_demand.promote --show
```

The pipeline exits **0 eligible**, **3 rejected** (a measured rule failed),
**4 blocked** (a required check is missing or invalid). A clean checkout has no
`registry/`, so a candidate there is **blocked** (no accepted model to compare
with): that is correct, not a bug. The first accepted model is registered once
with `--bootstrap` (the Lab 2 baseline, which must reproduce its recorded MAE).

Promotion, from `main` only, once the decision record is merged:

```powershell
uv run --locked python -m bike_demand.promote --decision decisions/<record>.json --approved-by <reviewer>
```

### What we found in the existing system

- **Training boundary**: `bike_demand.train` fits on 2011 and scores the
  2012-01..06 validation rows; it accepts only the Week 1 settings.
- **Overwrite risk**: `train_baseline` writes `artifacts/model.joblib`
  unconditionally, and the Lab 3-6 `Dockerfile` retrains during
  `docker build`: in both cases a model reaches serving without any decision.
  The pipeline never writes `artifacts/` or `registry/`, and the Cloud Run image
  is built with `Dockerfile.release`, which copies one accepted version and never
  trains.
- **Settings guard**: `train.load_config` refuses any change. The pipeline has
  its own guard, bounded by `candidate_settings` in the policy, so a settings
  change is reviewed as a policy change. Data path, the twelve ordered features
  and `random_state` cannot change.

### Pipeline boundary (choice, alternative, reason)

| Question | Our choice | Rejected alternative | Why |
| --- | --- | --- | --- |
| Stages | inputs -> train -> evaluate -> decide -> record, functions in one module | one container per stage | the data is small; separate functions already give each stage a contract, a container per stage adds hand-offs with no benefit here |
| Entry point | `python -m bike_demand.pipeline --candidate <yaml>` | a notebook or a Makefile | the lock and `uv run --locked` are all a clean checkout needs; same command locally and in CI |
| Failure | a failed stage still writes a **blocked** decision with the reason | stop with a traceback and no record | an incomplete evaluation must be visible, never confused with a pass |
| Retry | the whole run is safe to rerun: new run id, new folder, nothing overwritten | resume a half-finished run | a rerun is cheap (seconds) and cannot mix two runs' outputs |
| Partial output | written to `runs/<id>.partial/`, renamed only when the record is complete | write straight to `runs/<id>/` | a crashed run is visibly incomplete; `promote` never accepts it |
| Identity | data sha256 + candidate config sha256 + code commit + policy sha256 + settings + model sha256 | the run id alone | the run id names a run; the hashes say which bytes it consumed and produced |

### Fair comparison

| Question | Answer |
| --- | --- |
| Reference | the version named in `registry/current.json`, loaded only after its sha256 matches the record |
| Observations | candidate, train-mean baseline and accepted model predict the **same 4,358 validation rows**, same labels, in the same run |
| Metric | validation MAE in bikes per hour (lower is better) |
| Margin | 0.5 bikes/hour vs the accepted model, 20 vs the train mean; rationale in the policy file |
| Provenance | an old score is never reused: the accepted model is re-scored on the same rows in every run |
| Missing incumbent | `gain_vs_accepted` is **missing** -> decision **blocked**, never passed |

### What failure means

| Outcome | When | What to do |
| --- | --- | --- |
| eligible (0) | every quality, operation and integrity check passed | open a PR with the decision record; a reviewer approves; promote from `main` |
| rejected (3) | evidence is complete and a measured rule failed | keep the record; the accepted model stays as it is |
| blocked (4) | a check is missing or invalid (no accepted model, data hash differs, settings outside the guard, accepted bundle fails its checksum) | repair the cause, then rerun; never edit the record |

### Accepted-state boundary

| Question | Answer |
| --- | --- |
| What may a candidate write? | only `runs/<id>/` and one record in `decisions/` |
| What is immutable? | `registry/versions/<model_version>/` once promoted (model, metadata, decision) |
| Switch | copy to a staging folder, verify, rename to the final folder, then replace `current.json` in one step (`os.replace`) |
| Promotion stops halfway | `current.json` still names the previous version; a leftover `.staging-*` folder is listed as incomplete by `--show` |
| Incumbent changed meanwhile | promote refuses: the decision names the accepted model it was compared with |
| Recovery without retraining | the previous version stays in `registry/versions/`, its image stays in Artifact Registry and its Cloud Run revision stays available ([`reports/releases.md`](reports/releases.md)) |

Recovering a bundle on another machine, without retraining: pull the image by
digest from [`reports/releases.md`](reports/releases.md), then
`docker create` + `docker cp <container>:/app/artifacts ./recovered` and check
the sha256 against the decision record before using it.

### Serve the accepted version on Cloud Run

The Cloud Run image is built with [`Dockerfile.release`](Dockerfile.release):
it copies one promoted version from `registry/versions/` byte for byte and
never trains. Every accepted version gets its own image (by digest) and its own
Cloud Run revision; the previous revision is kept for rollback (Lab 8).
[`reports/releases.md`](reports/releases.md) is the retained record of what
each revision serves.

```powershell
$PROJECT = "<gcp project id>"; $REGION = "europe-west1"
$IMG = "$REGION-docker.pkg.dev/$PROJECT/bike-demand/api"
docker build -f Dockerfile.release --build-arg BUNDLE=registry/versions/$V --build-arg GIT_COMMIT=$SHA -t "${IMG}:$V" .
docker push "${IMG}:$V"
gcloud run deploy bike-demand --image "${IMG}@$DIGEST" --region $REGION --port 8000 --memory 1Gi --max-instances 2 --allow-unauthenticated --set-env-vars "BIKE_DEMAND_EXPECTED_MODEL_SHA256=$MSHA" --revision-suffix <label>
python scripts/check_deployment.py --url $URL --expected-metadata expected-<label>.json --expected-revision $SHA
```

`BIKE_DEMAND_EXPECTED_MODEL_SHA256` comes from the merged decision record, not
from the image: if the bytes in the image differ, the service stays not ready
(503) instead of serving them.

### Local and CI claims

The gate tests (`pytest -m gate`) run in CI on every PR with a throwaway
registry. The official decisions in `decisions/` were produced on the release
machine (named in each record's `environment`), not in CI: a clean runner has
no accepted model, so a candidate there would be blocked. Promotion and
deployment are manual.

### What the gate cannot know

One validation window (Jan-Jun 2012) cannot show that a gain holds later in
2012; the training year has `yr = 0` only, so no setting can learn the 2012
growth. Latency is measured on the release machine, not on Cloud Run. The gate
says nothing about drift after deployment: that is Lab 8.

## Lab 8: monitoring, incident and rollback

| What | Where |
| --- | --- |
| How to respond (symptom, first checks, safe action, verification) | [`RUNBOOK.md`](RUNBOOK.md) |
| What happened in the drill | [`reports/incidents/`](reports/incidents/) |
| Raw evidence (probe attempts and summaries, gcloud outputs, Cloud Run logs) | `reports/incidents/<record>/evidence/` |
| Rollback targets | [`reports/releases.md`](reports/releases.md) |

The API is unchanged: `GET /health` (200 when a verified model is loaded,
otherwise 503), `POST /predict` (prediction + `model_version`; invalid input
4xx; no usable model 503). The service never trains.

### Signals (same definitions in every period)

[`scripts/probe.py`](scripts/probe.py) replays a fixed cohort,
[`examples/replay-validation.jsonl`](examples/replay-validation.jsonl): 200
validation-period hours (every 21st hour of Jan-Jun 2012, made by
`scripts/make_replay.py`), plus 20 deliberately invalid requests. Labels stay
in the file; only the twelve features are sent.

| Signal | Eligible / population | Good | Unit, window | Missing data |
| --- | --- | --- | --- | --- |
| Valid prediction success | every attempt of the 200 valid replay requests, timeouts and connection errors included | HTTP 200, finite prediction >= 0, `model_version` present | ratio, one probe run | 0 eligible attempts = no evidence (null), never 100% |
| Invalid rejection | the 20 invalid requests (hr=24, temp=1.5, weathersit=5, missing field) | 4xx | ratio, same run | reported apart: a correct 422 is not a failure |
| Latency | successful valid attempts | | ms, caller side, p50 / p95 nearest rank, with n | failed attempts listed apart |
| Quality | good valid predictions matched to their label | | MAE bikes/hour + coverage matched/eligible | unmatched = unknown, never zero error |
| Identity | `/version` before and after the window, `model_version` counts in responses | | | |

Alert rules (`--baseline`, exit status 1): valid success < 0.99; MAE above the
baseline MAE + 5 bikes/hour (the model is deterministic and the cohort fixed,
so the same model gives the same MAE: +5 is far above any rounding); p95 above
3 x baseline (network jitter to Cloud Run is large); a `model_version` not
seen in the baseline. A short drill tests the loop; it does not establish a
long-term objective.

## Support and individual reports

If setup remains blocked after five minutes, contact the instructor using the
support route recorded in your working agreement. Do not spend the whole lab
repairing a laptop. Ask for an approved recovery function only if coding remains
blocked; acknowledge the supplied code and assistance in your report. Recovery
is instructor-controlled, not bundled here.

## Names, reports and screenshots

Repository names (lowercase, hyphens, the same for the whole course):

- Team repository: `mlops-<session>-<team-name>-bike-demand`, for example
  `mlops-thu1-sparrows-bike-demand`. Sessions: `thu1`, `thu2`, `fri1`, `fri2`
  (1 = morning, 2 = afternoon).
- Your private report repository: `mlops-<session>-<github-username>`, for example
  `mlops-thu1-minhtc`. You create it and invite the instructor (`minhtc-uca`). Start from the
  [report template](../report-template/README.md) and commit to `main`; no report
  pull request or CI is used.

Reports mix writing and images. Save screenshots in `reports/images/` and embed
them in the report (see the template). A screenshot supports, but does not replace,
the command, revision and your explanation. Never show tokens, passwords or
personal data. Team evidence goes in `reports/lab-01.md` and
`reports/week-01-team.md`, with team screenshots in `reports/images/`.
Each weekly report is due Sunday 23:59 of the same week (published time zone).
Assessment policy comes from the instructor, not this repository.
See `BACKLOG.md` for later labs.
