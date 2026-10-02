"""Tests for pairing: request, confirm, admin listing and the on/off switches."""

import logging

import httpx
import pytest
from sqlalchemy import func, select

from rest.db.models import UsageLog
from rest.pairing.store import (
    MAX_ATTEMPTS,
    MAX_FAILED_CODES,
    MAX_PENDING,
    get_store,
)

_ADMIN = {"Authorization": "Bearer test-admin-token"}


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture(autouse=True)
def _fresh_store():
    get_store.cache_clear()
    yield
    get_store.cache_clear()


@pytest.fixture
def clock():
    fake = _Clock()
    get_store()._clock = fake
    return fake


@pytest.fixture
async def pair_client(app_factory):
    app = app_factory()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as c:
        yield c


def _code_of(client_name: str) -> str:
    return next(
        r.code for r, _ in get_store().pending() if r.client_name == client_name
    )


async def _open(client, name="Laptop"):
    r = await client.post("/pairing/request", json={"client_name": name})
    assert r.status_code == 201
    return r.json()["request_id"]


async def test_full_flow_mints_a_working_token(pair_client):
    request_id = await _open(pair_client)
    r = await pair_client.post(
        "/pairing/confirm",
        json={"request_id": request_id, "code": _code_of("Laptop")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Laptop (paired)"
    assert body["token"].startswith("sk_")

    models = await pair_client.get(
        "/v1/models", headers={"Authorization": f"Bearer {body['token']}"}
    )
    assert models.status_code == 200

    again = await pair_client.post(
        "/pairing/confirm",
        json={"request_id": request_id, "code": "000000"},
    )
    assert again.status_code == 410


async def test_request_response_never_carries_the_code(pair_client):
    r = await pair_client.post("/pairing/request", json={"client_name": "  Desk  "})
    code = _code_of("Desk")
    assert r.json().keys() == {"request_id", "expires_in"}
    assert r.json()["expires_in"] == 120
    assert code not in r.text


async def test_code_is_logged_for_the_operator(pair_client, caplog):
    with caplog.at_level(logging.WARNING, logger="rest.pairing.routes"):
        await _open(pair_client, "Desk")
    code = _code_of("Desk")
    assert f"Pairing request from Desk: code {code}, valid 2 minutes" in caplog.text


@pytest.mark.parametrize("name", ["", "   ", "x" * 65])
async def test_client_name_is_validated(pair_client, name):
    r = await pair_client.post("/pairing/request", json={"client_name": name})
    assert r.status_code == 422


async def test_wrong_code_counts_attempts_then_drops(pair_client):
    request_id = await _open(pair_client)
    right = _code_of("Laptop")
    wrong = "000000" if right != "000000" else "111111"

    for _ in range(MAX_ATTEMPTS):
        r = await pair_client.post(
            "/pairing/confirm", json={"request_id": request_id, "code": wrong}
        )
        assert r.status_code == 401

    # Even the right code is refused once the request is dropped.
    r = await pair_client.post(
        "/pairing/confirm", json={"request_id": request_id, "code": right}
    )
    assert r.status_code == 410


async def test_fewer_wrong_codes_leave_the_request_alive(pair_client):
    request_id = await _open(pair_client)
    right = _code_of("Laptop")
    wrong = "000000" if right != "000000" else "111111"
    for _ in range(MAX_ATTEMPTS - 1):
        await pair_client.post(
            "/pairing/confirm", json={"request_id": request_id, "code": wrong}
        )
    r = await pair_client.post(
        "/pairing/confirm", json={"request_id": request_id, "code": right}
    )
    assert r.status_code == 200


async def test_unknown_request_is_gone(pair_client):
    r = await pair_client.post(
        "/pairing/confirm", json={"request_id": "nope", "code": "123456"}
    )
    assert r.status_code == 410


async def test_expired_request_is_gone(pair_client, clock):
    request_id = await _open(pair_client)
    code = _code_of("Laptop")
    clock.now += 121
    r = await pair_client.post(
        "/pairing/confirm", json={"request_id": request_id, "code": code}
    )
    assert r.status_code == 410


async def test_pending_cap_purges_expired_first(pair_client, clock):
    # The test client always calls from the same address, so the other
    # machines are opened on the store directly.
    for i in range(MAX_PENDING):
        get_store().create(f"c{i}", f"10.0.0.{i}")
    r = await pair_client.post("/pairing/request", json={"client_name": "late"})
    assert r.status_code == 429

    clock.now += 121
    r = await pair_client.post("/pairing/request", json={"client_name": "late"})
    assert r.status_code == 201


async def test_a_machine_holds_one_request_at_a_time(pair_client):
    first = await _open(pair_client, "Laptop")
    await _open(pair_client, "Laptop")

    r = await pair_client.post(
        "/pairing/confirm", json={"request_id": first, "code": "000000"}
    )
    assert r.status_code == 410
    assert len(get_store().pending()) == 1


async def test_wrong_codes_across_requests_turn_pairing_off(pair_client):
    for _ in range(MAX_FAILED_CODES // MAX_ATTEMPTS):
        request_id = await _open(pair_client)
        wrong = "000000" if _code_of("Laptop") != "000000" else "111111"
        for _ in range(MAX_ATTEMPTS):
            await pair_client.post(
                "/pairing/confirm", json={"request_id": request_id, "code": wrong}
            )

    r = await pair_client.post("/pairing/request", json={"client_name": "Laptop"})
    assert r.status_code == 404
    assert get_store().locked


async def test_the_lock_drops_what_was_pending(pair_client):
    get_store().create("Desk", "10.0.0.9")
    request_id = await _open(pair_client)
    wrong = "000000" if _code_of("Laptop") != "000000" else "111111"
    store = get_store()
    store._failed_codes = MAX_FAILED_CODES - 1

    await pair_client.post(
        "/pairing/confirm", json={"request_id": request_id, "code": wrong}
    )

    assert store.locked
    assert store.pending() == []


async def test_code_is_six_digits_zero_padded(pair_client, monkeypatch):
    monkeypatch.setattr("rest.pairing.store.secrets.randbelow", lambda _n: 42)
    await _open(pair_client)
    assert _code_of("Laptop") == "000042"


async def test_pairing_writes_no_usage_rows(pair_client, db_session_maker):
    request_id = await _open(pair_client)
    await pair_client.post(
        "/pairing/confirm",
        json={"request_id": request_id, "code": _code_of("Laptop")},
    )
    async with db_session_maker() as session:
        count = await session.scalar(select(func.count()).select_from(UsageLog))
    assert count == 0


async def test_disabled_answers_404(app_factory, monkeypatch):
    monkeypatch.setenv("PAIRING_ENABLED", "false")
    app = app_factory()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as c:
        r = await c.post("/pairing/request", json={"client_name": "x"})
        assert r.status_code == 404
        r = await c.post("/pairing/confirm", json={"request_id": "a", "code": "1"})
        assert r.status_code == 404
        listing = (await c.get("/admin/pairing", headers=_ADMIN)).json()
        assert listing == {"enabled": False, "requests": []}


async def test_off_without_admin_token(app_factory, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "")
    app = app_factory()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as c:
        r = await c.post("/pairing/request", json={"client_name": "x"})
        assert r.status_code == 404


async def test_admin_listing_requires_the_admin_token(pair_client):
    await _open(pair_client)
    assert (await pair_client.get("/admin/pairing")).status_code == 401
    bad = {"Authorization": "Bearer wrong"}
    assert (await pair_client.get("/admin/pairing", headers=bad)).status_code == 401


async def test_admin_listing_shows_code_and_time_left(pair_client, clock):
    await _open(pair_client, "Desk")
    clock.now += 30
    body = (await pair_client.get("/admin/pairing", headers=_ADMIN)).json()
    assert body["enabled"] is True
    assert body["requests"] == [
        {"client_name": "Desk", "code": _code_of("Desk"), "seconds_left": 90}
    ]


def test_txt_flag_follows_pairing_state():
    from unittest.mock import patch

    from rest import discovery
    from rest.settings import Settings

    def props(**kw):
        with (
            patch("rest.discovery._local_ipv4_addresses", return_value=["10.0.0.2"]),
            patch("rest.discovery.socket.gethostname", return_value="box"),
        ):
            info = discovery.build_service_info(
                Settings(DEVICE="cpu", _env_file=None, **kw)
            )
        assert info is not None
        return info.decoded_properties["pairing"]

    assert props(ADMIN_TOKEN="a") == "1"
    assert props(ADMIN_TOKEN="a", PAIRING_ENABLED=False) == "0"
    assert props(ADMIN_TOKEN="") == "0"
