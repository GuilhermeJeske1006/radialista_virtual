import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class BibliotecaAudioItem(Base):
    """Um audio proprio da conta (vinheta, efeito, jingle) disponivel pro cartwall da tela
    /live e pra Programa.estrutura_blocos (bloco "vinheta:<id>"). Ver app/biblioteca_audio/router.py.

    Tambem guarda as vinhetas geradas automaticamente pra cada programa (origem="auto", ver
    app/vinhetas/servico.py): voz TTS processada mixada sobre uma TrilhaVinheta. Essas nascem
    com status="pendente" e sem audio_path -- o arquivo final so' existe depois do job de audio.
    """

    __tablename__ = "biblioteca_audio_itens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)

    nome: Mapped[str] = mapped_column(String)

    # Categoria de vinhetagem (ver CategoriaVinheta). Nulo = "Sem categoria".
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categorias_vinheta.id"), nullable=True, index=True)

    # Caminho relativo dentro de settings.upload_dir. Nulo so' em vinheta gerada que ainda nao
    # terminou de mixar (ou falhou antes de ter qualquer audio).
    audio_path: Mapped[str | None] = mapped_column(String, nullable=True)
    audio_nome_original: Mapped[str | None] = mapped_column(String, nullable=True)

    duracao_segundos: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Cor hex opcional pro card no cartwall (ex.: "#E8A33D").
    cor: Mapped[str | None] = mapped_column(String, nullable=True)

    # Posicao no cartwall.
    ordem: Mapped[int] = mapped_column(Integer, default=0)

    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- Vinheta gerada (ver app/vinhetas/) -- tudo nulo/default em upload manual. ---

    # Programa dono da vinheta. Nulo = vinheta avulsa da conta.
    programa_id: Mapped[int | None] = mapped_column(ForeignKey("programas.id"), nullable=True, index=True)

    # "abertura" | "passagem" | "encerramento" -- decide o preset de mixagem e onde entra no roteiro.
    papel: Mapped[str | None] = mapped_column(String, nullable=True)

    # O que e' falado. Tambem e' o fallback do ao vivo (TTS na hora) enquanto nao ha audio_path.
    texto: Mapped[str | None] = mapped_column(String, nullable=True)

    # Nulo = voz do radialista dono do programa.
    voz_id: Mapped[str | None] = mapped_column(String, nullable=True)

    # Voz seca ja processada (sem trilha) -- guardada pra remixar sem pagar TTS de novo.
    voz_path: Mapped[str | None] = mapped_column(String, nullable=True)

    trilha_id: Mapped[int | None] = mapped_column(ForeignKey("trilhas_vinheta.id"), nullable=True, index=True)
    volume_trilha_db: Mapped[float] = mapped_column(Float, default=-14.0)
    usar_trilha: Mapped[bool] = mapped_column(Boolean, default=True)

    # "pendente" | "gerando" | "pronta" | "erro". Upload manual ja nasce "pronta".
    status: Mapped[str] = mapped_column(String, default="pronta")
    erro_msg: Mapped[str | None] = mapped_column(String, nullable=True)

    # "auto" (criada junto com o programa) | "manual" (upload do usuario).
    origem: Mapped[str] = mapped_column(String, default="manual")

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
