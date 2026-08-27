from abc import ABC, abstractmethod


class Storage(ABC):
    """Armazenamento de arquivos enviados pelo usuario, indexado por caminho relativo
    (ex.: "biblioteca_audio/123/abcd.mp3"). Implementacoes: disco local (dev) ou S3 (producao)."""

    @abstractmethod
    def save(self, path: str, content: bytes) -> None: ...

    @abstractmethod
    def read(self, path: str) -> bytes | None:
        """Devolve o conteudo do arquivo, ou None se ele nao existir."""

    @abstractmethod
    def delete(self, path: str) -> None:
        """Remove o arquivo. Nao falha se ele nao existir."""
