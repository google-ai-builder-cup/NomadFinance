from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from src.config import CORRIDORS, RPW_OUTPUT_FILE, Corridor
from src.loaders.world_bank import build_corridor, build_output, read_rpw_sheet
from src.validators.corridor import RpwCorridorFile, verify_against_source

SG_PH = next(c for c in CORRIDORS if c.corridor_id == "SG-PH")
AU_IN = next(c for c in CORRIDORS if c.corridor_id == "AU-IN")


def _row(**over: object) -> dict[str, object]:
    """One raw sheet row (SG-PH unless overridden), shaped like the real sheet's columns."""
    row: dict[str, object] = {
        "id": 1, "period": "2025_1Q", "corridor": "SGPPHL", "firm": "Acme Remit",
        "firm_type": "Money Transfer Operator", "payment instrument": "Cash",
        "access point": "Agent", "pickup method": "Cash", "speed actual": "Same day",
        "receiving network coverage": "High", "Standard Note": None,
        "date": datetime(2025, 2, 4), "inter lcu bank fx": 43.0, "cc1 lcu code": "SGD",
        "cc1 denomination amount": 200.0, "cc1 lcu amount": 260.0, "cc1 lcu fee": 5.0,
        "cc1 lcu fx rate": 42.5, "cc1 fx margin": 1.1, "cc1 total cost %": 3.0,
        "cc2 denomination amount": 500.0, "cc2 lcu amount": 645.0, "cc2 lcu fee": 5.0,
        "cc2 lcu fx rate": 42.5, "cc2 fx margin": 1.1, "cc2 total cost %": 1.9,
    }  # fmt: skip
    row.update(over)
    return row


def _frame(*rows: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


def _row_for(corridor: Corridor, **over: object) -> dict[str, object]:
    return _row(corridor=corridor.rpw_code, **{"cc1 lcu code": corridor.source_currency}, **over)


def _all_corridors(*extra: dict[str, object]) -> pd.DataFrame:
    """One row per configured corridor, plus any extra rows."""
    rows = [_row_for(c, id=100 + i) for i, c in enumerate(CORRIDORS)]
    return _frame(*rows, *extra)


def test_builds_ok_corridor_with_mapped_fields() -> None:
    doc = build_corridor(_frame(_row(id=1), _row(id=2, firm="Zed Bank")), SG_PH, "2025_1Q")

    assert doc.provider_count == 2
    first = doc.providers[0]
    assert (first.firm, first.payout_currency, first.surveyed_on.isoformat()) == (
        "Acme Remit",
        "PHP",
        "2025-02-04",
    )
    assert first.quote_200.total_cost_pct == 3.0
    assert first.quote_500.send_amount_lcu == 645.0


def test_corridor_missing_from_source_fails_loudly() -> None:
    with pytest.raises(ValueError, match="AU-IN: no rows for code AUSIND"):
        build_corridor(_frame(_row()), AU_IN, "2025_1Q")


def test_builds_au_in_from_its_own_rpw_code() -> None:
    doc = build_corridor(_frame(_row_for(AU_IN), _row()), AU_IN, "2025_1Q")

    assert (doc.corridor_id, doc.destination_currency, doc.provider_count) == ("AU-IN", "INR", 1)


def test_corridor_without_rows_in_period_fails_loudly() -> None:
    with pytest.raises(ValueError, match="no rows for period 2025_2Q"):
        build_corridor(_frame(_row()), SG_PH, "2025_2Q")


def test_usd_payout_is_tagged_when_interbank_rate_is_off_scale() -> None:
    frame = _frame(
        _row(id=1),
        _row(id=2, **{"inter lcu bank fx": 0.745, "cc1 lcu fx rate": 0.739}),
    )
    providers = {p.rpw_id: p for p in build_corridor(frame, SG_PH, "2025_1Q").providers}

    assert providers[1].payout_currency == "PHP"
    assert providers[2].payout_currency == "USD"


def test_negative_total_cost_is_kept() -> None:
    frame = _frame(_row(**{"cc2 total cost %": -1.15, "cc2 fx margin": -2.15}))

    assert build_corridor(frame, SG_PH, "2025_1Q").providers[0].quote_500.total_cost_pct == -1.15


def test_float_dust_from_excel_is_trimmed() -> None:
    frame = _frame(_row(**{"cc1 total cost %": 1.8499999999999999 + 1e-15}))

    assert build_corridor(frame, SG_PH, "2025_1Q").providers[0].quote_200.total_cost_pct == 1.85


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"cc1 total cost %": 250.0}, "RPW id 7"),
        ({"cc1 lcu fx rate": None}, "RPW id 7"),
        ({"firm": None}, "RPW id 7"),
        ({"cc1 lcu code": "USD"}, "currency USD != SGD"),
        ({"cc2 denomination amount": 300.0}, "not a USD 500 quote"),
    ],
)
def test_bad_rows_are_rejected_with_the_row_id(override: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        build_corridor(_frame(_row(id=7, **override)), SG_PH, "2025_1Q")


def test_old_style_text_dates_are_parsed() -> None:
    frame = _frame(_row(date="24/Jan/2025"))

    assert build_corridor(frame, SG_PH, "2025_1Q").providers[0].surveyed_on.isoformat() == (
        "2025-01-24"
    )


def test_output_is_deterministic_and_ordered_like_config() -> None:
    frame = _all_corridors(_row(id=1, firm="Zed Bank"))

    first = build_output(frame).model_dump_json()
    second = build_output(frame.iloc[::-1]).model_dump_json()

    assert first == second
    assert [c.corridor_id for c in build_output(frame).corridors] == [
        c.corridor_id for c in CORRIDORS
    ]


def test_missing_sheet_columns_are_reported(tmp_path: Path) -> None:
    path = tmp_path / "rpw.xlsx"
    pd.DataFrame({"id": [1]}).to_excel(path, sheet_name="Dataset (from Q2 2016)", index=False)

    with pytest.raises(ValueError, match="missing columns"):
        read_rpw_sheet(path)


def test_missing_source_file_points_to_download_steps(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="README"):
        read_rpw_sheet(tmp_path / "nope.xlsx")


def test_verification_passes_on_faithful_output_and_catches_tampering() -> None:
    frame = _all_corridors()
    output = build_output(frame)

    assert len(verify_against_source(frame, output, sample_size=5)) == 5

    tampered = frame.copy()
    tampered.loc[tampered["id"] == 100, "cc1 total cost %"] = 9.9
    with pytest.raises(ValueError, match="cost_200"):
        verify_against_source(tampered, output, sample_size=len(CORRIDORS))

    extra_raw_row = _all_corridors(_row(id=999))
    with pytest.raises(ValueError, match="SG-PH: 1 parsed vs 2 raw"):
        verify_against_source(extra_raw_row, output, sample_size=5)


def test_committed_output_file_is_valid_and_covers_all_corridors() -> None:
    output = RpwCorridorFile.model_validate_json(RPW_OUTPUT_FILE.read_text(encoding="utf-8"))

    assert [c.corridor_id for c in output.corridors] == [c.corridor_id for c in CORRIDORS]
    assert "AU-IN" in {c.corridor_id for c in output.corridors}
    assert output.source.attribution.startswith("The World Bank, Remittance Prices Worldwide")
