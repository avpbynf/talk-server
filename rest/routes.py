"""Router assembly with versioned prefix."""

from fastapi import APIRouter, Depends

from rest.auth.dependencies import authenticate_token, record_usage, verify_token
from rest.v1.models.router import router as models_router
from rest.v1.transcriptions.router import router as transcriptions_router

router = APIRouter(prefix="/v1")
router.include_router(
    transcriptions_router,
    dependencies=[Depends(verify_token), Depends(record_usage)],
)
# Clients poll this to check their token, every few seconds while in server
# mode. Counted as usage, it would bury the transcriptions in the statistics.
router.include_router(models_router, dependencies=[Depends(authenticate_token)])
