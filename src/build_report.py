"""
Step 5 - A short PDF report (reports/Server_Health_Report.pdf).

All numbers are filled in from findings.compute_findings().
"""
from fpdf import FPDF

from src.findings import CONNECTION_THRESHOLD, SPIKE_PCT
from src.paths import REPORT_PDF


class Report(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 15)
        self.cell(0, 9, "Server Health Analysis", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(180, 180, 180)
        self.line(10, 19, 200, 19)
        self.ln(5)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")

    def section(self, title, body, chart=None):
        if title:
            self.set_font("Helvetica", "B", 12)
            self.multi_cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")
        if body:
            self.set_font("Helvetica", size=10)
            self.multi_cell(0, 5.2, body, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
        if chart:
            self.image(str(chart), x=12, w=186)
        self.ln(5)


def build_report(f: dict, charts: dict, out=REPORT_PDF):
    pdf = Report()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    pdf.section(
        "Scope",
        f"One server-monitoring log from {f['start']:%d %b %H:%M} to {f['end']:%d %b %H:%M} "
        f"({f['hours_covered']} hours): resource readings every 10 minutes, security events "
        f"(per-user process counts and per-IP connection counts) and system warnings. "
        f"The raw text log was parsed into structured tables; every line parsed, none were dropped.",
    )
    pdf.section(
        "1. CPU load comes in short scheduled bursts",
        f"Average CPU is low ({f['cpu_avg']:.1f}%), but readings reach {f['cpu_peak']:.0f}% "
        f"(peak at {f['cpu_peak_at']:%d %b %H:%M}). All {f['cpu_spikes']} readings of {SPIKE_PCT}% or more "
        f"were taken at minute :00. Readings on the hour average {f['cpu_top_of_hour_avg']:.1f}%, every other "
        f"reading {f['cpu_other_avg']:.1f}%. That pattern points to a scheduled job (cron or similar), mostly "
        f"every two hours overnight. Hourly averaging flattens these bursts to at most "
        f"{f['cpu_peak_hourly_avg']:.1f}%, so a dashboard built on hourly averages understates peak load "
        f"about {f['cpu_peak'] / f['cpu_peak_hourly_avg']:.0f}x.",
        charts["cpu_memory"],
    )
    pdf.section("", "", charts["cpu_by_minute"])
    pdf.section(
        "2. The swapping warning resolved itself",
        f"One warning was logged: '{f['warning_detail']}' at {f['warning_at']:%d %b %H:%M}. Swap sat at "
        f"{f['swap_before']:.0f}% before it. {f['swap_release_minutes']:.0f} minutes later swap dropped to "
        f"{f['swap_after']:.0f}% and memory from {f['memory_before']:.0f}% to {f['memory_after']:.0f}% in the same "
        f"reading, which is consistent with a process being stopped or restarted. Swap then crept back to "
        f"{f['swap_end']:.0f}% by the end of the log, worth watching over a longer window.",
        charts["swap_warning"],
    )
    pdf.section(
        "3. One internal IP holds hundreds of connections",
        f"Every high-connection event came from {', '.join(f['source_ips'])}, a private (internal) address. "
        f"Its hourly peak was above {CONNECTION_THRESHOLD} in {f['conn_hours_over_threshold']} of "
        f"{f['conn_hours_total']} hours, up to {f['conn_peak']:.0f}. A single internal source at this volume is "
        f"more likely a service (load balancer, proxy, connection pool) than an attack; the next step is to "
        f"identify that host and set an expected baseline for it.",
        charts["connections"],
    )
    pdf.section(
        "4. User processes don't explain the CPU load",
        f"User '{f['proc_peak_user']}' peaked at {f['proc_peak']:.0f} active processes "
        f"({f['proc_peak_at']:%d %b %H:%M}), but hourly process counts and hourly CPU are essentially "
        f"uncorrelated (r = {f['cpu_proc_corr']:.2f}). The CPU bursts in finding 1 come from something else.",
        charts["processes_vs_cpu"],
    )
    pdf.section(
        "Limits",
        "This is a single 24-hour sample from one server, so it shows patterns, not trends. The pipeline and the "
        "Power BI model have date dimensions so more days of logs can be appended without changes.",
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out))
    print(f"[report] {out.name}")
