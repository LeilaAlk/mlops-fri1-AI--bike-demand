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
| `BIKE_DEMAND_LOG_LEVEL` | `INFO` | Log level of the JSON service logs |
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
