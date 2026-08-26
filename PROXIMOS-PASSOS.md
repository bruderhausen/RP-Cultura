# Próximos passos

Pendências conhecidas, em ordem de urgência. Atualizar conforme cada uma sai.

## Configuração no Render (bloqueia recursos já prontos)

O código está pronto e testado; falta só criar as variáveis de ambiente em
`rpcultura` → Environment. O painel `/diag.html` mostra o que está faltando.

| Variável | Para quê | Sem ela |
|---|---|---|
| `ADMIN_TOKEN` | senha de `/admin.html` | envio em massa bloqueado (503) |
| `GIST_ID` | id de um gist secreto | inscrições de push somem a cada restart |
| `GIST_TOKEN` | token do GitHub com escopo `gist` | idem |
| `VAPID_PUBLIC` / `VAPID_PRIVATE` / `VAPID_SUB` | assinatura do push | push desligado |

Nenhum desses valores pode ir para o repositório: ele é público, e o histórico
do git guarda o que for commitado mesmo depois de removido.

## Coleta

- **Endereço do ARQ.** O site deles não publica o endereço da casa e o nome não
  é encontrado pelo geocodificador, então os eventos caem no centro de Ribeirão.
  Com o endereço em mãos, basta uma entrada em `PLACES` no `server/app.py`.
- **Mais plataformas de evento.** Hoje são Sympla e ARQ. Casas que vendem em
  site próprio precisam de um coletor cada.

## Mapa

- **Agrupar pins próximos.** Com mais itens em local próprio, o zoom afastado
  vira amontoado. Hoje a solução é esconder tudo abaixo do zoom 10, que é
  grosseiro.
- **Ampliar a lista de bairros.** `BAIRROS_RP` cobre Ribeirão Preto; as outras
  cidades da região dependem só do regex de prefixo e do geocodificador.

## App

- **Service worker é network-first sem precache do app shell.** Abrir sem rede
  mostra tela vazia até o cache responder.
- **Imagens vêm no tamanho original da fonte.** Um proxy de redimensionamento
  cortaria bastante tráfego no celular.

## Infraestrutura

- **Disco persistente do Render** substituiria o backup no gist e simplificaria
  `push.py` e `lembretes.py`. Sai do plano gratuito.
- **O serviço hiberna sem tráfego.** O keepalive já existe, mas depende de
  `KEEPALIVE_URL` estar configurada.
