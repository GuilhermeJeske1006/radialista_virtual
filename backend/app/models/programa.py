import datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Programa(Base):
    """Um programa (atracao) de um radialista: horario de exibicao + todo o
    conteudo e regras usados ao vivo (tom, topicos, musicas, noticias, pesquisa).
    """

    __tablename__ = "programas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    radio_config_id: Mapped[int] = mapped_column(ForeignKey("radio_configs.id"), index=True)

    nome: Mapped[str] = mapped_column(String)

    # Dias da semana em que o programa vai ao ar (0=segunda ... 6=domingo). Vazio = todos os dias.
    # Ignorado quando data_especifica esta preenchida.
    dias_semana: Mapped[list[int]] = mapped_column(JSON, default=list)

    # Quando preenchida, o programa e "avulso": vai ao ar so nessa data, uma unica vez, e dias_semana e ignorado.
    data_especifica: Mapped[datetime.date | None] = mapped_column(Date, nullable=True, default=None)

    horario_inicio: Mapped[datetime.time] = mapped_column(Time)
    horario_fim: Mapped[datetime.time] = mapped_column(Time)

    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    tom: Mapped[str] = mapped_column(
        String, default="informal e descontraido, como um locutor de radio local conversando com o ouvinte"
    )
    topicos_permitidos: Mapped[list[str]] = mapped_column(JSON, default=list)
    topicos_proibidos: Mapped[list[str]] = mapped_column(JSON, default=list)
    mensagem_saudacao: Mapped[str] = mapped_column(String, default="E ai! No que posso ajudar?")
    mensagem_recusa: Mapped[str] = mapped_column(
        String, default="Desculpa, nao posso falar sobre isso por aqui. Bora falar de outro assunto?"
    )
    limite_mensagens_hora: Mapped[int] = mapped_column(Integer, default=10)

    generos_musicais: Mapped[list[str]] = mapped_column(JSON, default=list)
    musicas_permitidas: Mapped[list[str]] = mapped_column(JSON, default=list)
    musicas_bloqueadas: Mapped[list[str]] = mapped_column(JSON, default=list)
    criterios_busca_musicas: Mapped[str] = mapped_column(
        String,
        default="Priorizar musicas alinhadas ao perfil da radio, evitar letras explicitas e variar artistas.",
    )

    assuntos_ao_vivo: Mapped[list[str]] = mapped_column(JSON, default=list)
    tipos_noticias: Mapped[list[str]] = mapped_column(JSON, default=list)
    fontes_noticias: Mapped[list[str]] = mapped_column(JSON, default=list)

    pode_pesquisar: Mapped[bool] = mapped_column(Boolean, default=False)
    fontes_pesquisa: Mapped[list[str]] = mapped_column(JSON, default=list)
    instrucoes_pesquisa: Mapped[str] = mapped_column(
        String,
        default="Quando a pesquisa estiver habilitada, consulte apenas fontes permitidas e sinalize incertezas.",
    )

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
