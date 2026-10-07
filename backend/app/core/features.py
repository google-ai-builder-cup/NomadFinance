from __future__ import annotations

# The product area of a request, so logs, metrics and dashboards can be cut per feature
# (NF-F0-016). The names match `feature_of(operation)` for Gemini calls (`contract.detect` is
# `contract`), so a request and the Gemini calls it made share one `feature` value.
FEATURES = ("contract", "remittance", "radar", "fib", "coach", "scam", "platform")

# `/api/<version>/<first segment>/...`: the first segment names the feature.
_BY_SEGMENT = {
    "contracts": "contract",
    "remittance": "remittance",
    "radar": "radar",
    "fib": "fib",
    "coach": "coach",
    "scam": "scam",
}

# Cloud Scheduler jobs (`/api/v1/internal/<job>`) belong to the pillar whose data they keep fresh.
_BY_INTERNAL_JOB = {
    "refresh-rates": "remittance",
    "aggregate-radar": "radar",
    "recompute-fib-profiles": "fib",
    "aggregate-scam-stats": "scam",
}

PLATFORM = "platform"


def feature_for_path(path: str) -> str:
    """The feature a request path belongs to; `platform` for everything not owned by one.

    `/api/v1/contracts/extract` is `contract`, `/api/v2/scam/analyze` is `scam`,
    `/api/v1/internal/aggregate-radar` is `radar`, and `/health`, `/api/v2/flags`,
    `/api/v1/users/me` and unknown paths are `platform`.
    """
    parts = [part for part in path.split("/") if part]
    if len(parts) < 3 or parts[0] != "api":
        return PLATFORM
    segment = parts[2]
    if segment == "internal":
        return _BY_INTERNAL_JOB.get(parts[3], PLATFORM) if len(parts) > 3 else PLATFORM
    return _BY_SEGMENT.get(segment, PLATFORM)
