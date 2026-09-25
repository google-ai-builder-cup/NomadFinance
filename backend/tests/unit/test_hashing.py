from __future__ import annotations

from app.utils.hashing import hash_user_id


def test_hash_is_short_stable_and_hides_the_uid() -> None:
    uid = "kJ3xQ9pLmN2vB7cD5eF8gH1aZ4wR"

    first = hash_user_id(uid)

    assert first == hash_user_id(uid)
    assert len(first) == 16
    assert uid not in first
    assert first != hash_user_id(uid + "x")
