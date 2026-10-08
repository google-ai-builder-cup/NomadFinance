from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Resolved from this file so scripts behave the same from any working directory.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

LABOR_LAWS_DIR = DATA_DIR / "source" / "labor-laws"
COMPLAINT_TEMPLATES_DIR = DATA_DIR / "source" / "complaint-templates"
SCAM_TAXONOMY_DIR = DATA_DIR / "source" / "scam-taxonomy"
COST_BASELINES_DIR = DATA_DIR / "source" / "cost-baselines"
SCAM_PATTERNS_DIR = DATA_DIR / "source" / "scam-patterns"
# The golden eval sets of the Scam Analyzer (NF-SA-003 to -005): data-scripts/evals/.
EVALS_DIR = Path(__file__).resolve().parent.parent / "evals"
# Where the eval runner (NF-SA-014) writes its report: docs/evals/ at the repo root.
EVAL_REPORT_DIR = Path(__file__).resolve().parents[2] / "docs" / "evals"
RADAR_SEED_FILE = DATA_DIR / "seed" / "radar-reports" / "seed_reports.json"
SEED_USERS_DIR = DATA_DIR / "seed" / "users"
SEED_CONTRACTS_DIR = DATA_DIR / "seed" / "contracts"

RPW_SOURCE_FILE = DATA_DIR / "source" / "rpw_dataset_2011_2025_q1.xlsx"
RPW_OUTPUT_FILE = DATA_DIR / "processed" / "rpw_corridors.json"

# The workbook keeps pre- and post-Q2-2016 surveys on separate sheets with different columns.
# Only the newer layout is used: it is the one that carries payment instrument and access point.
RPW_SHEET = "Dataset (from Q2 2016)"

RPW_SOURCE_URL = "http://remittanceprices.worldbank.org"
# Wording is mandated by the World Bank terms of use for the dataset.
RPW_ATTRIBUTION = "The World Bank, Remittance Prices Worldwide, available at http://remittanceprices.worldbank.org"


@dataclass(frozen=True)
class Corridor:
    """One send-money corridor and how it is spelled in the RPW workbook."""

    corridor_id: str
    rpw_code: str
    source_country: str
    destination_country: str
    source_currency: str
    destination_currency: str


# Final project scope; order here is the order of the output file.
CORRIDORS: tuple[Corridor, ...] = (
    Corridor("SG-PH", "SGPPHL", "SG", "PH", "SGD", "PHP"),
    Corridor("SG-IN", "SGPIND", "SG", "IN", "SGD", "INR"),
    Corridor("AU-IN", "AUSIND", "AU", "IN", "AUD", "INR"),
    Corridor("MY-ID", "MYSIDN", "MY", "ID", "MYR", "IDR"),
    Corridor("JP-PH", "JPNPHL", "JP", "PH", "JPY", "PHP"),
    Corridor("AU-PH", "AUSPHL", "AU", "PH", "AUD", "PHP"),
)
