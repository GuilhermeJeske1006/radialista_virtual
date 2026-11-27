"""Aplica o formato musical com curadoria a um programa existente, com backup e trava de transmissão.

python -m app.live.configurar_musical --account-id 1 --programa-id 3 [--repertorio arquivo.txt] [--aplicar]
Sem --aplicar apenas valida e mostra os campos que mudariam. O repertório é um arquivo com uma obra por linha
("Artista - Título"); sem ele o programa segue a busca normal, com as regras editoriais do formato.
`--perfil flashback` mantém o perfil legado, que traz a reserva de clássicos 1970–1999 (usado pelo programa 3).
"""
import argparse
import datetime
import json

from app.db.database import SessionLocal
from app.live.musical_curado import ID as PERFIL_CURADO, PERFIL_LEGADO_FLASHBACK, RESERVA
from app.models.biblioteca_audio import BibliotecaAudioItem
from app.models.canal_whatsapp import EstadoTransmissao
from app.models.programa import Programa
from app.models.account import Account
from app.models.radio_config import RadioConfig
from app.storage import get_storage


def configurar(db, account_id: int, programa_id: int, aplicar: bool = False, perfil: str = PERFIL_CURADO,
               repertorio: list[str] | None = None, exigir_flashback_no_nome: bool = False):
    programa = db.query(Programa).join(RadioConfig).filter(
        Programa.id == programa_id, RadioConfig.account_id == account_id).with_for_update(of=Programa).first()
    if programa is None:
        raise ValueError("Programa não encontrado nesta conta")
    if exigir_flashback_no_nome and "flashback" not in programa.nome.lower():
        raise ValueError("O piloto só se aplica a um programa de flashback")
    if perfil not in (PERFIL_CURADO, PERFIL_LEGADO_FLASHBACK):
        raise ValueError("Perfil inválido")
    if perfil == PERFIL_LEGADO_FLASHBACK and repertorio is None:
        repertorio = [f"{artista} - {titulo}" for artista, titulo in RESERVA]
    repertorio = list(repertorio or [])
    conta = db.get(Account, account_id)
    radialista = db.get(RadioConfig, programa.radio_config_id)
    agora = datetime.datetime.now(datetime.timezone.utc)
    estado = db.get(EstadoTransmissao, programa_id)
    if estado and (agora - estado.heartbeat_em.replace(tzinfo=datetime.timezone.utc)).total_seconds() < 60:
        raise ValueError("Há um player ativo; aguarde o fim da transmissão")
    vinhetas = db.query(BibliotecaAudioItem).filter_by(
        account_id=account_id, programa_id=programa_id, ativo=True).order_by(BibliotecaAudioItem.id).all()
    abertura = next((v for v in vinhetas if v.papel == "abertura"), None)
    passagem = next((v for v in vinhetas if v.papel == "passagem"), None)
    roteiro = ([f"vinheta:{abertura.id}"] if abertura else []) + [
        "abertura", "musica", "musica", "comentario", "musica", "musica", "identificacao",
        "musica", "musica", "chamada_ouvinte", "musica", "musica",
    ] + ([f"vinheta:{passagem.id}"] if passagem else []) + ["encerramento"]
    mudancas = {
        "perfil_programacao": perfil, "ia_pode_adicionar_blocos": False,
        "estrutura_blocos": roteiro,
        "tom": "animado, próximo e conciso; uma ideia por entrada, sem exageros nem bordões repetidos",
        "publico_alvo": programa.publico_alvo or f"Ouvintes adultos de {conta.cidade or 'sua cidade'} e região.",
        "musicas_permitidas": repertorio,
        "criterios_busca_musicas": "Obras do repertório aprovado; artista e título exatos. "
            "Preferir estúdio e radio edit, sem demo, cover, medley ou apresentação de TV. "
            "Separar artista por pelo menos 45 minutos; variar épocas, idioma e intensidade.",
        "mensagem_saudacao": f"{radialista.nome_locutor} no {programa.nome}, aqui na {conta.nome_radio}. "
            "Clássicos para acompanhar o seu dia!",
        "pode_pesquisar": False,
        "instrucoes_pesquisa": "Curiosidades apenas do banco editorial verificado e dos metadados confirmados; "
            "sem fonte, não afirmar ano, créditos, vendas ou bastidores. Não usar data de upload como lançamento.",
    }
    anteriores = {chave: getattr(programa, chave) for chave in mudancas}
    alterados = [chave for chave in mudancas if anteriores[chave] != mudancas[chave]]
    if not aplicar or not alterados:
        return {"programa_id": programa_id, "campos": alterados, "aplicado": False}
    backup = f"config_backups/{account_id}/musical-{programa_id}-{agora:%Y%m%dT%H%M%S}.json"
    get_storage().save(backup, json.dumps(anteriores, ensure_ascii=False).encode())
    for chave, valor in mudancas.items():
        setattr(programa, chave, valor)
    db.commit()
    return {"programa_id": programa_id, "campos": alterados, "aplicado": True, "backup": backup}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-id", type=int, required=True)
    parser.add_argument("--programa-id", type=int, required=True)
    parser.add_argument("--aplicar", action="store_true")
    parser.add_argument("--perfil", default=PERFIL_CURADO, choices=(PERFIL_CURADO, PERFIL_LEGADO_FLASHBACK))
    parser.add_argument("--repertorio", help="arquivo com uma obra por linha: Artista - Título")
    args = parser.parse_args()
    obras = None
    if args.repertorio:
        with open(args.repertorio, encoding="utf-8") as arquivo:
            obras = [linha.strip() for linha in arquivo if " - " in linha]
    with SessionLocal() as sessao:
        print(json.dumps(configurar(sessao, args.account_id, args.programa_id, args.aplicar, args.perfil, obras),
                         ensure_ascii=False))
