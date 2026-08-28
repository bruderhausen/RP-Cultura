# RP Cultural

<p align="center"><img src="assets/icon-512.png" alt="RP Cultural" width="160"></p>

App mobile-first de notícias, eventos e cultura de Ribeirão Preto e região, feito a partir dos
wireframes de baixa fidelidade (páginas 01, 02 e 03). Conteúdo real: notícias vindas dos RSS dos
veículos da região e eventos das plataformas de ingresso.

**No ar:** https://rpcultura.onrender.com · adicione à tela de início para abrir como app.

## Como rodar

```bash
python server/app.py
```

`http://localhost:5173` — de preferência no modo dispositivo móvel do navegador (375×812).
Precisa de Python 3.9+. A única dependência externa é `cryptography`, e só o push a usa: sem ela o
app roda igual, apenas sem notificação.

## Telas

| Tela | O que faz |
|---|---|
| **Splash** | Animação do logo "RP" com a faixa CULTURAL, ~2,5 s. |
| **Guia** | Quatro slides no primeiro uso, revisível pelo Perfil: o que o app reúne, a cor dos pins do mapa, o aviso dos salvos e a personalização. |
| **Início** | Mostra um tipo por vez — Notícias, Eventos ou Cinema — no mesmo cartão, com busca, filtro de categoria e manchete. Evento e cinema ordenam por data ou por distância. |
| **Matéria** | Imagem, categoria, fonte, tempo de leitura, resumo, link para a matéria original, salvar e compartilhar. |
| **Mapa** | Mapa real (Leaflet) com pins no local exato: **azul é notícia, amarelo é evento, vermelho é cinema**, cada um com o próprio desenho para não depender da cor. Filtro no canto marca vários tipos ao mesmo tempo. Ao afastar, os pins que se encostariam viram um só com a contagem; abaixo do zoom 11 cada cidade vira um cartão branco com quantas notícias, eventos e sessões ela tem. O toque enquadra o grupo. Toque abre a aba com resumo, fonte e "Também aqui". |
| **Perfil** | Foto com recorte circular, preferências do que receber, interesses, salvos e link para o guia. |
| **Salvos** | Notícias e eventos em abas separadas. Na aba Eventos há o interruptor de aviso: com ele ligado, cada evento salvo vira uma notificação 30 min, 1 h, 3 h ou 1 dia antes de começar. |
| **Cinema** | Cartaz das quatro salas de Ribeirão, um cartão por filme, com os horários por dia atrás de "Ver horários" e link direto para a compra da sessão. |
| **Tradução** | Português → English → Español na interface e nos títulos. |

Preferências, salvos, idioma, foto e localização ficam no `localStorage` (`rpcultural.v1`). O que sai
do aparelho é só o endpoint de push e a lista de eventos a avisar — nada que identifique a pessoa.

## Backend

`server/app.py` serve o app e a API:

| Rota | O que faz |
|---|---|
| `GET /api/feed` | notícias, eventos, cinema, pins e fontes |
| `GET /api/stream` | SSE: avisa o app quando entra conteúdo novo |
| `GET /api/refresh` | força uma leitura agora |
| `GET /api/health` | status e contagem |
| `GET /api/push/chave` | chave pública VAPID e se o push está ligado |
| `POST /api/push/inscrever` · `/api/push/sair` | entra e sai da lista de inscrições |
| `POST /api/lembrete/sincronizar` | manda os eventos salvos e a antecedência escolhida |
| `POST /api/lembrete/sair` | apaga os lembretes daquele aparelho |

**Notícias** — RSS do G1 Ribeirão/Franca, Tribuna Ribeirão, G1 São Paulo e Folha (os dois últimos
filtrados por termos da região). Cada item é classificado por categoria, separado entre notícia e
evento e deduplicado por semelhança de título.

**Eventos** — `server/eventos.py` lê as páginas de cidade da Sympla (Ribeirão, Franca, Sertãozinho,
Barretos, Araraquara) e extrai nome, data, casa, endereço com número e coordenadas; eventos ficam no
feed até a data acontecer. A Agenda da Encruzilhada (`agenda.macumbox.app.br`) entra pelo mesmo módulo: ela serve HTML pronto,
com data, hora, local e tipo em atributos do próprio card, e traz show de casa que não vende por
plataforma nenhuma. Há um adaptador da Eventim pronto, ativado por `EVENTIM_WEBID` /
`EVENTIM_KEY` (a API deles exige credencial de afiliado).

**Cinema** — `server/cinema.py` lê a API de conteúdo da Ingresso.com, que responde sem chave nem cadastro. O item é o par filme × sala, não a sessão: sessão vira item afogaria o feed, e o mapa precisa de um ponto por casa. As coordenadas das quatro salas são fixas no código porque o geocodificador erra o número em duas delas. O cartaz é substituído inteiro a cada leitura, já que horário não tem histórico que valha guardar.

**Notificações** — `server/push.py` fala Web Push direto, sem biblioteca: monta o cabeçalho VAPID
(um JWT ES256, único trecho que precisa de `cryptography`) e deixa a entrega com o serviço do próprio
navegador. `server/lembretes.py` guarda os lembretes dos eventos salvos, porque o navegador não roda
nada com o app fechado — quem precisa saber que chegou a hora é quem envia. Título e local do evento
ficam congelados no momento da marcação, para o aviso não depender de o evento ainda estar no
histórico. Sem `VAPID_PUBLIC` / `VAPID_PRIVATE` o interruptor some e o resto do app continua igual.

**Localização** — o local sai primeiro de um dicionário de lugares conhecidos, depois de
rua/avenida/bairro com número citados no texto (geocodificados no Nominatim com validação de cidade
e distância) e, por último, da cidade citada. Três workers processam as matérias novas em segundo
plano e avisam o app por SSE, então o pin aparece em tempo real.

**Atualização** — releitura a cada 5 min no servidor, push por SSE, e o app rebusca a cada 90 s e ao
voltar para o primeiro plano. Um auto-ping a cada 10 min evita a hibernação do plano gratuito.

### Variáveis

| Variável | Padrão | Para quê |
|---|---|---|
| `PORT` | 5173 | porta |
| `REFRESH_SECONDS` | 300 | intervalo de leitura das fontes |
| `HISTORY_DAYS` | 7 | histórico guardado |
| `KEEPALIVE_URL` | `RENDER_EXTERNAL_URL` | endereço do auto-ping |
| `GIST_ID` / `GIST_TOKEN` | — | backup do histórico fora do disco efêmero |
| `EVENTIM_WEBID` / `EVENTIM_KEY` | — | integração da Eventim |
| `VAPID_PUBLIC` / `VAPID_PRIVATE` | — | assinatura do push; sem elas, push desligado |
| `VAPID_SUB` | `mailto:contato@rpcultural.app` | contato exigido pelo VAPID |
| `ADMIN_TOKEN` | — | senha de `/admin.html`; sem ela, envio em massa bloqueado |

Nenhuma delas entra no repositório, que é público. `PROXIMOS-PASSOS.md` lista onde cada uma é
configurada.

## Estrutura

```
index.html          telas e navegação
css/styles.css      design system
js/app.js           estado, navegação, mapa, recorte de foto
js/live.js          consumo da API, SSE e atualização contínua
js/data.js          conteúdo de demonstração (só sem backend)
js/i18n.js          textos da interface e traduções
sw.js               service worker (rede primeiro) e recebimento do push
server/app.py       API, leitura das fontes e localização
server/eventos.py   Sympla e Eventim
server/cinema.py    cartaz e sessões da Ingresso.com
server/push.py      Web Push e assinatura VAPID
server/lembretes.py agenda do aviso dos eventos salvos
admin.html          envio manual de aviso, protegido por ADMIN_TOKEN
```

## Créditos

As fotos das matérias vêm dos próprios veículos e aparecem com o crédito do fotógrafo quando ele
está publicado na página de origem ("Foto: …"). Textos e imagens pertencem aos veículos citados; o
app mostra apenas manchete, resumo e link para a matéria completa.

## Deploy

`Dockerfile` e `render.yaml` prontos: no Render, *New → Blueprint Instance* apontando para o
repositório. Serve para qualquer host com Docker. No plano gratuito não há disco persistente — o
histórico se refaz na primeira leitura (ou vem do Gist, se configurado).
