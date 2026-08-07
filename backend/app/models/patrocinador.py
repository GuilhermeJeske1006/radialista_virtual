import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Patrocinador(Base):
    """Um patrocinador/anunciante da radio: conteudo fixo (texto ou audio pre-gravado)
    que o usuario insere em posicoes especificas de Programa.estrutura_blocos, no formato
    "patrocinador:<id>" -- ver app/live/router.py.
    """

    __tablename__ = "patrocinadores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)

    nome: Mapped[str] = mapped_column(String)

    # "texto" (lido pelo TTS do locutor) ou "audio" (arquivo pre-gravado do proprio anunciante).
    tipo_conteudo: Mapped[str] = mapped_column(String, default="texto")

    texto: Mapped[str | None] = mapped_column(String, nullable=True)

    # Voz especifica pra ler este patrocinador (catalogo em app/tts/voices.py). So usado quando
    # tipo_conteudo == "texto"; nulo = usa a voz do radialista que estiver no ar.
    voz_id: Mapped[str | None] = mapped_column(String, nullable=True)

    # Caminho relativo dentro de settings.upload_dir. Nulo quando tipo_conteudo == "texto".
    audio_path: Mapped[str | None] = mapped_column(String, nullable=True)
    audio_nome_original: Mapped[str | None] = mapped_column(String, nullable=True)

    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
