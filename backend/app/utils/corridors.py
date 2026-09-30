from __future__ import annotations

# Every (host_country, home_country) pair that is one of the 6 surveyed corridors
# (schemas/remittance_compare.py's CorridorId), for the alert cron's default-subscribed
# cohort (users.md: "missing means all on for the user's own corridor", NF-P3-004). Two of
# onboarding's five home-country options (NP, BD) aren't in any corridor, so a worker from
# either has no default.
CORRIDOR_HOST_HOME: dict[str, tuple[str, str]] = {
    "SG-PH": ("SG", "PH"),
    "SG-IN": ("SG", "IN"),
    "AU-IN": ("AU", "IN"),
    "MY-ID": ("MY", "ID"),
    "JP-PH": ("JP", "PH"),
    "AU-PH": ("AU", "PH"),
}


def host_and_home(corridor_id: str) -> tuple[str, str]:
    """The (host_country, home_country) pair a corridor id is made of.

    Raises:
        KeyError: `corridor_id` is not one of the 6 surveyed corridors.
    """
    return CORRIDOR_HOST_HOME[corridor_id]
