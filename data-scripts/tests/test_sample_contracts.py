from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from src.config import SEED_CONTRACTS_DIR
from src.loaders import sample_contract_pdf, sample_contracts
from src.loaders.sample_contracts import PREFIX, object_metadata, upload_all
from src.validators.labor_law import COUNTRIES
from src.validators.sample_contract import Manifest, load, main


class _Blob:
    def __init__(self, store: dict[str, _Blob], name: str) -> None:
        self._store = store
        self.name = name
        self.data = b""
        self.metadata: dict[str, str] | None = None
        self.content_type: str | None = None

    @property
    def md5_hash(self) -> str:
        return sample_contracts._md5(self.data)

    def upload_from_string(self, data: bytes, content_type: str) -> None:
        self.data, self.content_type = data, content_type
        self._store[self.name] = self

    def delete(self) -> None:
        self._store.pop(self.name, None)


class _Bucket:
    def __init__(self) -> None:
        self.store: dict[str, _Blob] = {}

    def get_blob(self, name: str) -> _Blob | None:
        return self.store.get(name)

    def blob(self, name: str) -> _Blob:
        return _Blob(self.store, name)

    def list_blobs(self, prefix: str) -> list[_Blob]:
        return [b for n, b in self.store.items() if n.startswith(prefix)]


def _raw() -> dict[str, Any]:
    return json.loads((SEED_CONTRACTS_DIR / "manifest.json").read_text(encoding="utf-8"))


def test_committed_set_passes_every_check() -> None:
    manifest = load()
    assert sorted(c.country for c in manifest.contracts) == sorted(COUNTRIES)
    assert main([]) == 0


def test_every_pdf_matches_its_text() -> None:
    assert (
        sample_contract_pdf.build(SEED_CONTRACTS_DIR / "source", SEED_CONTRACTS_DIR, check=True)
        == []
    )


@pytest.mark.parametrize("contract", load().contracts, ids=lambda c: c.id)
def test_pdf_carries_the_clauses_in_plain_text(contract: Any) -> None:
    # Streams are uncompressed on purpose: the text is readable without a PDF library.
    data = (SEED_CONTRACTS_DIR / contract.file).read_bytes()
    assert data.count(b"/Type /Page ") >= 2
    assert b"Terms of employment" in data
    for issue in contract.planted_issues:
        assert f"({issue.clause}. ".encode() in data


def test_text_outside_windows_1252_is_rejected() -> None:
    with pytest.raises(UnicodeEncodeError):
        sample_contract_pdf.render_pdf("# Title\n\nPay: ₹500", "Title")


def test_render_is_deterministic() -> None:
    text = "# Title\n\n1. A clause that is long enough to need a second line " * 3
    assert sample_contract_pdf.render_pdf(text, "T") == sample_contract_pdf.render_pdf(text, "T")


def test_overall_label_must_fit_the_danger_count() -> None:
    raw = _raw()
    raw["contracts"][0]["overall"] = "risky"  # SG has no danger issue
    with pytest.raises(ValidationError, match="do not fit"):
        Manifest.model_validate(raw)


def test_one_contract_per_country() -> None:
    raw = _raw()
    raw["contracts"][1]["country"] = "SG"
    with pytest.raises(ValidationError):
        Manifest.model_validate(raw)


def test_unknown_category_is_rejected() -> None:
    raw = _raw()
    raw["contracts"][0]["planted_issues"][0]["category"] = "free_snacks"
    with pytest.raises(ValidationError):
        Manifest.model_validate(raw)


def test_missing_clause_is_reported(tmp_path: Path) -> None:
    shutil.copytree(SEED_CONTRACTS_DIR, tmp_path / "c")
    raw = _raw()
    raw["contracts"][0]["planted_issues"][0]["clause"] = "99"
    (tmp_path / "c" / "manifest.json").write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="clause 99"):
        load(tmp_path / "c")


def test_truncated_pdf_is_reported(tmp_path: Path) -> None:
    shutil.copytree(SEED_CONTRACTS_DIR, tmp_path / "c")
    pdf = tmp_path / "c" / "kr_manufacturing_worker.pdf"
    pdf.write_bytes(pdf.read_bytes()[:200])
    with pytest.raises(ValueError, match="not a complete PDF"):
        load(tmp_path / "c")


def test_unlisted_pdf_is_reported(tmp_path: Path) -> None:
    shutil.copytree(SEED_CONTRACTS_DIR, tmp_path / "c")
    (tmp_path / "c" / "xx_extra.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
    with pytest.raises(ValueError, match="not in the manifest"):
        load(tmp_path / "c")


def test_radar_slug_must_exist_in_the_radar_seed(tmp_path: Path) -> None:
    shutil.copytree(SEED_CONTRACTS_DIR, tmp_path / "c")
    raw = _raw()
    raw["contracts"][1]["radar_entity_slug"] = "no-such-business"
    (tmp_path / "c" / "manifest.json").write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="not in the radar seed"):
        load(tmp_path / "c")


def test_upload_writes_all_six_with_metadata() -> None:
    bucket = _Bucket()
    manifest = load()
    assert upload_all(bucket, manifest, SEED_CONTRACTS_DIR) == (6, 0, 0)
    assert sorted(bucket.store) == sorted(PREFIX + c.file for c in manifest.contracts)
    kr = bucket.store[PREFIX + "kr_manufacturing_worker.pdf"]
    assert kr.content_type == "application/pdf"
    assert kr.metadata == object_metadata(manifest.contracts[1])
    assert kr.metadata["radar_entity_slug"] == "han-river-metals-co"
    assert kr.metadata["synthetic"] == "true"


def test_second_run_changes_nothing() -> None:
    bucket = _Bucket()
    manifest = load()
    upload_all(bucket, manifest, SEED_CONTRACTS_DIR)
    assert upload_all(bucket, manifest, SEED_CONTRACTS_DIR) == (0, 6, 0)


def test_changed_object_is_replaced_and_stale_one_removed() -> None:
    bucket = _Bucket()
    manifest = load()
    upload_all(bucket, manifest, SEED_CONTRACTS_DIR)
    bucket.store[PREFIX + "sg_domestic_worker.pdf"].data = b"old"
    bucket.blob(PREFIX + "old_name.pdf").upload_from_string(b"x", "application/pdf")
    other = bucket.blob("contracts/uid_x/c1/keep.pdf")  # outside our folder: never touched
    other.upload_from_string(b"x", "application/pdf")
    assert upload_all(bucket, manifest, SEED_CONTRACTS_DIR) == (1, 5, 1)
    assert PREFIX + "old_name.pdf" not in bucket.store
    assert "contracts/uid_x/c1/keep.pdf" in bucket.store


def test_dry_run_needs_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_: Any, **__: Any) -> None:
        raise AssertionError("dry run must not open a bucket")

    monkeypatch.setattr(sample_contracts.storage, "bucket", fail)
    assert sample_contracts.main(["--dry-run", "--bucket", "demo-bucket"]) == 0
