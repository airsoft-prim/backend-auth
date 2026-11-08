from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response

from src.application.session import CloseOtherSessions, CloseSession, ListSessions

from .deps import (
    CurrentSession,
    get_close_other_sessions,
    get_close_session,
    get_current_session,
    get_list_sessions,
)
from .docs import CLOSE_OTHER_SESSIONS_DOCS, CLOSE_SESSION_DOCS, LIST_SESSIONS_DOCS
from .schemas import SessionData

router = APIRouter(prefix="/sessions", tags=["Сессии"])


@router.get("", **LIST_SESSIONS_DOCS)
async def get_all_sessions(
    current: Annotated[CurrentSession, Depends(get_current_session)],
    list_sessions: Annotated[ListSessions, Depends(get_list_sessions)],
) -> list[SessionData]:
    """Возвращает активные сессии владельца `refresh`-токена.

    Args:
        current (CurrentSession): Владелец и `sid` сессии запроса.
        list_sessions (ListSessions): Use case списка активных сессий.

    Returns:
        list[SessionData]: Активные сессии с признаком текущей.
    """
    sessions = await list_sessions(current.user_id)

    # TODO: Упросить валидацию до from_attributes
    return [
        SessionData(
            id=session.id,
            current=session.id == current.sid,
            created_at=session.created_at,
            expires_at=session.expires_at,
            ip=session.ip,
            platform=session.platform,
            browser=session.browser,
        )
        for session in sessions
    ]


@router.delete("/{session_id}", response_class=Response, **CLOSE_SESSION_DOCS)
async def close_session(
    session_id: Annotated[str, Path(description="Идентификатор сессии.")],
    current: Annotated[CurrentSession, Depends(get_current_session)],
    close: Annotated[CloseSession, Depends(get_close_session)],
) -> None:
    """Закрывает выбранную сессию текущего пользователя.

    Args:
        session_id (str): Идентификатор закрываемой сессии (`sid`).
        current (CurrentSession): Владелец сессии запроса.
        close (CloseSession): Use case закрытия одной сессии.
    """
    await close(current.user_id, session_id)


@router.delete("", response_class=Response, **CLOSE_OTHER_SESSIONS_DOCS)
async def close_other_sessions(
    current: Annotated[CurrentSession, Depends(get_current_session)],
    close_others: Annotated[CloseOtherSessions, Depends(get_close_other_sessions)],
) -> None:
    """Закрывает сессии пользователя, кроме текущей.

    Args:
        current (CurrentSession): Владелец и `sid` сессии запроса.
        close_others (CloseOtherSessions): Use case закрытия всех сессий, кроме текущей.
    """
    await close_others(current.user_id, current.sid)
