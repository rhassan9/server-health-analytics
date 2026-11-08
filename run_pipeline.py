#!/usr/bin/env python3
"""Run the whole pipeline: raw log -> tables -> findings -> charts -> PDF report."""
from src.build_report import build_report
from src.findings import compute_findings, summary_lines
from src.parse_log import parse_log
from src.transform import transform
from src.visualize import visualize


def main():
    events = parse_log()
    tables = transform(events)
    findings = compute_findings(tables)
    charts = visualize(tables)
    build_report(findings, charts)

    print("\nFindings")
    for line in summary_lines(findings):
        print(f"  - {line}")


if __name__ == "__main__":
    main()
