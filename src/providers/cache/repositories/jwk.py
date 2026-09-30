from collections.abc import Sequence
import json
from string import Template

from jwt.types import JWKDict

from ._base import RedisRepository


class PublicJWKRepository(RedisRepository):
    """Репозитория для взаимодействия с публичными JWK ключами в Redis.

    На каждый ключ хранится одно значение — публичный JWK в JSON по RFC 7517.
    """

    _key_template = Template("jwk:$kid")

    async def store(self, kid: str, jwk: JWKDict) -> None:
        """Сохраняет публичный JWK по его `kid`.

        Args:
            kid (str): Идентификатор ключа (`kid`).
            jwk (JWKDict): Публичный JWK.

        Raises:
            RepositoryError: Если обращение к Redis завершилось ошибкой.
        """
        key = self.compile_template({"kid": kid})
        payload = json.dumps(jwk)

        with self._as_repository_error("Public JWK saving error."):
            await self.client.set(key, payload)

    async def acquire(self, kid: str) -> JWKDict | None:
        """Возвращает публичный JWK по его `kid`.

        Args:
            kid (str): Идентификатор ключа (`kid`).

        Raises:
            RepositoryError: Если обращение к Redis завершилось ошибкой.

        Returns:
            JWKDict | None: Публичный JWK или None, если ключ не опубликован.
        """
        key = self.compile_template({"kid": kid})

        with self._as_repository_error("Public JWK getting error."):
            payload = await self.client.get(key)

        return json.loads(payload) if payload is not None else payload

    async def acquire_all(self) -> Sequence[JWKDict]:
        """Возвращает все опубликованные публичные JWK.

        Raises:
            RepositoryError: Если обращение к Redis завершилось ошибкой.

        Returns:
            Sequence[JWKDict]: Публичные JWK из кеша.
        """
        # Пустые значения шаблона компилируются в glob-маску: jwk:*.
        pattern = self.compile_template({})

        with self._as_repository_error("Public JWK listing error."):
            keys = [key async for key in self.client.scan_iter(match=pattern)]
            payloads = await self.client.mget(keys)

        return [json.loads(payload) for payload in payloads if payload is not None]

    async def expire_rotated(self, generated_kid: str, ttl: int) -> None:
        """Назначает время жизни публичным JWK, чьи приватные пары были ротированы.

        Затрагиваются все опубликованные ключи, кроме только что созданного: выданные ранее
        токены остаются проверяемыми до истечения `ttl`.

        Args:
            generated_kid (str): Идентификатор (`kid`) нового ключа — его время жизни не
                ограничивается.
            ttl (int): Время жизни прошлых ключей в секундах.

        Raises:
            RepositoryError: Если обращение к Redis завершилось ошибкой.
        """
        # Пустые значения шаблона компилируются в glob-маску: jwk:*.
        pattern = self.compile_template({})
        fresh_key = self.compile_template({"kid": generated_kid})

        with self._as_repository_error("Rotated public JWK expiring error."):
            keys = [key async for key in self.client.scan_iter(match=pattern)]
            rotated_keys = [key for key in keys if key != fresh_key]

            async with self.client.pipeline(transaction=False) as pipeline:
                for key in rotated_keys:
                    pipeline.expire(key, ttl)

                await pipeline.execute()
