"""
Step 3 - Compute the headline findings from the processed tables.

Every number quoted in the PDF report comes from here, so the narrative can't
drift from the data when the log changes.
"""
import pandas as pd

CONNECTION_THRESHOLD = 300  # same threshold line as the Power BI anomaly chart
SPIKE_PCT = 15              # a CPU reading this high counts as a spike (median reading is 2%)


def compute_findings(tables: dict) -> dict:
    stats = tables["stats"]
    sec = tables["security_events"]
    warns = tables["warnings"]
    hourly = tables["stats_hourly"].copy()
    hourly["slot"] = pd.to_datetime(hourly["date"].astype(str)) + pd.to_timedelta(hourly["hour"], unit="h")

    f = {}
    all_ts = pd.concat([stats["timestamp"], sec["timestamp"], warns["timestamp"]])
    f["start"], f["end"] = all_ts.min(), all_ts.max()
    f["hours_covered"] = len(hourly)

    # Resource load
    cpu = stats.dropna(subset=["cpu_pct"])
    peak = cpu.loc[cpu["cpu_pct"].idxmax()]
    f["cpu_avg"] = cpu["cpu_pct"].mean()
    f["cpu_peak"], f["cpu_peak_at"] = peak["cpu_pct"], peak["timestamp"]
    f["cpu_peak_hourly_avg"] = hourly["cpu_pct"].max()
    # Spikes cluster at minute :00, the signature of a scheduled job.
    on_the_hour = cpu["timestamp"].dt.minute == 0
    f["cpu_top_of_hour_avg"] = cpu.loc[on_the_hour, "cpu_pct"].mean()
    f["cpu_other_avg"] = cpu.loc[~on_the_hour, "cpu_pct"].mean()
    spikes = cpu[cpu["cpu_pct"] >= SPIKE_PCT]
    f["cpu_spikes"] = len(spikes)
    f["cpu_spikes_on_the_hour"] = int((spikes["timestamp"].dt.minute == 0).sum())
    f["cpu_spike_times"] = list(spikes["timestamp"])
    f["memory_avg"] = stats["memory_pct"].mean()
    f["memory_peak"] = stats["memory_pct"].max()

    # Swap around the warning
    f["warning_count"] = len(warns)
    swap = stats.dropna(subset=["swap_pct"]).sort_values("timestamp")
    if len(warns):
        w = warns.iloc[0]
        f["warning_at"], f["warning_detail"] = w["timestamp"], w["warning_detail"]
        before = swap[swap["timestamp"] < w["timestamp"]]
        after = swap[swap["timestamp"] > w["timestamp"]]
        f["swap_before"] = before["swap_pct"].iloc[-1]
        f["memory_before"] = before["memory_pct"].iloc[-1]
        released = after[after["swap_pct"] < f["swap_before"]]
        if len(released):
            r = released.iloc[0]
            f["swap_released_at"], f["swap_after"], f["memory_after"] = r["timestamp"], r["swap_pct"], r["memory_pct"]
            f["swap_release_minutes"] = (r["timestamp"] - w["timestamp"]).total_seconds() / 60
        f["swap_end"] = swap["swap_pct"].iloc[-1]

    # Connections
    conns = sec.dropna(subset=["connection_count"])
    f["source_ips"] = sorted(conns["source_ip"].unique())
    f["conn_peak"] = conns["connection_count"].max()
    f["conn_peak_ip"] = conns.loc[conns["connection_count"].idxmax(), "source_ip"]
    conn_hourly = conns.groupby(["date", "hour"])["connection_count"].max()
    f["conn_hours_over_threshold"] = int((conn_hourly > CONNECTION_THRESHOLD).sum())
    f["conn_hours_total"] = len(conn_hourly)

    # User processes, and whether they explain CPU
    procs = sec.dropna(subset=["active_processes"])
    f["users"] = sorted(procs["username"].unique())
    top = procs.loc[procs["active_processes"].idxmax()]
    f["proc_peak"], f["proc_peak_user"], f["proc_peak_at"] = top["active_processes"], top["username"], top["timestamp"]
    proc_hourly = procs.groupby(["date", "hour"])["active_processes"].max().rename("procs")
    joined = hourly.set_index(["date", "hour"]).join(proc_hourly, how="inner").dropna(subset=["cpu_pct", "procs"])
    # Two pairings, so the conclusion doesn't hinge on one choice of aggregation.
    f["cpu_proc_corr"] = joined["cpu_pct"].corr(joined["procs"])            # hourly average CPU
    f["cpu_peak_proc_corr"] = joined["cpu_peak_pct"].corr(joined["procs"])  # hourly peak CPU

    # What each series was doing at the other's peak (latest reading at or before that moment).
    def value_at(df, col, ts):
        before = df[df["timestamp"] <= ts]
        return before[col].iloc[-1] if len(before) else None

    f["cpu_at_proc_peak"] = value_at(cpu, "cpu_pct", f["proc_peak_at"])
    f["procs_at_cpu_peak"] = value_at(procs, "active_processes", f["cpu_peak_at"])
    night = joined[joined.index.get_level_values("hour") < 6]
    day = joined[joined.index.get_level_values("hour").isin(range(9, 18))]
    f["cpu_night_avg"], f["cpu_day_avg"] = night["cpu_pct"].mean(), day["cpu_pct"].mean()
    return f


def spike_schedule(f: dict) -> str:
    """'16:00, 18:00, ... (23 Mar) and 00:00, ... (24 Mar)' - the times the CPU spikes landed."""
    by_day: dict = {}
    for ts in f["cpu_spike_times"]:
        by_day.setdefault(ts.strftime("%d %b"), []).append(ts.strftime("%H:%M"))
    return " and ".join(f"{', '.join(times)} ({day})" for day, times in by_day.items())


def summary_lines(f: dict) -> list[str]:
    """Plain-text findings, printed by the pipeline and used in the report."""
    lines = [
        f"Window: {f['start']:%Y-%m-%d %H:%M} to {f['end']:%Y-%m-%d %H:%M} ({f['hours_covered']} hourly slots)",
        f"CPU: average {f['cpu_avg']:.1f}%, peak reading {f['cpu_peak']:.0f}% at {f['cpu_peak_at']:%m-%d %H:%M} "
        f"(highest hourly average only {f['cpu_peak_hourly_avg']:.1f}%)",
        f"CPU spikes: {f['cpu_spikes_on_the_hour']} of {f['cpu_spikes']} readings >= {SPIKE_PCT}% land at minute :00; "
        f"readings at :00 average {f['cpu_top_of_hour_avg']:.1f}% vs {f['cpu_other_avg']:.1f}% otherwise; "
        f"spikes at {spike_schedule(f)}",
        f"CPU by time of day: {f['cpu_night_avg']:.1f}% hourly average overnight (00-06h) vs {f['cpu_day_avg']:.1f}% in working hours (09-18h)",
        f"Memory: average {f['memory_avg']:.1f}%, peak {f['memory_peak']:.0f}%",
        f"Connections: all from {', '.join(f['source_ips'])}; peak {f['conn_peak']:.0f}; "
        f"above {CONNECTION_THRESHOLD} in {f['conn_hours_over_threshold']} of {f['conn_hours_total']} hours",
        f"Processes: peak {f['proc_peak']:.0f} for user '{f['proc_peak_user']}' at {f['proc_peak_at']:%m-%d %H:%M} "
        f"(CPU then {f['cpu_at_proc_peak']:.0f}%); at the CPU peak the user had {f['procs_at_cpu_peak']:.0f}. "
        f"Correlation with hourly CPU: r = {f['cpu_proc_corr']:.2f} (average), {f['cpu_peak_proc_corr']:.2f} (peak)",
    ]
    if f["warning_count"]:
        lines.append(
            f"Warnings: {f['warning_count']} - '{f['warning_detail']}' at {f['warning_at']:%m-%d %H:%M}; "
            f"{f['swap_release_minutes']:.0f} min later swap fell {f['swap_before']:.0f}% -> {f['swap_after']:.0f}% "
            f"and memory {f['memory_before']:.0f}% -> {f['memory_after']:.0f}% (swap ends the log at {f['swap_end']:.0f}%)"
        )
    return lines
