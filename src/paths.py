"""Project paths, resolved from the repo root so scripts work from any directory."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RAW_LOG = ROOT / "data" / "raw" / "server-health-monitor.log"
INTERIM_DIR = ROOT / "data" / "interim"
PROCESSED_DIR = ROOT / "data" / "processed"
CHARTS_DIR = ROOT / "reports" / "charts"
REPORT_PDF = ROOT / "reports" / "Server_Health_Report.pdf"
