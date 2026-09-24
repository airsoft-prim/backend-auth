from pathlib import Path

import aiofiles


class FileRepository:
    """_summary_"""

    def __init__(self, path: Path) -> None:
        """_summary_

        Args:
            path (Path): _description_
        """
        self._path = path

    async def read(self) -> bytes:
        """_summary_

        Returns:
            bytes: _description_
        """
        async with aiofiles.open(self._path, "rb") as file:
            return await file.read()

    async def write(self, data: bytes) -> None:
        """_summary_

        Args:
            data (bytes): _description_
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(self._path, "wb") as file:
            await file.write(data)
