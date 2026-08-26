# RP Cultural

PWA de notícias e eventos de Ribeirão Preto e região. Servidor em Python só com
a biblioteca padrão, salvo `cryptography`, exigida pelo push. Front em HTML, CSS
e JavaScript sem framework.

## Resposta

Modo caveman nível **ultra** por padrão, sem precisar invocar. Frases curtas,
sem preâmbulo, sem recapitular o que já foi dito, sem repetir no texto o que o
commit já explica.

Teto de **5 linhas** por resposta, sempre. Depois de uma tarefa: uma a três
linhas com o resultado e o hash do commit. Detalhar só o que muda a decisão de
quem lê, e só quando eu perguntar. Resposta longa gasta token à toa.

Nada de tabela, emoji ou lista decorativa. Lista só quando são itens de verdade.

## Ferramentas

Cada saída de ferramenta entra no contexto e custa tokens em toda mensagem
seguinte, então ela é o gasto que mais importa cortar:

- Cortar toda saída longa com `| tail -N`, `| head -N` ou `grep`.
- Ler trecho de arquivo com `sed -n` em vez do arquivo inteiro.
- Testes: só a última linha do resultado, salvo quando falham.
- Não reler arquivo que já foi lido nem confirmar edição relendo.
- Uma chamada que resolve, e não três que exploram.

## Trabalho

Rodar `python -m unittest discover -s tests` antes de qualquer commit.

Validar contra o dado real antes de dizer que funciona: os defeitos desta base
apareceram quase todos em produção, não em exemplo inventado.

Commitar e publicar no fim de cada tarefa, sem perguntar. Mensagem de commit em
português, explicando a causa do problema e não só o que mudou.

Segredo nenhum entra no repositório. Ele é privado hoje, mas o app é aberto e
pode virar público a qualquer momento, e segredo commitado fica no histórico
mesmo depois de removido. Chave e senha vivem em variável de ambiente,
listadas em `PROXIMOS-PASSOS.md`.
