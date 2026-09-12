import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.database import Base


class GeracaoIA(Base):
    """Registro de cada geracao/refinamento via IA de radialista+programa (ver Fase 10 do plano
    de melhoria) -- loop de aprendizado: `proposta` e' o que a IA devolveu, `proposta_final` e'
    o que de fato foi commitado (POST /gerar-ia/commit ou .../programas) depois do cliente
    revisar/editar na tela de preview. O diff entre os dois aponta exatamente que campos a IA
    erra sistematicamente, pra alimentar os exemplos de prompt (ver app.llm.exemplos_config) com
    configuracoes reais aceitas em vez de exemplos escritos a mao.

    `edicoes_48h` fica vazio por enquanto -- reservado pra um job futuro que recalcula o diff
    depois que o cliente teve tempo de editar a configuracao pos-commit (nao implementado
    nesta fase; ver Fase 10 do plano)."""

    __tablename__ = "geracoes_ia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)

    # radialista (par persona+programa) | programa (programa avulso) | refinamento (Fase 7:
    # persona/programa/ajuste sobre uma proposta ja existente)
    tipo: Mapped[str] = mapped_column(String)

    descricao: Mapped[str] = mapped_column(String, default="")

    # Snapshot do contexto passado ao prompt (tipo_radio, dados da conta, tamanho do roster
    # existente etc.) -- nao o prompt inteiro, so' o suficiente pra entender o que influenciou
    # essa geracao especifica.
    contexto_usado: Mapped[dict] = mapped_column(JSON, default=dict)

    proposta: Mapped[dict] = mapped_column(JSON, default=dict)

    aceita: Mapped[bool] = mapped_column(Boolean, default=False)
    proposta_final: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    edicoes_48h: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
