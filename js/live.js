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

function shape(i) {
  const d = new Date(i.published);
  const palavras = (i.lead || "").split(/\s+/).length;
  return Object.assign({}, i, {
    time: ago(i.published),
    read: `${Math.max(1, Math.round(palavras / 180))} min`,
    body: [],
    figcap: [i.srcName, i.place].filter(Boolean).join(" · "),
    day: String(d.getDate()).padStart(2, "0"),
    month: MESES[d.getMonth()],
    place: i.place || "Ribeirão Preto e região"
  });
}

function paintLiveBadge() {
  const el = document.getElementById("liveBadge");
  if (!el || !liveUpdated) return;
  el.hidden = false;
  el.innerHTML = `<i></i> ao vivo · ${ago(liveUpdated)}`;
}

async function loadLive(aviso) {
  let data;
  try {
    const r = await fetch(API + "feed", { cache: "no-store" });
    if (!r.ok) throw new Error(r.status);
    data = await r.json();
  } catch (e) { return false; }
  if (!data.news.length && !data.events.length) return false;

  SOURCES = data.sources;
  NEWS = data.news.map(shape);
  EVENTS = data.events.map(shape);
  ALL = [...NEWS, ...EVENTS];
  PINS = data.pins;
  UPDATES = ALL.slice(0, 4).map(i => ({
    ic: { Cidade: "traffic", Show: "ticket", Festival: "ticket", Cultura: "ticket", Gastronomia: "bus" }[i.cat] || "sun",
    t: i.title,
    s: `${i.srcName} · ${i.time}`
  }));
  liveUpdated = data.updated;

  if (!document.getElementById("app").hidden) {
    renderHome(); renderMap(); paintLiveBadge();
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
    if (d.type === "news") {
      loadLive(`${d.count} ${d.count === 1 ? "notícia nova" : "notícias novas"}`);
    }
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
