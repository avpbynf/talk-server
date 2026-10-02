"""Response models for the OpenAI-compatible models listing."""

from pydantic import BaseModel, ConfigDict


class ModelInfo(BaseModel):
    """One model entry, shaped like the OpenAI model object."""

    model_config = ConfigDict(frozen=True)

    id: str
    object: str = "model"
    owned_by: str = "talk"


class ModelList(BaseModel):
    """Response of GET /v1/models."""

    model_config = ConfigDict(frozen=True)

    object: str = "list"
    data: list[ModelInfo]
