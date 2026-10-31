from typing import Annotated

from fastapi import APIRouter, Depends

from src.application.jwk import CollectJwks

from .deps import get_collect_jwks
from .docs import JWKS_DOCS
from .schemas import JSONWebKeySet

router = APIRouter(prefix="/.well-known", tags=["Служебные метаданные"])


@router.get("/jwks.json", **JWKS_DOCS)
async def get_jwks(
    collect: Annotated[CollectJwks, Depends(get_collect_jwks)],
) -> JSONWebKeySet:
    """Функция получения набора публичных ключей подписи токенов.

    Args:
        collect (CollectJwks): Use case сбора публичных JWK.

    Returns:
        JSONWebKeySet: Набор публичных ключей подписи из кеша.
    """
    return JSONWebKeySet.model_validate({"keys": list(await collect())})
