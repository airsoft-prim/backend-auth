from typing import Annotated

from fastapi import APIRouter, Depends

from src.services.jwk import JWKPublishingService

from .deps import get_jwk_publishing_service
from .docs import JWKS_DOCS
from .schemas import JSONWebKeySet

router = APIRouter(prefix="/.well-known", tags=["Служебные метаданные"])


@router.get("/jwks.json", **JWKS_DOCS)
async def get_jwks(
    service: Annotated[JWKPublishingService, Depends(get_jwk_publishing_service)],
) -> JSONWebKeySet:
    """Функция получения набора публичных ключей подписи токенов.

    Args:
        service (JWKPublishingService): Сервис публикации публичных JWK.

    Returns:
        JSONWebKeySet: Набор публичных ключей подписи из кеша.
    """
    return JSONWebKeySet.model_validate({"keys": list(await service.collect())})
