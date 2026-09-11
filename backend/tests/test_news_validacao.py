from app.news.validacao import frase_proibida_em, tem_atribuicao


def test_frase_proibida_detecta_locutor_narrando_a_propria_regra():
    fala = "Então eu fico só no que está confirmado, sem especular sobre causa ou desfecho."
    assert frase_proibida_em(fala) == "sem especular"


def test_frase_proibida_none_quando_fala_limpa():
    fala = "Segundo a Defesa Civil, a Rua São Paulo segue interditada até as seis da tarde."
    assert frase_proibida_em(fala) is None


def test_tem_atribuicao_com_marcador_generico():
    assert tem_atribuicao("A Defesa Civil informou que vinte casas foram atingidas.")


def test_tem_atribuicao_com_nome_da_fonte_sem_marcador_generico():
    assert tem_atribuicao("A Prefeitura de Blumenau soltou boletim às dez da manhã.", fonte_nome="Prefeitura de Blumenau")


def test_tem_atribuicao_falso_quando_informacao_solta():
    assert not tem_atribuicao("Vinte casas foram atingidas pela enchente esta manhã.")
