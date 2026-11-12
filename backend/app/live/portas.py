"""Portas da emissão (F3): as funções que a geração da fala chama fora dos módulos puros.

Os módulos extraídos de app/live/router.py (contexto, roteiro, geração) não importam o router nem chamam
LLM, música, notícia, TTS ou Redis de sessão diretamente: recebem um `PortasEmissao`. O router monta as
portas com ligação tardia (`ligar(globals())`): cada porta procura o nome no módulo do router no momento da
chamada. Assim os testes que trocam `app.live.router.<nome>` (gerar_resposta, buscar_musica, ...) e os dublês
do simulador continuam valendo sem editar nada, e um teste novo pode passar portas falsas direto
(docs/refatoracao.md §5, primeiro passo da injeção de dependência).
"""

import dataclasses
import typing
from typing import Any, Callable

Funcao = Callable[..., Any]


@dataclasses.dataclass(frozen=True)
class PortasEmissao:
    # LLM (app.llm.client) e notícias
    gerar_resposta: Funcao
    gerar_dialogo_multivoz: Funcao
    classificar_fio_condutor: Funcao
    pesquisar_noticias: Funcao
    proxima_noticia: Funcao
    proximas_noticias: Funcao
    proxima_para_plantao: Funcao
    correcao_pendente: Funcao
    montar_system_prompt: Funcao
    # Dados verificáveis (F5): leitura do clima com horário e fonte (app.weather.client)
    obter_leitura_clima: Funcao
    # Música e pedidos
    buscar_musica: Funcao
    buscar_musica_para_bloco: Funcao
    contexto_musica: Funcao
    historico_musicas: Funcao
    registrar_musica_tocada: Funcao
    registrar_historico_persistente: Funcao
    selecionar_pedido: Funcao
    pedidos_em_fila: Funcao
    proximo_pedido_fila: Funcao
    proximo_pedido_fila_dentre: Funcao
    pedido_recente_nao_atendido: Funcao
    ouvinte_recorrente_anterior: Funcao
    ouvinte_recorrente_dias_anteriores: Funcao
    # Promessas e participação (F4): leituras do banco
    promessas_abertas: Funcao
    nomes_da_transmissao: Funcao
    reprovar_pedido: Funcao
    # Roteiro e memória da sessão (Redis e banco)
    categoria_bloco: Funcao
    proxima_variacao: Funcao
    instrucao_transicao: Funcao
    historico_falas: Funcao
    historico_temas: Funcao
    temas_recentes_da_radio: Funcao
    ultimo_tom: Funcao
    fio_condutor: Funcao
    proximo_assunto: Funcao
    pipeline_tem_estoque: Funcao
    registrar_callback_musica: Funcao
    buscar_roster: Funcao
    # Decisão do bloco (app.live.roteiro)
    ultima_categoria_bloco: Funcao
    tipo_proximo_bloco: Funcao
    planejar_relogio: Funcao
    resolver_musica_do_relogio: Funcao
    buscar_vinheta_ativa: Funcao
    buscar_patrocinador_ativo: Funcao
    # Relógio do programa
    ajuste_energia_meio_programa: Funcao
    marco_tempo_programa: Funcao
    minutos_restantes: Funcao

    # Nome do campo -> nome no módulo do router, quando diferem (atributo de classe, não é campo).
    NO_ROUTER: typing.ClassVar[dict[str, str]] = {
        "buscar_musica_para_bloco": "_buscar_musica_para_bloco",
        "contexto_musica": "_contexto_musica",
        "historico_musicas": "_historico_musicas",
        "registrar_musica_tocada": "_registrar_musica_tocada",
        "registrar_historico_persistente": "_registrar_historico_persistente",
        "selecionar_pedido": "_selecionar_pedido_atendimento",
        "pedidos_em_fila": "_pedidos_em_fila",
        "proximo_pedido_fila": "_proximo_pedido_fila",
        "proximo_pedido_fila_dentre": "_proximo_pedido_fila_dentre",
        "pedido_recente_nao_atendido": "_pedido_recente_nao_atendido",
        "ouvinte_recorrente_anterior": "_ouvinte_recorrente_anterior",
        "ouvinte_recorrente_dias_anteriores": "_ouvinte_recorrente_dias_anteriores",
        "promessas_abertas": "_promessas_abertas",
        "nomes_da_transmissao": "_nomes_da_transmissao",
        "reprovar_pedido": "_reprovar_pedido",
        "categoria_bloco": "_categoria_bloco",
        "proxima_variacao": "_proxima_variacao",
        "instrucao_transicao": "_instrucao_transicao",
        "historico_falas": "_historico_falas",
        "historico_temas": "_historico_temas",
        "temas_recentes_da_radio": "_temas_recentes_da_radio",
        "ultimo_tom": "_ultimo_tom",
        "fio_condutor": "_fio_condutor",
        "buscar_roster": "_buscar_roster",
        "ajuste_energia_meio_programa": "_ajuste_energia_meio_programa",
        "marco_tempo_programa": "_marco_tempo_programa",
        "ultima_categoria_bloco": "_ultima_categoria_bloco",
        "tipo_proximo_bloco": "_tipo_proximo_bloco",
        "planejar_relogio": "_planejar_relogio",
        "resolver_musica_do_relogio": "_resolver_musica_do_relogio",
        "buscar_vinheta_ativa": "_buscar_vinheta_ativa",
        "buscar_patrocinador_ativo": "_buscar_patrocinador_ativo",
    }

    @classmethod
    def nomes(cls) -> tuple[str, ...]:
        return tuple(f.name for f in dataclasses.fields(cls))


def ligar(namespace: dict[str, Any]) -> PortasEmissao:
    """Portas com ligação tardia: cada chamada procura o nome em `namespace` (os globals do router) na hora."""

    def tardia(nome: str) -> Funcao:
        def chamar(*args, **kwargs):
            return namespace[nome](*args, **kwargs)

        chamar.__name__ = nome
        return chamar

    return PortasEmissao(**{campo: tardia(PortasEmissao.NO_ROUTER.get(campo, campo))
                            for campo in PortasEmissao.nomes()})
