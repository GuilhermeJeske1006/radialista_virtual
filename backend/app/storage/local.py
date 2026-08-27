from pathlib import Path

from .base import Storage


class LocalStorage(Storage):
    def __init__(self, root: str):
        self._root = Path(root)

    def save(self, path: str, content: bytes) -> None:
        destino = self._root / path
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(content)

    def read(self, path: str) -> bytes | None:
        origem = self._root / path
        if not origem.is_file():
            return None
        return origem.read_bytes()

    def delete(self, path: str) -> None:
        (self._root / path).unlink(missing_ok=True)
