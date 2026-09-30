from __future__ import annotations

from slugify import slugify as _slugify

__all__ = ["slugify"]


def slugify(name: str) -> str:
    """The id of a `radar_entities` document, from a business name (radar.md).

    The one place in the backend that turns a name into a slug, so every writer (the
    contract signal, NF-P2-021; a worker's own report, NF-P3-001) produces the same slug for
    the same name — the slug is the join key the cross-pillar badges match on.
    """
    return _slugify(name)
