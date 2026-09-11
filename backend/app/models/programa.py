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

    # Texto livre explicando do que se trata o programa (formato, proposta, publico) --
    # da mais contexto pro agente alem do tom e dos topicos permitidos.
    descricao: Mapped[str] = mapped_column(String, default="")

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
    limite_mensagens_hora: Mapped[int] = mapped_column(Integer, default=1000)

    # Sequencia pre-estabelecida de blocos do programa (ex.: ["abertura", "saudacao", "musica",
    # "abertura", "noticia", "musica"]). Guia a ordem do ao vivo; a IA segue essa estrutura mas
    # pode inserir blocos extras entre os definidos quando ia_pode_adicionar_blocos for True.
    estrutura_blocos: Mapped[list[str]] = mapped_column(JSON, default=list)
    perfil_programacao: Mapped[str] = mapped_column(String, default="padrao")
    ia_pode_adicionar_blocos: Mapped[bool] = mapped_column(Boolean, default=True)

    generos_musicais: Mapped[list[str]] = mapped_column(JSON, default=list)
    musicas_permitidas: Mapped[list[str]] = mapped_column(JSON, default=list)
    musicas_bloqueadas: Mapped[list[str]] = mapped_column(JSON, default=list)
    criterios_busca_musicas: Mapped[str] = mapped_column(
        String,
        default="Priorizar musicas alinhadas ao perfil da radio, evitar letras explicitas e variar artistas.",
    )
    # Titulo+artista (ex.: "Lofi Chill Beats - Instrumental") que o usuario escolheu como musica de
    # fundo fixa, tocada em loop enquanto o locutor fala em vez do genero sorteado aleatoriamente
    # (ver buscar_musica_fundo em app.live.music). Vazio = mantem o comportamento atual (sorteio).
    musica_fundo_escolhida: Mapped[str] = mapped_column(String, default="")

    assuntos_ao_vivo: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Quadros fixos do programa: label (que tambem deve estar em estrutura_blocos, ex.
    # "Curiosidade das 10") -> pool de conteudos possiveis pra esse quadro. Cada vez que o bloco com
    # esse label sai no roteiro, um item do pool e' sorteado em rotacao (ver _proxima_variacao em
    # app.live.router) -- da identidade fixa e reconhecivel ao quadro, com conteudo sempre novo.
    quadros_fixos: Mapped[dict[str, list[str]]] = mapped_column(JSON, default=dict)

    # Feriados municipais (cadastro manual: [{"data": "MM-DD", "nome": "..."}]) -- ao contrario
    # do feriado nacional (calculado por formula, ver app.feriados), nao da pra calcular nem
    # existe fonte gratuita confiavel pras ~5000 cidades brasileiras, entao e' o usuario quem
    # informa (mesmo padrao de assuntos_ao_vivo/musicas_bloqueadas).
    feriados_municipais: Mapped[list[dict]] = mapped_column(JSON, default=list)
    tipos_noticias: Mapped[list[str]] = mapped_column(JSON, default=list)
    fontes_noticias: Mapped[list[str]] = mapped_column(JSON, default=list)

    pode_pesquisar: Mapped[bool] = mapped_column(Boolean, default=False)
    fontes_pesquisa: Mapped[list[str]] = mapped_column(JSON, default=list)
    instrucoes_pesquisa: Mapped[str] = mapped_column(
        String,
        default="Quando a pesquisa estiver habilitada, consulte apenas fontes permitidas e sinalize incertezas.",
    )

    # Preset de criacao (ver Fase 4 do plano de jornalismo): musical | jornalismo | esportivo |
    # variedades | religioso | comunitario. So preenche campos no momento da criacao -- nao trava
    # nada em runtime, o usuario edita os campos normalmente depois (ver app.config.router).
    perfil: Mapped[str] = mapped_column(String, default="musical")

    # Dosagem de noticia (ver Fase 5 do plano de jornalismo) -- noticia nao e' so' do perfil
    # "jornalismo": qualquer programa pode ter um pouco, regulado por aqui.
    # nenhuma | pitada | equilibrada | jornalistica. Default "jornalistica" (sem restricao de
    # categoria) preserva o comportamento anterior a esse campo existir -- "pitada", o default
    # sugerido pro preset musical, so' se aplica a partir da criacao via esse preset.
    dose_noticia: Mapped[str] = mapped_column(String, default="jornalistica")

    # Texto livre, mais rico que assuntos_ao_vivo: quem de fato ouve este programa (ver Fase H do
    # plano-assuntos.md). Opcional -- app.topics.reserva deriva um briefing de publico a partir de
    # horario/generos/tom/cidade/interacao quando este campo estiver vazio (ver ADR item 4), entao
    # a ausencia dele nao trava a reserva estrategica, so' a deixa mais generica.
    publico_alvo: Mapped[str] = mapped_column(String, default="")

    # Quao informado e' o comentario livre: leve (papo, so' cai pro assunto quando render natural)
    # | equilibrada | informado (prioriza assunto com fatos sobre papo sem pauta). Ver Fase H do
    # plano-assuntos.md -- mesmo espirito de dose_noticia, mas pro banco de assuntos.
    densidade_assunto: Mapped[str] = mapped_column(String, default="leve")

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
