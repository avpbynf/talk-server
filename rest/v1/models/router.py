"""FastAPI router for the models listing (OpenAI-compatible)."""

from fastapi import APIRouter

from rest.settings import get_settings
from rest.v1.models.models import ModelInfo, ModelList

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=ModelList)
async def list_models() -> ModelList:
    """List the model this server transcribes with.

    Returns:
        ModelList holding the configured Whisper model.
    """
    return ModelList(data=[ModelInfo(id=get_settings().WHISPER_MODEL)])
