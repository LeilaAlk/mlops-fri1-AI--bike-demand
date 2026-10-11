"""Chronological partitions; test targets are never evaluated in Week 1."""

import pandas as pd

WINDOWS = {
    "train": ("2011-01-01", "2011-12-31"),
    "validation": ("2012-01-01", "2012-06-30"),
    "test": ("2012-07-01", "2012-12-31"),
}


def split_data(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    ordered = frame.sort_values(["dteday", "hr", "instant"])
    partitions = {}
    assigned = pd.Series(0, index=ordered.index)
    for name, (start, end) in WINDOWS.items():
        inside = ordered["dteday"].between(pd.Timestamp(start), pd.Timestamp(end))
        partitions[name] = ordered.loc[inside]
        assigned += inside.astype(int)
    if (assigned == 0).any():
        raise ValueError("split: partitions must be complete; row outside all windows")
    if (assigned > 1).any():
        raise ValueError("split: partitions must be disjoint")
    for name, part in partitions.items():
        if part.empty:
            raise ValueError(f"split: {name} partition must be nonempty")
    return partitions


def partition_summary(partitions: dict[str, pd.DataFrame]) -> dict:
    return {
        name: {
            "rows": len(part),
            "date_min": str(part["dteday"].min().date()),
            "date_max": str(part["dteday"].max().date()),
        }
        for name, part in partitions.items()
    }
