"""In-memory store of pending pairing requests."""

import functools
import logging
import secrets
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

REQUEST_TTL_SECONDS = 120
MAX_PENDING = 5
MAX_ATTEMPTS = 5
# Across every request, for the life of the process. Five attempts per request
# bound nothing on their own: dropping a request frees its slot, and opening a
# new one costs nothing, so an attacker could cycle through requests until one
# of a million codes came up. Ten wrong codes in total leaves them a chance in
# a hundred thousand, and then pairing stays off until the server restarts.
MAX_FAILED_CODES = 10


class PairingFullError(Exception):
    """Too many requests are pending."""


class PairingGoneError(Exception):
    """The request is unknown, expired, or used up its attempts."""


class PairingCodeError(Exception):
    """The code does not match."""


class PairingLockedError(Exception):
    """Too many wrong codes: pairing is off until the server restarts."""


@dataclass
class PairingRequest:
    """A pending request. Attempts are counted in place."""

    id: str
    client_name: str
    code: str
    expires_at: float
    client_host: str | None = None
    attempts: int = 0


class PairingStore:
    """Pending pairing requests, kept in memory only.

    A restart drops them, which is fine for a code that lives two minutes.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._pending: dict[str, PairingRequest] = {}
        self._failed_codes = 0

    @property
    def locked(self) -> bool:
        """Whether wrong codes have used up the budget."""
        return self._failed_codes >= MAX_FAILED_CODES

    def _purge(self) -> None:
        now = self._clock()
        for request_id in [r.id for r in self._pending.values() if r.expires_at <= now]:
            del self._pending[request_id]

    def create(
        self, client_name: str, client_host: str | None = None
    ) -> PairingRequest:
        """Open a request with a fresh 6-digit code.

        A machine holds one request at a time: asking again replaces the
        previous one, so a single machine cannot fill every slot and keep
        everybody else out.

        Raises:
            PairingLockedError: when wrong codes have used up the budget.
            PairingFullError: when MAX_PENDING requests are already waiting.
        """
        if self.locked:
            raise PairingLockedError
        self._purge()
        if client_host is not None:
            for request_id in [
                r.id for r in self._pending.values() if r.client_host == client_host
            ]:
                del self._pending[request_id]
        if len(self._pending) >= MAX_PENDING:
            raise PairingFullError
        request = PairingRequest(
            id=str(uuid.uuid4()),
            client_name=client_name,
            code=f"{secrets.randbelow(1_000_000):06d}",
            expires_at=self._clock() + REQUEST_TTL_SECONDS,
            client_host=client_host,
        )
        self._pending[request.id] = request
        return request

    def confirm(self, request_id: str, code: str) -> PairingRequest:
        """Check a code and consume the request when it matches.

        Raises:
            PairingLockedError: when wrong codes have used up the budget.
            PairingGoneError: unknown or expired request, or attempts used up.
            PairingCodeError: wrong code.
        """
        if self.locked:
            raise PairingLockedError
        self._purge()
        request = self._pending.get(request_id)
        if request is None:
            raise PairingGoneError
        if secrets.compare_digest(code.encode(), request.code.encode()):
            del self._pending[request_id]
            return request
        request.attempts += 1
        self._failed_codes += 1
        if self.locked:
            self._pending.clear()
            logger.warning(
                "Pairing turned off after %d wrong codes, "
                "restart the server to turn it back on",
                MAX_FAILED_CODES,
            )
        elif request.attempts >= MAX_ATTEMPTS:
            del self._pending[request_id]
            logger.warning(
                "Pairing request from %s dropped after %d wrong codes",
                request.client_name,
                MAX_ATTEMPTS,
            )
        raise PairingCodeError

    def pending(self) -> list[tuple[PairingRequest, int]]:
        """Return live requests with the whole seconds each has left."""
        self._purge()
        now = self._clock()
        return [(r, max(0, int(r.expires_at - now))) for r in self._pending.values()]


@functools.lru_cache
def get_store() -> PairingStore:
    """Return the process-wide store. Tests reset it with cache_clear()."""
    return PairingStore()
