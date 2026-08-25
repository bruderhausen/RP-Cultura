# RP Cultural

Protótipo navegável (mobile first) do divulgador de notícias e eventos de Ribeirão Preto e região,
feito a partir dos wireframes de baixa fidelidade (páginas 01, 02 e 03).

## Como abrir

```bash
python server/app.py
```

Depois acesse `http://localhost:5173` — de preferência com o modo dispositivo móvel do navegador
(375×812). Abrir o `index.html` direto pelo arquivo também funciona.

## O que está implementado

| Tela | Detalhes |
|---|---|
| **Splash** | Animação de introdução: o traço do logo "RP" é desenhado, os pontos aparecem e a faixa amarela **CULTURAL** sobe. Dura ~2,5 s e some. |
| **Guia do app** | Três slides com deslize horizontal, indicador de progresso, "Pular" e "Começar". Aparece só no primeiro uso e pode ser revisto pelo Perfil. |
| **Início** | Busca ("Eventos perto de mim"), filtro de região, chips de categoria, manchete em destaque, lista de principais notícias, carrossel de eventos e atualizações da região. Todo card é clicável. |
| **Notícia / Evento** | Imagem, categoria, manchete, fonte, tempo de leitura, texto, imagem secundária com legenda, link para a matéria original e "Leia também". Botão de salvar no topo. |
| **Mapa** | Malha de ruas com pins clicáveis (roxo = notícia, amarelo = evento). Ao tocar, abre uma aba inferior com resumo e **link da fonte** (G1, UOL, Folha, A Cidade ON, Revide). |
| **Perfil** | Foto editável, "Entre ou cadastre-se", contador de salvos, preferências do que receber (notícias / eventos / alertas), interesses e link para rever o guia. |
| **Salvos** | Notícias e eventos em **áreas separadas** por abas, com remoção item a item. |
| **Entrar / Cadastrar** | Segmentos ENTRAR e CADASTRAR, campo de e-mail validado e "continuar »". |
| **Tradução** | Botão no topo da Home alterna Português → English → Español: traduz a interface e os títulos/resumos dos conteúdos, marcando-os como traduzidos automaticamente. |

Preferências, salvos, idioma, foto e conta ficam no `localStorage` (chave `rpcultural.v1`).

## Estrutura

```
index.html          telas e navegação
css/styles.css      design system (cores, tipografia, componentes)
js/data.js          notícias, eventos, atualizações, pins e fontes
js/i18n.js          textos da interface e traduções de conteúdo
js/app.js           estado, navegação e renderização
```

As imagens são geradas em SVG por categoria — o protótipo não depende de nenhum arquivo externo.
O conteúdo é fictício e serve só para demonstrar a navegação.


## Notícias reais (backend)

[server/app.py](server/app.py) lê os RSS dos veículos da região a cada 5 minutos, guarda
**7 dias de histórico** em `data/news.json` e serve o app junto com a API:

| Rota | O que faz |
|---|---|
| `GET /api/feed` | notícias, eventos, pins do mapa e fontes |
| `GET /api/stream` | SSE — avisa o app no instante em que entram notícias novas |
| `GET /api/refresh` | força uma leitura dos feeds agora |
| `GET /api/health` | status e quantidade de itens |

Fontes: G1 Ribeirão/Franca, Tribuna Ribeirão, G1 São Paulo e Folha (as duas últimas
filtradas por termos da região). O backend classifica cada item em categoria,
separa notícia de evento e crava o pin no mapa quando reconhece um lugar da cidade.

Variáveis: `PORT`, `REFRESH_SECONDS` (padrão 300), `HISTORY_DAYS` (padrão 7).

O app ([js/live.js](js/live.js)) consome a API e, se não encontrar backend, continua
funcionando com o conteúdo de demonstração.

## Publicar para acessar do celular

Precisa de um host rodando 24h — o [Dockerfile](Dockerfile) e o [render.yaml](render.yaml)
já estão prontos:

1. suba a pasta para um repositório no GitHub;
2. no Render, *New → Web Service*, aponte para o repositório (ele lê o `render.yaml`);
3. o endereço gerado (`https://rpcultural.onrender.com`) abre no celular de qualquer lugar.

Vale para Railway, Fly.io ou qualquer host com Docker. No plano gratuito do Render o
serviço hiberna sem acesso e demora alguns segundos para acordar.
