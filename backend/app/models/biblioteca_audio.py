import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class BibliotecaAudioItem(Base):
    """Um audio proprio da conta (vinheta, efeito, jingle) disponivel pro cartwall da tela
    /live -- disparo manual sob demanda, fora de Programa.estrutura_blocos. Ver app/biblioteca_audio/router.py.
    """

    __tablename__ = "biblioteca_audio_itens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)

    nome: Mapped[str] = mapped_column(String)

    # Categoria de vinhetagem (ver CategoriaVinheta). Nulo = "Sem categoria".
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categorias_vinheta.id"), nullable=True, index=True)

    # Caminho relativo dentro de settings.upload_dir.
    audio_path: Mapped[str] = mapped_column(String)
    audio_nome_original: Mapped[str] = mapped_column(String)

    duracao_segundos: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Cor hex opcional pro card no cartwall (ex.: "#E8A33D").
    cor: Mapped[str | None] = mapped_column(String, nullable=True)

    # Posicao no cartwall.
    ordem: Mapped[int] = mapped_column(Integer, default=0)

    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
