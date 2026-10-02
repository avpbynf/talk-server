"""Tests for the mDNS announcement. Nothing here touches the real network."""

import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from rest import discovery
from rest.settings import Settings


def _adapter(*ips, name="eth0"):
    return SimpleNamespace(
        name=name,
        nice_name=name,
        ips=[SimpleNamespace(ip=ip, is_IPv4=isinstance(ip, str)) for ip in ips],
    )


def _settings(**overrides):
    return Settings(DEVICE="cpu", PORT=8123, WHISPER_MODEL="tiny", **overrides)


def test_local_addresses_skip_loopback_and_link_local():
    adapters = [
        _adapter("127.0.0.1", "192.168.1.20"),
        _adapter("169.254.9.17", "192.168.1.20", ("fe80::1", 0, 0)),
        _adapter("10.0.0.5"),
    ]
    with patch("rest.discovery.ifaddr.get_adapters", return_value=adapters):
        assert discovery._local_ipv4_addresses() == ["192.168.1.20", "10.0.0.5"]


def test_local_addresses_skip_container_bridges_and_virtual_switches():
    adapters = [
        _adapter("172.17.0.1", name="docker0"),
        _adapter("172.18.0.1", name="br-5f2c"),
        _adapter("172.29.16.1", name="vEthernet (WSL)"),
        _adapter("192.168.1.20", name="Ethernet"),
    ]
    with patch("rest.discovery.ifaddr.get_adapters", return_value=adapters):
        assert discovery._local_ipv4_addresses() == ["192.168.1.20"]


def test_build_service_info_describes_the_server():
    with (
        patch("rest.discovery._local_ipv4_addresses", return_value=["192.168.1.20"]),
        patch("rest.discovery.socket.gethostname", return_value="box.lan"),
    ):
        info = discovery.build_service_info(_settings(ADMIN_TOKEN=""))

    assert info is not None
    assert info.type == "_talk._tcp.local."
    assert info.name == "box._talk._tcp.local."
    assert info.port == 8123
    assert info.addresses == [socket.inet_aton("192.168.1.20")]
    assert info.decoded_properties == {
        "engine": "faster-whisper",
        "model": "tiny",
        "auth": "token",
        "pairing": "0",
    }


def test_build_service_info_without_address_returns_none():
    with patch("rest.discovery._local_ipv4_addresses", return_value=[]):
        assert discovery.build_service_info(_settings()) is None


async def test_start_announcement_registers_the_service():
    zc = MagicMock(async_register_service=AsyncMock())
    with (
        patch("rest.discovery._local_ipv4_addresses", return_value=["192.168.1.20"]),
        patch("rest.discovery.AsyncZeroconf", return_value=zc),
    ):
        result = await discovery.start_announcement(_settings())

    assert result is zc
    zc.async_register_service.assert_awaited_once()


async def test_start_announcement_disabled_does_nothing():
    with patch("rest.discovery.AsyncZeroconf") as cls:
        result = await discovery.start_announcement(_settings(MDNS_ENABLED=False))

    assert result is None
    cls.assert_not_called()


async def test_start_announcement_without_address_returns_none(caplog):
    with (
        patch("rest.discovery._local_ipv4_addresses", return_value=[]),
        patch("rest.discovery.AsyncZeroconf") as cls,
    ):
        result = await discovery.start_announcement(_settings())

    assert result is None
    cls.assert_not_called()
    assert "no network address" in caplog.text


async def test_start_announcement_swallows_a_registration_failure(caplog):
    zc = MagicMock(
        async_register_service=AsyncMock(side_effect=OSError("port busy")),
        async_close=AsyncMock(),
    )
    with (
        patch("rest.discovery._local_ipv4_addresses", return_value=["192.168.1.20"]),
        patch("rest.discovery.AsyncZeroconf", return_value=zc),
    ):
        result = await discovery.start_announcement(_settings())

    assert result is None
    zc.async_close.assert_awaited_once()
    assert "port busy" in caplog.text


async def test_start_announcement_swallows_a_startup_failure(caplog):
    with (
        patch("rest.discovery._local_ipv4_addresses", return_value=["192.168.1.20"]),
        patch("rest.discovery.AsyncZeroconf", side_effect=OSError("no socket")),
    ):
        result = await discovery.start_announcement(_settings())

    assert result is None
    assert "no socket" in caplog.text


async def test_start_announcement_survives_a_failing_cleanup():
    zc = MagicMock(
        async_register_service=AsyncMock(side_effect=OSError("boom")),
        async_close=AsyncMock(side_effect=RuntimeError("again")),
    )
    with (
        patch("rest.discovery._local_ipv4_addresses", return_value=["192.168.1.20"]),
        patch("rest.discovery.AsyncZeroconf", return_value=zc),
    ):
        assert await discovery.start_announcement(_settings()) is None


async def test_stop_announcement_unregisters_and_closes():
    zc = MagicMock(async_unregister_all_services=AsyncMock(), async_close=AsyncMock())
    await discovery.stop_announcement(zc)

    zc.async_unregister_all_services.assert_awaited_once()
    zc.async_close.assert_awaited_once()


async def test_stop_announcement_accepts_none():
    await discovery.stop_announcement(None)


async def test_stop_announcement_swallows_a_failure(caplog):
    zc = MagicMock(async_unregister_all_services=AsyncMock(side_effect=OSError("x")))
    await discovery.stop_announcement(zc)

    assert "mDNS shutdown failed" in caplog.text
