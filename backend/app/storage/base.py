from abc import ABC, abstractmethod
from pathlib import PurePosixPath


class CaminhoInvalido(ValueError):
    """Path de storage fora do diretorio/bucket esperado (ex.: ".." ou absoluto)."""


def validar_path(path: str) -> str:
    """Defesa em profundidade: hoje todo caminho passado a Storage e' gerado internamente
    (uuid4/nome fixo -- ver biblioteca_audio/router.py, sons_padrao.py, patrocinadores/router.py),
    nunca a partir de input de usuario direto. Se algum caminho futuro vier a incluir algo
    controlado pelo usuario, isso evita ".." escapar do diretorio local ou virar acesso a
    outra chave/objeto no bucket S3.
    """
    partes = PurePosixPath(path).parts
    if not path or path.startswith("/") or ".." in partes:
        raise CaminhoInvalido(f"Caminho de storage invalido: {path!r}")
    return path


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
