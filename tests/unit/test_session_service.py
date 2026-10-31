"""Тесты сервиса сессий: контекст входа, список и закрытие сессий."""

from datetime import UTC, datetime, timedelta

import pytest

from src.adapters.cache.repositories import RedisRevokedTokensRepository, RedisSessionRepository
from src.application import CloseOtherSessions, CloseSession, CreateSession, ListSessions
from src.application.session import parse_user_agent
from src.domain.entities import Session
from src.domain.errors import SessionNotFoundError
from tests.doubles import InMemoryRedis

USER_ID = 42
OTHER_USER_ID = 43
TTL_SECONDS = 3600
SESSION_LIMIT = 2

CHROME_WINDOWS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
FIREFOX_LINUX = "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"
SAFARI_MACOS = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)
EDGE_WINDOWS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
)
IPHONE_SAFARI = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
ANDROID_CHROME = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)


@pytest.mark.parametrize(
    ("user_agent", "platform", "browser"),
    [
        (CHROME_WINDOWS, "Windows", "Chrome"),
        (FIREFOX_LINUX, "Linux", "Firefox"),
        (SAFARI_MACOS, "macOS", "Safari"),
        (EDGE_WINDOWS, "Windows", "Edge"),
        (IPHONE_SAFARI, "iOS", "Safari"),
        (ANDROID_CHROME, "Android", "Chrome"),
    ],
)
async def test_parse_user_agent_detects_platform_and_browser(
    user_agent: str,
    platform: str,
    browser: str,
) -> None:
    """Разбор известных User-Agent.

    Given: строка User-Agent известного браузера и платформы,
    When: сервис разбирает заголовок,
    Then: он возвращает ожидаемые платформу и браузер.
    """
    # Когда
    parsed = parse_user_agent(user_agent)

    # Тогда
    assert parsed == (platform, browser)


async def test_parse_user_agent_returns_none_for_unknown() -> None:
    """Разбор неизвестного User-Agent.

    Given: строка без известных признаков платформы и браузера,
    When: сервис разбирает заголовок,
    Then: он возвращает пару из None.
    """
    # Когда
    parsed = parse_user_agent("curl/8.0.1")

    # Тогда
    assert parsed == (None, None)


async def test_create_session_stores_login_context(
    session_repository: RedisSessionRepository,
) -> None:
    """Создание сессии с контекстом входа.

    Given: сервис создания сессии и IP с User-Agent входа,
    When: сессия создаётся,
    Then: контекст фиксируется в сессии и переживает чтение из хранилища.
    """
    # Дано
    create_session = CreateSession(session_repository, TTL_SECONDS, max_active=5)

    # Когда
    session = await create_session(USER_ID, ip="203.0.113.7", user_agent=CHROME_WINDOWS)

    # Тогда
    assert session.ip == "203.0.113.7"
    assert session.user_agent == CHROME_WINDOWS
    assert session.platform == "Windows"
    assert session.browser == "Chrome"
    assert session.location is None

    stored = await session_repository.get(session.id)
    assert stored is not None
    assert stored.ip == "203.0.113.7"
    assert stored.platform == "Windows"
    assert stored.browser == "Chrome"


async def test_create_session_revokes_oldest_over_limit(
    session_repository: RedisSessionRepository,
) -> None:
    """Создание сессии сверх лимита отзывает самую старую.

    Given: лимит активных сессий равен двум,
    When: создаётся третья сессия,
    Then: самая старая сессия отзывается, а новых остаётся две.
    """
    # Дано
    create_session = CreateSession(session_repository, TTL_SECONDS, max_active=SESSION_LIMIT)
    oldest = await create_session(USER_ID)
    await create_session(USER_ID)

    # Когда
    await create_session(USER_ID)

    # Тогда
    assert len(list(await session_repository.list_active(USER_ID))) == SESSION_LIMIT

    revoked = await session_repository.get(oldest.id)
    assert revoked is not None
    assert revoked.revoked_at is not None


async def test_list_sessions_returns_active_sorted_newest_first(
    session_repository: RedisSessionRepository,
) -> None:
    """Список активных сессий отсортирован от новых к старым.

    Given: две активные сессии одного пользователя,
    When: сервис запрашивает список активных сессий,
    Then: он возвращает обе, первой — созданную позже.
    """
    # Дано
    now = datetime.now(UTC)
    older = Session(
        id="older-session",
        user_id=USER_ID,
        created_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(hours=1),
    )
    newer = Session(
        id="newer-session",
        user_id=USER_ID,
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    await session_repository.save(older)
    await session_repository.save(newer)

    # Когда
    sessions = await ListSessions(session_repository)(USER_ID)

    # Тогда
    assert [session.id for session in sessions] == ["newer-session", "older-session"]


async def test_close_session_revokes_owned_session(
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
    session_repository: RedisSessionRepository,
    redis_double: InMemoryRedis,
) -> None:
    """Закрытие собственной сессии.

    Given: активная сессия пользователя,
    When: сервис закрывает её по `sid`,
    Then: сессия помечается отозванной до конца срока действия.
    """
    # Дано
    create_session = CreateSession(session_repository, TTL_SECONDS, max_active=5)
    session = await create_session(USER_ID)

    # Когда
    await CloseSession(blacklisted_tokens_repository, session_repository)(USER_ID, session.id)

    # Тогда
    key = f"session:revoked:{session.id}"
    assert redis_double.values[key] == "1"
    assert 0 < redis_double.ttl[key] <= TTL_SECONDS

    stored = await session_repository.get(session.id)
    assert stored is not None
    assert stored.revoked_at is not None


async def test_close_session_is_idempotent(
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
    session_repository: RedisSessionRepository,
) -> None:
    """Повторное закрытие сессии не поднимает ошибку.

    Given: сессия уже отозвана,
    When: сервис закрывает её повторно,
    Then: вызов завершается без ошибки.
    """
    # Дано
    create_session = CreateSession(session_repository, TTL_SECONDS, max_active=5)
    session = await create_session(USER_ID)
    close_session = CloseSession(blacklisted_tokens_repository, session_repository)
    await close_session(USER_ID, session.id)

    # Когда / Тогда
    await close_session(USER_ID, session.id)


async def test_close_session_raises_for_foreign_session(
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
    session_repository: RedisSessionRepository,
) -> None:
    """Закрытие чужой сессии отклоняется.

    Given: сессия другого пользователя,
    When: сервис пытается закрыть её от имени текущего пользователя,
    Then: он сообщает, что сессия не найдена.
    """
    # Дано
    now = datetime.now(UTC)
    foreign = Session(
        id="foreign-session",
        user_id=OTHER_USER_ID,
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    await session_repository.save(foreign)

    close_session = CloseSession(blacklisted_tokens_repository, session_repository)

    # Когда / Тогда
    with pytest.raises(SessionNotFoundError, match="Session not found"):
        await close_session(USER_ID, foreign.id)


async def test_close_session_raises_for_unknown_session(
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
    session_repository: RedisSessionRepository,
) -> None:
    """Закрытие несуществующей сессии отклоняется.

    Given: сессии с указанным `sid` нет,
    When: сервис пытается закрыть её,
    Then: он сообщает, что сессия не найдена.
    """
    # Когда / Тогда
    close_session = CloseSession(blacklisted_tokens_repository, session_repository)
    with pytest.raises(SessionNotFoundError, match="Session not found"):
        await close_session(USER_ID, "missing-session")


async def test_close_other_sessions_keeps_current(
    blacklisted_tokens_repository: RedisRevokedTokensRepository,
    session_repository: RedisSessionRepository,
) -> None:
    """Закрытие всех сессий, кроме текущей.

    Given: две активные сессии пользователя,
    When: сервис закрывает все сессии, кроме текущей,
    Then: вторая отзывается, а текущая остаётся активной.
    """
    # Дано
    now = datetime.now(UTC)
    current = Session(
        id="current-session",
        user_id=USER_ID,
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    other = Session(
        id="other-session",
        user_id=USER_ID,
        created_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(hours=1),
    )
    await session_repository.save(current)
    await session_repository.save(other)

    close_session = CloseSession(blacklisted_tokens_repository, session_repository)
    close_others = CloseOtherSessions(session_repository, close_session)

    # Когда
    await close_others(USER_ID, current.id)

    # Тогда
    stored_current = await session_repository.get(current.id)
    stored_other = await session_repository.get(other.id)
    assert stored_current is not None
    assert stored_current.revoked_at is None
    assert stored_other is not None
    assert stored_other.revoked_at is not None
