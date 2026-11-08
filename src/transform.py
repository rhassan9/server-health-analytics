"""
Step 2 - Turn the event table into analysis-ready tables.

The log mixes three kinds of event in one free-text column. This step splits
them, extracts the numbers from the message text and writes:

  data/processed/stats.csv            one row per resource reading (CPU / memory / swap %)
  data/processed/stats_hourly.csv     hourly averages, plus the hour's highest CPU reading
  data/processed/security_events.csv  one row per security event (user processes or IP connections)
  data/processed/security_hourly.csv  the same events keyed by date + hour, without the timestamp
  data/processed/warnings.csv         system warnings with their detail
  data/processed/server_health_summary.xlsx
                                      Stats / Security / Warnings sheets for Excel users

stats_hourly, security_hourly and warnings are the three fact tables the Power BI
model (powerbi/) loads. Their file names and columns are part of that contract:
changing them breaks the model's refresh.
"""
import pandas as pd

from src.paths import PROCESSED_DIR

PCT_FIELDS = {
    "cpu_pct": r"CPU:\s*(\d+(?:\.\d+)?)%",
    "memory_pct": r"Memory:\s*(\d+(?:\.\d+)?)%",
    "swap_pct": r"Swap:\s*(\d+(?:\.\d+)?)%",
}


def _add_time_keys(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = df["timestamp"].dt.date
    df["hour"] = df["timestamp"].dt.hour
    return df


def build_stats(events: pd.DataFrame) -> pd.DataFrame:
    """Resource readings. CPU and memory/swap arrive on separate lines, so each row has gaps."""
    df = _add_time_keys(events[events["type"] == "STATS"])
    for col, pattern in PCT_FIELDS.items():
        df[col] = df["message"].str.extract(pattern, expand=False).astype(float)

    readings = df[list(PCT_FIELDS)]
    unrecognised = readings.isna().all(axis=1)
    if unrecognised.any():
        print(f"[transform] {unrecognised.sum()} Stats lines had no CPU/memory/swap value")
    out_of_range = ((readings < 0) | (readings > 100)).any(axis=1)
    if out_of_range.any():
        raise ValueError(f"{out_of_range.sum()} Stats readings fall outside 0-100%")

    return df.loc[~unrecognised, ["timestamp", "date", "hour", *PCT_FIELDS]]


def build_security(events: pd.DataFrame) -> pd.DataFrame:
    """Two event shapes: per-user process counts, and per-IP connection counts."""
    df = _add_time_keys(events[events["type"] == "SECURITY"])
    msg = df["message"]
    df["username"] = msg.str.extract(r"User\s+'([^']+)'", expand=False)
    # Nullable integers: each event carries one of the two counts, and the CSV should read "32", not "32.0".
    df["active_processes"] = msg.str.extract(r"has\s+(\d+)\s+active processes", expand=False).astype("Int64")
    df["connection_count"] = msg.str.extract(r"High connections\s+\((\d+)\)", expand=False).astype("Int64")
    df["source_ip"] = msg.str.extract(r"from IP\s+(\d{1,3}(?:\.\d{1,3}){3})", expand=False)

    unrecognised = df["active_processes"].isna() & df["connection_count"].isna()
    if unrecognised.any():
        print(f"[transform] {unrecognised.sum()} SECURITY lines matched neither known format")
    return df.loc[~unrecognised, ["timestamp", "date", "hour", "username",
                                  "active_processes", "connection_count", "source_ip"]]


def build_warnings(events: pd.DataFrame) -> pd.DataFrame:
    df = _add_time_keys(events[events["type"] == "WARNING"])
    df["warning_detail"] = df["message"].str.extract(r"\(([^)]+)\)", expand=False)
    return df[["timestamp", "date", "hour", "warning_detail", "message"]]


def hourly_stats(stats: pd.DataFrame) -> pd.DataFrame:
    """Hourly averages, plus the highest single CPU reading in the hour.

    Averages alone hide the short CPU bursts (a 60% reading becomes an 11.7% hourly
    average), so the peak is kept as its own column for the 'Daily Peak CPU' measure.
    """
    grouped = stats.groupby(["date", "hour"])
    hourly = grouped[list(PCT_FIELDS)].mean().round(2)
    hourly["cpu_peak_pct"] = grouped["cpu_pct"].max()
    return hourly.reset_index()


def security_by_hour(security: pd.DataFrame) -> pd.DataFrame:
    """Security events keyed by date + hour: the shape the Power BI model expects."""
    return security.drop(columns=["timestamp"])


def transform(events: pd.DataFrame, out_dir=PROCESSED_DIR) -> dict:
    tables = {
        "stats": build_stats(events),
        "security_events": build_security(events),
        "warnings": build_warnings(events),
    }
    tables["stats_hourly"] = hourly_stats(tables["stats"])
    tables["security_hourly"] = security_by_hour(tables["security_events"])

    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)

    # Power BI source: full timestamps, one sheet per fact table.
    with pd.ExcelWriter(out_dir / "server_health_summary.xlsx",
                        datetime_format="YYYY-MM-DD HH:MM:SS") as xl:
        tables["stats"].drop(columns=["date", "hour"]).to_excel(xl, sheet_name="Stats", index=False)
        tables["security_events"].drop(columns=["date", "hour"]).to_excel(xl, sheet_name="Security", index=False)
        tables["warnings"].drop(columns=["date", "hour"]).to_excel(xl, sheet_name="Warnings", index=False)

    print("[transform] " + ", ".join(f"{k}={len(v)} rows" for k, v in tables.items()))
    return tables
