# Week 2, Lab 3: team evidence

## Team and roles

| Area | Author | Reviewer | PR |

| --- | --- | --- | --- |

| Lock | Talia (@taliaalg) | Julia | #… |

| Dockerfile | Andrea (@andrea180904) | Leila | #… |

| README + team report | Leila (@LeilaAlk) | Andrea | #… |

| Clean rerun | Julia (@JuliaEzzedine) | Talia | #… |

## Revision

TO FILL (Julia): packaged commit SHA, link to uv.lock at that commit, uv.lock

SHA-256.

## Image

TO FILL (Julia): link to the build log, image ID, base image digest.

## Run and comparison with Lab 2

TO FILL (Julia): MAEs, run IDs, model, comparison table and explanation of

differences.

## Lock checks

TO FILL (Julia): links to lock-check.log, lock-missing.log, lock-stale.log,

docker-lock-stale.log.

## Reviews

TO FILL: one line per PR with the reviewer's finding.

## Blocked steps

None so far.

## Local runs vs CI

Docker builds and reruns were run locally. CI checks `uv lock --check`, `uv

sync --locked`, preflight, ruff and tests; it does not build the image.

