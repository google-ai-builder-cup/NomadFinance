"""Feature flags for the Future Scope modules (NF-F0-005).

`config/feature_flags` holds one flag per module. A flag is on for a user when its `enabled`
is true or the user's uid is in its `allow_uids` (docs/data-model/collections/config.md).
The document is read at most once a minute per instance, so a change made in the Firebase
console takes effect within that minute and needs no deploy.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, get_args

from fastapi.concurrency import run_in_threadpool
from google.api_core.exceptions import GoogleAPIError
from google.auth.exceptions import GoogleAuthError

from app.repositories.config_repo import ConfigRepository

logger = logging.getLogger(__name__)

FlagName = Literal["coach", "scam"]
FLAG_NAMES: tuple[FlagName, ...] = get_args(FlagName)

CACHE_SECONDS = 60.0
# The documented size of an allow-list. Entries past it are ignored rather than treated as a
# malformed flag, so a long list never switches a module off for everyone.
MAX_ALLOW_UIDS = 200


@dataclass(frozen=True)
class _Flag:
    enabled: bool
    allow_uids: frozenset[str]


def _parse_flag(name: str, raw: Any) -> _Flag:
    # `is True`, not truthiness: "false" or 1 in a hand-edited document must not turn a
    # module on.
    enabled = isinstance(raw, dict) and raw.get("enabled") is True
    uids = raw.get("allow_uids") if isinstance(raw, dict) else None
    if not isinstance(uids, list):
        return _Flag(enabled, frozenset())
    if len(uids) > MAX_ALLOW_UIDS:
        logger.warning("feature_flag_allow_list_truncated flag=%s size=%d", name, len(uids))
    return _Flag(
        enabled, frozenset(uid for uid in uids[:MAX_ALLOW_UIDS] if isinstance(uid, str) and uid)
    )


def _parse(document: dict[str, Any] | None) -> dict[FlagName, _Flag]:
    """A missing document, a missing flag or a malformed value all read as off."""
    flags = document.get("flags") if document else None
    if not isinstance(flags, dict):
        return {}
    return {name: _parse_flag(name, flags[name]) for name in FLAG_NAMES if name in flags}


class FeatureFlagService:
    """Answers "is this module on for this user", from a one-minute in-memory copy."""

    def __init__(
        self,
        repo: ConfigRepository,
        *,
        clock: Callable[[], float] = time.monotonic,
        cache_seconds: float = CACHE_SECONDS,
    ) -> None:
        self._repo = repo
        self._clock = clock
        self._cache_seconds = cache_seconds
        self._flags: dict[FlagName, _Flag] = {}
        self._loaded_at: float | None = None

    async def _snapshot(self) -> dict[FlagName, _Flag]:
        now = self._clock()
        if self._loaded_at is not None and now - self._loaded_at < self._cache_seconds:
            return self._flags
        try:
            document = await run_in_threadpool(self._repo.get_feature_flags)
        except (GoogleAPIError, GoogleAuthError) as exc:
            # Keep the last good copy (everything off if there never was one) and leave
            # `_loaded_at` alone, so the next request tries Firestore again. An outage must
            # not switch a module on, and must not hide one that was on.
            logger.warning("feature_flags_read_failed error=%s", type(exc).__name__)
            return self._flags
        self._flags = _parse(document)
        self._loaded_at = now
        return self._flags

    async def is_enabled(self, flag: FlagName, uid: str) -> bool:
        entry = (await self._snapshot()).get(flag)
        return entry is not None and (entry.enabled or uid in entry.allow_uids)

    async def enabled_for(self, uid: str) -> dict[FlagName, bool]:
        snapshot = await self._snapshot()
        return {
            name: (entry := snapshot.get(name)) is not None
            and (entry.enabled or uid in entry.allow_uids)
            for name in FLAG_NAMES
        }
