"""Promote one eligible, reviewed decision into the accepted-model store.

    uv run --locked python -m bike_demand.promote --decision decisions/<record>.json --approved-by <github-user>
    uv run --locked python -m bike_demand.promote --show

Promotion is a manual step, from reviewed main: the decision record must be
committed and unchanged. It refuses (and changes nothing) when:

- the decision is not 'eligible' (rejected or blocked),
- the candidate bytes are missing or differ from the sha256 in the decision,
- the accepted model changed since the decision was made (concurrent update),
- the version already exists (versions are immutable, never overwritten).

Order of the switch: copy into a temporary folder, verify, rename it into
registry/versions/<model_version>/ (immutable from then on), then replace
registry/current.json in one step (os.replace). If anything stops before the
last step, 'current' still names the previous accepted version. The version
being replaced is kept, and named in current.json as 'previous'.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from bike_demand.registry import (
    BUNDLE_FILES,
    IntegrityError,
    read_current,
    registry_root,
    snapshot,
    verify_bundle,
    version_dir,
)


class PromotionRefused(ValueError):
    """Promotion would not be safe; nothing was changed."""


def require_reviewed(root: Path, decision_path: Path) -> str:
    """The decision record must be committed on main and unchanged."""

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True
        )

    relative = decision_path.as_posix()
    if git("ls-files", "--error-unmatch", relative).returncode != 0:
        raise PromotionRefused(f"{relative} is not committed: merge it through a PR")
    if git("diff", "--quiet", "HEAD", "--", relative).returncode != 0:
        raise PromotionRefused(f"{relative} differs from the committed version")
    branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if branch != "main":
        raise PromotionRefused(f"promote from reviewed main, not from {branch!r}")
    return git("rev-parse", "HEAD").stdout.strip()


def promote(
    root: Path,
    decision_path: Path,
    approved_by: str,
    reviewed: bool = True,
) -> dict:
    main_commit = require_reviewed(root, decision_path) if reviewed else "not checked"
    decision = json.loads((root / decision_path).read_text())
    if decision.get("outcome") != "eligible":
        raise PromotionRefused(
            f"decision is {decision.get('outcome')!r}, only 'eligible' can be promoted"
        )
    if not approved_by.strip():
        raise PromotionRefused("name the reviewer who approved the promotion")
    candidate = decision["candidate"]
    registry = registry_root(root)
    current = read_current(registry)
    before = decision.get("accepted_before")
    if decision.get("kind") == "bootstrap":
        if current is not None:
            raise PromotionRefused(
                "bootstrap refused: an accepted model already exists"
            )
    elif current is None or before is None:
        raise PromotionRefused("no accepted model recorded before this decision")
    elif current["model_sha256"] != before["model_sha256"]:
        raise PromotionRefused(
            "the accepted model changed since this decision "
            f"({before['model_version']} -> {current['model_version']}): rerun the "
            "pipeline against the current accepted model"
        )
    source = root / candidate["run_dir"]
    verify_bundle(source, candidate["model_sha256"])
    target = version_dir(registry, candidate["model_version"])
    if target.exists():
        raise PromotionRefused(f"{target.as_posix()} exists: versions are immutable")
    # 1. Copy into a temporary folder and verify the copy.
    staging = registry / "versions" / f".staging-{decision['decision_id']}"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    for name in BUNDLE_FILES:
        shutil.copy2(source / name, staging / name)
    shutil.copy2(root / decision_path, staging / "decision.json")
    verify_bundle(staging, candidate["model_sha256"])
    # 2. Make the version visible under its final, immutable name.
    staging.rename(target)
    # 3. Move the 'current' reference in one step; keep the one it replaces.
    record = {
        "model_version": candidate["model_version"],
        "model_sha256": candidate["model_sha256"],
        "decision_id": decision["decision_id"],
        "decision_record": decision_path.as_posix(),
        "promoted_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "approved_by": approved_by,
        "from_main_commit": main_commit,
        "previous": (
            None
            if current is None
            else {k: current[k] for k in ("model_version", "model_sha256")}
        ),
    }
    temporary = registry / "current.json.tmp"
    temporary.write_text(json.dumps(record, indent=2) + "\n")
    os.replace(temporary, registry / "current.json")
    with (registry / "history.jsonl").open("a") as history:
        history.write(json.dumps(record) + "\n")
    return record


def show(root: Path) -> int:
    registry = registry_root(root)
    current = read_current(registry)
    print(json.dumps({"current": current}, indent=2))
    versions = registry / "versions"
    for folder in sorted(versions.iterdir()) if versions.exists() else []:
        if folder.name.startswith("."):
            print(f"  incomplete (ignored): {folder.name}")
            continue
        metadata = json.loads((folder / "model-metadata.json").read_text())
        try:
            verify_bundle(folder, metadata["model_sha256"])
            state = "verified"
        except IntegrityError as error:
            state = f"INTEGRITY FAILURE: {error}"
        mark = "current" if current and folder.name == current["model_version"] else ""
        print(f"  {folder.name}  {metadata['model_sha256'][:12]}  {state}  {mark}")
    print("registry files sha256:")
    for path, digest in snapshot(registry).items():
        print(f"  {digest}  {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--decision", type=Path)
    parser.add_argument("--approved-by", default="")
    parser.add_argument("--show", action="store_true", help="print the accepted state")
    args = parser.parse_args()
    root = Path.cwd()
    if args.show:
        return show(root)
    if args.decision is None:
        parser.error("--decision is required (or use --show)")
    try:
        record = promote(root, args.decision, args.approved_by)
    except (PromotionRefused, IntegrityError, OSError, KeyError) as error:
        print(f"promotion refused, nothing changed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
