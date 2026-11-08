import pandas as pd
import pytest

from src.findings import compute_findings
from src.parse_log import parse_lines, parse_log
from src.paths import RAW_LOG
from src.transform import build_security, build_stats, build_warnings, hourly_stats, transform

SAMPLE = [
    "2026-03-23 12:00:02 - Stats: CPU: 46%",
    "2026-03-23 12:10:01 - Stats: CPU: 2%",
    "2026-03-23 12:10:02 - Stats: Memory: 28% | Swap: 12%",
    "2026-03-23 12:13:20 - SECURITY: User 'geneva' has 32 active processes.",
    "2026-03-23 12:13:20 - SECURITY: High connections (433) from IP 10.239.61.54",
    "2026-03-23 18:00:02 - WARNING: Active swapping detected (Swap IO: 816 blocks/s)",
    "",
    "this line is not in the log format",
]


@pytest.fixture
def events():
    df, _ = parse_lines(SAMPLE)
    return df


def test_parse_splits_fields_and_reports_bad_lines():
    df, rejected = parse_lines(SAMPLE)
    assert len(df) == 6
    assert list(df["type"].unique()) == ["STATS", "SECURITY", "WARNING"]
    assert df["timestamp"].dtype.kind == "M"
    assert rejected == ["this line is not in the log format"]  # blank line skipped, bad line kept for reporting


def test_stats_extracts_each_metric(events):
    stats = build_stats(events)
    assert stats["cpu_pct"].dropna().tolist() == [46.0, 2.0]
    row = stats.dropna(subset=["memory_pct"]).iloc[0]
    assert (row["memory_pct"], row["swap_pct"]) == (28.0, 12.0)


def test_stats_rejects_impossible_percentages():
    df, _ = parse_lines(["2026-03-23 12:00:02 - Stats: CPU: 140%"])
    with pytest.raises(ValueError):
        build_stats(df)


def test_hourly_stats_keeps_the_peak_the_average_hides(events):
    hourly = hourly_stats(build_stats(events)).iloc[0]
    assert hourly["cpu_pct"] == 24.0       # (46 + 2) / 2
    assert hourly["cpu_peak_pct"] == 46.0  # what the 'Daily Peak CPU' measure reads


def test_security_handles_both_event_shapes(events):
    sec = build_security(events)
    user = sec.dropna(subset=["username"]).iloc[0]
    ip = sec.dropna(subset=["source_ip"]).iloc[0]
    assert (user["username"], user["active_processes"]) == ("geneva", 32)
    assert (ip["source_ip"], ip["connection_count"]) == ("10.239.61.54", 433)


def test_warning_detail(events):
    assert build_warnings(events)["warning_detail"].tolist() == ["Swap IO: 816 blocks/s"]


def test_power_bi_contract(tmp_path, events):
    """The Power BI model loads these files by name and column; keep them stable."""
    transform(events, out_dir=tmp_path)
    expected = {
        "stats_hourly.csv": ["date", "hour", "cpu_pct", "memory_pct", "swap_pct", "cpu_peak_pct"],
        "security_hourly.csv": ["date", "hour", "username", "active_processes", "connection_count", "source_ip"],
        "warnings.csv": ["timestamp", "date", "hour", "warning_detail", "message"],
    }
    for name, columns in expected.items():
        assert list(pd.read_csv(tmp_path / name).columns) == columns, name
    assert (tmp_path / "security_hourly.csv").read_text().splitlines()[1] == "2026-03-23,12,geneva,32,,"


def test_full_log_parses_completely_and_findings_hold(tmp_path):
    events = parse_log(RAW_LOG, out_dir=tmp_path)
    assert len(events) == sum(1 for line in open(RAW_LOG) if line.strip())
    f = compute_findings(transform(events, out_dir=tmp_path))
    assert f["cpu_peak"] == 60 and f["cpu_spikes"] == f["cpu_spikes_on_the_hour"]
    assert f["swap_before"] == 12 and f["swap_after"] == 2
    # Processes don't explain CPU, whether CPU is averaged or peaked per hour...
    assert abs(f["cpu_proc_corr"]) < 0.3 and abs(f["cpu_peak_proc_corr"]) < 0.3
    # ...and the process peak falls in a quiet CPU reading, not a spike.
    assert f["cpu_at_proc_peak"] < 15 and f["procs_at_cpu_peak"] < f["proc_peak"]
    # Every spike is on the hour.
    assert all(ts.minute == 0 for ts in f["cpu_spike_times"])
