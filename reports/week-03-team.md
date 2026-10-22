# Week 3, Labs 5-6: team evidence

## Lab 5: deploy, log and check the service

### Team and roles

| Part | Author | Reviewer | PR |
| --- | --- | --- | --- |
| Start-up: settings, `/version`, fail-closed expected hash | Talia | Andrea | #17 |
| Structured logging: one JSON line per request | Julia | Leila | #18 |
| Deployment check script | Andrea | Talia | #19 |
| README "Lab 5: deploy and check the service" | Leila | Julia | #20 |
| Final check from a fresh clone + this section | Andrea | Talia | #21 |

"Deployed" is defined in the README (Lab 5 section): image from a known commit,
started with the README command, `scripts/check_deployment.py` exits 0 against
the running container, and the log lines show which model and code answered.
The final check was run by Andrea, who did not write the start-up code or the README.

### Commit -> image -> run

- Commit: `a970abba447d3dd2a25ea6233ce3d32b52af6c18` ([final-commit.txt](logs/lab-05/final-commit.txt)).
- Image: `sha256:c283510c04c7d93b9125d66226e329a31587b72ca3d73ba0b8d04a82d5ca86ea`, label `org.opencontainers.image.revision` = `a970abba447d3dd2a25ea6233ce3d32b52af6c18`
  ([image inspect](logs/lab-05/final-image-inspect.json), [build log](logs/lab-05/final-build.log)).
  Command: `docker run -d --name lab5-api -p 127.0.0.1:8000:8000 bike-demand:lab5`.
- Expected model, copied out of the image before start-up:
  [expected-model.json](logs/lab-05/expected-model.json) (`model_version` `baseline-68d00f8187dd`, `model_sha256` `d24c050e3631d5b4c2feb8cb571bef6382d8c975c42a5c11edd28de78a0b8c07`).
- Run: check output [final-check.txt](logs/lab-05/final-check.txt) (8/8 ok, exit 0),
  [final-check.json](logs/lab-05/final-check.json); container logs
  [final-docker-logs.txt](logs/lab-05/final-docker-logs.txt) (one `request` line per call,
  with `request_id`, status, outcome, duration, `service_revision`, `model_version`, `model_sha256`).

![Deployment check passes against the running container](images/lab-05-team-check.png)

![One JSON log line per request with identity fields](images/lab-05-team-logs.png)

### Break it on purpose

Started the same image with `-e BIKE_DEMAND_EXPECTED_MODEL_SHA256=0000000000000000`
(an expected model that is not the one in the image).

- `/health` -> 503 ([broken-health.txt](logs/lab-05/broken-health.txt)).
- Start-up log line `model_unavailable` with
  `"reason": "model.joblib sha256 d24c050e3631 differs from expected 000000000000"`
  ([broken-docker-logs.txt](logs/lab-05/broken-docker-logs.txt)).
- Check: 5 of 8 claims FAIL (ready, `model_version`, `model_sha256`, valid input -> 200, prediction `model_version`); `service_revision`, request id and the 422 rejection still pass; exit status 1 ([broken-check.txt](logs/lab-05/broken-check.txt)).
- Could a stranger find the cause? Yes: the start-up log line `model_unavailable` names both hashes (loaded `d24c050e3631`, expected `000000000000`) and the code revision, and the check output shows that only the model claims fail while the code identity and input validation still work. The fix is to start without the wrong `BIKE_DEMAND_EXPECTED_MODEL_SHA256` (or with the real hash).

![Broken start-up: check fails and the log names both hashes](images/lab-05-team-broken.png)

### Reviews

- Start-up PR (#17) reviewed by Andrea: changed how it starts with `-e BIKE_DEMAND_EXPECTED_MODEL_SHA256=0000000000000000`; `/health` returned 503 naming both hashes (`d24c050e3631` vs `000000000000`) and `/version` reported `"ready": false` with null model fields. Without the override the service was ready and `service_revision` matched the branch commit (`a22929e6`). Approved.
- Logging PR (#18) reviewed by Leila: asked to change the reviewer section and add @LeilaAlk; otherwise "everything is clear". Approved.
- Check script PR (#19) reviewed by Talia: built the image from `lab05/check` (`6b8f62c`), copied `model-metadata.json` out with `docker cp` and ran the script over HTTP: correct expectations 8/8 ok, exit 0; `--expected-revision 0000000` only `service_revision` FAIL, exit 1; container stopped: all 8 claims FAIL, exit 1 (the script never reports ok when it cannot check). Observation: when the service is down the output does not say why (connection refused); a one-line "cannot reach" message would help. Not blocking. Approved.
- README PR (#20) reviewed by Julia (followed only the README from a fresh clone at `9943cf3`): check 8/8 ok, exit 0; `/version` 200 with the right `service_revision`, ready true, `X-Request-ID` present. Restarted with `BIKE_DEMAND_LOG_LEVEL=WARNING`: `/health` still 200 but no JSON log line at all, not even `model_loaded`, so a reader of the logs alone could not tell which model and code run. Asked to document that WARNING hides the start-up line and that the deployment check expects the default INFO level; also noted the empty PR description. Approved.
- Final check PR (#21) reviewed by Talia: see the PR conversation.

### Blocked steps

None.

### Local runs vs CI

The image build, the container runs, the HTTP checks and the logs above were
produced locally with Docker Desktop. GitHub Actions does not build the image or
run the deployment check yet (Lab 6 will add this).
