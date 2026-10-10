"""Moves a persona's leaving date to the day the run happens (D-203).

The fixture's dates are fixed (15 Nov 2026 to 1 Mar 2027), but the question bank only accepts a
date from 30 days ago to two years ahead, so on a later night the real coach would answer with an
`out_of_range` follow-up and the run would fail on the clock, not on a bug. Every date is moved
by the same number of days, so the gaps between the personas stay what the fixture says.
"""

from __future__ import annotations

from datetime import date

# The day the fixture was written (docs/runbooks/NF-FC-007-coach-personas.md).
ANCHOR = date(2026, 10, 9)

# The month names the scripts use: English (also in Tagalog sentences), Hindi and Indonesian.
MONTHS: dict[str, tuple[str, ...]] = {
    "en": (
        "January", "February", "March", "April", "May", "June", "July", "August",
        "September", "October", "November", "December",
    ),
    "hi": (
        "जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त",
        "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर",
    ),
    "id": (
        "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
        "September", "Oktober", "November", "Desember",
    ),
}  # fmt: skip


def shifted(original: date, today: date) -> date:
    """The date `original` would be if the fixture had been written today."""
    return today + (original - ANCHOR)


def spellings(day: date) -> list[str]:
    """Every way the scripts write a date, in a fixed order so two dates line up one to one."""
    spelled = [f"{MONTHS['en'][day.month - 1]} {day.day}, {day.year}"]
    for names in MONTHS.values():
        spelled.append(f"{day.day} {names[day.month - 1]} {day.year}")
    return spelled


def shift_text(text: str, original: date, today: date) -> str:
    """`text` with the date it states moved, written the same way.

    Raises:
        ValueError: The message does not state `original` in a spelling the scripts use.
    """
    moved = shifted(original, today)
    for old, new in zip(spellings(original), spellings(moved), strict=True):
        if old in text:
            return text.replace(old, new)
    raise ValueError(f"no spelling of {original.isoformat()} in {text!r}")
