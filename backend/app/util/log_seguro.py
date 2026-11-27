"""Mascara segredos em logs e eventos do Sentry.

A chave da YouTube Data API ia na query string e aparecia na URL impressa pelo logger do httpx
(INFO) e nas mensagens de HTTPStatusError, que seguem para o Sentry Logs. Mascarar na saída cobre
também segredos que ainda não conhecemos (api_key, token, access_token).
"""
import logging
import re

_PADRAO = re.compile(r"""(?P<nome>\b(?:key|api_key|apikey|token|access_token)=)[^&\s"'<>]+""", re.IGNORECASE)
_BEARER = re.compile(r"(?i)(authorization['\"]?\s*[:=]\s*['\"]?(?:bearer|basic)\s+)[^\s'\"]+")
MASCARA = "***"


def mascarar(texto):
    if not isinstance(texto, str) or not texto:
        return texto
    texto = _PADRAO.sub(lambda m: m.group("nome") + MASCARA, texto)
    return _BEARER.sub(lambda m: m.group(1) + MASCARA, texto)


class FiltroSegredos(logging.Filter):
    """Reescreve a mensagem já formatada; mantém exc_info (o traceback é mascarado ao formatar)."""

    def filter(self, record):
        try:
            mensagem = record.getMessage()
        except Exception:  # noqa: BLE001 - nunca derrubar o log por formatação
            return True
        mascarada = mascarar(mensagem)
        if mascarada != mensagem:
            record.msg, record.args = mascarada, None
        if record.exc_info and not record.exc_text:
            record.exc_text = mascarar(logging.Formatter().formatException(record.exc_info))
        elif record.exc_text:
            record.exc_text = mascarar(record.exc_text)
        return True


def _varrer(valor):
    if isinstance(valor, str):
        return mascarar(valor)
    if isinstance(valor, dict):
        return {k: _varrer(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_varrer(v) for v in valor]
    if isinstance(valor, tuple):
        return tuple(_varrer(v) for v in valor)
    return valor


def sentry_before_send(evento, _hint=None):
    return _varrer(evento)


def sentry_before_send_log(log, _hint=None):
    return _varrer(log)


def configurar_logging(handlers=None, nivel=logging.INFO):
    """basicConfig com filtro de segredos em todos os handlers (o log INFO do httpx fica, útil para contar chamadas)."""
    logging.basicConfig(level=nivel, handlers=handlers)
    filtro = FiltroSegredos()
    for handler in logging.getLogger().handlers:
        if not any(isinstance(f, FiltroSegredos) for f in handler.filters):
            handler.addFilter(filtro)
