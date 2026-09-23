# Banco local de trilhas de vinheta

Fallback de `app/vinhetas/trilha.py` quando a trilha por IA (ElevenLabs Music API) está
desligada ou falha. Cada pasta é um estilo; o programa cai num estilo pelo mapeamento
`_GENERO_PARA_ESTILO` (gêneros musicais do programa) e, sem arquivo no estilo, em `generico/`.
Banco vazio = vinheta só com a voz processada.

Pastas: `sertanejo/`, `gospel/`, `pop_jovem/`, `jornalismo/`, `romantico/`, `eletronico/`, `generico/`.

## Regras para incluir um arquivo

- Só MP3, de 10 a 20 s, instrumental (sem voz cantada), com final marcado.
- Só trilhas livres de direitos ou com licença que permita uso comercial em rádio **sem**
  atribuição no ar. Nada de música do YouTube nem de biblioteca com licença só pessoal.
- Registre cada arquivo na tabela abaixo antes do commit.

| Arquivo | Estilo | Autor / fonte | Licença | Link da licença |
|---------|--------|---------------|---------|-----------------|
| _(nenhum ainda)_ | | | | |
