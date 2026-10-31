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
from .schemas import SessionData, SessionsList

router = APIRouter(prefix="/sessions", tags=["Сессии"])


@router.get("", **LIST_SESSIONS_DOCS)
async def list_sessions(
    current: Annotated[CurrentSession, Depends(get_current_session)],
    list_sessions_: Annotated[ListSessions, Depends(get_list_sessions)],
) -> SessionsList:
    """Функция получения активных сессий владельца токена.

    Args:
        current (CurrentSession): Владелец и `sid` сессии запроса.
        list_sessions_ (ListSessions): Use case списка активных сессий.

    Returns:
        SessionsList: Активные сессии с признаком текущей.
    """
    sessions = await list_sessions_(current.user_id)

    items = [
        SessionData(
            id=session.id,
            current=session.id == current.sid,
            created_at=session.created_at,
            expires_at=session.expires_at,
            ip=session.ip,
            platform=session.platform,
            browser=session.browser,
            location=session.location,
        )
        for session in sessions
    ]

    return SessionsList(sessions=items)


@router.delete("/{session_id}", response_class=Response, **CLOSE_SESSION_DOCS)
async def close_session(
    session_id: Annotated[str, Path(description="Идентификатор сессии (`sid`).")],
    current: Annotated[CurrentSession, Depends(get_current_session)],
    close: Annotated[CloseSession, Depends(get_close_session)],
) -> None:
    """Функция закрытия выбранной сессии.

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
    """Функция закрытия всех сессий, кроме текущей.

    Args:
        current (CurrentSession): Владелец и `sid` сессии запроса.
        close_others (CloseOtherSessions): Use case закрытия всех сессий, кроме текущей.
    """
    await close_others(current.user_id, current.sid)
