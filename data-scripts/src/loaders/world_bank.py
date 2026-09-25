"""Parse the World Bank RPW workbook into one document per project corridor.

Run from data-scripts/:  python -m src.loaders.world_bank
Only parses; loading into Firestore belongs to NF-P1-016.
"""

from __future__ import annotations

import argparse
import logging
import math
from datetime import datetime
from pathlib import Path

import pandas as pd
from pydantic import ValidationError

from src.config import (
    CORRIDORS,
    RPW_ATTRIBUTION,
    RPW_OUTPUT_FILE,
    RPW_SHEET,
    RPW_SOURCE_FILE,
    RPW_SOURCE_URL,
    Corridor,
)
from src.validators.corridor import (
    CorridorDoc,
    ProviderRecord,
    RpwCorridorFile,
    SourceInfo,
    verify_against_source,
)

log = logging.getLogger(__name__)

REQUIRED_COLUMNS = frozenset(
    {
        "id", "period", "corridor", "firm", "firm_type", "payment instrument", "access point",
        "pickup method", "speed actual", "receiving network coverage", "Standard Note", "date",
        "inter lcu bank fx", "cc1 lcu code", "cc1 denomination amount", "cc1 lcu amount",
        "cc1 lcu fee", "cc1 lcu fx rate", "cc1 fx margin", "cc1 total cost %",
        "cc2 denomination amount", "cc2 lcu amount", "cc2 lcu fee", "cc2 lcu fx rate",
        "cc2 fx margin", "cc2 total cost %",
    }
)  # fmt: skip

# RPW quotes a few services in USD instead of the destination currency. Their interbank rate is
# then off by orders of magnitude from every local-currency row of the same corridor.
_USD_PAYOUT_RATIO_LIMITS = (0.5, 2.0)


def read_rpw_sheet(path: Path = RPW_SOURCE_FILE, sheet: str = RPW_SHEET) -> pd.DataFrame:
    """Read the survey sheet and check it still has the columns this parser depends on."""
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Download steps: data-scripts/data/source/README.md"
        )
    df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
    # The sheet has ~30 unnamed trailing columns left over from the export.
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
    df.columns = pd.Index([str(c).strip() for c in df.columns])
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"RPW sheet {sheet!r} is missing columns: {sorted(missing)}")
    return df


def _clean(value: object) -> object:
    """Turn NaN and blank strings into None so Pydantic sees a plain missing value."""
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str):
        return value.strip() or None
    return value


def _round(value: object, digits: int) -> object:
    """Trim float dust from the Excel export (e.g. 1.8499999999999999) without losing precision."""
    return round(value, digits) if isinstance(value, int | float) else value


def _survey_date(value: object) -> str:
    """ISO date of the survey; the sheet holds real dates, older exports held '24/Jan/2011'."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    return datetime.strptime(str(value), "%d/%b/%Y").date().isoformat()


def _quote(
    row: dict[str, object], prefix: str, usd_amount: float, corridor: Corridor
) -> dict[str, object]:
    """Build one quote dict, refusing rows that are not the documented USD 200/500 survey."""
    if row[f"{prefix} denomination amount"] != usd_amount:
        raise ValueError(f"{prefix} is not a USD {usd_amount:g} quote")
    if prefix == "cc1" and row["cc1 lcu code"] != corridor.source_currency:
        raise ValueError(f"currency {row['cc1 lcu code']} != {corridor.source_currency}")
    return {
        "send_amount_lcu": _round(row[f"{prefix} lcu amount"], 6),
        "fee_lcu": _round(row[f"{prefix} lcu fee"], 6),
        # Rates keep more digits: JPY to USD is about 0.0066 and 6 decimals would cost precision.
        "fx_rate": _round(row[f"{prefix} lcu fx rate"], 10),
        "fx_margin_pct": _round(row[f"{prefix} fx margin"], 6),
        "total_cost_pct": _round(row[f"{prefix} total cost %"], 6),
    }


def _provider(raw_row: pd.Series, corridor: Corridor, median_interbank: float) -> ProviderRecord:
    row = {str(k): _clean(v) for k, v in raw_row.items()}
    interbank = row["inter lcu bank fx"]
    low, high = _USD_PAYOUT_RATIO_LIMITS
    ratio = float(interbank) / median_interbank if isinstance(interbank, int | float) else 0.0
    local_payout = low <= ratio <= high
    try:
        return ProviderRecord.model_validate(
            {
                "rpw_id": row["id"],
                "firm": row["firm"],
                "firm_type": row["firm_type"],
                "payment_instrument": row["payment instrument"],
                "access_point": row["access point"],
                "pickup_method": row["pickup method"],
                "speed": row["speed actual"],
                "network_coverage": row["receiving network coverage"],
                "note": row["Standard Note"],
                "payout_currency": corridor.destination_currency if local_payout else "USD",
                "interbank_rate": _round(interbank, 10),
                "surveyed_on": _survey_date(row["date"]),
                "quote_200": _quote(row, "cc1", 200, corridor),
                "quote_500": _quote(row, "cc2", 500, corridor),
            }
        )
    except (ValidationError, ValueError, KeyError) as exc:
        raise ValueError(f"RPW id {row.get('id')} ({corridor.corridor_id}): {exc}") from exc


def build_corridor(df: pd.DataFrame, corridor: Corridor, period: str) -> CorridorDoc:
    """Build the document for one corridor from the surveys of a single quarter."""
    rows = df[df["corridor"] == corridor.rpw_code]
    if rows.empty:
        # Every configured corridor exists in RPW, so no rows at all means a wrong rpw_code.
        raise ValueError(f"{corridor.corridor_id}: no rows for code {corridor.rpw_code} in RPW")
    latest = rows[rows["period"] == period]
    if latest.empty:
        raise ValueError(f"{corridor.corridor_id}: no rows for period {period}")

    median_interbank = float(latest["inter lcu bank fx"].median())
    providers = sorted(
        (_provider(r, corridor, median_interbank) for _, r in latest.iterrows()),
        key=lambda p: (p.firm.lower(), p.payment_instrument, p.access_point, p.rpw_id),
    )
    return CorridorDoc(
        corridor_id=corridor.corridor_id,
        source_country=corridor.source_country,
        destination_country=corridor.destination_country,
        source_currency=corridor.source_currency,
        destination_currency=corridor.destination_currency,
        period=period,
        provider_count=len(providers),
        providers=providers,
    )


def build_output(
    df: pd.DataFrame, period: str | None = None, path: Path = RPW_SOURCE_FILE
) -> RpwCorridorFile:
    """Parse every configured corridor; `period` defaults to the newest survey quarter."""
    period = period or str(df["period"].max())
    return RpwCorridorFile(
        source=SourceInfo(
            name="World Bank Remittance Prices Worldwide",
            url=RPW_SOURCE_URL,
            attribution=RPW_ATTRIBUTION,
            file_name=path.name,
            sheet=RPW_SHEET,
        ),
        period=period,
        corridors=[build_corridor(df, c, period) for c in CORRIDORS],
    )


def write_output(output: RpwCorridorFile, path: Path = RPW_OUTPUT_FILE) -> None:
    """Write deterministic JSON (stable order, no timestamps) so re-runs give no git diff."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(output.model_dump_json(indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Parse World Bank RPW data for our corridors.")
    parser.add_argument("--source", type=Path, default=RPW_SOURCE_FILE, help="RPW .xlsx file")
    parser.add_argument("--output", type=Path, default=RPW_OUTPUT_FILE, help="JSON to write")
    parser.add_argument("--period", help="survey quarter such as 2025_1Q (default: newest)")
    parser.add_argument("--sample", type=int, default=15, help="records to spot-check")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    log.info("Reading %s (about 30 s)", args.source)
    df = read_rpw_sheet(args.source)
    output = build_output(df, args.period, args.source)

    for line in verify_against_source(df, output, args.sample):
        log.info("  verified: %s", line)
    write_output(output, args.output)

    for doc in output.corridors:
        log.info("%s  %3d records", doc.corridor_id, doc.provider_count)
    total = sum(d.provider_count for d in output.corridors)
    log.info("Period %s, %d records written to %s", output.period, total, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
