"""Validação determinística. A correspondência semântica exige revisão humana."""
import datetime as dt
import hashlib
import json
from urllib.parse import urlsplit

from app.esportes.schemas import Bloco, ConteudoEdicao

UTC = dt.timezone.utc


def agora():
    return dt.datetime.now(UTC)


def assinatura(dados) -> str:
    return hashlib.sha256(json.dumps(dados, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def espelho(modelo: str) -> list[Bloco]:
    if modelo != "programa_30":
        tempos = [10, 75, 25, 10] if modelo == "boletim_2" else [15, 115, 35, 15]
        itens = [("abertura", "Abertura"), ("noticias", "Notícias verificadas"), ("agenda", "Agenda"), ("encerramento", "Encerramento")]
    else:
        tempos = [60, 300, 300, 60, 300, 180, 60, 180, 240, 120]
        itens = [("abertura", "Abertura e pergunta do dia"), ("noticias", "Esporte regional"),
                 ("noticias", "Futebol nacional"), ("intervalo", "Intervalo 1"), ("analise", "Pauta principal"),
                 ("noticias", "Internacional e outras modalidades"), ("intervalo", "Intervalo 2"),
                 ("torcida", "Torcida ou quadro de reserva"), ("agenda", "Agenda esportiva"), ("encerramento", "Encerramento")]
    return [Bloco(id=f"bloco_{i + 1}", titulo=titulo, tipo=tipo, duracao_s=tempo,
                  responsavel="Operador" if tipo == "intervalo" else "Apresentador",
                  transicao="Vinheta breve" if tipo not in ("abertura", "encerramento") else "",
                  opcional=tipo in ("analise", "torcida"),
                  reserva="Usar explicação de regra ou curiosidade verificada aprovada; reduzir se não houver material." if tipo in ("analise", "torcida") else "")
            for i, ((tipo, titulo), tempo) in enumerate(zip(itens, tempos))]


def alertas(conteudo: ConteudoEdicao, fontes: dict, instante=None) -> list[str]:
    instante = instante or agora()
    limite = max(instante, conteudo.exibicao_em) + dt.timedelta(seconds=sum(b.duracao_s for b in conteudo.blocos))
    erros = []
    usados = {fid for b in conteudo.blocos for fid in b.fato_ids}
    fatos = {f.id: f for f in conteudo.fatos}
    repetidos = set()
    for b in conteudo.blocos:
        if not b.texto.strip():
            erros.append(f"{b.titulo}: preencha o roteiro ou a chamada do intervalo.")
        if b.tipo not in ("abertura", "encerramento", "intervalo") and not b.fato_ids:
            erros.append(f"{b.titulo}: vincule fatos e evidências, inclusive no quadro de reserva.")
        if b.opcional and not b.reserva.strip():
            erros.append(f"{b.titulo}: descreva a reserva editorial.")
        if any(termo in b.texto.lower() for termo in ("neste momento", "ao vivo", "agora mesmo")):
            erros.append(f"{b.titulo}: retire expressões de atualização ao vivo da edição pré-gravada.")
        for fid in b.fato_ids:
            f = fatos[fid]
            # Uma origem republicada continua sendo um só acontecimento.
            chave = (f.evento.casefold(), f.tipo, f.origem_comum.casefold())
            if chave in repetidos and b.tipo not in ("abertura", "encerramento", "analise"):
                erros.append(f"{b.titulo}: fato já usado em outro bloco; revise a repetição.")
            repetidos.add(chave)
    for f in conteudo.fatos:
        if f.id not in usados:
            continue
        prefixo = f"Fato {f.id}"
        fonte = fontes.get(f.fonte_id)
        if not fonte or not fonte.dados["ativa"]:
            erros.append(f"{prefixo}: fonte ausente ou bloqueada.")
        elif f.fonte_revisao != fonte.revisao:
            erros.append(f"{prefixo}: cadastro da fonte mudou; confira a evidência e vincule a revisão atual.")
        elif urlsplit(f.url).hostname.lower().rstrip(".") != fonte.dominio:
            erros.append(f"{prefixo}: a página deve pertencer ao domínio exato aprovado.")
        if f.valido_ate <= limite:
            erros.append(f"{prefixo}: validade insuficiente até o fim da exibição.")
        if f.coletado_em > instante or f.publicado_em > instante:
            erros.append(f"{prefixo}: publicação ou coleta no futuro.")
        if not f.revisado:
            erros.append(f"{prefixo}: evidência ainda não revisada pelo editor.")
        if f.sensivel and not f.revisao_sensivel:
            erros.append(f"{prefixo}: tema sensível exige revisão humana específica.")
        if f.confirmacao == "contestado":
            erros.append(f"{prefixo}: fontes divergentes; resolva a apuração antes de escrever.")
        if f.tipo == "agenda" and (f.ocorrido_em <= limite or f.confirmacao in ("adiado", "cancelado")):
            erros.append(f"{prefixo}: agenda vencida, adiada ou cancelada; revise a pauta antes da reprodução.")
        if f.tipo == "resultado" and f.ocorrido_em > instante:
            erros.append(f"{prefixo}: evento futuro não pode ter resultado final.")
        if f.tipo == "resultado" and f.confirmacao != "encerrado":
            erros.append(f"{prefixo}: resultado final exige evento encerrado.")
        if f.tipo == "escalacao" and (f.confirmacao != "confirmado" or not f.oficial):
            erros.append(f"{prefixo}: o piloto só aceita escalação oficialmente confirmada.")
        if f.tipo == "transferencia" and f.confirmacao != "confirmado":
            erros.append(f"{prefixo}: negociação não é transferência confirmada.")
        # Duas evidências sobre o mesmo resultado não podem discordar silenciosamente.
        if f.tipo == "resultado":
            resultados = [outro for outro in conteudo.fatos if outro.id in usados and outro.evento.casefold() == f.evento.casefold() and outro.tipo == "resultado"]
            if any((outro.participantes, outro.placar, outro.competicao, outro.confirmacao) != (f.participantes, f.placar, f.competicao, f.confirmacao) for outro in resultados):
                erros.append(f"{prefixo}: resultados divergentes para o mesmo evento.")
    return list(dict.fromkeys(erros))


def alertas_audio(edicao, conteudo):
    erros = []
    for b in conteudo.blocos:
        audio = edicao.audios.get(b.id)
        if not audio or audio["assinatura"] != assinatura(edicao.dados):
            erros.append(f"{b.titulo}: áudio da versão atual pendente.")
    if not erros:
        total = sum(a["duracao_s"] for a in edicao.audios.values())
        alvo = sum(b.duracao_s for b in conteudo.blocos)
        if abs(total - alvo) > 5:
            erros.append(f"Áudios somam {total:.1f}s; ajuste o roteiro ou as inserções até {alvo}s (tolerância de 5s). Nenhuma fala será cortada.")
    return erros


def estado(edicao, erros):
    usados = {fid for b in edicao.dados["blocos"] for fid in b["fato_ids"]}
    if any(f["id"] in usados and dt.datetime.fromisoformat(f["valido_ate"].replace("Z", "+00:00")) <= agora() for f in edicao.dados["fatos"]):
        return "expirado"
    if erros:
        return "bloqueado" if edicao.aprovacao_roteiro else "rascunho"
    if edicao.aprovacao_audio:
        return "aprovado"
    if edicao.audios:
        return "audio_pronto" if not alertas_audio(edicao, ConteudoEdicao(**edicao.dados)) else "em_producao"
    return "roteiro_aprovado" if edicao.aprovacao_roteiro else "em_revisao"
