"""Tests for GET /v1/models."""

from sqlalchemy import func, select

from rest.db.models import Token, UsageLog


async def test_models_requires_token(unauth_client):
    response = await unauth_client.get("/v1/models")
    assert response.status_code == 401


async def test_models_rejects_unknown_token(unauth_client):
    response = await unauth_client.get(
        "/v1/models", headers={"Authorization": "Bearer sk_nope"}
    )
    assert response.status_code == 401


async def test_models_lists_the_configured_model(client):
    response = await client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert len(data["data"]) == 1
    entry = data["data"][0]
    assert entry["id"] == "Systran/faster-whisper-large-v3"
    assert entry["object"] == "model"
    assert entry["owned_by"] == "talk"


async def test_models_check_is_not_counted_as_usage(client, db_session_maker):
    await client.get("/v1/models")

    async with db_session_maker() as s:
        logs = (
            await s.execute(select(func.count()).select_from(UsageLog))
        ).scalar_one()
        counts = (await s.execute(select(Token.usage_count))).scalars().all()

    assert logs == 0
    assert all(count == 0 for count in counts)
