"""Announce the server on the local network over mDNS / DNS-SD."""

import ipaddress
import logging
import socket

import ifaddr
from zeroconf import ServiceInfo
from zeroconf.asyncio import AsyncZeroconf

from rest.settings import Settings

logger = logging.getLogger(__name__)

SERVICE_TYPE = "_talk._tcp.local."

# Bridges and tunnels that only this machine, its containers or its VMs can
# reach. Announcing them hands a client an address it may pick and never get
# through: docker0 is 172.17.0.1 on every host running Docker.
_VIRTUAL_ADAPTER_PREFIXES = (
    "docker",
    "br-",
    "veth",
    "virbr",
    "lxc",
    "cni",
    "flannel",
    "vethernet",
)


def _is_virtual(adapter: ifaddr.Adapter) -> bool:
    names = (str(adapter.name), str(adapter.nice_name))
    return any(name.lower().startswith(_VIRTUAL_ADAPTER_PREFIXES) for name in names)


def _local_ipv4_addresses() -> list[str]:
    """Return the machine's IPv4 addresses a LAN client could reach.

    Loopback and link-local addresses are skipped: neither is routable from
    another machine. So are container bridges and virtual switches.
    """
    found: list[str] = []
    for adapter in ifaddr.get_adapters():
        if _is_virtual(adapter):
            continue
        for ip in adapter.ips:
            if not ip.is_IPv4 or not isinstance(ip.ip, str):
                continue
            addr = ipaddress.IPv4Address(ip.ip)
            if addr.is_loopback or addr.is_link_local:
                continue
            if ip.ip not in found:
                found.append(ip.ip)
    return found


def build_service_info(settings: Settings) -> ServiceInfo | None:
    """Build the DNS-SD record describing this server.

    Args:
        settings: Application settings (port and model are announced).

    Returns:
        The service record, or None when the machine has no usable address.
    """
    addresses = _local_ipv4_addresses()
    if not addresses:
        return None

    hostname = socket.gethostname().split(".")[0]
    return ServiceInfo(
        SERVICE_TYPE,
        f"{hostname}.{SERVICE_TYPE}",
        port=settings.PORT,
        properties={
            "engine": "faster-whisper",
            "model": settings.WHISPER_MODEL,
            "auth": "token",
            "pairing": "1" if settings.pairing_active else "0",
        },
        server=f"{hostname}.local.",
        addresses=[socket.inet_aton(a) for a in addresses],
    )


async def start_announcement(settings: Settings) -> AsyncZeroconf | None:
    """Register the service on the network.

    Never raises: a failure to announce must not stop the server.

    Args:
        settings: Application settings.

    Returns:
        The running zeroconf instance to hand to stop_announcement, or None
        when nothing is announced.
    """
    if not settings.MDNS_ENABLED:
        return None

    zc: AsyncZeroconf | None = None
    try:
        info = build_service_info(settings)
        if info is None:
            logger.warning("mDNS announcement skipped: no network address found")
            return None
        zc = AsyncZeroconf()
        await zc.async_register_service(info)
    except Exception as exc:
        logger.warning("mDNS announcement failed: %s", exc)
        if zc is not None:
            try:
                await zc.async_close()
            except Exception:
                logger.debug("closing zeroconf after a failed start", exc_info=True)
        return None

    logger.info("Announcing %s on port %d", info.name, settings.PORT)
    return zc


async def stop_announcement(zc: AsyncZeroconf | None) -> None:
    """Unregister the service and close zeroconf.

    Args:
        zc: The instance returned by start_announcement, if any.
    """
    if zc is None:
        return
    try:
        await zc.async_unregister_all_services()
        await zc.async_close()
    except Exception as exc:
        logger.warning("mDNS shutdown failed: %s", exc)
