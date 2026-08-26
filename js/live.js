/* =========================================================
   RP Cultural — camada ao vivo
   Busca /api/feed (backend em server/app.py) e substitui os
   dados de demonstração. Sem backend, o app segue com a demo.
   ========================================================= */
const API = "api/";
const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
let liveUpdated = null;

function ago(iso) {
  const d = new Date(iso), min = Math.round((Date.now() - d) / 60000);
  if (min < 2) return "agora";
  if (min < 60) return `há ${min} min`;
  const h = Math.round(min / 60);
  if (h < 24) return `há ${h} h`;
  const dias = Math.round(h / 24);
  return dias === 1 ? "ontem" : `há ${dias} dias`;
}

function quando(iso) {
  const d = new Date(iso), hoje = new Date();
  const dias = Math.round((d - hoje) / 86400000);
  const data = d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
  if (dias === 0) return "hoje";
  if (dias === 1) return "amanhã";
  return dias > 0 ? `${data}` : data;
}

function shape(i) {
  const d = new Date(i.when || i.published);
  const palavras = (i.lead || "").split(/\s+/).length;
  return Object.assign({}, i, {
    time: i.when ? quando(i.when) : ago(i.published),
    read: `${Math.max(1, Math.round(palavras / 180))} min`,
    body: [],
    figcap: [i.srcName, i.place].filter(Boolean).join(" · "),
    day: String(d.getDate()).padStart(2, "0"),
    month: MESES[d.getMonth()],
    place: i.place || "Ribeirão Preto e região",
    price: i.price || null,
    credit: i.credit || null
  });
}

function paintLiveBadge() {
  const el = document.getElementById("liveBadge");
  if (!el || !liveUpdated) return;
  el.hidden = false;
  el.innerHTML = `<i></i> ao vivo · ${ago(liveUpdated)}`;
}

function semServidor(ligado) {
  const el = document.getElementById("liveBadge");
  if (!el) return;
  el.hidden = false;
  el.classList.toggle("live--off", ligado);
  if (ligado) el.innerHTML = "sem conexão com o servidor";
}

async function loadLive(aviso) {
  let data;
  try {
    const r = await fetch(API + "feed", { cache: "no-store" });
    if (!r.ok) throw new Error(r.status);
    data = await r.json();
  } catch (e) {
    // nunca mostrar o conteúdo de demonstração como se fosse notícia real
    NEWS = []; EVENTS = []; ALL = []; PINS = []; UPDATES = []; CIDADES = [];
    if (!document.getElementById("app").hidden) { renderHome(); renderMap(); }
    semServidor(true);
    setTimeout(() => loadLive(), 15000);
    return false;
  }
  if (!data.news.length && !data.events.length) return false;

  const antes = liveUpdated;
  SOURCES = data.sources;
  NEWS = data.news.map(shape);
  EVENTS = data.events.map(shape);
  ALL = [...NEWS, ...EVENTS];
  PINS = data.pins;
  CIDADES = data.cidades || [];
  liveUpdated = data.updated;
  semServidor(false);

  // A releitura de 90 s quase sempre volta igual. Repintar a home inteira e o
  // mapa sem novidade custava caro no celular, e ainda apagava o scroll.
  const mudou = data.updated !== antes;
  if (!document.getElementById("app").hidden) {
    if (mudou) { renderHome(); renderMap(); }
    paintLiveBadge();
  }
  if (aviso) toast(aviso);
  return true;
}

/* SSE: o servidor avisa assim que entram notícias novas */
function connectStream() {
  if (!window.EventSource) return;
  const es = new EventSource(API + "stream");
  es.onmessage = ev => {
    let d = {}; try { d = JSON.parse(ev.data); } catch (e) { return; }
    if (d.type === "feed" || d.type === "news") {
      // o servidor manda a contagem separada por tipo; d.count é o formato
      // antigo, ainda possível num cliente servido de cache
      const n = d.news != null ? d.news : d.count || 0;
      const m = d.events || 0;
      const partes = [];
      if (n) partes.push(`${n} ${n === 1 ? "notícia nova" : "notícias novas"}`);
      if (m) partes.push(`${m} ${m === 1 ? "evento novo" : "eventos novos"}`);
      loadLive(partes.join(" e "));
    } else loadLive();                     // pins recém-localizados
  };
  es.onerror = () => { es.close(); setTimeout(connectStream, 30000); };
}

/* liga tudo assim que o app abre */
(async () => {
  if (await loadLive()) {
    connectStream();
    setInterval(() => { NEWS.forEach(i => i.time = ago(i.published)); paintLiveBadge(); }, 60000);
    setInterval(() => loadLive(), 90000);                       // busca periódica
    document.addEventListener("visibilitychange", () => {       // voltou para o app
      if (!document.hidden) loadLive();
    });
  }
})();
