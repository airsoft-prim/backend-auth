from fastapi import APIRouter

from .docs import JWKS_DOCS
from .schemas import JSONWebKeySet

router = APIRouter(prefix="/.well-known", tags=["Служебные метаданные"])


@router.get("/jwks.json", **JWKS_DOCS)
async def get_jwks() -> JSONWebKeySet:
    """Функция получения набора публичных ключей подписи токенов.

    Returns:
        KeySet: Набор ключей JWKS без ключей внутри.
    """
    return JSONWebKeySet(keys=[])
