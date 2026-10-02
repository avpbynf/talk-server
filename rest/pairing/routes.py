"""Pairing routes: no auth, the code only the operator sees is the credential."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession

from rest.auth.tokens import create_token
from rest.db.database import get_db
from rest.pairing.store import (
    REQUEST_TTL_SECONDS,
    PairingCodeError,
    PairingFullError,
    PairingGoneError,
    PairingLockedError,
    get_store,
)
from rest.settings import get_settings

logger = logging.getLogger(__name__)


class PairingRequestBody(BaseModel):
    """Request body for opening a pairing request."""

    model_config = ConfigDict(frozen=True)

    client_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
    ]


class PairingRequestResponse(BaseModel):
    """Handle for a pending request. The code is never part of it."""

    model_config = ConfigDict(frozen=True)

    request_id: str
    expires_in: int


class PairingConfirmBody(BaseModel):
    """Request body for confirming a pairing request."""

    model_config = ConfigDict(frozen=True)

    request_id: Annotated[str, StringConstraints(max_length=64)]
    code: Annotated[str, StringConstraints(max_length=16)]


class PairingConfirmResponse(BaseModel):
    """The minted token, shown once."""

    model_config = ConfigDict(frozen=True)

    token: str
    name: str


async def require_pairing() -> None:
    """Answer 404 when pairing is off, as if the routes did not exist.

    Locked by wrong codes counts as off.
    """
    if not get_settings().pairing_active or get_store().locked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


router = APIRouter(
    prefix="/pairing", tags=["pairing"], dependencies=[Depends(require_pairing)]
)


@router.post(
    "/request",
    response_model=PairingRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_pairing(
    body: PairingRequestBody, http_request: Request
) -> PairingRequestResponse:
    """Open a request. The operator reads the code in the server log or dashboard."""
    client_host = http_request.client.host if http_request.client else None
    try:
        request = get_store().create(body.client_name, client_host)
    except PairingLockedError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not Found"
        ) from None
    except PairingFullError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many pairing requests pending, try again shortly",
        ) from None
    logger.warning(
        "Pairing request from %s: code %s, valid 2 minutes",
        request.client_name,
        request.code,
    )
    return PairingRequestResponse(request_id=request.id, expires_in=REQUEST_TTL_SECONDS)


@router.post("/confirm", response_model=PairingConfirmResponse)
async def confirm_pairing(
    body: PairingConfirmBody,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PairingConfirmResponse:
    """Trade the code for a token."""
    try:
        request = get_store().confirm(body.request_id, body.code)
    except PairingLockedError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not Found"
        ) from None
    except PairingGoneError:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Pairing request expired or unknown",
        ) from None
    except PairingCodeError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong code"
        ) from None
    token, plain = await create_token(db, f"{request.client_name} (paired)")
    logger.info("Paired %s", request.client_name)
    return PairingConfirmResponse(token=plain, name=token.name)
