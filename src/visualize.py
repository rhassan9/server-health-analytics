"""
Step 4 - Charts for the PDF report and README (reports/charts/*.png).

Each chart is a function that draws onto a matplotlib Axes, so the same code
renders the individual PNGs and the 2x2 overview.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from src.findings import CONNECTION_THRESHOLD, SPIKE_PCT
from src.paths import CHARTS_DIR

CPU, MEM, SWAP, ALERT, MUTED = "#e4572e", "#2e86ab", "#f3a712", "#c0392b", "#9aa5b1"


def _slot(df):
    return pd.to_datetime(df["date"].astype(str)) + pd.to_timedelta(df["hour"], unit="h")


def _hourly_peak(t, key, value):
    """Highest value per hour for each user / IP."""
    sec = t["security_events"].dropna(subset=[key, value])
    return sec.groupby(["date", "hour", key], as_index=False)[value].max()


def _time_axis(ax):
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b\n%H:%M"))
    ax.grid(alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)


def plot_cpu_memory(ax, t):
    stats, hourly = t["stats"], t["stats_hourly"]
    cpu = stats.dropna(subset=["cpu_pct"])
    spikes = cpu[cpu["cpu_pct"] >= SPIKE_PCT]
    ax.scatter(cpu["timestamp"], cpu["cpu_pct"], s=10, color=MUTED, label="CPU reading", zorder=2)
    ax.scatter(spikes["timestamp"], spikes["cpu_pct"], s=28, color=CPU, label=f"CPU spike (≥{SPIKE_PCT}%)", zorder=3)
    ax.plot(_slot(hourly), hourly["cpu_pct"], color=CPU, lw=1.5, alpha=0.6, label="CPU, hourly average")
    ax.plot(_slot(hourly), hourly["memory_pct"], color=MEM, lw=2, label="Memory, hourly average")
    ax.set_title("CPU and memory: hourly averages hide the spikes", loc="left", fontweight="bold")
    ax.set_ylabel("% used")
    ax.legend(fontsize=8, ncol=2, frameon=False)
    _time_axis(ax)


def plot_cpu_by_minute(ax, t):
    cpu = t["stats"].dropna(subset=["cpu_pct"]).copy()
    cpu["minute"] = cpu["timestamp"].dt.minute
    minutes = sorted(cpu["minute"].unique())
    data = [cpu.loc[cpu["minute"] == m, "cpu_pct"] for m in minutes]
    ax.boxplot(data, tick_labels=[f":{m:02d}" for m in minutes], patch_artist=True,
               boxprops=dict(facecolor="#f6d5cc", color=CPU), medianprops=dict(color=CPU),
               flierprops=dict(markerfacecolor=CPU, markeredgecolor=CPU, markersize=4))
    ax.set_title("CPU by minute of the hour: spikes only at :00", loc="left", fontweight="bold")
    ax.set_xlabel("Minute the reading was taken")
    ax.set_ylabel("CPU %")
    ax.grid(axis="y", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)


def plot_swap_warning(ax, t):
    stats = t["stats"].dropna(subset=["swap_pct"])
    ax.plot(stats["timestamp"], stats["swap_pct"], color=SWAP, lw=2, label="Swap %")
    ax.plot(stats["timestamp"], stats["memory_pct"], color=MEM, lw=1.2, alpha=0.7, label="Memory %")
    for _, w in t["warnings"].iterrows():
        ax.axvline(w["timestamp"], color=ALERT, ls="--", lw=1.2)
        ax.annotate(f"WARNING\n{w['warning_detail']}", (w["timestamp"], ax.get_ylim()[1] * 0.92),
                    xytext=(6, 0), textcoords="offset points", color=ALERT, fontsize=8, va="top")
    ax.set_title("Swap and memory around the swapping warning", loc="left", fontweight="bold")
    ax.set_ylabel("% used")
    ax.legend(fontsize=8, frameon=False, loc="upper right")
    _time_axis(ax)


def plot_connections(ax, t):
    h = _hourly_peak(t, "source_ip", "connection_count")
    for ip, g in h.groupby("source_ip"):
        over = g["connection_count"] > CONNECTION_THRESHOLD
        ax.bar(_slot(g), g["connection_count"], width=0.035,
               color=[ALERT if o else MUTED for o in over], label=ip)
    ax.axhline(CONNECTION_THRESHOLD, color=ALERT, ls=":", lw=1.2, label=f"Threshold ({CONNECTION_THRESHOLD})")
    ax.legend(fontsize=8, frameon=True, loc="lower right")
    ax.set_title(f"Peak hourly connections from {', '.join(h['source_ip'].unique())}", loc="left", fontweight="bold")
    ax.set_ylabel("Connections")
    _time_axis(ax)


def plot_processes_vs_cpu(ax, t):
    h = _hourly_peak(t, "username", "active_processes")
    for user, g in h.groupby("username"):
        ax.plot(_slot(g), g["active_processes"], marker="o", ms=3, color="#3d8b37", lw=2, label=f"'{user}' peak processes")
    ax.set_ylabel("Active processes")
    ax2 = ax.twinx()
    hourly = t["stats_hourly"]
    ax2.plot(_slot(hourly), hourly["cpu_pct"], color=CPU, lw=1.2, alpha=0.7, label="CPU, hourly average")
    ax2.set_ylabel("CPU %")
    ax2.spines[["top"]].set_visible(False)
    lines = ax.get_legend_handles_labels()[0] + ax2.get_legend_handles_labels()[0]
    ax.legend(lines, [l.get_label() for l in lines], fontsize=8, frameon=False, loc="lower left")
    ax.set_title("User processes don't track CPU load", loc="left", fontweight="bold")
    _time_axis(ax)


CHARTS = {
    "cpu_memory": plot_cpu_memory,
    "cpu_by_minute": plot_cpu_by_minute,
    "swap_warning": plot_swap_warning,
    "connections": plot_connections,
    "processes_vs_cpu": plot_processes_vs_cpu,
}


def visualize(tables: dict, out_dir=CHARTS_DIR) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "font.family": "DejaVu Sans"})
    paths = {}
    for name, draw in CHARTS.items():
        fig, ax = plt.subplots(figsize=(10, 4.5))
        draw(ax, tables)
        fig.tight_layout()
        paths[name] = out_dir / f"{name}.png"
        fig.savefig(paths[name], dpi=150)
        plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(16, 9))
    for ax, name in zip(axes.flat, ["cpu_memory", "cpu_by_minute", "swap_warning", "connections"]):
        CHARTS[name](ax, tables)
    fig.tight_layout(pad=2)
    paths["overview"] = out_dir / "overview.png"
    fig.savefig(paths["overview"], dpi=120)
    plt.close(fig)

    print(f"[visualize] {len(paths)} charts -> {out_dir.relative_to(out_dir.parents[1])}")
    return paths
