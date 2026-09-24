from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Identity,
    Index,
    MetaData,
    String,
    false,
    func,
    text,
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.general.enums import UserRole

# Единый naming convention: Alembic генерирует миграции,
# имена констрейнтов и индексов в них консистентны.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class BaseModel(AsyncAttrs, DeclarativeBase):
    """Базовый класс всех ORM-моделей.

    AsyncAttrs даёт awaitable_attrs: ленивая загрузка отношений
    в асинхронном коде через `await obj.awaitable_attrs.<relation>`.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampedModel(BaseModel):
    """Класс моделей с временными метками.

    Метки проставляются на стороне PostgreSQL (`now()`):
    значения не зависят от часов и таймзоны инстанса приложения.
    """

    __abstract__ = True

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class User(TimestampedModel):
    """Игрок, зарегистрированный на портале."""

    __tablename__ = "users"
    __table_args__ = (
        Index("uq_users_email_lower", text("lower(email)"), unique=True),
        {"schema": "auth"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(255))

    pswd_hash: Mapped[str] = mapped_column(String(255))
    last_pswd_change: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    system_role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            schema="auth",
            values_callable=UserRole.values,
        ),
        default=UserRole.USER,
        server_default=UserRole.USER.value,
    )

    disabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
