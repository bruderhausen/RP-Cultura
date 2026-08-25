/* =========================================================
   RP Cultural — base de dados de demonstração
   Conteúdo fictício, apenas para o protótipo navegável.
   ========================================================= */

let SOURCES = {
  g1:   { name: "G1 Ribeirão", url: "https://g1.globo.com/sp/ribeirao-preto-franca/" },
  uol:  { name: "UOL",          url: "https://www.uol.com.br/" },
  folha:{ name: "Folha",        url: "https://www.folha.uol.com.br/" },
  acid: { name: "A Cidade ON",  url: "https://www.acidadeon.com/ribeiraopreto/" },
  rev:  { name: "Revide",       url: "https://www.revide.com.br/" }
};

/* ---------- NOTÍCIAS ---------- */
let NEWS = [
  {
    id: "n1",
    kind: "noticia",
    hero: true,
    cat: "Festival",
    title: "Lollapalooza chega a Ribeirão Preto",
    lead: "Pela primeira vez fora da capital, o festival monta três palcos no complexo do Parque Permanente de Exposições em novembro.",
    body: [
      "A organização confirmou nesta manhã a edição regional do festival, que ocupará o Parque Permanente de Exposições com três palcos simultâneos e uma área gastronômica com produtores da região.",
      "Segundo os organizadores, a expectativa é receber 45 mil pessoas ao longo dos dois dias. O line-up completo será divulgado em setembro, mas nomes nacionais do rock e do rap já estão fechados.",
      "A prefeitura anunciou um esquema especial de transporte, com linhas extras saindo do Terminal Central a cada dez minutos durante o evento, além de área exclusiva para aplicativos de transporte.",
      "Os ingressos do primeiro lote começam a ser vendidos na próxima quinta-feira, com meia-entrada garantida para estudantes e moradores da região metropolitana."
    ],
    figcap: "Montagem dos palcos começa em outubro no Parque Permanente",
    time: "há 2 h",
    read: "4 min",
    src: "g1",
    place: "Parque Permanente de Exposições",
    tone: 0
  },
  {
    id: "n2",
    kind: "noticia",
    cat: "Cultura",
    title: "Theatro Pedro II reabre sala principal após restauro",
    lead: "Obra de dez meses recuperou o forro, a acústica e as poltronas originais da sala de 1930.",
    body: [
      "Depois de dez meses fechada, a sala principal do Theatro Pedro II volta a receber público neste fim de semana com um concerto gratuito da orquestra sinfônica municipal.",
      "O restauro recuperou o forro decorado, refez a instalação elétrica e devolveu à sala a acústica original, perdida em intervenções feitas nos anos 1980.",
      "A programação de reabertura vai até o fim do mês, com sessões abertas de ensaio nas manhãs de sábado."
    ],
    figcap: "Sala principal recuperou o forro decorado original",
    time: "há 5 h",
    read: "3 min",
    src: "acid",
    place: "Theatro Pedro II",
    tone: 1
  },
  {
    id: "n3",
    kind: "noticia",
    cat: "Cidade",
    title: "Corredor da Avenida Independência ganha nova ciclovia",
    lead: "Trecho de 4,2 km liga o Campus da USP ao centro e deve ser entregue em setembro.",
    body: [
      "A obra da ciclovia da Avenida Independência entrou na fase de sinalização e deve ser entregue em setembro, segundo a Secretaria de Obras.",
      "O trecho de 4,2 km conecta o campus da USP ao centro, com dez travessias semaforizadas e dois bicicletários cobertos.",
      "Durante a última etapa, o trânsito terá desvios pontuais entre 9h e 16h."
    ],
    figcap: "Novo trecho terá dez travessias semaforizadas",
    time: "há 8 h",
    read: "2 min",
    src: "folha",
    place: "Avenida Independência",
    tone: 2
  },
  {
    id: "n4",
    kind: "noticia",
    cat: "Gastronomia",
    title: "Feira de produtores volta ao Bosque aos domingos",
    lead: "Trinta bancas de agricultores da região se reúnem no Bosque Municipal a partir deste domingo.",
    body: [
      "A feira de produtores retoma as edições semanais no Bosque Municipal, reunindo trinta bancas de agricultura familiar de Ribeirão Preto e cidades vizinhas.",
      "Além de hortifrúti, o espaço terá cozinha ao vivo com chefs locais e uma área infantil.",
      "O funcionamento é das 8h às 14h, com estacionamento gratuito na lateral do parque."
    ],
    figcap: "Trinta bancas ocupam a alameda central do Bosque",
    time: "ontem",
    read: "2 min",
    src: "rev",
    place: "Bosque Municipal",
    tone: 3
  },
  {
    id: "n5",
    kind: "noticia",
    cat: "Show",
    title: "Choperia recebe maratona de rock autoral da região",
    lead: "Doze bandas se revezam em dois palcos na virada cultural da Choperia Pinguim.",
    body: [
      "Doze bandas autorais de Ribeirão Preto, Sertãozinho e Franca se apresentam em dois palcos durante a maratona de rock que ocupa a Choperia neste sábado.",
      "A curadoria priorizou grupos com material inédito lançado no último ano.",
      "A entrada é gratuita até as 19h e, depois, custa o valor de um ingresso social."
    ],
    figcap: "Bandas autorais dividem dois palcos na virada",
    time: "ontem",
    read: "3 min",
    src: "uol",
    place: "Choperia Pinguim",
    tone: 4
  },
  {
    id: "n6",
    kind: "noticia",
    cat: "Cultura",
    title: "Museu do Café abre acervo digital com 12 mil fotos",
    lead: "Imagens do ciclo cafeeiro da região ficam disponíveis para consulta gratuita online.",
    body: [
      "O Museu do Café concluiu a digitalização de doze mil fotografias do ciclo cafeeiro paulista, agora disponíveis em consulta gratuita.",
      "O acervo cobre o período de 1890 a 1960 e inclui registros de fazendas, do porto e das primeiras ferrovias da região.",
      "Pesquisadores podem solicitar arquivos em alta resolução pelo próprio portal."
    ],
    figcap: "Acervo cobre sete décadas do ciclo cafeeiro",
    time: "há 2 dias",
    read: "3 min",
    src: "g1",
    place: "Museu do Café",
    tone: 5
  }
];

/* ---------- EVENTOS ---------- */
let EVENTS = [
  {
    id: "e1", kind: "evento", cat: "Festival",
    title: "Lollapalooza RP", day: "14", month: "nov", place: "Parque Permanente",
    lead: "Dois dias, três palcos e mais de 30 atrações nacionais e internacionais.",
    body: [
      "A edição regional do festival ocupa o Parque Permanente de Exposições com três palcos simultâneos.",
      "A área gastronômica reúne produtores e restaurantes da cidade, e há espaço dedicado a projetos culturais independentes."
    ],
    figcap: "Três palcos simultâneos no Parque Permanente",
    time: "14 e 15 de nov", read: "2 min", src: "g1", tone: 0
  },
  {
    id: "e2", kind: "evento", cat: "Cultura",
    title: "Concerto de reabertura", day: "06", month: "set", place: "Theatro Pedro II",
    lead: "Orquestra sinfônica municipal marca a volta da sala principal com entrada gratuita.",
    body: [
      "O concerto de reabertura traz obras de compositores brasileiros e tem entrada gratuita mediante retirada de ingresso.",
      "A bilheteria abre duas horas antes, com limite de dois ingressos por pessoa."
    ],
    figcap: "Sala principal reabre com concerto gratuito",
    time: "06 de set · 20h", read: "2 min", src: "acid", tone: 1
  },
  {
    id: "e3", kind: "evento", cat: "Gastronomia",
    title: "Feira de produtores", day: "31", month: "ago", place: "Bosque Municipal",
    lead: "Trinta bancas de agricultura familiar, cozinha ao vivo e área infantil.",
    body: [
      "A feira acontece todo domingo, das 8h às 14h, na alameda central do Bosque Municipal.",
      "A cozinha ao vivo tem participação de chefs da cidade a cada edição."
    ],
    figcap: "Bancas de agricultura familiar no Bosque",
    time: "domingo · 8h", read: "1 min", src: "rev", tone: 3
  },
  {
    id: "e4", kind: "evento", cat: "Show",
    title: "Maratona de rock autoral", day: "30", month: "ago", place: "Choperia Pinguim",
    lead: "Doze bandas da região se revezam em dois palcos até a madrugada.",
    body: [
      "A maratona começa às 16h e vai até as 2h, com trocas de palco a cada 40 minutos.",
      "Entrada gratuita até as 19h."
    ],
    figcap: "Doze bandas em dois palcos",
    time: "sábado · 16h", read: "1 min", src: "uol", tone: 4
  },
  {
    id: "e5", kind: "evento", cat: "Cultura",
    title: "Sarau na Praça XV", day: "05", month: "set", place: "Praça XV de Novembro",
    lead: "Poesia, roda de samba e feira de fanzines no coração do centro histórico.",
    body: [
      "O sarau reúne poetas da cidade, roda de samba e uma feira de publicações independentes.",
      "A programação vai das 17h às 22h, com microfone aberto na primeira hora."
    ],
    figcap: "Microfone aberto abre a programação",
    time: "05 de set · 17h", read: "1 min", src: "rev", tone: 5
  }
];

/* ---------- ATUALIZAÇÕES DA REGIÃO ---------- */
let UPDATES = [
  { ic: "traffic", t: "Avenida Independência com desvio entre 9h e 16h", s: "Obras da ciclovia · atualizado há 20 min" },
  { ic: "sun",     t: "Sol entre nuvens, máxima de 31°C em Ribeirão Preto", s: "Previsão do dia · atualizado há 1 h" },
  { ic: "ticket",  t: "Primeiro lote do Lollapalooza RP abre quinta-feira", s: "Agenda cultural · atualizado há 2 h" },
  { ic: "bus",     t: "Linhas extras para o Parque Permanente no fim de semana", s: "Transporte · atualizado há 3 h" }
];

/* ---------- PINS DO MAPA (coordenadas em % da área) ---------- */
let PINS = [
  { id: "e1", lat: -21.1930, lng: -47.7855, label: "Parque Permanente", type: "ev" },
  { id: "n2", lat: -21.1783, lng: -47.8106, label: "Theatro Pedro II", type: "news" },
  { id: "n3", lat: -21.1712, lng: -47.8218, label: "Av. Independência", type: "news" },
  { id: "n4", lat: -21.1671, lng: -47.8022, label: "Bosque Municipal", type: "news" },
  { id: "e4", lat: -21.1795, lng: -47.8148, label: "Choperia Pinguim", type: "ev" },
  { id: "n6", lat: -21.1766, lng: -47.8117, label: "Museu do Café", type: "news" }
];

/* ---------- CATEGORIAS ---------- */
const CATS = ["Todos", "Show", "Festival", "Cultura", "Cidade", "Gastronomia"];

/* ---------- PALETAS PARA AS IMAGENS GERADAS ---------- */
const TONES = [
  ["#4B2ED4", "#B14BE8"],
  ["#7A2E8E", "#E8574B"],
  ["#1F6FD0", "#41C3C0"],
  ["#E0762B", "#F2C043"],
  ["#2B2153", "#7C4BE0"],
  ["#0E7B63", "#8CC63F"]
];

let ALL = [...NEWS, ...EVENTS];

/* [nome, quantidade] por município, vindo de /api/feed. Alimenta o filtro de
   cidade; sem servidor, fica vazio e o filtro não aparece. */
let CIDADES = [];
