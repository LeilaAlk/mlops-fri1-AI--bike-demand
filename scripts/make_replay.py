"""Write examples/replay-validation.jsonl: the fixed cohort the probe replays.

200 validation-period hours (2012-01-01..2012-06-30), every 21st row in time
order, with the twelve contract features and the observed count as a separate
label. The label is never sent to the service; the probe only uses it to
measure prediction error afterwards. No held-test row is included.

    uv run --locked python scripts/make_replay.py
"""

import json
from pathlib import Path

from bike_demand.split import split_data
from bike_demand.validate import FEATURES, NORMALISED, load_data

STEP = 21
COUNT = 200


def main() -> None:
    validation = split_data(load_data("data/raw/hour.csv"))["validation"]
    rows = validation.iloc[::STEP].head(COUNT)
    out = Path("examples/replay-validation.jsonl")
    with out.open("w", encoding="utf-8", newline="\n") as stream:
        for _, row in rows.iterrows():
            features = {
                name: float(row[name]) if name in NORMALISED else int(row[name])
                for name in FEATURES
            }
            key = f"{row['dteday'].date()}T{int(row['hr']):02d}"
            line = {"key": key, "features": features, "label_cnt": int(row["cnt"])}
            stream.write(json.dumps(line) + "\n")
    print(f"wrote {len(rows)} rows to {out.as_posix()}")


if __name__ == "__main__":
    main()
