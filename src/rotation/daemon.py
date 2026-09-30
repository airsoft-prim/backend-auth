import asyncio
from asyncio import EventLoop
from datetime import UTC, datetime
from itertools import pairwise

from croniter import croniter
from loguru import logger

from src.services.jwk import JWKGenerationService


# TODO: Реализовать
class JWKRotationDaemon:
    """Демон ротации приватного JWK.

    Планирует ротацию по cron-правилу: рассчитывает момент следующего запуска и
    просыпается к нему, после чего инициирует генерацию нового приватного JWK.
    Первый запуск выполняется сразу при старте, не дожидаясь ближайшего момента по
    расписанию, — иначе сервис оставался бы без ключа подписи до него.
    """

    def __init__(
        self,
        jwk_service: JWKGenerationService,
        cron_rule: str,
        initial_overwrite: bool = False,
        *,
        event_loop: EventLoop | None = None,
    ) -> None:
        """Инициализация класса.

        Args:
            jwk_service (JWKGenerationService): Сервис генерации и публикации JWK.
            cron_rule (str): Cron-правило расписания, по которому рассчитываются моменты
                ротации.
            initial_overwrite (bool, optional): Признак перезаписи приватного JWK при первом
                запуске демона. `True` — ключ генерируется заново, даже если уже существует,
                что приводит к перезаписи ключа после каждого рестрарта приложения.
                `False` — используется существующий ключ, если такой имеется.
                Defaults to False.
            event_loop (EventLoop | None, optional): Цикл событий для планировщика; передаётся
                только как именованный аргумент. Если не передан или уже закрыт, используется
                текущий запущенный цикл. Defaults to None.
        """
        self._rotation_clock = croniter(cron_rule, self._current_time(), ret_type=datetime)
        self._event_loop = event_loop

        self._jwk_service = jwk_service

        self._initial_overwrite = initial_overwrite
        self._first_iteration = True

    def start(self) -> None:
        """Запускает демон ротации.

        Ставит задачу планировщика в цикл событий. Ссылка на задачу не сохраняется:
        демон работает до остановки цикла.
        """
        if not self._event_loop or self._event_loop.is_closed():
            self._event_loop = asyncio.get_running_loop()

        self._event_loop.create_task(self._handle_rotation())

    def _current_time(self) -> datetime:
        """Возвращает текущий момент времени в UTC.

        Returns:
            datetime: Текущий момент времени с зоной UTC.
        """
        return datetime.now(UTC)

    async def _handle_rotation(self) -> None:
        """Бесконечно повторяет цикл «дождаться момента ротации — выполнить ротацию».

        Первая итерация выполняется без ожидания, для последующих интервал ожидания
        пересчитывается по cron-расписанию. Время жизни ключей прошлых ротаций берётся
        равным интервалу между соседними моментами ротации: такой ключ остаётся в наборе
        JWKS до следующей ротации.
        """
        for execution_time, next_execution_time in pairwise(self._rotation_clock.all_next()):
            if not self._first_iteration:
                logger.debug(f"Next Private JWK rotation time - {execution_time}")
                wait_time = (execution_time - self._current_time()).total_seconds()

            else:
                wait_time = 0

            await asyncio.sleep(wait_time)
            await self._rotate(int((next_execution_time - execution_time).total_seconds()))

            self._first_iteration = False

    async def _rotate(self, rotated_ttl: int) -> None:
        """Генерирует или ротирует приватный JWK.

        Args:
            rotated_ttl (int): Время жизни в секундах, назначаемое публичным ключам прошлых
                ротаций.
        """
        if self._first_iteration:
            logger.info("Generating Private JWK...")
            overwrite = self._initial_overwrite

        else:
            logger.info("Rotating previosly generated Private JWK...")
            overwrite = True

        await self._jwk_service.generate_jwk(rotated_ttl, overwrite=overwrite)
