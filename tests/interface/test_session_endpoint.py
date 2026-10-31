"""Тесты HTTP-контракта слоя `/sessions`."""

from datetime import UTC, datetime, timedelta

from fastapi import FastAPI, status
import pytest

from src.adapters.cache.repositories import RedisRevokedTokensRepository, RedisSessionRepository
from src.application import (
    CloseOtherSessions,
    CloseSession,
    EnsureTokenActive,
    ListSessions,
    SignToken,
    VerifyToken,
)
from src.application.jwk import RotateJwk
from src.domain.entities import Session
from src.domain.tokens import RefreshTokenClaims
from src.interface.auth.deps import get_ensure_token_active, get_verify_refresh_token
from src.interface.sessions.deps import (
    get_close_other_sessions,
    get_close_session,
    get_list_sessions,
)
from tests.asgi_client import ASGIClient
from tests.doubles import InMemoryRedis

LIST_PATH = "/sessions"
SEEDED_SESSIONS = 2
USER_ID = 42
CURRENT_SID = "current-session"
OTHER_SID = "other-session"
TTL_SECONDS = 3600


@pytest.fixture
def session_client(
    api_app: FastAPI,
    verify_refresh_token: VerifyToken[RefreshTokenClaims],
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
    session_repository: RedisSessionRepository,
) -> ASGIClient:
    """Отдаёт клиент `/sessions` с подменами проверки refresh-токена, сессий и отзыва.

    Args:
        api_app (FastAPI): Приложение под тестом.
        verify_refresh_token (VerifyToken[RefreshTokenClaims]): Use case проверки
            refresh-токенов.
        blacklisted_tokens_repository (RedisRevokedTokensRepository): Репозиторий
            отозванных токенов поверх подмены Redis.
        session_repository (RedisSessionRepository): Репозиторий сессий поверх подмены Redis.

    Returns:
        ASGIClient: Клиент маршрутов `/sessions`.
    """
    api_app.dependency_overrides[get_verify_refresh_token] = lambda: verify_refresh_token
    api_app.dependency_overrides[get_ensure_token_active] = lambda: EnsureTokenActive(
        blacklisted_tokens_repository
    )
    api_app.dependency_overrides[get_list_sessions] = lambda: ListSessions(session_repository)

    close_session = CloseSession(blacklisted_tokens_repository, session_repository)
    api_app.dependency_overrides[get_close_session] = lambda: close_session
    api_app.dependency_overrides[get_close_other_sessions] = lambda: CloseOtherSessions(
        session_repository, close_session
    )

    return ASGIClient(api_app)


async def _issue_refresh_token(
    rotate_jwk: RotateJwk,
    sign_refresh_token: SignToken,
    *,
    sid: str = CURRENT_SID,
) -> str:
    """Публикует ключ и выпускает refresh-токен для проверки `/sessions`.

    Args:
        rotate_jwk (RotateJwk): Use case генерации и публикации ключей.
        sign_refresh_token (SignToken): Use case выпуска refresh-токенов.
        sid (str, optional): Идентификатор сессии в `sid`. Defaults to CURRENT_SID.

    Returns:
        str: Подписанный refresh-токен.
    """
    await rotate_jwk(TTL_SECONDS)
    token, _ = await sign_refresh_token(USER_ID, sid)

    return token


def _cookie(token: str) -> dict[str, str]:
    """Собирает заголовок cookie с refresh-токеном.

    Args:
        token (str): Refresh-токен.

    Returns:
        dict[str, str]: Заголовок `Cookie`.
    """
    return {"cookie": f"refresh_token={token}"}


async def _seed_sessions(session_repository: RedisSessionRepository) -> None:
    """Кладёт в подмену Redis две активные сессии пользователя.

    Args:
        session_repository (RedisSessionRepository): Репозиторий сессий поверх подмены Redis.
    """
    now = datetime.now(UTC)
    current = Session(
        id=CURRENT_SID,
        user_id=USER_ID,
        created_at=now,
        expires_at=now + timedelta(hours=1),
        ip="203.0.113.7",
        platform="Windows",
        browser="Chrome",
    )
    other = Session(
        id=OTHER_SID,
        user_id=USER_ID,
        created_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(hours=1),
        ip="198.51.100.9",
        platform="Linux",
        browser="Firefox",
    )
    await session_repository.save(current)
    await session_repository.save(other)


async def test_list_sessions_returns_active_sessions(
    session_client: ASGIClient,
    session_repository: RedisSessionRepository,
    rotate_jwk: RotateJwk,
    sign_refresh_token: SignToken,
) -> None:
    """Список активных сессий владельца refresh-токена.

    Given: две активные сессии пользователя и действующий refresh-токен,
    When: владелец запрашивает список сессий,
    Then: приходит 200 с обеими сессиями, меткой текущей и контекстом входа.
    """
    # Дано
    await _seed_sessions(session_repository)
    token = await _issue_refresh_token(rotate_jwk, sign_refresh_token)

    # Когда
    response = await session_client.get(LIST_PATH, headers=_cookie(token))

    # Тогда
    assert response.status_code == status.HTTP_200_OK

    sessions = response.payload["sessions"]
    assert len(sessions) == SEEDED_SESSIONS

    by_id = {item["id"]: item for item in sessions}
    assert by_id[CURRENT_SID]["current"] is True
    assert by_id[OTHER_SID]["current"] is False
    assert by_id[CURRENT_SID]["ip"] == "203.0.113.7"
    assert by_id[CURRENT_SID]["platform"] == "Windows"
    assert by_id[CURRENT_SID]["browser"] == "Chrome"
    assert by_id[OTHER_SID]["ip"] == "198.51.100.9"
    assert by_id[OTHER_SID]["platform"] == "Linux"
    assert by_id[OTHER_SID]["browser"] == "Firefox"


async def test_list_sessions_requires_refresh_cookie(session_client: ASGIClient) -> None:
    """Список сессий без refresh-токена в cookie.

    Given: запрос без cookie с refresh-токеном,
    When: клиент запрашивает список сессий,
    Then: приходит 401: сессию не идентифицировать.
    """
    # Когда
    response = await session_client.get(LIST_PATH)

    # Тогда
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers["www-authenticate"] == "Bearer"


async def test_list_sessions_rejects_invalid_token(session_client: ASGIClient) -> None:
    """Список сессий с невалидным refresh-токеном.

    Given: в cookie передана строка, не являющаяся JWT,
    When: клиент запрашивает список сессий,
    Then: приходит 403: токен не проходит проверку.
    """
    # Когда
    response = await session_client.get(LIST_PATH, headers=_cookie("not-a-jwt"))

    # Тогда
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_close_session_revokes_selected_session(
    session_client: ASGIClient,
    session_repository: RedisSessionRepository,
    rotate_jwk: RotateJwk,
    sign_refresh_token: SignToken,
    redis_double: InMemoryRedis,
) -> None:
    """Закрытие выбранной сессии.

    Given: две активные сессии пользователя,
    When: владелец закрывает одну из них,
    Then: приходит 204, выбранная сессия отзывается, а текущая остаётся.
    """
    # Дано
    await _seed_sessions(session_repository)
    token = await _issue_refresh_token(rotate_jwk, sign_refresh_token)

    # Когда
    response = await session_client.request(
        "DELETE", f"{LIST_PATH}/{OTHER_SID}", headers=_cookie(token)
    )

    # Тогда
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.body == b""

    assert redis_double.values[f"session:revoked:{OTHER_SID}"] == "1"

    stored_current = await session_repository.get(CURRENT_SID)
    stored_other = await session_repository.get(OTHER_SID)
    assert stored_current is not None
    assert stored_current.revoked_at is None
    assert stored_other is not None
    assert stored_other.revoked_at is not None


async def test_close_session_rejects_unknown_session(
    session_client: ASGIClient,
    rotate_jwk: RotateJwk,
    sign_refresh_token: SignToken,
) -> None:
    """Закрытие несуществующей сессии.

    Given: сессии с указанным `sid` нет,
    When: владелец пытается её закрыть,
    Then: приходит 404: сессия не найдена.
    """
    # Дано
    token = await _issue_refresh_token(rotate_jwk, sign_refresh_token)

    # Когда
    response = await session_client.request(
        "DELETE", f"{LIST_PATH}/missing-session", headers=_cookie(token)
    )

    # Тогда
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.payload["message"] == "Session not found."


async def test_close_other_sessions_keeps_current(
    session_client: ASGIClient,
    session_repository: RedisSessionRepository,
    rotate_jwk: RotateJwk,
    sign_refresh_token: SignToken,
) -> None:
    """Закрытие всех сессий, кроме текущей.

    Given: две активные сессии пользователя,
    When: владелец закрывает все сессии, кроме текущей,
    Then: приходит 204, вторая сессия отзывается, а текущая остаётся активной.
    """
    # Дано
    await _seed_sessions(session_repository)
    token = await _issue_refresh_token(rotate_jwk, sign_refresh_token)

    # Когда
    response = await session_client.request("DELETE", LIST_PATH, headers=_cookie(token))

    # Тогда
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.body == b""

    stored_current = await session_repository.get(CURRENT_SID)
    stored_other = await session_repository.get(OTHER_SID)
    assert stored_current is not None
    assert stored_current.revoked_at is None
    assert stored_other is not None
    assert stored_other.revoked_at is not None
