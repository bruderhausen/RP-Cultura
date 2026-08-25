# RP Cultural

App mobile-first de notícias, eventos e cultura de Ribeirão Preto e região, feito a partir dos
wireframes de baixa fidelidade (páginas 01, 02 e 03). Conteúdo real: notícias vindas dos RSS dos
veículos da região e eventos das plataformas de ingresso.

**No ar:** https://rpcultura.onrender.com · adicione à tela de início para abrir como app.

## Como rodar

```bash
python server/app.py
```

`http://localhost:5173` — de preferência no modo dispositivo móvel do navegador (375×812).
Só precisa de Python 3.9+; não há dependências externas.

## Telas

| Tela | O que faz |
|---|---|
| **Splash** | Animação do logo "RP" com a faixa CULTURAL, ~2,5 s. |
| **Guia** | Três slides no primeiro uso, revisível pelo Perfil. |
| **Início** | Busca, filtro de categoria, manchete, 3 principais notícias + **Ver todas** (separadas por dia), carrossel de eventos com data, local e ingresso. |
| **Matéria** | Imagem, categoria, fonte, tempo de leitura, resumo, link para a matéria original, salvar e compartilhar. |
| **Mapa** | Mapa real (Leaflet + CARTO Voyager) com pins no local exato; toque abre a aba com resumo, fonte e "Também aqui". Ponto azul acompanha o usuário. |
| **Perfil** | Foto com recorte circular, preferências do que receber, interesses, salvos e link para o guia. |
| **Salvos** | Notícias e eventos em abas separadas. |
| **Tradução** | Português → English → Español na interface e nos títulos. |

Preferências, salvos, idioma, foto e localização ficam no `localStorage` (`rpcultural.v1`).

## Backend

`server/app.py` (só biblioteca padrão) serve o app e a API:

| Rota | O que faz |
|---|---|
| `GET /api/feed` | notícias, eventos, pins e fontes |
| `GET /api/stream` | SSE: avisa o app quando entra conteúdo novo |
| `GET /api/refresh` | força uma leitura agora |
| `GET /api/health` | status e contagem |

**Notícias** — RSS do G1 Ribeirão/Franca, Tribuna Ribeirão, G1 São Paulo e Folha (os dois últimos
filtrados por termos da região). Cada item é classificado por categoria, separado entre notícia e
evento e deduplicado por semelhança de título.

**Eventos** — `server/eventos.py` lê as páginas de cidade da Sympla (Ribeirão, Franca, Sertãozinho,
Barretos, Araraquara) e extrai nome, data, casa, endereço com número e coordenadas; eventos ficam no
feed até a data acontecer. Há um adaptador da Eventim pronto, ativado por `EVENTIM_WEBID` /
`EVENTIM_KEY` (a API deles exige credencial de afiliado).

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

## Estrutura

```
index.html          telas e navegação
css/styles.css      design system
js/app.js           estado, navegação, mapa, recorte de foto
js/live.js          consumo da API, SSE e atualização contínua
js/data.js          conteúdo de demonstração (só sem backend)
js/i18n.js          textos da interface e traduções
sw.js               service worker (rede primeiro)
server/app.py       API, leitura das fontes e localização
server/eventos.py   Sympla e Eventim
```

## Deploy

`Dockerfile` e `render.yaml` prontos: no Render, *New → Blueprint Instance* apontando para o
repositório. Serve para qualquer host com Docker. No plano gratuito não há disco persistente — o
histórico se refaz na primeira leitura (ou vem do Gist, se configurado).
