"""Nearest-neighbour sanity check for the scam pattern library (NF-SA-006).

Run from data-scripts/:  python -m src.loaders.scam_patterns_check [--firestore]

Takes the scam messages of the golden eval sets (evals/scam_golden_*.jsonl), which no template was
written from, redacts and embeds each the way the analyzer will, and asks for its 3 nearest
templates. A message is a hit when at least one of the 3 has the same scam type. The tracker's bar
is 10 held-out scams that each hit; the 10 are a fixed pick (the same ones every run) covering all
8 types and all 6 languages, and every other golden scam is reported too, so a weak type shows up.

  default      embeds the library in memory and ranks by cosine similarity. Needs GEMINI_API_KEY.
  --firestore  asks the live `scam_patterns` collection (Firestore vector search, flat index on
               `embedding`, 768 dimensions), so it also proves the index and the loaded vectors.
               Needs the index deployed (D-114) and credentials, and the loader already run.
"""

from __future__ import annotations

import argparse
import importlib.util
import logging
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from src.config import EVALS_DIR, SCAM_PATTERNS_DIR
from src.embedding import Embedder
from src.validators.scam_golden import GoldenRow, load_rows
from src.validators.scam_patterns import LANGUAGES, check_library, load_all

log = logging.getLogger(__name__)

TOP_K = 3
HELD_OUT = 10
_REDACT_FILE = Path(__file__).resolve().parents[3] / "backend" / "app" / "core" / "redact.py"

Neighbours = list[tuple[str, float]]  # (pattern id, cosine similarity), closest first


@dataclass(frozen=True)
class Outcome:
    """One golden scam and what the search found for it."""

    row: GoldenRow
    neighbours: Neighbours

    @property
    def hit(self) -> bool:
        return any(type_of(pattern_id) == self.row.scam_type for pattern_id, _ in self.neighbours)


def type_of(pattern_id: str) -> str:
    """`illegal_recruitment_fee-en-004` -> `illegal_recruitment_fee`."""
    return pattern_id.rsplit("-", 2)[0]


def load_redactor() -> Callable[[str], str]:
    """The backend's redactor, loaded by path: the analyzer embeds redacted text, not raw text."""
    if not _REDACT_FILE.exists():
        log.warning(
            "backend redactor not found at %s: queries are embedded unredacted", _REDACT_FILE
        )
        return lambda text: text
    spec = importlib.util.spec_from_file_location("nf_backend_redact", _REDACT_FILE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {_REDACT_FILE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # the module's dataclasses look themselves up here
    spec.loader.exec_module(module)
    redact_text: Callable[[str], str] = module.redact_text
    return redact_text


def golden_scams(directory: Path = EVALS_DIR) -> list[GoldenRow]:
    """Every scam row of every golden set, in id order."""
    rows: list[GoldenRow] = []
    for path in sorted(directory.glob("scam_golden_*.jsonl")):
        loaded, problems = load_rows(path)
        if problems:
            raise ValueError(f"{path.name}: {problems[0]}")
        rows.extend(r for r in loaded if r.is_scam)
    return sorted(rows, key=lambda r: r.id)


def pick_held_out(rows: Sequence[GoldenRow], count: int = HELD_OUT) -> list[GoldenRow]:
    """A fixed pick, one scam type after another and the six languages in turn, so 10 cover every
    type and language. The same rows every run, so a result can be compared between runs."""
    types = sorted({r.scam_type for r in rows if r.scam_type})
    chosen: list[GoldenRow] = []
    for i in range(count):
        scam_type, language = types[i % len(types)], LANGUAGES[i % len(LANGUAGES)]
        pool = [r for r in rows if r.scam_type == scam_type and r not in chosen]
        pool.sort(key=lambda r: (r.language != language, r.id))
        if not pool:
            raise ValueError(f"no scam row left for {scam_type}")
        chosen.append(pool[0])
    return chosen


def cosine_neighbours(
    query: list[float], library: list[tuple[str, list[float]]], k: int = TOP_K
) -> Neighbours:
    """Vectors are unit length, so the dot product is the cosine similarity."""
    scored = [(pid, sum(a * b for a, b in zip(query, vec, strict=True))) for pid, vec in library]
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:k]


def evaluate(
    rows: Sequence[GoldenRow],
    embedder: Embedder,
    search: Callable[[list[float]], Neighbours],
    redact: Callable[[str], str],
) -> list[Outcome]:
    vectors = embedder.embed([redact(r.text) for r in rows])
    return [Outcome(row, search(vec)) for row, vec in zip(rows, vectors, strict=True)]


def report(outcomes: list[Outcome], gate: list[GoldenRow]) -> bool:
    """Print the result; True when every held-out scam hit."""
    gate_ids = {r.id for r in gate}
    gate_outcomes = [o for o in outcomes if o.row.id in gate_ids]
    print(f"Held-out gate: {sum(o.hit for o in gate_outcomes)} of {len(gate_outcomes)} hit")
    for outcome in gate_outcomes:
        print(_line(outcome))
    total_hits = sum(o.hit for o in outcomes)
    print(f"\nAll golden scams: {total_hits} of {len(outcomes)} hit in the top {TOP_K}")
    for label, key in (("type", lambda o: o.row.scam_type), ("language", lambda o: o.row.language)):
        per: dict[str | None, list[bool]] = defaultdict(list)
        for outcome in outcomes:
            per[key(outcome)].append(outcome.hit)
        print(
            f"  by {label}: " + ", ".join(f"{k} {sum(v)}/{len(v)}" for k, v in sorted(per.items()))
        )
    misses = [o for o in outcomes if not o.hit and o.row.id not in gate_ids]
    if misses:
        print(f"\nMisses outside the gate ({len(misses)}):")
        for outcome in misses:
            print(_line(outcome))
    return all(o.hit for o in gate_outcomes)


def _line(outcome: Outcome) -> str:
    near = ", ".join(f"{pid} {score:.3f}" for pid, score in outcome.neighbours)
    mark = "HIT " if outcome.hit else "MISS"
    return f"  {mark} {outcome.row.id} ({outcome.row.scam_type}): {near}"


def _firestore_search(collection: str) -> Callable[[list[float]], Neighbours]:
    from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
    from google.cloud.firestore_v1.vector import Vector

    from src.firestore_client import get_firestore_client

    coll = get_firestore_client().collection(collection)

    def search(vector: list[float]) -> Neighbours:
        query = coll.find_nearest(
            vector_field="embedding",
            query_vector=Vector(vector),
            distance_measure=DistanceMeasure.COSINE,
            limit=TOP_K,
            distance_result_field="distance",
        )
        # cosine distance is 1 - similarity
        return [(doc.id, 1.0 - float(doc.get("distance"))) for doc in query.stream()]

    return search


def main(argv: list[str] | None = None) -> int:
    from src.embedding import GeminiEmbedder
    from src.loaders.scam_patterns import SCAM_PATTERNS_COLLECTION

    parser = argparse.ArgumentParser(description="Nearest-neighbour check of the scam patterns.")
    parser.add_argument("--firestore", action="store_true", help="search the live collection")
    parser.add_argument("--collection", default=SCAM_PATTERNS_COLLECTION)
    parser.add_argument("--held-out", type=int, default=HELD_OUT)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    patterns, problems = load_all(SCAM_PATTERNS_DIR)
    problems = problems or check_library(patterns)
    if problems:
        log.error("the pattern library is not valid: %s", problems[0])
        return 1

    embedder = GeminiEmbedder()
    if args.firestore:
        search = _firestore_search(args.collection)
    else:
        vectors = embedder.embed([p.text for p in patterns])
        library = [(p.id, v) for p, v in zip(patterns, vectors, strict=True)]

        def search(vector: list[float]) -> Neighbours:
            return cosine_neighbours(vector, library)

    scams = golden_scams()
    outcomes = evaluate(scams, embedder, search, load_redactor())
    ok = report(outcomes, pick_held_out(scams, args.held_out))
    counts = Counter(o.hit for o in outcomes)
    log.info(
        "source: %s, %d queries, %d hit, %d miss",
        "firestore" if args.firestore else "local",
        len(outcomes),
        counts[True],
        counts[False],
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
