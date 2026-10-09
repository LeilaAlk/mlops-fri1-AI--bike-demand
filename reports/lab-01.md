# Lab 1: Team workflow and check record

Record observed facts or blocked/not-run with reasons. This team worksheet is
not an individual's graded Week 1 report.

## Team and setup

- Team/repository: team AI, https://github.com/LeilaAlk/mlops-fri1-AI--bike-demand
- Week/date: Week 1, 2026-10-09
- Members and temporary roles: Julia (driver and author of PR #1), Leila (repository owner, reviewer of PR #1), Talia (driver and author of the docs PR), Andrea (reviewer of the docs PR)
- Repository/authentication access checks: all members and the instructor (minhtc-uca) added as collaborators; HTTPS with a personal access token. The first push was rejected twice: the repository had been created with a README (fixed by merging unrelated histories), then the token lacked the workflow scope (added).
- Mac version/architecture, Python and uv versions: no Mac; Windows x86_64, Python 3.12.15, uv 0.12.24
- Environment/preflight command and actual outcome: `uv sync --locked` installed 97 packages; `uv run --locked python -m bike_demand.preflight` -> "Preflight passed: imports, frozen snapshot and writable outputs."
- Working agreement and backlog links: WORKING-AGREEMENT.md at the repository root; no backlog yet
- Ignored outputs and secret-protection checks: `git status` showed only the two edited source files; `.venv` is not tracked; no token or password committed

## Reviewed change and checks

- Branch, pull request and checked commit: lab1-fix-team-slug, PR #1, commits 6c2c77f and 0508114, merged to main as 9b0a16a
- Substantive change and responsible contributor: Julia; `normalize_team_slug` now returns `"-".join(team_name.split()).lower()` instead of using `replace(" ", "-")`, which kept repeated spaces and tabs
- Additional test and why it is useful: `test_joins_newlines_and_mixed_whitespace` (newline and mixed space/tab between words) and `test_trims_tabs_and_newlines` (leading/trailing tab and newline); the starter tests only covered spaces and a single tab
- Reviewer observation, response and merge status: Leila asked for a test on leading/trailing tabs and newlines -> added in 0508114. She also asked for a one-line docstring -> not in PR #1, added in the docs PR. PR #1 approved and merged.
- Local lint/format/test commands and actual results: `ruff check .` -> All checks passed!; `ruff format --check .` -> 2 files would be reformatted, fixed with `ruff format .`, then 10 files already formatted; `pytest -q -m lab1` -> 5 passed
- Intentional exercise failure versus infrastructure failures: `pytest -q -m infra` -> 9 passed, no infrastructure failure. `pytest -q -m lab1` before the fix -> 1 failed, 2 passed (`test_joins_whitespace_with_hyphens`: got `team---blue\tnorth`, expected `team-blue-north`), the intentional exercise failure.
- CI check names, actual statuses and checked revision: workflow "Week 1 checks", job "infrastructure" -> passed on 0508114 (latest pushed commit of PR #1)
- Starter/reference/collaborator/other assistance: course starter repository; an AI assistant (Claude) helped with the setup, the bug diagnosis, the fix, the test ideas and the wording of this report

## Lab 2 handover

- Next driver/reviewer: to be decided at the start of Lab 2
- Readiness and remaining blockers: setup verified on Julia's and Talia's machines; Leila and Andrea to confirm theirs; no blocker
- One bounded next action and owner: to be decided at the start of Lab 2
- Own-contribution links retained for each student's Week 1 report: PR #1 (Julia: author, Leila: review); docs PR (Talia: author, Andrea: review)

## Screenshots

Save images in `reports/images/` and embed them below, for example
`![PR checks on a1b2c3d](images/lab-01-pr-checks.png)`. Add one line saying what each
image shows and which commit or pull request it belongs to. Include at least the
failing and the passing `lab1` run, and the pull request checks. Crop to the
relevant part and hide tokens, passwords and personal data.

![lab1 failing run before the fix](images/lab-01-fail.png)
Failing `pytest -m lab1` on the starter commit a869cc8: 1 failed, 2 passed.

![lab1 passing run after the fix](images/lab-01-pass.png)
Passing `pytest -m lab1` on commit 0508114: 5 passed.

![PR #1 checks](images/lab-01-pr-checks.png)
"Week 1 checks / infrastructure" passed on PR #1, commit 0508114.