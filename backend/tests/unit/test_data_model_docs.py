"""The Firestore docs against the code, the rules and the index file (NF-HR-013).

`docs/data-model/firestore-schema.md` is the one page that lists every collection, so a collection
the code writes, the rules name or an index covers must be on it. These tests fail when a new
collection is added and the page is not.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCHEMA_PAGE = REPO / "docs" / "data-model" / "firestore-schema.md"
RULES = REPO / "frontend" / "firestore.rules"
INDEXES = REPO / "frontend" / "firestore.indexes.json"
CODE_ROOTS = (REPO / "backend" / "app", REPO / "data-scripts" / "src")

_NAME = r"([a-z][a-z0-9_]*)"
# `.collection("x")`, `.collection_group("x")`, `collection_name = "x"`, `FOO_COLLECTION = "x"`.
_CODE_PATTERNS = (
    re.compile(rf'\.collection(?:_group)?\(\s*"{_NAME}"'),
    re.compile(rf'collection_name\s*=\s*"{_NAME}"'),
    re.compile(rf'[A-Z_]*COLLECTION\s*=\s*"{_NAME}"'),
)
_STORAGE_PREFIX = re.compile(r'f"([a-z][a-z-]*)/\{')


def _section(text: str, heading: str) -> str:
    """The text under `## heading` up to the next `## `."""
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert match is not None, f"no '## {heading}' section in {SCHEMA_PAGE.name}"
    return match.group(1)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _mapped_collections() -> set[str]:
    """Every collection name in the paths of the page's collection map (first column)."""
    names: set[str] = set()
    for line in _section(_read(SCHEMA_PAGE), "Collection map").splitlines():
        if not line.startswith("| `"):
            continue
        for path in re.findall(r"`([^`]+)`", line.split("|")[1]):
            for segment in path.split("/"):
                if segment and not segment.startswith(("{", ".")):
                    names.add(segment)
    return names


def _code_collections() -> dict[str, str]:
    """Collection names found in the backend and the data scripts, with a file that uses each."""
    found: dict[str, str] = {}
    for root in CODE_ROOTS:
        for path in root.rglob("*.py"):
            text = _read(path)
            for pattern in _CODE_PATTERNS:
                for name in pattern.findall(text):
                    found.setdefault(name, str(path.relative_to(REPO)))
    return found


def test_every_collection_the_code_writes_is_in_the_collection_map() -> None:
    mapped = _mapped_collections()
    missing = {name: where for name, where in _code_collections().items() if name not in mapped}
    assert missing == {}, f"collections used in code but absent from the map: {missing}"


def test_every_collection_the_rules_name_is_in_the_collection_map() -> None:
    rules = _read(RULES)
    named: set[str] = set()
    for block in re.findall(r"collection in \[(.*?)\]", rules, re.S):
        named.update(re.findall(r"'([a-z_]+)'", block))
    # `match /users/{uid}/contracts/{id}/reports/{language}` style segments.
    for path in re.findall(r"match (/[^\s{]*(?:\{[^}]+\}/[^\s{]*)*)", rules):
        named.update(s for s in path.split("/") if s and not s.startswith("{"))
    named -= {"databases", "documents"}
    missing = named - _mapped_collections()
    assert missing == set(), f"collections the rules name but the map lacks: {sorted(missing)}"


def test_every_top_level_collection_has_a_row_in_the_access_matrix() -> None:
    page = _read(SCHEMA_PAGE)
    matrix = _section(page, "Access matrix")
    top_level = set()
    for line in _section(page, "Collection map").splitlines():
        if line.startswith("| `"):
            top_level.update(re.findall(r"`([a-z_]+)(?:/|`)", line.split("|")[1])[:1])
    missing = {name for name in top_level if not re.search(rf"\b{name}\b", matrix)}
    assert missing == set(), f"collections with no mention in the access matrix: {sorted(missing)}"


def test_every_index_in_the_index_file_is_described_on_the_page() -> None:
    page = _read(SCHEMA_PAGE)
    section = page[page.index("## Required indexes") : page.index("## Time to live")]
    spec = json.loads(_read(INDEXES))
    wanted: list[tuple[str, list[str]]] = []
    for index in spec["indexes"]:
        wanted.append((index["collectionGroup"], [f["fieldPath"] for f in index["fields"]]))
    for override in spec["fieldOverrides"]:
        wanted.append((override["collectionGroup"], [override["fieldPath"]]))
    # A table row, so the collection and its fields are named together and not just somewhere.
    rows = [line for line in section.splitlines() if line.startswith("|")]
    missing = [
        (group, fields)
        for group, fields in wanted
        if not any(f"`{group}`" in row and all(f"`{f}`" in row for f in fields) for row in rows)
    ]
    assert (
        missing == []
    ), f"indexes in firestore.indexes.json with no table row on the page: {missing}"


def test_every_storage_folder_the_backend_writes_is_in_the_storage_table() -> None:
    table = _section(
        _read(SCHEMA_PAGE), "Cloud Storage paths (not Firestore, referenced by it) [P]"
    )
    written: set[str] = set()
    for path in (REPO / "backend" / "app" / "integrations").rglob("*.py"):
        written.update(_STORAGE_PREFIX.findall(_read(path)))
    assert written, "the pattern found no Storage folder, so this test checks nothing"
    missing = {folder for folder in written if f"`{folder}/" not in table}
    assert missing == set(), f"Storage folders written but not listed: {sorted(missing)}"
