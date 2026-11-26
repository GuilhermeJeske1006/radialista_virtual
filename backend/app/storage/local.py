from pathlib import Path
import shutil

from .base import Storage, validar_path


class LocalStorage(Storage):
    def __init__(self, root: str):
        self._root = Path(root)

    def save(self, path: str, content: bytes) -> None:
        destino = self._root / validar_path(path)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(content)

    def read(self, path: str) -> bytes | None:
        origem = self._root / validar_path(path)
        if not origem.is_file():
            return None
        return origem.read_bytes()

    def save_file(self, path: str, filename: str) -> None:
        destino = self._root / validar_path(path)
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(filename, destino)

    def iter_read(self, path: str):
        with (self._root / validar_path(path)).open("rb") as arquivo:
            while pedaco := arquivo.read(1024 * 1024):
                yield pedaco

    def delete(self, path: str) -> None:
        (self._root / validar_path(path)).unlink(missing_ok=True)
