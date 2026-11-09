# Releases: what each Cloud Run revision serves

Retained record, written when a version is deployed and never rewritten (add a
line, change only the Status column). It is the independent expectation used
to verify the live service and to choose a rollback target (Lab 8).

Service: `bike-demand`, project `bike-demand-ai`, region `europe-west1`,
URL `https://bike-demand-6zxggmsv2a-ew.a.run.app`.

| Cloud Run revision | model_version | model_sha256 | Decision record | Image digest | Code commit | Deployed (UTC) | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `bike-demand-v1-baseline` | `baseline-51e768eff2cb` | `fd98ceafc57a5babce61ce703cbf9cb8d1f83c6820b0b34fe30ad1a0fc49c304` | [`decisions/20261108T212133Z-baseline-eligible.json`](../decisions/20261108T212133Z-baseline-eligible.json) | `sha256:4af3cd600c9e98e4ebc04bbbb81aba3773149cdc653ae7420020b0da0488accb` | `230d46289f38fc80b1b5dceed64e0201cb303c62` | see gcloud run revisions list | retained |
| `bike-demand-v2-deeper` | `deeper-trees-e024f62d651a` | `94f4f4b8f3482d034c10cec68cd65e66fdb91b0aac4119c61979f8bd2de9f857` | [`decisions/20261108T215758Z-deeper-trees-eligible.json`](../decisions/20261108T215758Z-deeper-trees-eligible.json) | `sha256:0f643f971c168b85b1007789b598dffe721ab00122dfcaabef44c25b980fc59b` | `a9eda78d66c42d08b84a325cfcf5eac86bda4ebc` | see gcloud run revisions list | serving 100% |

Status values: `serving 100%`, `retained` (no traffic, available for rollback),
`rehearsal only` (Lab 8 drill, never an accepted version).
