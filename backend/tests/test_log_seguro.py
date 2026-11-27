import logging

from app.util.log_seguro import FiltroSegredos, mascarar, sentry_before_send


def test_mascara_chave_na_url_e_variantes():
    url = "GET https://www.googleapis.com/youtube/v3/search?key=SEGREDO123&part=snippet&q=a+b"
    assert "SEGREDO123" not in mascarar(url)
    assert "key=***&part=snippet" in mascarar(url)
    assert mascarar("token=abc123 e api_key=zzz") == "token=*** e api_key=***"
    assert "XYZ" not in mascarar("Authorization: Bearer XYZ")
    assert mascarar("sem segredo aqui") == "sem segredo aqui"


def test_filtro_mascara_mensagem_formatada_e_traceback(caplog):
    logger = logging.getLogger("teste.log_seguro")
    registros = []

    class _H(logging.Handler):
        def emit(self, record):
            registros.append(self.format(record))

    h = _H()
    h.addFilter(FiltroSegredos())
    logger.addHandler(h)
    logger.setLevel(logging.INFO)
    try:
        logger.info("HTTP Request: GET %s", "https://x/y?key=SEGREDO123&q=1")
        try:
            raise ValueError("Client error for url 'https://x/y?key=SEGREDO123'")
        except ValueError:
            logger.warning("falhou", exc_info=True)
    finally:
        logger.removeHandler(h)
    assert len(registros) == 2
    assert all("SEGREDO123" not in r for r in registros)


def test_sentry_before_send_varre_o_evento():
    evento = {"message": "url?key=SEGREDO123", "extra": {"lista": ["a?token=T0K"]}}
    limpo = sentry_before_send(evento)
    assert "SEGREDO123" not in str(limpo) and "T0K" not in str(limpo)
