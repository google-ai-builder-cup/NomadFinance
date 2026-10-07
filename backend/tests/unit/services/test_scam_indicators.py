from __future__ import annotations

import hashlib
import json
import socket
from typing import Any

import pytest

from app.core.redact import redact_text
from app.services.scam import indicator_checks as checks
from app.services.scam.indicators import (
    MAX_INDICATORS,
    Signals,
    extract_signals,
    make_indicator,
)

Expected = list[tuple[str, str, tuple[str, ...], str | None]]  # kind, value, flags, imitates

# (id, message as the worker pasted it, corridor, what must be found, in order of appearance)
FIXTURES: list[tuple[str, str, str | None, Expected]] = [
    # ---- links
    ("plain-link", "Apply at https://careers-agency.example/jobs today", "SG-IN",
     [("url", "careers-agency.example", (), None)]),
    ("www-and-case", "Visit WWW.Example-Hire.COM/apply?x=1 now", None,
     [("url", "example-hire.com", (), None)]),
    ("path-and-token-dropped", "Pay at https://pay.example/x/y?token=SECRET123&id=77#frag", None,
     [("url", "pay.example", (), None)]),
    ("port-and-userinfo", "Open http://user:pw@evil.example:8080/x", None,
     [("url", "evil.example", (), None)]),
    ("ip-address-host", "Log in at http://192.168.1.1/login", None,
     [("url", "192.168.1.1", (), None)]),
    ("defanged", "Click hxxps://bit[.]ly/abc123 to claim", None,
     [("url", "bit.ly", ("shortener",), None)]),
    ("shortener-bare", "Details: bit.ly/3xYz now", None, [("url", "bit.ly", ("shortener",), None)]),
    ("shortener-tinyurl", "Go to https://tinyurl.com/job-sg", None,
     [("url", "tinyurl.com", ("shortener",), None)]),
    ("shortener-t-co", "See https://t.co/AbC123", None, [("url", "t.co", ("shortener",), None)]),
    ("punycode-label", "Verify at https://xn--mm-bla.example/login", None,
     [("url", "xn--mm-bla.example", ("punycode",), None)]),
    ("punycode-from-unicode", "Verify at https://пример.example/login", None,
     [("url", "xn--e1afmkfd.example", ("punycode",), None)]),
    # ---- links that copy a real organisation
    ("lookalike-prefix", "Check your pass: https://mom.gov.sg.verify-now.com/pass", "SG-PH",
     [("url", "mom.gov.sg.verify-now.com", ("lookalike",), "mom.gov.sg")]),
    ("lookalike-dashes", "Login https://dbs-com-sg-login.net", "SG-IN",
     [("url", "dbs-com-sg-login.net", ("lookalike",), "dbs.com.sg")]),
    ("lookalike-brand", "Your Singpass is locked: singpass-verify.com/unlock", "SG-PH",
     [("url", "singpass-verify.com", ("lookalike",), "singpass.gov.sg")]),
    ("lookalike-rn-for-m", "Maybank login: https://rnaybank2u.com.my", "MY-ID",
     [("url", "rnaybank2u.com.my", ("lookalike",), "maybank2u.com.my")]),
    ("lookalike-8-for-b", "Open https://d8s.com.sg/secure", "SG-IN",
     [("url", "d8s.com.sg", ("lookalike",), "dbs.com.sg")]),
    ("lookalike-remit", "Transfer on wise.com.login-secure.net", "SG-PH",
     [("url", "wise.com.login-secure.net", ("lookalike",), "wise.com")]),
    ("lookalike-gcash-brand", "Claim at https://gcash-promo.xyz/win", "JP-PH",
     [("url", "gcash-promo.xyz", ("lookalike",), "gcash.com")]),
    ("lookalike-shortener-and-copy", "https://bit.ly/x and https://ica-gov-sg.net/pass", "SG-IN",
     [("url", "bit.ly", ("shortener",), None),
      ("url", "ica-gov-sg.net", ("lookalike",), "ica.gov.sg")]),
    # ---- real sites are not flagged
    ("real-site", "Read https://www.mom.gov.sg/passes/work-permit", "SG-PH",
     [("url", "mom.gov.sg", (), None)]),
    ("real-subdomain", "Log in: https://onlinebanking.dbs.com.sg/login", "SG-IN",
     [("url", "onlinebanking.dbs.com.sg", (), None)]),
    ("other-government-site", "See https://www.moe.gov.sg/news", "SG-IN",
     [("url", "moe.gov.sg", (), None)]),
    ("short-name-by-coincidence", "Shop at https://i-wise.com.au/sale", "AU-IN",
     [("url", "i-wise.com.au", (), None)]),
    # ---- phone numbers
    ("phone-host-country", "Call +65 9123 4567 for the job", "SG-IN",
     [("phone", "6591234567", (), None)]),
    ("phone-home-country", "Call +91 98765 43210 for the job", "SG-IN",
     [("phone", "919876543210", (), None)]),
    ("phone-unexpected-country", "Call +44 7911 123456 for the job", "SG-IN",
     [("phone", "447911123456", ("unexpected_country",), None)]),
    ("phone-unexpected-no-route", "Call +234 802 123 4567 for the job", None,
     [("phone", "2348021234567", ("unexpected_country",), None)]),
    ("phone-known-country-no-route", "Call +63 917 123 4567 for the job", None,
     [("phone", "639171234567", (), None)]),
    ("phone-00-prefix", "Call 0044 7911 123456 now", "SG-PH",
     [("phone", "447911123456", ("unexpected_country",), None)]),
    ("phone-local-no-country", "WhatsApp 9123 4567 now", "SG-IN",
     [("phone", "91234567", (), None)]),
    ("phone-premium-singapore", "Call 1900 123 4567 to confirm", "SG-IN",
     [("phone", "19001234567", ("premium_rate",), None)]),
    ("phone-premium-australia", "Call 1902 345 678 to confirm", "AU-IN",
     [("phone", "1902345678", ("premium_rate",), None)]),
    ("phone-premium-international", "Call +979123456789 to confirm", "SG-IN",
     [("phone", "979123456789", ("premium_rate", "unexpected_country"), None)]),
    ("phone-devanagari-digits", "कॉल +९१ ९८७६५ ४३२१० अभी", "SG-IN",
     [("phone", "919876543210", (), None)]),
    ("phone-same-number-two-ways", "Call +65 9123 4567 or +65-9123-4567", "SG-IN",
     [("phone", "6591234567", (), None)]),
    ("phone-from-whatsapp-link", "Chat: https://wa.me/6591234567", "SG-IN",
     [("phone", "6591234567", (), None)]),
    # ---- emails and handles
    ("email-lowercased", "Write to HR@Brightpath.Example today", None,
     [("email", "hr@brightpath.example", (), None)]),
    ("email-on-a-copy", "Mail hr@mom-gov-sg.com", "SG-PH",
     [("email", "hr@mom-gov-sg.com", ("lookalike",), "mom.gov.sg")]),
    ("handle", "Message @Agent_SG on Telegram", None, [("handle", "agent_sg", (), None)]),
    ("handle-from-telegram-link", "Join t.me/VisaHelpDesk now", None,
     [("handle", "visahelpdesk", (), None)]),
    # ---- not indicators, and repeats
    ("account-and-id-are-not-indicators",
     "Pay account 123456789012. NRIC S1234567D. Date 12/10/2026", None, []),
    ("nothing-to-find", "Your parcel arrives tomorrow between 9 and 12.", None, []),
    ("same-link-twice", "Open https://x-job.example/a then https://x-job.example/b", None,
     [("url", "x-job.example", (), None)]),
    ("order-of-appearance",
     "Call +65 9123 4567 or open https://a-job.example or mail a@b-job.example", "SG-IN",
     [("phone", "6591234567", (), None), ("url", "a-job.example", (), None),
      ("email", "a@b-job.example", (), None)]),
]  # fmt: skip


def _found(text: str, corridor: str | None) -> Expected:
    signals = extract_signals(text, redact_text(text), corridor_id=corridor)  # type: ignore[arg-type]
    return [(i.kind, i.value, tuple(i.flags), i.imitates) for i in signals.indicators]


def test_there_are_at_least_thirty_fixtures_with_every_flag_and_kind() -> None:
    assert len(FIXTURES) >= 30
    flags = {f for _, _, _, expected in FIXTURES for _, _, fl, _ in expected for f in fl}
    kinds = {k for _, _, _, expected in FIXTURES for k, _, _, _ in expected}
    assert flags == {"shortener", "punycode", "lookalike", "premium_rate", "unexpected_country"}
    assert kinds == {"url", "phone", "email", "handle"}


@pytest.mark.parametrize(
    ("text", "corridor", "expected"),
    [pytest.param(t, c, e, id=name) for name, t, c, e in FIXTURES],
)
def test_each_fixture_gives_exactly_these_indicators(
    text: str, corridor: str | None, expected: Expected
) -> None:
    assert _found(text, corridor) == expected


# ---------------------------------------------------------------- nothing is ever fetched


class _Forbidden:
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("an extracted address was used for a network call")


def test_no_fixture_makes_a_connection_or_a_dns_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """A link in a scam message is data: never fetched, resolved, opened or previewed."""
    import http.client
    import urllib.request

    forbidden = _Forbidden()
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket, "gethostbyname", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(http.client.HTTPConnection, "request", forbidden)
    try:
        import httpx

        monkeypatch.setattr(httpx.Client, "send", forbidden)
        monkeypatch.setattr(httpx.AsyncClient, "send", forbidden)
    except ImportError:  # pragma: no cover
        pass

    for _, text, corridor, expected in FIXTURES:
        assert _found(text, corridor) == expected  # still finds everything, with no network


def test_the_extractor_imports_no_http_client() -> None:
    import app.services.scam.indicator_checks as module_a
    import app.services.scam.indicators as module_b

    for module in (module_a, module_b):
        names = set(vars(module))
        assert not names & {"httpx", "requests", "urllib3", "aiohttp", "socket", "urlopen"}


# ---------------------------------------------------------------- the answer's shape


def test_an_indicator_id_is_the_first_eight_hex_of_the_documented_key() -> None:
    indicator = make_indicator("phone", "6591234567")

    key = hashlib.sha256(b"phone:6591234567").hexdigest()
    assert indicator.id == key[:8] and indicator.seen is None


def test_the_same_value_gives_the_same_id_whatever_the_formatting() -> None:
    a = extract_signals("Call +65 9123 4567", "x", corridor_id="SG-IN").indicators[0]
    b = extract_signals("Call +65-9123-4567", "x", corridor_id="SG-IN").indicators[0]

    assert a.id == b.id


def test_at_most_ten_and_the_flagged_ones_are_kept_first() -> None:
    plain = " ".join(f"https://site{i}-job.example" for i in range(12))
    text = f"{plain} and https://bit.ly/last"

    found = extract_signals(text, redact_text(text), corridor_id=None).indicators

    assert len(found) == MAX_INDICATORS
    assert "bit.ly" in [i.value for i in found]  # last in the message, still kept
    assert [i.value for i in found][-1] == "bit.ly"  # and the order of appearance is kept


def test_the_values_never_reach_the_prompt_only_flags_imitations_and_amounts() -> None:
    text = (
        "Pay SGD 800 at https://mom.gov.sg.verify-now.com/x, call +44 7911 123456, "
        "mail hr@brightpath.example, @agent_sg and https://bit.ly/abc"
    )
    signals = extract_signals(text, redact_text(text), corridor_id="SG-IN")

    prompt = signals.for_prompt()
    dumped = json.dumps(prompt)

    assert prompt["links"] == [
        {"flags": ["lookalike"], "imitates": "mom.gov.sg"},
        {"flags": ["shortener"]},
    ]
    assert prompt["phones"] == [{"flags": ["unexpected_country"]}]
    assert prompt["emails"] == [{"flags": []}] and prompt["handles"] == [{"flags": []}]
    assert prompt["amounts"] == [{"amount": 800.0, "currency": "SGD"}]
    for value in ("verify-now", "7911", "brightpath", "agent_sg", "bit.ly"):
        assert value not in dumped


def test_a_message_with_nothing_found_gives_an_empty_signal() -> None:
    signals = extract_signals("Hello", "Hello", corridor_id=None)

    assert signals == Signals([], []) and signals.for_prompt() == {}


def test_the_log_line_has_kinds_and_flags_never_values(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    text = "Call +44 7911 123456 or open https://bit.ly/secretpath"
    with caplog.at_level(logging.DEBUG):
        extract_signals(text, redact_text(text), corridor_id="SG-IN")

    assert "kinds=['phone', 'url']" in caplog.text
    assert "shortener" in caplog.text and "unexpected_country" in caplog.text
    for value in ("7911", "bit.ly", "secretpath"):
        assert value not in caplog.text


# ---------------------------------------------------------------- the curated lists


def test_the_curated_lists_are_valid_and_real_domains_are_never_lookalikes() -> None:
    data = checks.load_data()

    assert len(data.shorteners) >= 20 and len(data.protected) >= 50
    for p in data.protected:
        assert checks.lookalike_of(p.domain) is None, p.domain
        assert checks.lookalike_of(f"www.{p.domain}") is None
        assert checks.lookalike_of(f"login.{p.domain}") is None
        assert p.org and (p.brand is None or p.brand in p.domain)


def test_every_corridor_country_has_protected_domains() -> None:
    domains = {p.domain for p in checks.load_data().protected}

    for suffix in (".gov.sg", ".gov.ph", ".gov.in", ".gov.au", ".gov.my", ".go.id", ".go.jp"):
        assert any(d.endswith(suffix) for d in domains), suffix


def test_a_bad_entry_stops_the_load(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    broken = tmp_path / "data.json"
    broken.write_text(
        json.dumps({"shorteners": ["Not A Domain"], "protected": []}), encoding="utf-8"
    )
    monkeypatch.setattr(checks, "_DATA_FILE", broken)
    checks.load_data.cache_clear()
    try:
        with pytest.raises(ValueError, match="not a lowercase domain"):
            checks.load_data()
    finally:
        monkeypatch.undo()
        checks.load_data.cache_clear()


@pytest.mark.parametrize(
    ("digits", "international", "premium"),
    [
        ("19001234567", False, True),  # Singapore 1900, 11 digits
        ("6519001234567", True, True),
        ("1902345678", False, True),  # Australia 190X XXX XXX
        ("979123456789", True, True),  # ITU international premium rate
        ("979123456789", False, False),  # +979 only means something written internationally
        ("18001234567", False, False),  # Singapore 1800 is toll free
        ("6591234567", True, False),
        ("447911123456", True, False),
    ],
)
def test_premium_rate_ranges(digits: str, international: bool, premium: bool) -> None:
    assert checks.is_premium_rate(digits, international) is premium


@pytest.mark.parametrize(
    ("a", "b", "distance"),
    [
        ("abc", "abc", 0),
        ("abc", "abd", 1),
        ("abc", "ab", 1),
        ("kitten", "sitting", 3),
        ("", "ab", 2),
    ],
)
def test_edit_distance(a: str, b: str, distance: int) -> None:
    assert checks._distance(a, b) == distance
