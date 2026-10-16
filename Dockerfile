# Lab 3: rerun the Lab 2 baseline in a clean container.
# Build:  docker build --build-arg GIT_COMMIT=$(git rev-parse HEAD) -t bike-demand:lab3 .
# Train:  docker run --name lab3-train bike-demand:lab3
# Tests:  docker run --rm bike-demand:lab3 uv run --locked pytest -q

# Pinned Python minor version (the project requires >=3.12,<3.13).
# For a fully reproducible build, replace the tag with its digest after the
# first pull: FROM python:3.12-slim@sha256:<digest>
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1


# train.py runs `git rev-parse` to record the commit; the slim image has no git.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*

# Same uv version as CI (.github/workflows/ci.yml) and pyproject.toml (>=0.12.19,<0.13).
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /uvx /bin/

# Use the image's Python, never download another one; copy files instead of
# hard-linking (no shared cache in the image); byte-compile for faster startup.
ENV UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# 1) Manifest and lock first: this layer and the install below stay cached as
#    long as dependencies do not change, even when the code changes.
COPY pyproject.toml uv.lock .python-version ./

# 2) Install exactly the lock, dependencies only. --locked stops the build if
#    uv.lock is missing or out of date instead of regenerating it.
#    Dev dependencies (pytest, ruff) are kept: the image must also run the tests
#    and preflight imports both.
RUN uv sync --locked --no-install-project

# 3) Code, config, frozen data snapshot, tests, and the files preflight requires.
COPY README.md ./
COPY src ./src
COPY configs ./configs
COPY data ./data
COPY tests ./tests
COPY reports/week-01-team.md ./reports/
COPY .github/workflows/ci.yml ./.github/workflows/

# 4) Install the project itself, still strictly from the lock.
RUN uv sync --locked

# .git is not in the image, so train.py records training_commit "unavailable".
# The commit used to build is recorded on the image instead (docker image inspect).
ARG GIT_COMMIT=unknown
LABEL org.opencontainers.image.revision=$GIT_COMMIT \
      org.opencontainers.image.source="https://github.com/LeilaAlk/mlops-fri1-AI--bike-demand"

# Default: the Lab 2 baseline (validate, split, train, compare, readback).
CMD ["uv", "run", "--locked", "python", "-m", "bike_demand.train", "--config", "configs/baseline.yaml"]
