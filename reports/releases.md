# Releases: what each Cloud Run revision serves

Retained record, written when a version is deployed and never rewritten (add a
line, change only the Status column). It is the independent expectation used
to verify the live service and to choose a rollback target (Lab 8).

Service: `bike-demand`, project `bike-demand-ai`, region `europe-west1`,
URL `<https://...run.app>`.

|Cloud Run revision|model\_version|model\_sha256|Decision record|Image digest|Code commit|Deployed (UTC)|Status|
|-|-|-|-|-|-|-|-|
|`bike-demand-v1-baseline`|`<baseline-...>`|`<sha256>`|[`decisions/<...>-baseline-eligible.json`](../decisions/)|`sha256:<...>`|`<sha>`|`<time>`|retained|
|`bike-demand-v2-deeper`|`<deeper-trees-...>`|`<sha256>`|[`decisions/<...>-deeper-trees-eligible.json`](../decisions/)|`sha256:<...>`|`<sha>`|`<time>`|serving 100%|

Status values: `serving 100%`, `retained` (no traffic, available for rollback),
`rehearsal only` (Lab 8 drill, never an accepted version).

