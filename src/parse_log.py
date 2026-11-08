"""
Step 1 - Parse the raw monitoring log into a structured event table.

Each log line looks like:
    2026-03-23 12:13:19 - Stats: Memory: 28% | Swap: 12%
    2026-03-23 12:13:20 - SECURITY: User 'geneva' has 32 active processes.
    2026-03-23 18:00:02 - WARNING: Active swapping detected (Swap IO: 816 blocks/s)

Output: data/interim/server_health.csv with columns timestamp, type, message.
Lines that don't match the format are counted and reported rather than
silently dropped, so a change in the monitor's output is noticed.
"""
import re
from pathlib import Path

import pandas as pd

from src.paths import INTERIM_DIR, RAW_LOG

LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - (\w+): (.*)$")


def parse_lines(lines):
    """Split log lines into (events DataFrame, list of rejected lines)."""
    records, rejected = [], []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        m = LINE_RE.match(line)
        if m:
            records.append(m.groups())
        else:
            rejected.append(line)

    df = pd.DataFrame(records, columns=["timestamp", "type", "message"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="%Y-%m-%d %H:%M:%S")
    df["type"] = df["type"].str.upper()
    return df, rejected


def parse_log(path: Path = RAW_LOG, out_dir: Path = INTERIM_DIR) -> pd.DataFrame:
    with open(path, encoding="utf-8") as f:
        df, rejected = parse_lines(f)

    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "server_health.csv", index=False)

    counts = ", ".join(f"{t}={n}" for t, n in df["type"].value_counts().items())
    print(f"[parse] {len(df)} events ({counts}); {len(rejected)} unparseable lines")
    for line in rejected[:5]:
        print(f"[parse]   rejected: {line[:100]}")
    return df


if __name__ == "__main__":
    parse_log()
