/* =========================================================
   RP Cultural — lógica do protótipo
   ========================================================= */
const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

/* ---------------- estado ---------------- */
const KEY = "rpcultural.v1";
const S = Object.assign({
  cat: "Todos", q: "", lang: "pt", screen: "home", cidade: "",
  antes: "1h", avisarSalvos: false,
  saved: [], prefs: { noticias: true, eventos: true, cinema: true, alertas: false },
  interests: [], geo: null, user: null, avatar: null, guideSeen: false,
  /* Tipo que a home mostra, sempre exatamente um. Não existe "todos": a
     notícia se mede pelo tempo desde que saiu e o evento pelo tempo que falta
     para começar, então misturar os dois numa lista só põe duas réguas opostas
     lado a lado. Separado do filtro do mapa: olhar cinema no mapa não deve
     trocar o que a home mostra. */
  homeTipo: "noticia",
  /* "data" ou "perto": vale para evento e para cinema */
  ordem: "data"
}, JSON.parse(localStorage.getItem(KEY) || "{}"));

/* Object.assign é raso: o `prefs` gravado antes de existir o cinema
   substituía o objeto inteiro, e `S.prefs.cinema` ficava undefined. Com isso a
   aba de cinema abria vazia em quem já usava o app. */
S.prefs = Object.assign({ noticias: true, eventos: true, cinema: true, alertas: false },
                        S.prefs || {});

const save = () => localStorage.setItem(KEY, JSON.stringify(S));
const t = k => (UI[S.lang] || UI.pt)[k];

/* conteúdo traduzido (título e resumo) */
function loc(item) {
  const tr = CONTENT_I18N[S.lang] && CONTENT_I18N[S.lang][item.id];
  return tr ? { title: tr[0], lead: tr[1] } : { title: item.title, lead: item.lead };
}
const byId = id => ALL.find(i => i.id === id);
const catLabel = c => (CATS_I18N[S.lang] && CATS_I18N[S.lang][c]) || c;

/* ---------------- arte gerada (sem imagens externas) ---------------- */
function art(item, extra = "") {
  const [a, b] = TONES[item.tone % TONES.length];
  const g = "g" + item.id;
  const glyph = {
    Festival: '<path d="M22 78 L50 22 L78 78 Z" fill="none" stroke="#fff" stroke-width="3"/><circle cx="50" cy="46" r="8" fill="#fff"/>',
    Show:     '<path d="M38 70V32l30-7v38" fill="none" stroke="#fff" stroke-width="3.5" stroke-linejoin="round"/><circle cx="32" cy="70" r="7" fill="#fff"/><circle cx="62" cy="63" r="7" fill="#fff"/>',
    Cultura:  '<path d="M24 74h52M30 74V38M46 74V38M62 74V38M70 74V38M22 34l28-14 28 14z" fill="none" stroke="#fff" stroke-width="3.2" stroke-linejoin="round"/>',
    Cidade:   '<path d="M20 78V44l16-10v44M44 78V30l18-12v60M66 78V48l14 8v22" fill="none" stroke="#fff" stroke-width="3.2" stroke-linejoin="round"/>',
    Esporte: '<circle cx="50" cy="50" r="24" fill="none" stroke="#fff" stroke-width="3.2"/><path d="M50 26v48M26 50h48M34 34l32 32M66 34 34 66" fill="none" stroke="#fff" stroke-width="2.4"/>',
    "Política": '<path d="M24 46h52v32H24z" fill="none" stroke="#fff" stroke-width="3.2" stroke-linejoin="round"/><path d="M38 46V26h24v20" fill="none" stroke="#fff" stroke-width="3.2" stroke-linejoin="round"/><path d="M36 56h28" stroke="#fff" stroke-width="3.4" stroke-linecap="round"/>',
    Gastronomia: '<path d="M32 22v26a8 8 0 0 0 16 0V22M40 48v30M62 78V22c8 4 10 12 10 22 0 6-4 8-10 8" fill="none" stroke="#fff" stroke-width="3.2" stroke-linecap="round"/>'
  }[item.cat] || "";
  return `<div class="ph">
    <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <defs><linearGradient id="${g}" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/></linearGradient></defs>
      <rect width="100" height="100" fill="url(#${g})"/>
      <circle cx="82" cy="18" r="30" fill="#fff" opacity=".10"/>
      <circle cx="14" cy="86" r="24" fill="#000" opacity=".10"/>
      <g opacity=".85">${glyph}</g>
    </svg>${item.img ? `<img class="ph__img" src="${item.img}" alt="" loading="lazy" onerror="this.remove()">` : ""}${extra}</div>`;
}

/* ---------------- toast ---------------- */
let toastT;
function toast(msg) {
  const el = $("#toast");
  el.textContent = msg; el.hidden = false;
  clearTimeout(toastT);
  toastT = setTimeout(() => { el.hidden = true; }, 2000);
}

/* ---------------- salvos ---------------- */
const isSaved = id => S.saved.includes(id);
function toggleSave(id) {
  const i = S.saved.indexOf(id);
  if (i > -1) { S.saved.splice(i, 1); toast(t("remove")); }
  else { S.saved.unshift(id); toast(t("saved2") + " ✓"); }
  save(); paintSavedCount();
  // o evento salvo é o que gera lembrete: não há mais botão separado
  if (S.avisarSalvos) enviarLembretes();
  return isSaved(id);
}

/* eventos salvos que ainda vão acontecer: só esses podem ser avisados */
const eventosParaAvisar = () => S.saved.map(byId)
  .filter(i => i && i.kind === "evento" && i.when && new Date(i.when) > new Date());
const paintSavedCount = () => { $("#savedCount").textContent = S.saved.length; };

/* =========================================================
   SPLASH → GUIA → APP
   ========================================================= */
window.addEventListener("load", () => {
  const sp = $("#splash");
  // sem animação, a bola e a tinta não existem: não faz sentido esperar por elas
  const parado = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (parado) {
    setTimeout(() => {
      if (S.guideSeen) startApp(); else openGuide();
      setTimeout(() => sp.remove(), 60);
    }, 1200);
    return;
  }
  setTimeout(() => {
    sp.classList.add("is-throw");                  // a bola vem para cima do usuário
    setTimeout(() => {
      // a tela está inteira coberta pela bola e nada se move: é a janela certa
      // para montar o app. Antes ele montava durante o fade e o custo de
      // renderHome, renderMap e Leaflet aparecia como travada
      // erro ao montar não pode prender o usuário na tela cheia da tinta:
      // melhor entrar num app quebrado e ver o problema do que não entrar
      try {
        if (S.guideSeen) startApp(); else openGuide();
      } catch (e) {
        console.error("falha ao montar o app", e);
        $("#app").hidden = false;
      }
      setTimeout(() => {
        sp.classList.add("is-paint");              // a tinta escorre e revela
        setTimeout(() => sp.remove(), 1650);
      }, 140);                                     // deixa o app pintar antes
    }, 700);
  }, 2950);
});

/* Um item por filme E por sala chega do servidor, porque o mapa precisa de um
   ponto por cinema. A home mostra o filme uma vez só, com as salas dentro. */
function porFilme(lista) {
  const m = new Map();
  lista.forEach(f => {
    const g = m.get(f.movieId);
    if (g) { g.salas.push(f); if (f.when < g.when) g.when = f.when; }
    else m.set(f.movieId, Object.assign({}, f, { salas: [f] }));
  });
  return [...m.values()].sort((a, b) => a.when < b.when ? -1 : 1);
}
/* O horário é o dado que a pessoa foi buscar no cinema; sem ele a ficha vira
   sinopse. Cada chip leva direto à compra daquela sessão. */
function sessoesHTML(i) {
  if (i.kind !== "cinema" || !(i.sessoes || []).length) return "";
  const dias = new Map();
  i.sessoes.forEach(s => {
    const d = new Date(s.quando);
    const rot = d.toDateString() === new Date().toDateString()
      ? "Hoje" : `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;
    (dias.get(rot) || dias.set(rot, []).get(rot)).push(s);
  });
  return `<details class="sessoes"><summary class="sessoes__abre">
    <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4.5" width="18" height="16" rx="3"/><path d="M3 9.5h18M8 2.5v4M16 2.5v4"/></svg>
    ${t("showTimes")} <b>(${i.sessoes.length})</b>
    <svg class="sessoes__seta" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>
  </summary>${[...dias].map(([rot, ss]) => `
    <div class="sessoes__dia"><b>${rot}</b>
      <div class="sessoes__hs">${ss.map(s => `
        <a class="sessao" href="${s.url}" target="_blank" rel="noopener"
           title="${[s.sala, s.tipo].filter(Boolean).join(" · ")}">${s.hora}</a>`).join("")}</div>
    </div>`).join("")}</details>`;
}

$("#ordemLinha").addEventListener("click", e => {
  const b = e.target.closest("button[data-ordem]");
  if (!b || b.disabled) return;
  S.ordem = b.dataset.ordem; save();
  $$("#ordemLinha button").forEach(x => {
    const on = x === b;
    x.classList.toggle("is-on", on);
    x.setAttribute("aria-checked", on);
  });
  renderHome();
});

/* ---------------- tipo da tela inicial ---------------- */
function pintarTipos() {
  $$("#ordemLinha button").forEach(b => {
    const on = b.dataset.ordem === S.ordem;
    b.classList.toggle("is-on", on);
    b.setAttribute("aria-checked", on);
  });
  $$("#tipoChips button").forEach(b => {
    const on = b.dataset.tp === S.homeTipo;
    b.classList.toggle("is-on", on);
    b.setAttribute("aria-checked", on);
  });
}
$("#tipoChips").addEventListener("click", e => {
  const b = e.target.closest("button[data-tp]");
  if (!b) return;
  // escolha exclusiva: tocar num tipo troca, nunca soma
  S.homeTipo = b.dataset.tp;
  save(); pintarTipos(); renderHome();
});


/* ---------------- guia ---------------- */
let gi = 0;
/* O guia mostra a marca de verdade, montada pela mesma função do mapa: copiar o
   desenho no HTML deixaria o guia mentindo no dia em que a marca mudasse. */
function pintarMarcasDoGuia() {
  $$("#guide [data-marca]").forEach(el => {
    if (!el.firstChild) el.innerHTML = marcaHTML({ type: el.dataset.marca });
  });
}
function openGuide() {
  gi = 0;
  const g = $("#guide");
  pintarMarcasDoGuia();
  g.hidden = false;
  $("#guideTrack").scrollTo({ left: 0 });
  $$("#guide .guide__slide").forEach(sl => sl.classList.remove("is-live"));
  paintGuide();
}
function closeGuide() {
  S.guideSeen = true; save();
  const g = $("#guide");
  g.style.transition = "opacity .3s"; g.style.opacity = "0";
  setTimeout(() => { g.hidden = true; g.style.opacity = ""; }, 300);
  startApp();
}
/* último slide vem da marcação: assim dá para incluir slide sem mexer aqui */
const guideLast = () => $$("#guide .guide__slide").length - 1;
/* a ilustração só anima no slide aberto; fora dele a animação passaria despercebida */
function paintGuide() {
  $$("#guideDots i").forEach((d, i) => d.classList.toggle("on", i === gi));
  $$("#guide .guide__slide").forEach((sl, i) => sl.classList.toggle("is-live", i === gi));
  $("#guideNext").textContent = gi === guideLast() ? "Começar" : "Continuar";
}
$("#guideNext").addEventListener("click", () => {
  if (gi >= guideLast()) return closeGuide();
  gi++;
  const tr = $("#guideTrack");
  tr.scrollTo({ left: gi * tr.clientWidth, behavior: "smooth" });
  paintGuide();
});
$("#guideSkip").addEventListener("click", closeGuide);
$("#guideTrack").addEventListener("scroll", () => {
  const tr = $("#guideTrack");
  const n = Math.round(tr.scrollLeft / tr.clientWidth);
  if (n !== gi) { gi = n; paintGuide(); }
});

/* ---------------- instalar na tela de início ---------------- */
let _instalar = null;
const instalado = () => matchMedia("(display-mode: standalone)").matches || navigator.standalone;

window.addEventListener("beforeinstallprompt", e => {
  e.preventDefault(); _instalar = e;
  if (!instalado()) $("#btnInstalar").hidden = false;
});
window.addEventListener("appinstalled", () => { $("#btnInstalar").hidden = true; _instalar = null; });

$("#btnInstalar").addEventListener("click", async () => {
  if (_instalar) { _instalar.prompt(); await _instalar.userChoice; _instalar = null; $("#btnInstalar").hidden = true; }
  else toast("Toque em Compartilhar e depois em Adicionar à Tela de Início");
});

/* ---------------- boot do app ---------------- */
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
}

function startApp() {
  $("#app").hidden = false;
  history.replaceState({ root: 1 }, "");
  pushLayer();   // passo extra: o primeiro "voltar" nunca sai do app
  renderChips(); pintarTipos(); renderHome(); renderMap(); renderProfile(); paintSavedCount(); applyLang();
  pintarCidade();
  if (window.paintLiveBadge) paintLiveBadge();
  garantirInscricao();
  // iPhone não dispara o evento de instalação: mostramos o atalho mesmo assim
  if (!instalado() && /iphone|ipad|ipod/i.test(navigator.userAgent)) $("#btnInstalar").hidden = false;
}

/* =========================================================
   NAVEGAÇÃO
   ========================================================= */
$("#tabbar").addEventListener("click", e => {
  const b = e.target.closest(".tab"); if (!b) return;
  go(b.dataset.go);
});
function go(name) {
  S.screen = name;
  $$(".screen").forEach(s => { s.hidden = s.dataset.screen !== name; });
  $$(".tab").forEach(b => b.classList.toggle("is-on", b.dataset.go === name));
  if (name === "perfil") renderProfile();
  if (name === "mapa") {
    refreshMapSize();
    // posição salva de uma sessão anterior não dispensa o watch: sem ele o
    // marcador ficava congelado onde o usuário estava da última vez
    if (!S.geo && !S.geoNegado) pedirLocalizacao(true, true);   // pede ao abrir o mapa
    else { marcarUsuario(false); iniciarWatch(); }
  }
}

/* páginas empilhadas — cada camada aberta vira um passo no histórico,
   para o botão voltar do celular fechar a camada em vez de sair do app */
const pushLayer = () => history.pushState({ layer: Date.now() }, "");

let _camada = 0;

function openPage(el, html) {
  pushLayer();
  el.style.zIndex = 1000 + ++_camada;
  el.innerHTML = html; el.hidden = false;
  el.scrollTop = 0;
  el.querySelector("[data-back]")?.addEventListener("click", () => history.back());
}
function openLayer() {
  return [$("#pageArticle"), $("#pageSaved"), $("#pageAuth")].find(p => !p.hidden);
}

let sairEm = 0;
window.addEventListener("popstate", () => {
  const page = openLayer();
  if (page) return closePage(page);
  if (!$("#mapSheet").hidden) return closeSheet();
  if (Date.now() < sairEm) return;            // segundo toque: sai do app
  sairEm = Date.now() + 2500;
  pushLayer();
  toast("Toque em voltar de novo para sair");
});

function closePage(el) {
  el.classList.add("is-closing");
  setTimeout(() => {
    el.hidden = true; el.classList.remove("is-closing"); el.innerHTML = "";
    el.style.zIndex = ""; _camada = Math.max(0, _camada - 1);
  }, 220);
}

/* =========================================================
   HOME
   ========================================================= */
function renderChips() {
  $("#catChips").innerHTML = CATS.map(c =>
    `<button class="chip${c === S.cat ? " is-on" : ""}" data-cat="${c}">${catLabel(c)}</button>`).join("");
}
$("#catChips").addEventListener("click", e => {
  const b = e.target.closest(".chip"); if (!b) return;
  S.cat = b.dataset.cat; save(); renderChips(); renderHome();
});
$("#searchInput").addEventListener("input", e => { S.q = e.target.value.trim().toLowerCase(); renderHome(); });
/* ---------------- filtro de cidade ---------------- */
function pintarCidade() {
  $("#regionLabel").textContent = S.cidade ? S.cidade.split(" ")[0] : t("allCities");
  $("#regionBtn").classList.toggle("is-on", !!S.cidade);
}

$("#regionBtn").addEventListener("click", () => {
  const lista = CIDADES.length ? CIDADES : [];
  if (!lista.length) return pedirLocalizacao(false);   // sem servidor, sem filtro
  const total = lista.reduce((s, [, n]) => s + n, 0);
  openPage($("#pageSaved"), `
    <div class="page__bar">
      <button class="circbtn" data-back aria-label="Voltar"><svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7"/></svg></button>
      <h1>${t("chooseCity")}</h1><span style="width:38px"></span>
    </div>
    <div class="saved-list"><div class="cidades" id="listaCidades">
      <button class="cidade ${S.cidade ? "" : "is-on"}" data-cidade="">
        ${t("allCities")}<b>${total}</b></button>
      ${lista.map(([nome, n]) => `<button class="cidade ${S.cidade === nome ? "is-on" : ""}"
        data-cidade="${nome}">${nome}<b>${n}</b></button>`).join("")}
    </div></div>`);
  $("#listaCidades").addEventListener("click", e => {
    const b = e.target.closest("[data-cidade]"); if (!b) return;
    S.cidade = b.dataset.cidade; save();
    pintarCidade(); renderHome(); renderMap();
    history.back();
  });
});

function match(i) {
  if (i.kind === "noticia" && !S.prefs.noticias) return false;
  if (i.kind === "evento" && !S.prefs.eventos) return false;
  if (i.kind === "cinema" && !S.prefs.cinema) return false;
  if (S.homeTipo && i.kind !== S.homeTipo) return false;
  if (S.cidade && i.cidade !== S.cidade) return false;
  const okCat = S.cat === "Todos" || i.cat === S.cat;
  const L = loc(i);
  const okQ = !S.q || (L.title + " " + L.lead + " " + (i.place || "")).toLowerCase().includes(S.q);
  return okCat && okQ;
}

function km(a, b) {
  const r = x => x * Math.PI / 180, R = 6371;
  const h = Math.sin(r(b[0] - a[0]) / 2) ** 2 +
            Math.cos(r(a[0])) * Math.cos(r(b[0])) * Math.sin(r(b[1] - a[1]) / 2) ** 2;
  return Math.round(R * 2 * Math.asin(Math.sqrt(h)));
}

function calcDist(lista) {
  if (!S.geo) return lista;
  lista.forEach(i => { i.dist = (i.lat != null) ? km(S.geo, [i.lat, i.lng]) : null; });
  return lista;
}
/* Item com data se ordena pelo que vem primeiro, não pelo que foi publicado
   antes. Por distância, o mais perto sobe mesmo que aconteça daqui a um mês. */
function ordenaDatados(lista) {
  calcDist(lista);
  const porData = (a, b) => new Date(a.when || 0) - new Date(b.when || 0);
  if (S.ordem !== "perto" || !S.geo) return [...lista].sort(porData);
  return [...lista].sort((a, b) => ((a.dist ?? 9999) - (b.dist ?? 9999)) || porData(a, b));
}

const TITULO_FEED = { noticia: "Principais notícias",
                      evento: "Eventos na região", cinema: "Cinema hoje" };
/* estado antigo pode ter "" gravado, de quando existia "Todos" */
if (!TITULO_FEED[S.homeTipo]) S.homeTipo = "noticia";

function renderHome() {
  // interesses só mudam a ordem: nada some da lista
  const porInteresse = l => {
    if (S.cat !== "Todos" || !S.interests.length) return l;
    return [...l].sort((a, b) =>
      (S.interests.includes(b.cat) ? 1 : 0) - (S.interests.includes(a.cat) ? 1 : 0));
  };
  // o cartaz chega como filme x sala; na lista o filme aparece uma vez só
  const filmes = ordenaDatados(porFilme(CINEMA.filter(match)));
  const evs = ordenaDatados(EVENTS.filter(match));
  const news = NEWS.filter(match);

  const lista = porInteresse(
    S.homeTipo === "evento" ? evs : S.homeTipo === "cinema" ? filmes : news);

  // O seletor de ordem só faz sentido onde existe data e lugar
  $("#ordemLinha").hidden = S.homeTipo === "noticia";
  $("#ordemPerto").disabled = !S.geo;
  $("#ordemPerto").title = S.geo ? "" : "Ative a localização para ordenar por distância";

  $("#feedTitulo").textContent = TITULO_FEED[S.homeTipo];
  // No evento quem abre a lista completa é a Agenda; dois botões para a mesma
  // tela só ocupavam espaço.
  $("#verAgenda").hidden = S.homeTipo !== "evento";

  const hero = lista[0];
  $("#heroCard").hidden = !hero;
  if (hero) {
    const L = loc(hero);
    $("#heroCard").dataset.id = hero.id;
    $("#heroCard").innerHTML = `
      <div class="hero__bg">${art(hero)}</div><div class="hero__shade"></div>
      <div class="hero__in">
        <div class="hero__tags"><span class="tag">${catLabel(hero.cat)}</span><span class="tag tag--ghost">${hero.place || ""}</span></div>
        <h3>${L.title}</h3>
        <div class="hero__meta"><span class="src">${SOURCES[hero.src].name}</span><i class="dot-sep"></i>${hero.time}</div>
      </div>`;
  }

  const rest = lista.slice(hero ? 1 : 0);
  $("#newsList").innerHTML = rest.length ? rest.slice(0, 6).map(cardHTML).join("")
    : `<div class="empty">${t("emptyFeed")}</div>`;
  $("#verTodas").hidden = rest.length <= 6 || S.homeTipo === "evento";
  $("#verTodas").firstChild.textContent = `Ver tudo (${lista.length}) `;
}

const ICONE_PIN = '<svg viewBox="0 0 24 24" class="svg-ico"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>';

/* Um cartão só para notícia, evento e cinema. O trilho horizontal mostrava
   dois eventos por tela e escondia o resto; a lista vertical mostra o triplo e
   deixa "Todos" ser uma lista de verdade em vez de três blocos empilhados. */
const primeiraHora = f =>
  ((f.salas || [f]).map(s => (s.sessoes || [])[0]).filter(Boolean)[0] || {}).hora || "";

function cardHTML(i) {
  const L = loc(i);
  const datado = i.kind === "evento" || i.kind === "cinema";
  const selo = i.kind === "cinema"
    ? `<span class="card__quando card__quando--cine"><b>${primeiraHora(i)}</b><i>hoje</i></span>`
    : i.kind === "evento" ? `<span class="card__quando"><b>${i.day}</b><i>${i.month}</i></span>` : "";
  const rodape = datado
    ? `<span class="card__local">${i.place || ""}</span>${
        i.price ? `<span class="tag tag--price">${i.price}</span>` : ""}`
    : `<span class="src">${SOURCES[i.src].name}</span><i class="dot-sep"></i>${i.time}`;
  return `<button class="card" data-open="${i.id}">
    <div class="card__thumb">${art(i, selo)}</div>
    <div class="card__body">
      <div class="card__cat">${catLabel(i.cat)}</div>
      <div class="card__title">${L.title}</div>
      <div class="card__meta">${rodape}</div>
    </div></button>`;
}

function updIcon(k) {
  const p = {
    traffic: '<circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6L17 7M7 17l-1.4 1.4"/>',
    ticket: '<path d="M4 9V7h16v2a3 3 0 0 0 0 6v2H4v-2a3 3 0 0 0 0-6z"/><path d="M13 7v10"/>',
    bus: '<rect x="4" y="4" width="16" height="13" rx="3"/><path d="M4 11h16M7 20v-3M17 20v-3"/><circle cx="8.5" cy="14.5" r=".8"/><circle cx="15.5" cy="14.5" r=".8"/>'
  }[k];
  return `<svg viewBox="0 0 24 24">${p}</svg>`;
}

/* lista completa de notícias */
function diaChave(iso) {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function rotuloDia(chave) {
  const hoje = diaChave(new Date()), d = new Date(chave + "T12:00:00");
  const ontem = diaChave(new Date(Date.now() - 86400000));
  if (chave === hoje) return "Hoje";
  if (chave === ontem) return "Ontem";
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
}

function abrirListaPorDia() {
  // Segue o tipo escolhido na home. Antes listava só notícia, então "Ver tudo"
  // com Cinema marcado abria uma tela que não tinha nada a ver com a lista.
  const news = S.homeTipo === "evento" ? ordenaDatados(EVENTS.filter(match))
    : S.homeTipo === "cinema" ? ordenaDatados(porFilme(CINEMA.filter(match)))
    : NEWS.filter(match);
  // o item datado se organiza pelo dia em que acontece, não em que foi publicado
  const dia = i => diaChave(i.when || i.published);
  // Ordenar por data e inverter colocava a sessão mais distante no futuro como
  // dia inicial. Aqui o dia de hoje vem primeiro, e os vizinhos se afastam dele.
  const hoje = diaChave(new Date().toISOString());
  const dias = [...new Set(news.map(dia))]
    .sort((x, y) => Math.abs(Date.parse(x) - Date.parse(hoje))
                  - Math.abs(Date.parse(y) - Date.parse(hoje)));
  let diaAtivo = dias[0];

  const listar = () => {
    const doDia = news.filter(i => dia(i) === diaAtivo);
    $("#listaDia").innerHTML = doDia.length ? doDia.map(cardHTML).join("")
      : `<div class="empty">${t("emptyFeed")}</div>`;
    $$("#chipsDia .chip").forEach(c => c.classList.toggle("is-on", c.dataset.dia === diaAtivo));
  };

  openPage($("#pageSaved"), `
    <div class="page__bar">
      <button class="circbtn" data-back aria-label="Voltar"><svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7"/></svg></button>
      <h1>${S.homeTipo === "evento" ? t("agenda") : TITULO_FEED[S.homeTipo]}</h1><span style="width:38px"></span>
    </div>
    <div class="chips" id="chipsDia">
      ${dias.map(d => `<button class="chip" data-dia="${d}">${rotuloDia(d)}
        <b>${news.filter(i => dia(i) === d).length}</b></button>`).join("")}
    </div>
    <div class="saved-list"><div class="list" id="listaDia" style="padding-bottom:24px"></div></div>`);

  $("#chipsDia").addEventListener("click", e => {
    const b = e.target.closest("[data-dia]"); if (!b) return;
    diaAtivo = b.dataset.dia; listar();
  });
  listar();
}
$("#verTodas").addEventListener("click", abrirListaPorDia);
/* A Agenda tinha tela própria, com o mesmo desenho pior. Agora ela abre esta. */
$("#verAgenda").addEventListener("click", abrirListaPorDia);


function horaDe(iso) {
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}


/* Sem coordenada não há pin para abrir, e um botão que não leva a lugar nenhum
   é pior do que texto. */
function localHTML(i) {
  return i.lat != null
    ? `<button class="art__local" data-mapa="${i.id}" title="Ver no mapa">${ICONE_PIN} ${i.place}</button>`
    : `<span>${ICONE_PIN} ${i.place}</span>`;
}

/* clique em qualquer card */
document.addEventListener("click", e => {
  // o atalho do local fica dentro do cartão, então precisa ser testado antes
  const mp = e.target.closest("[data-mapa]");
  if (mp) { abrirNoMapa(mp.dataset.mapa); return; }
  const o = e.target.closest("[data-open]");
  if (o) { openArticle(o.dataset.open); return; }
  const h = e.target.closest("#heroCard");
  if (h && h.dataset.id) openArticle(h.dataset.id);
});

/* =========================================================
   ARTIGO
   ========================================================= */
function openArticle(id) {
  const i = byId(id); if (!i) return;
  const L = loc(i), src = SOURCES[i.src];
  const related = ALL.filter(x => x.id !== i.id && x.cat === i.cat &&
    (!x.img || x.img !== i.img)).slice(0, 2);
  const badge = (S.lang !== "pt" && CONTENT_I18N[S.lang] && CONTENT_I18N[S.lang][i.id]) ? `<span class="tag tag--ghost" style="background:var(--surface-2);color:var(--ink-3)">${t("translated")}</span>` : "";

  openPage($("#pageArticle"), `
    <div class="page__bar">
      <button class="circbtn" data-back aria-label="Voltar"><svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7"/></svg></button>
      <h1>${i.kind === "evento" ? t("event") : t("news")}</h1>
      <button class="circbtn" id="shareBtn" aria-label="Compartilhar">
        <svg viewBox="0 0 24 24"><circle cx="18" cy="5" r="2.5"/><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="19" r="2.5"/><path d="M8.2 10.8l7.6-4.4M8.2 13.2l7.6 4.4"/></svg></button>
      <button class="circbtn${isSaved(i.id) ? " is-on" : ""}" id="saveBtn" aria-label="${t("save")}">
        <svg viewBox="0 0 24 24"><path d="M7 4h10v16l-5-4-5 4z"/></svg></button>
    </div>
    <div class="art">
      <div class="art__hero">${art(i)}<span class="tag art__cat">${catLabel(i.cat)}</span></div>
      ${i.credit ? `<p class="art__credito">Foto: ${i.credit}</p>` : ""}
      <div class="art__in">
        <h1>${L.title}</h1>
        <div class="art__meta"><span class="src">${src.name}</span><i class="dot-sep"></i>${i.time}${
          i.place ? `<i class="dot-sep"></i>${localHTML(i)}` : ""} ${badge}</div>
        <p class="art__lead">${L.lead}</p>
        ${sessoesHTML(i)}
        ${i.body.slice(0, 2).map(p => `<p>${p}</p>`).join("")}
        ${i.body.length ? `<figure class="art__fig">${art(i)}</figure>
        <p class="art__figcap">${i.figcap}</p>` : ""}
        ${i.body.slice(2).map(p => `<p>${p}</p>`).join("")}
        <a class="art__src" href="${i.url || src.url}" target="_blank" rel="noopener">
          <span><small>${t("source")}</small><b>${src.name}</b></span>
          <span class="sourcelink">${i.kind === "cinema" ? t("buyTicket") : t("openSource")}
            <svg viewBox="0 0 24 24"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>
          </span>
        </a>
      </div>
      ${related.length ? `<div class="sec-head"><h2>${t("relatedTitle")}</h2></div>
        <div class="list related">${related.map(cardHTML).join("")}</div>` : ""}
    </div>`);

  $("#shareBtn").addEventListener("click", async () => {
    const dados = { title: L.title, text: L.lead, url: i.url || src.url };
    if (navigator.share) { try { await navigator.share(dados); } catch (e) {} }
    else { navigator.clipboard?.writeText(dados.url); toast("Link copiado"); }
  });
  $("#saveBtn").addEventListener("click", () => {
    $("#saveBtn").classList.toggle("is-on", toggleSave(i.id));
  });
}

/* =========================================================
   MAPA
   ========================================================= */
let _map, _pinLayer;
let _marcas = {};   /* marca do mapa por id, para achar a que precisa de realce */
/* O que o mapa mostra, independente do que a home mostra. Conjunto vazio quer
   dizer "todos": assim incluir um tipo novo não exige mexer aqui. */
let _filtroMapa = new Set();
let _zoomT = 0;              /* espera o zoom parar antes de refazer os pins */
let _assinaturaPins = null;  /* o que esta desenhado agora, para nao redesenhar igual */
const RP = [-21.1775, -47.8103];

function renderMap() {
  if (!window.L) return;
  if (!_map) {
    _map = L.map("map", { zoomControl: false, attributionControl: true,
                          maxZoom: 19 }).setView(RP, 13);
    setTimeout(() => _map.invalidateSize(), 300);
    // A CARTO passou a exigir chave e devolve o tile com a marca "API KEY
    // REQUIRED" carimbada por cima do mapa. O OpenStreetMap serve sem chave;
    // em troca pede uso moderado, então nada de pré-carregar área.
    // Camada vetorial do OpenFreeMap: sem cadastro, com rodovia em amarelo,
    // rio em azul e rótulo legível em qualquer zoom. Os provedores raster
    // gratuitos ou pediam chave (CARTO), recusavam a origem (Wikimedia) ou
    // paravam de ter dado em zoom alto e carimbavam "map data not yet
    // available" (Esri, a partir do 17 aqui).
    if (L.maplibreGL) {
      const camada = L.maplibreGL({
        style: "https://tiles.openfreemap.org/styles/liberty",
        attribution: '&copy; <a href="https://openfreemap.org">OpenFreeMap</a> '
                   + '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(_map);
      const gl = camada.getMaplibreMap();
      // styledata cobre o caso de o estilo já ter carregado antes de chegarmos
      // aqui, que "load" sozinho deixaria passar
      gl.on("styledata", () => realcarVias(gl));
      if (gl.isStyleLoaded()) realcarVias(gl);
    } else {
      // navegador sem WebGL: o mapa continua de pé, só em cinza
      L.tileLayer("https://services.arcgisonline.com/ArcGIS/rest/services/"
                  + "Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
        maxZoom: 16,
        attribution: 'Esri, HERE, Garmin',
      }).addTo(_map);
    }
    L.control.zoom({ position: "bottomright" }).addTo(_map);
    _pinLayer = L.layerGroup().addTo(_map);
    _map.on("zoomend", () => { clearTimeout(_zoomT); _zoomT = setTimeout(renderMap, 120); });
    // arrastar o mapa é o usuário dizendo que quer olhar outro lugar
    _map.on("dragstart", () => { _seguindo = false; });
  }
  marcarUsuario(false);
  const longe = _map.getZoom() < 10;   // só bem afastado é que filtra
  const visiveis = PINS.filter(p => {
    if (p.lat == null) return false;
    if (_filtroMapa.size && !_filtroMapa.has(p.type === "ev" ? "ev"
        : p.type === "cine" ? "cine" : "news")) return false;
    // afastado demais, só os favoritos, para o mapa não virar um amontoado
    if (longe && !isSaved(p.id) && !(p.more || []).some(isSaved)) return false;
    // o pin some quando nenhum item dele passa no filtro de cidade
    if (S.cidade && ![p.id, ...(p.more || [])].some(id => { const i = byId(id); return i && i.cidade === S.cidade; })) return false;
    return true;
  });
  // Mesmo conjunto de pins: nao ha o que redesenhar. Isso corta o zoom, o
  // filtro que nao mudou nada e a releitura de 90 s que veio sem novidade.
  const assinatura = visiveis.map(p => p.id + ":" + p.n).join(",");
  if (assinatura === _assinaturaPins) return;
  _assinaturaPins = assinatura;
  _pinLayer.clearLayers();
  _marcas = {};
  visiveis.forEach(p => {
    const icon = L.divIcon({
      className: "pinwrap", iconSize: [36, 46], iconAnchor: [18, 40],
      html: marcaHTML(p)
    });
    _marcas[p.id] = L.marker([p.lat, p.lng], { icon, zIndexOffset: p.n > 1 ? 600 : 0 })
      .addTo(_pinLayer)
      .on("click", e => { destacarPin(e.target.getElement()); openSheet(p.id, p.more, p.n); });
  });
}

/* A cor sozinha não diz o tipo para quem não distingue azul de amarelo, então
   cada marca carrega também o desenho: linhas de texto na notícia, calendário
   no evento. */
const GLIFO = {
  news: '<path d="M10.6 11.6h10.8M10.6 15.6h10.8M10.6 19.6h6.6"/>',
  ev: '<rect x="10.4" y="11.2" width="11.2" height="10.2" rx="2.6"/>' +
      '<path d="M10.4 14.8h11.2M13.7 9v3.2M18.3 9v3.2"/>',
  // pipoca: o balde e os três grãos saindo por cima
  cine: '<path d="M11.4 13.2h9.2l-1 8.6h-7.2z"/>' +
        '<path d="M14.7 13.6v7.8M17.3 13.6v7.8"/>' +
        '<circle cx="13.4" cy="10.6" r="1.7"/><circle cx="16.6" cy="9.4" r="1.9"/>' +
        '<circle cx="19.6" cy="10.8" r="1.6"/>'
};
function marcaHTML(p) {
  const tipo = GLIFO[p.type] ? p.type : "news";
  const rotulo = p.label ? `<span class="pin__label">${p.label}</span>` : "";
  return `<span class="pin pin--${tipo}">
    <span class="pin__pulse"></span>
    <svg viewBox="0 0 32 40" class="pin__svg" aria-hidden="true">
      <path class="pin__shape" d="M11 2h10a9 9 0 0 1 9 9v8a9 9 0 0 1-9 9h-1.4L16 37.4 12.4 28H11a9 9 0 0 1-9-9v-8a9 9 0 0 1 9-9z"/>
      <g class="pin__ico">${GLIFO[tipo]}</g>
    </svg>
    ${rotulo}
    ${p.n > 1 ? `<b class="pin__n">${p.n > 99 ? "99+" : p.n}</b>` : ""}</span>`;
}
/* o realce existia no CSS mas nada o ligava: a marca tocada ficava igual às outras */
function destacarPin(el, piscar) {
  $$(".pin").forEach(x => x.classList.remove("is-on", "is-flash"));
  const marca = el && el.querySelector(".pin");
  if (!marca) return;
  marca.classList.add("is-on");
  // Chegando de fora do mapa a pessoa não sabe para onde olhar: a troca de cor
  // por 0,3 s diz qual dos pins é o da matéria que ela estava lendo.
  if (piscar) {
    marca.classList.add("is-flash");
    setTimeout(() => marca.classList.remove("is-flash"), 700);
  }
}

/* leva ao mapa e abre a ficha em cima do pin que já existe para o evento */
function abrirNoMapa(id) {
  const i = byId(id);
  if (!i || i.lat == null) return;
  _seguindo = false;              // ele quer ver o evento, não a própria posição

  // A matéria é uma camada por cima da tela: trocar de tela por baixo dela não
  // muda o que se vê, e o toque no local parecia não fazer nada. Ela sai por
  // history.back(), e quem fecha de fato é o popstate — chamar closePage()
  // junto fecharia duas vezes e furaria a conta de _camada.
  //
  // O resto só começa depois que a camada saiu. Fazendo em paralelo, o popstate
  // chegava atrasado, encontrava a ficha já aberta e fechava a ficha em vez da
  // camada: a pessoa via o mapa piscar e voltar ao normal.
  const tinhaCamada = !!openLayer();
  if (tinhaCamada) history.back();

  const seguir = () => {
    go("mapa");
    $$(".tab").forEach(b => b.classList.toggle("is-on", b.dataset.go === "mapa"));
    setTimeout(() => {
      if (!_map) return;
      _map.invalidateSize();
      const p = PINS.find(x => x.id === id || (x.more || []).includes(id));
      let feito = false;
      const chegou = () => {
        if (feito) return;                  // moveend e rede de segurança
        feito = true;
        if (p && _marcas[p.id]) destacarPin(_marcas[p.id].getElement(), true);
        openSheet(id, p ? p.more : []);
      };
      // flyTo em vez de setView: o salto seco não mostrava o caminho, e sem ver
      // o mapa se mover ninguém sabe onde o ponto foi parar. O destaque e a
      // ficha esperam o voo acabar, senão piscam com o mapa ainda correndo.
      // Já no lugar: voar para onde se está sacode a tela sem levar a lugar
      // nenhum, e o Leaflet nem sempre emite moveend quando a origem e o
      // destino são o mesmo ponto, então a ficha ainda esperava a rede de
      // segurança. Perto o bastante, vai direto ao destaque.
      const alvo = L.latLng(i.lat, i.lng);
      const parado = _map.getCenter().distanceTo(alvo) < 40
                  && Math.abs(_map.getZoom() - 16) < 0.2;
      if (parado) return chegou();
      _map.once("moveend", chegou);
      _map.flyTo(alvo, 16, { duration: 1.1 });
      // com o app em segundo plano o voo congela e moveend não vem; sem esta
      // rede a ficha nunca abriria
      setTimeout(chegou, 1600);
    }, 120);
  };

  // 260 ms cobre a saída da camada, que leva 220 ms
  tinhaCamada ? setTimeout(seguir, 260) : seguir();
}

/* o cartão de evento é uma div com role=button: Enter e espaço não
   disparam clique sozinhos como fariam num <button> */
document.addEventListener("keydown", e => {
  if (e.key !== "Enter" && e.key !== " ") return;
  const b = e.target.closest('[role="button"][data-open]');
  if (!b) return;
  e.preventDefault();
  b.click();
});

/* O estilo vem em tons de areia, discreto demais para um mapa que serve de
   fundo a pins: rodovia e rio somem no meio do bege. Aqui eles voltam a ser
   amarelo e azul, num tom suave, e as vias afinam: a espessura do estilo é
   pensada para mapa de navegação e, no zoom afastado, vira uma mancha. */
const AMARELO_VIA = "#F0D486";
const AMARELO_BORDA = "#DCBB68";
const AZUL_AGUA = "#9FCBE8";
const FATOR_ESPESSURA = 0.62;

/* Envolver a largura num ["*", ...] não funciona: o MapLibre exige que a
   expressão de zoom seja a raiz da propriedade. O jeito é escalar os valores
   de saída do interpolate, um a um. */
function escalar(largura, fator) {
  if (typeof largura === "number") return largura * fator;
  if (!Array.isArray(largura) || largura[0] !== "interpolate") return largura;
  const saida = largura.slice();
  for (let i = 4; i < saida.length; i += 2) {     // 3 é parada, 4 é valor
    if (typeof saida[i] === "number") saida[i] = +(saida[i] * fator).toFixed(3);
  }
  return saida;
}

function realcarVias(gl) {
  // styledata dispara a cada carga de fonte e de tile; sem esta trava a
  // largura seria multiplicada de novo a cada evento até a via desaparecer
  if (gl._viasRealcadas) return;
  gl._viasRealcadas = true;

  const tenta = fn => { try { fn(); } catch (e) { /* camada ausente no estilo */ } };
  for (const camada of gl.getStyle().layers) {
    const id = camada.id;
    if (/^(road|tunnel|bridge)_(motorway|trunk|primary|secondary)/.test(id)) {
      tenta(() => gl.setPaintProperty(
        id, "line-color", /casing$/.test(id) ? AMARELO_BORDA : AMARELO_VIA));
      tenta(() => {
        const largura = gl.getPaintProperty(id, "line-width");
        if (largura !== undefined) {
          gl.setPaintProperty(id, "line-width", escalar(largura, FATOR_ESPESSURA));
        }
      });
    } else if (/^(water|waterway)/.test(id) && !/label/.test(id)) {
      tenta(() => gl.setPaintProperty(
        id, camada.type === "fill" ? "fill-color" : "line-color", AZUL_AGUA));
    }
  }
}

function refreshMapSize() {
  if (_map) setTimeout(() => _map.invalidateSize(), 80);
}

let _euMarker, _euCirculo;

function marcarUsuario(centralizar) {
  if (!_map || !S.geo) return;
  const [lat, lng, prec] = S.geo;
  if (!_euMarker) {
    _euMarker = L.marker([lat, lng], {
      zIndexOffset: 1000,
      icon: L.divIcon({ className: "euwrap", iconSize: [22, 22], iconAnchor: [11, 11],
        html: '<span class="eu"><i></i></span>' })
    }).addTo(_map).bindTooltip("Você está aqui");
    _euCirculo = L.circle([lat, lng], { radius: prec || 120, color: "#1A73E8",
      weight: 1, fillColor: "#1A73E8", fillOpacity: .12 }).addTo(_map);
  } else {
    _euMarker.setLatLng([lat, lng]);
    _euCirculo.setLatLng([lat, lng]).setRadius(prec || 120);
  }
  if (centralizar) _map.setView([lat, lng], 14);
  // segue o usuário só enquanto ele não tiver arrastado o mapa
  else if (_seguindo && !_map.getBounds().pad(-0.25).contains([lat, lng])) _map.panTo([lat, lng]);
}

/* =========================================================
   localização ao vivo
   ========================================================= */
let _watch = null;
let _seguindo = true;        // volta a false quando o usuário arrasta o mapa
let _ultimoRender = 0;       // throttle do renderHome
let _ultimaPos = null;

const OPCOES_WATCH = { enableHighAccuracy: true, maximumAge: 0, timeout: 27000 };

/* metros entre duas coordenadas, para decidir se vale re-renderizar */
function metros(a, b) {
  const R = 6371000, r = Math.PI / 180;
  const dLat = (b[0] - a[0]) * r, dLng = (b[1] - a[1]) * r;
  const m = Math.sin(dLat / 2) ** 2 +
            Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(m));
}

function guardarPos(pos, centrar) {
  const lat = +pos.coords.latitude.toFixed(6);
  const lng = +pos.coords.longitude.toFixed(6);
  const prec = Math.round(pos.coords.accuracy || 120);

  // leitura muito ruim: só aceita se ainda não temos nada melhor
  if (prec > 200 && _ultimaPos && _ultimaPos[2] <= 200) return;

  const antes = _ultimaPos;
  _ultimaPos = [lat, lng, prec];
  S.geo = _ultimaPos;
  S.geoNegado = false;

  marcarUsuario(centrar);

  // o marcador acompanha todo tique do GPS, mas a lista de "perto de você"
  // só é refeita quando o usuário andou de verdade: reordenar a cada metro
  // faria os cartões dançarem embaixo do dedo dele
  const andou = !antes || metros(antes, _ultimaPos) > 25;
  const agora = Date.now();
  if (andou && agora - _ultimoRender > 4000) {
    _ultimoRender = agora;
    save();
    renderHome();
  }
}

function pararWatch() {
  if (_watch !== null) { navigator.geolocation.clearWatch(_watch); _watch = null; }
}

function iniciarWatch() {
  if (_watch !== null || !navigator.geolocation || S.geoNegado) return;
  _watch = navigator.geolocation.watchPosition(
    p => guardarPos(p, false),
    err => {
      // permissão revogada no meio do caminho: não adianta insistir
      if (err.code === err.PERMISSION_DENIED) { pararWatch(); S.geoNegado = true; save(); }
    },
    OPCOES_WATCH
  );
}

function pedirLocalizacao(centralizar = true, silencioso = false) {
  if (!navigator.geolocation) return silencioso || toast("Este aparelho não informa a localização");
  if (!silencioso) toast("Buscando sua localização…");
  navigator.geolocation.getCurrentPosition(pos => {
    guardarPos(pos, centralizar);
    save();
    if (!silencioso) toast("Mostrando o que está perto de você");
    iniciarWatch();
  }, () => { S.geoNegado = true; save(); if (!silencioso) toast("Não consegui acessar sua localização"); },
     { enableHighAccuracy: true, timeout: 9000, maximumAge: 60000 });
}

/* o navegador suspende o watch com o app em segundo plano e nem sempre o
   retoma sozinho; recriar na volta garante posição fresca */
document.addEventListener("visibilitychange", () => {
  if (document.hidden) { pararWatch(); return; }
  if (S.screen === "mapa" || S.geo) iniciarWatch();
});
window.addEventListener("pagehide", pararWatch);

$("#mapRecenter").addEventListener("click", () => {
  closeSheet();
  if (_map) _map.invalidateSize();
  _seguindo = true;
  if (S.geo) { marcarUsuario(true); iniciarWatch(); } else { pedirLocalizacao(true); }
});

function dataLonga(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "long" }) +
         " · " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

/* No mesmo lugar, notícia e evento pedem listas diferentes: uma é um índice
   de manchetes, a outra é uma agenda, e quem abre um pin de casa de show quer
   saber que dia é cada coisa sem ter que entrar em todas. */
function maisDaquiHTML(item, more, total) {
  const outros = (more || []).map(byId).filter(Boolean);
  if (!outros.length) return "";
  const resto = total > outros.length + 1
    ? `<i class="sheet__resto">e mais ${total - outros.length - 1} neste local</i>` : "";

  if (item.kind !== "evento") {
    return `<div class="sheet__more"><b>Também aqui</b>
      ${outros.map(m => `<button data-open="${m.id}">${loc(m).title}</button>`).join("")}
      ${resto}</div>`;
  }

  const agenda = outros.filter(e => e.when)
    .sort((a, b) => new Date(a.when) - new Date(b.when));
  const sem = outros.filter(e => !e.when);
  return `<div class="sheet__agenda">
    <b>Próximos aqui <span>${total - 1}</span></b>
    ${[...agenda, ...sem].map(e => `<button class="proxev" data-open="${e.id}">
      <span class="proxev__d">${e.when
        ? `<b>${new Date(e.when).getDate()}</b><i>${MESES_CURTOS[new Date(e.when).getMonth()]}</i>`
        : "<b>—</b>"}</span>
      <span class="proxev__b">
        <span class="proxev__t">${loc(e).title}</span>
        <span class="proxev__h">${e.when ? horaDe(e.when) : ""}${
          e.price ? ` · ${e.price}` : ""}</span>
      </span>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>
    </button>`).join("")}
    ${resto}</div>`;
}

const MESES_CURTOS = ["jan", "fev", "mar", "abr", "mai", "jun",
                      "jul", "ago", "set", "out", "nov", "dez"];

function openSheet(id, more = [], total = 0) {
  const i = byId(id); if (!i) return;
  if ($("#mapSheet").hidden) pushLayer();
  const L = loc(i), src = SOURCES[i.src];
  $("#mapSheetBody").innerHTML = `
    <div class="sheet__img">${art(i)}</div>
    <div class="sheet__row"><span class="tag">${catLabel(i.cat)}</span>${i.price ? `<span class="tag tag--price">${i.price}</span>` : ""}<span class="ev__p"><svg viewBox="0 0 24 24" class="svg-ico"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"></path><circle cx="12" cy="10" r="3"></circle></svg> ${i.place}</span></div>
    <h3>${L.title}</h3>
    <div class="sheet__quando">${i.kind === "evento" && i.when ? `<svg viewBox="0 0 24 24" class="svg-ico"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg> ${dataLonga(i.when)}` : i.time}</div>
    ${sessoesHTML(i)}
    <p class="sheet__sum">${L.lead}</p>
    <a class="sourcelink" href="${i.url || src.url}" target="_blank" rel="noopener">
      ${t("readAt")}: <b>${src.name}</b>
      <svg viewBox="0 0 24 24"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>
    </a>
    <div class="sheet__acts" style="margin-top:14px">
      <button class="btn btn--ghost" id="sheetSave">${isSaved(i.id) ? t("saved2") + " ✓" : t("save")}</button>
      <button class="btn btn--primary" data-open="${i.id}">${t("openSource")}</button>
    </div>
    ${maisDaquiHTML(i, more, total)}`;
  // A sinopse inteira empurrava o "Também aqui" para fora da ficha. Na ficha
  // ela é chamariz, não leitura: o texto completo continua na matéria.
  $("#mapSheet").classList.toggle("sheet--cine", i.kind === "cinema");
  $("#mapSheet").hidden = false;
  $("#mapScrim").hidden = false;
  $("#mapFiltro").classList.add("is-hidden");
  abrirFiltroMapa(false);
  $("#sheetSave").addEventListener("click", () => {
    $("#sheetSave").textContent = toggleSave(i.id) ? t("saved2") + " ✓" : t("save");
  });
}
function closeSheet() {
  $("#mapSheet").classList.remove("is-tall");
  $("#mapSheet").style.transform = "";
  $("#mapSheet").hidden = true; $("#mapScrim").hidden = true;
  $("#mapFiltro").classList.remove("is-hidden");
  $$(".pin").forEach(p => p.classList.remove("is-on"));
}
const ROTULO_MF = { news: "Notícias", ev: "Eventos", cine: "Cinema" };
function pintarFiltroMapa() {
  $$("#mapFiltroLista button").forEach(b => {
    const on = b.dataset.mf === "todos" ? !_filtroMapa.size : _filtroMapa.has(b.dataset.mf);
    b.classList.toggle("is-on", on);
    b.setAttribute("aria-checked", on);
  });
  // Rótulo fechado: o que está marcado, ou a contagem quando não cabe
  const marcados = [..._filtroMapa];
  $("#mapFiltroRotulo").textContent =
    !marcados.length ? "Todos"
    : marcados.length === 1 ? ROTULO_MF[marcados[0]]
    : `${marcados.length} tipos`;
}
function abrirFiltroMapa(abrir) {
  $("#mapFiltroLista").hidden = !abrir;
  $("#mapFiltro").classList.toggle("is-aberto", abrir);
  $("#mapFiltroAbre").setAttribute("aria-expanded", abrir);
}
$("#mapFiltroAbre").addEventListener("click", () =>
  abrirFiltroMapa($("#mapFiltroLista").hidden));

$("#mapFiltroLista").addEventListener("click", e => {
  const b = e.target.closest("button[data-mf]");
  if (!b) return;
  const t = b.dataset.mf;
  // "Todos" e tipo marcado são estados que se excluem: marcar um limpa o outro
  if (t === "todos") _filtroMapa.clear();
  else if (_filtroMapa.has(t)) _filtroMapa.delete(t);
  else _filtroMapa.add(t);
  pintarFiltroMapa();
  renderMap();
});
// tocar fora fecha a gaveta, senão ela cobre o mapa
document.addEventListener("click", e => {
  if (!$("#mapFiltroLista").hidden && !e.target.closest("#mapFiltro")) abrirFiltroMapa(false);
});
$("#mapScrim").addEventListener("click", () => history.back());
$("#sheetClose").addEventListener("click", () => history.back());

/* arrastar a aba: para cima expande, para baixo fecha */
(function sheetDrag() {
  const sh = $("#mapSheet");
  let y0 = null, dy = 0;
  sh.addEventListener("touchstart", e => {
    if (sh.scrollTop > 0) { y0 = null; return; }
    y0 = e.touches[0].clientY; dy = 0; sh.style.transition = "none";
  }, { passive: true });
  sh.addEventListener("touchmove", e => {
    if (y0 === null) return;
    dy = e.touches[0].clientY - y0;
    if (dy > 0 && e.cancelable) e.preventDefault();   // impede o "puxar para atualizar"
    if (dy < -30) sh.classList.add("is-tall");
    if (dy > 0) sh.style.transform = `translateY(${dy}px)`;
  }, { passive: false });
  sh.addEventListener("touchend", () => {
    sh.style.transition = ""; sh.style.transform = "";
    if (dy > 90) history.back();
    y0 = null; dy = 0;
  }, { passive: true });
})();

/* =========================================================
   PERFIL
   ========================================================= */
function pintarPrefs() {
  $$("[data-pref]").forEach(c => { c.checked = !!S.prefs[c.dataset.pref]; });
}

function renderProfile() {
  $("#profName").textContent = S.user ? S.user : t("visitor");
  $("#profSub").textContent  = "Suas preferências ficam salvas neste aparelho";
  pintarPrefs();
  if (S.avatar) { $("#avatarImg").src = S.avatar; $("#avatarImg").hidden = false; $(".avatar__ph").style.display = "none"; }
  $("#interestChips").innerHTML = CATS.filter(c => c !== "Todos")
    .map(c => `<button class="chip${S.interests.includes(c) ? " is-on" : ""}" data-int="${c}">${catLabel(c)}</button>`).join("");
  paintSavedCount();
}
$("#interestChips").addEventListener("click", e => {
  const b = e.target.closest("[data-int]"); if (!b) return;
  const c = b.dataset.int, i = S.interests.indexOf(c);
  i > -1 ? S.interests.splice(i, 1) : S.interests.push(c);
  save(); b.classList.toggle("is-on"); renderHome();
});
$$("[data-pref]").forEach(c => c.addEventListener("change", async () => {
  S.prefs[c.dataset.pref] = c.checked; save(); renderHome();
  // "Alertas da região" é o único que precisa de permissão do sistema:
  // os outros dois só filtram o que já está na tela
  if (c.dataset.pref === "alertas") {
    const ok = c.checked ? await ligarPush() : await desligarPush();
    if (c.checked && !ok) { c.checked = false; S.prefs.alertas = false; save(); return; }
  }
  toast(`${c.parentElement.querySelector("b").textContent}: ${c.checked ? "ativado" : "desativado"}`);
}));

/* ---------------- lembrete dos eventos salvos ----------------
   Não há botão por evento: o que a pessoa salvou é o que ela quer
   acompanhar. O interruptor na aba de eventos salvos liga o aviso para
   todos eles de uma vez.                                              */
async function meuEndpoint() {
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    return sub ? sub.endpoint : null;
  } catch (e) { return null; }
}

const rotuloAntes = a => ({ "30m": "30 minutos", "1h": "1 hora",
                            "3h": "3 horas", "1d": "1 dia" }[a] || a);

/* manda a lista inteira: o servidor a espelha, então remover dos salvos
   também apaga o lembrete, sem chamada extra */
async function enviarLembretes() {
  const endpoint = await meuEndpoint();
  if (!endpoint) return null;
  try {
    const r = await fetch("api/lembrete/sincronizar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        endpoint,
        eventos: S.avisarSalvos ? eventosParaAvisar().map(e => e.id) : [],
        antecedencia: S.antes,
      }),
    });
    return await r.json();
  } catch (e) { return null; }
}

/* Reinscreve em silêncio a cada abertura.

   O servidor pode ter esquecido o aparelho: no plano free o container é
   recriado e o disco vai junto. O navegador também renova a inscrição por
   conta própria de tempos em tempos. Em qualquer um dos casos a pessoa
   continuaria com o interruptor ligado e sem receber nada. */
async function garantirInscricao() {
  if (!S.prefs.alertas) return;
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;
  if (Notification.permission !== "granted") return;   // sem permissão, nada a fazer
  try {
    const reg = await navigator.serviceWorker.ready;
    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      const chave = await (await fetch("api/push/chave", { cache: "no-store" })).json();
      if (!chave.ativo) return;
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true, applicationServerKey: bytesDaChave(chave.chave) });
    }
    // sempre reenvia: é barato e cobre o servidor que perdeu a lista
    await fetch("api/push/inscrever", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint: sub.endpoint }) });
    if (S.avisarSalvos) await enviarLembretes();
  } catch (e) { /* offline: tenta de novo na próxima abertura */ }
}

/* o navegador pode trocar a inscrição sozinho; sem isto o aparelho fica mudo */
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.addEventListener("message", e => {
    if (e.data === "reinscrever") garantirInscricao();
  });
}
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) garantirInscricao();
});

async function ligarAvisoSalvos(ligar) {
  if (ligar) {
    const endpoint = await meuEndpoint();
    if (!endpoint && !await ligarPush()) return false;
    S.prefs.alertas = true;
  }
  S.avisarSalvos = ligar; save();
  const d = await enviarLembretes();
  if (ligar && !d) { S.avisarSalvos = false; save(); toast("Sem conexão com o servidor"); return false; }
  pintarPrefs();
  toast(ligar ? `Aviso ${rotuloAntes(S.antes)} antes` : "Avisos desligados");
  return true;
}

/* ---------------- notificação ---------------- */
function bytesDaChave(base64) {
  const txt = atob(base64.replace(/-/g, "+").replace(/_/g, "/") +
                   "=".repeat((4 - base64.length % 4) % 4));
  return Uint8Array.from(txt, c => c.charCodeAt(0));
}

async function ligarPush() {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    toast("Este aparelho não aceita notificações"); return false;
  }
  let chave;
  try {
    const r = await fetch("api/push/chave", { cache: "no-store" });
    chave = await r.json();
  } catch (e) { chave = null; }
  if (!chave || !chave.ativo) { toast("Notificações indisponíveis no momento"); return false; }

  if (Notification.permission === "denied") {
    toast("Libere as notificações nos ajustes do navegador"); return false;
  }
  if (Notification.permission !== "granted" &&
      await Notification.requestPermission() !== "granted") return false;

  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription() ||
      await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: bytesDaChave(chave.chave),
      });
    await fetch("api/push/inscrever", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint: sub.endpoint }),
    });
    return true;
  } catch (e) {
    toast("Não consegui ativar as notificações"); return false;
  }
}

async function desligarPush() {
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    if (!sub) return true;
    await fetch("api/push/sair", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint: sub.endpoint }),
    });
    await sub.unsubscribe();
  } catch (e) { /* já estava fora */ }
  return true;
}
$("#avatarBtn").addEventListener("click", () => $("#avatarFile").click());
/* ---- recorte circular da foto de perfil ---- */
const CROP = 260;                       // diâmetro do recorte na tela
let _cropEstado = null;

$("#avatarFile").addEventListener("change", e => {
  const f = e.target.files[0]; if (!f) return;
  const r = new FileReader();
  r.onload = () => abrirRecorte(r.result);
  r.readAsDataURL(f);
  e.target.value = "";
});

function abrirRecorte(src) {
  const img = $("#cropImg");
  img.onload = () => {
    const base = CROP / Math.min(img.naturalWidth, img.naturalHeight);   // cobre o círculo
    _cropEstado = { img, base, zoom: 1, x: 0, y: 0 };
    const area = $("#cropArea").getBoundingClientRect();
    _cropEstado.x = (area.width - img.naturalWidth * base) / 2;
    _cropEstado.y = (area.height - img.naturalHeight * base) / 2;
    $("#cropZoom").value = 1;
    aplicarRecorte();
  };
  img.src = src;
  $("#crop").hidden = false;
}

function aplicarRecorte() {
  const c = _cropEstado; if (!c) return;
  const area = $("#cropArea").getBoundingClientRect();
  const e = c.base * c.zoom, w = c.img.naturalWidth * e, h = c.img.naturalHeight * e;
  const bx = (area.width - CROP) / 2, by = (area.height - CROP) / 2;   // borda do círculo
  c.x = Math.min(bx, Math.max(bx + CROP - w, c.x));                    // nunca deixa buraco
  c.y = Math.min(by, Math.max(by + CROP - h, c.y));
  c.img.style.transform = `translate(${c.x}px, ${c.y}px) scale(${e})`;
}

(function arrastarRecorte() {
  const area = $("#cropArea");
  let p0 = null, d0 = 0, z0 = 1;
  const dist = t => Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY);
  area.addEventListener("touchstart", ev => {
    if (ev.touches.length === 2) { d0 = dist(ev.touches); z0 = _cropEstado.zoom; p0 = null; }
    else { p0 = { x: ev.touches[0].clientX - _cropEstado.x, y: ev.touches[0].clientY - _cropEstado.y }; }
  }, { passive: true });
  area.addEventListener("touchmove", ev => {
    if (!_cropEstado) return;
    if (ev.touches.length === 2 && d0) {
      _cropEstado.zoom = Math.min(4, Math.max(1, z0 * dist(ev.touches) / d0));
      $("#cropZoom").value = _cropEstado.zoom;
    } else if (p0) {
      _cropEstado.x = ev.touches[0].clientX - p0.x;
      _cropEstado.y = ev.touches[0].clientY - p0.y;
    }
    aplicarRecorte();
    if (ev.cancelable) ev.preventDefault();
  }, { passive: false });
  area.addEventListener("mousedown", ev => {
    p0 = { x: ev.clientX - _cropEstado.x, y: ev.clientY - _cropEstado.y };
    const mover = m => { _cropEstado.x = m.clientX - p0.x; _cropEstado.y = m.clientY - p0.y; aplicarRecorte(); };
    const soltar = () => { document.removeEventListener("mousemove", mover); document.removeEventListener("mouseup", soltar); };
    document.addEventListener("mousemove", mover); document.addEventListener("mouseup", soltar);
  });
})();

$("#cropZoom").addEventListener("input", e => {
  if (!_cropEstado) return;
  _cropEstado.zoom = +e.target.value; aplicarRecorte();
});
$("#cropCancel").addEventListener("click", () => { $("#crop").hidden = true; _cropEstado = null; });
$("#cropOk").addEventListener("click", () => {
  const c = _cropEstado; if (!c) return;
  const area = $("#cropArea").getBoundingClientRect();
  const e = c.base * c.zoom, lado = CROP / e;
  const sx = ((area.width - CROP) / 2 - c.x) / e, sy = ((area.height - CROP) / 2 - c.y) / e;
  const cv = document.createElement("canvas"); cv.width = cv.height = 320;
  cv.getContext("2d").drawImage(c.img, sx, sy, lado, lado, 0, 0, 320, 320);
  S.avatar = cv.toDataURL("image/jpeg", 0.88); save();
  $("#avatarImg").src = S.avatar; $("#avatarImg").hidden = false;
  $(".avatar__ph").style.display = "none";
  $("#crop").hidden = true; _cropEstado = null; toast("Foto atualizada");
});
$("#replayGuide").addEventListener("click", () => { $("#app").hidden = true; openGuide(); });
$("#authBtn")?.addEventListener("click", openAuth);
$("#savedBtn").addEventListener("click", openSaved);

/* =========================================================
   SALVOS  (notícias e eventos em áreas separadas)
   ========================================================= */
let savedTab = "noticia";
function openSaved() {
  openPage($("#pageSaved"), `
    <div class="page__bar">
      <button class="circbtn" data-back aria-label="Voltar"><svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7"/></svg></button>
      <h1>${t("saved")}</h1><span style="width:38px"></span>
    </div>
    <div class="tabs" id="savedTabs">
      <button data-st="noticia" class="${savedTab === "noticia" ? "is-on" : ""}">${t("savedNews")}</button>
      <button data-st="evento" class="${savedTab === "evento" ? "is-on" : ""}">${t("savedEvents")}</button>
    </div>
    <div class="aviso-salvos" id="avisoSalvos" hidden></div>
    <div class="saved-list" id="savedList"></div>`);
  paintSaved();
  $("#savedTabs").addEventListener("click", e => {
    const b = e.target.closest("[data-st]"); if (!b) return;
    savedTab = b.dataset.st;
    $$("#savedTabs button").forEach(x => x.classList.toggle("is-on", x === b));
    paintSaved();
  });
}
function paintSaved() {
  const items = S.saved.map(byId).filter(i => i && i.kind === savedTab);
  pintarAvisoSalvos();
  $("#savedList").innerHTML = items.length ? items.map(i => {
    const L = loc(i);
    return `<div class="savecard">
      <div class="card__thumb" style="width:64px;height:64px" data-open="${i.id}">${art(i)}</div>
      <div class="savecard__b" data-open="${i.id}">
        <div class="savecard__t">${L.title}</div>
        <div class="savecard__s">${L.lead}</div>
      </div>
      <button class="savecard__x" data-unsave="${i.id}" aria-label="${t("remove")}">
        <svg viewBox="0 0 24 24"><path d="M7 7l10 10M17 7L7 17"/></svg></button>
    </div>`;
  }).join("") : `<div class="empty">${savedTab === "noticia" ? t("emptyNews") : t("emptyEvents")}</div>`;

  $$("#savedList [data-unsave]").forEach(b => b.addEventListener("click", ev => {
    ev.stopPropagation(); toggleSave(b.dataset.unsave); paintSaved();
  }));
}

/* o painel de aviso só faz sentido na aba de eventos: notícia não tem hora */
function pintarAvisoSalvos() {
  const caixa = $("#avisoSalvos");
  if (!caixa) return;
  const futuros = eventosParaAvisar().length;
  caixa.hidden = savedTab !== "evento";
  if (caixa.hidden) return;
  caixa.innerHTML = `
    <label class="pref">
      <span><b>${t("warnMe")}</b><i>${futuros
        ? `${futuros} ${futuros === 1 ? t("eventAhead") : t("eventsAhead")}`
        : t("noneAhead")}</i></span>
      <input type="checkbox" id="avisoSw" ${S.avisarSalvos ? "checked" : ""}>
      <em class="sw"></em>
    </label>
    <div class="antes" id="antesLembrete" ${S.avisarSalvos ? "" : "hidden"}>
      ${["30m", "1h", "3h", "1d"].map(a => `<button class="antes__op${
        S.antes === a ? " is-on" : ""}" data-antes="${a}">${rotuloAntes(a)}</button>`).join("")}
    </div>`;
  $("#avisoSw").addEventListener("change", async e => {
    const ok = await ligarAvisoSalvos(e.target.checked);
    if (!ok && e.target.checked) e.target.checked = false;
    paintSaved();
  });
  $("#antesLembrete").addEventListener("click", async e => {
    const b = e.target.closest("[data-antes]"); if (!b) return;
    S.antes = b.dataset.antes; save();
    // reagenda o que já estava marcado, senão a escolha só valeria pros próximos
    await enviarLembretes();
    paintSaved();
    toast(`Aviso ${rotuloAntes(S.antes)} antes`);
  });
}

/* =========================================================
   ENTRAR / CADASTRAR
   ========================================================= */
let authMode = "signin";
function openAuth() {
  openPage($("#pageAuth"), `
    <div class="page__bar">
      <button class="circbtn" data-back aria-label="Voltar"><svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7"/></svg></button>
      <h1></h1><span style="width:38px"></span>
    </div>
    <div class="auth">
      <div class="auth__logo">
        <svg viewBox="0 0 200 120"><g fill="none" stroke="currentColor" stroke-width="10" stroke-linejoin="round" stroke-linecap="round">
          <path d="M30 102 V26 h32 a20 20 0 0 1 0 40 H30"/><path d="M60 66 L92 102"/>
          <path d="M114 102 V26 h32 a21 21 0 0 1 0 42 h-32"/></g>
          <circle cx="48" cy="46" r="5.5" fill="currentColor"/><circle cx="132" cy="47" r="5.5" fill="currentColor"/></svg>
        <span>CULTURAL</span>
      </div>
      <div class="seg" id="authSeg">
        <button data-am="signin" class="${authMode === "signin" ? "is-on" : ""}">${t("signin")}</button>
        <button data-am="signup" class="${authMode === "signup" ? "is-on" : ""}">${t("signup")}</button>
      </div>
      <div class="field">
        <label for="authEmail">${t("email")}</label>
        <input id="authEmail" type="email" inputmode="email" placeholder="email@exemplo.com" autocomplete="email">
        <button class="auth__go" id="authGo">${t("cont")} <svg viewBox="0 0 24 24"><path d="M5 12h13M13 6l6 6-6 6"/></svg></button>
      </div>
      <p class="auth__note">Protótipo de navegação — nenhum dado é enviado.</p>
    </div>`);

  $("#authSeg").addEventListener("click", e => {
    const b = e.target.closest("[data-am]"); if (!b) return;
    authMode = b.dataset.am;
    $$("#authSeg button").forEach(x => x.classList.toggle("is-on", x === b));
  });
  $("#authGo").addEventListener("click", () => {
    const v = $("#authEmail").value.trim();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v)) { toast("Digite um e-mail válido"); return; }
    const nome = v.split("@")[0].replace(/[._-]+/g, " ").replace(/\b\w/g, m => m.toUpperCase());
    S.user = nome; save();
    closePage($("#pageAuth")); renderProfile();
    toast(authMode === "signin" ? `Bem-vindo, ${nome}!` : `Cadastro criado, ${nome}!`);
  });
}

/* =========================================================
   FERRAMENTA DE TRADUÇÃO
   ========================================================= */
$("#langBtn").addEventListener("click", () => {
  const idx = LANGS.findIndex(l => l.code === S.lang);
  S.lang = LANGS[(idx + 1) % LANGS.length].code;
  save(); applyLang();
  toast(`${t("langTitle")}: ${LANGS.find(l => l.code === S.lang).label}`);
});
function applyLang() {
  document.documentElement.lang = S.lang === "pt" ? "pt-BR" : S.lang;
  $("#langBtn").classList.toggle("is-on", S.lang !== "pt");
  $("#searchInput").placeholder = t("search");
  const H = $$(".sec-head h2", $('[data-screen="home"]'));
  if (H[0]) H[0].textContent = t("main");
  if (H[1]) H[1].textContent = t("events");
  if (H[2]) H[2].textContent = t("updates");
  // estes dois são opcionais: a home já trocou "deslize" pelo atalho da agenda
  // estes dois são opcionais: a home já trocou "deslize" pelo atalho da agenda
  const dica = $(".sec-head__hint"); if (dica) dica.textContent = t("swipe");
  const agenda = $("#verAgenda"); if (agenda) agenda.firstChild.textContent = t("agenda") + " ";
  const P = $$(".sec-head h2", $('[data-screen="perfil"]'));
  if (P[0]) P[0].textContent = t("receive");
  if (P[1]) P[1].textContent = t("reminder");
  if (P[2]) P[2].textContent = t("interests");
  $$("#tipoChips button").forEach(b => b.textContent = t(
    { noticia: "mapNews", evento: "mapEvents", cinema: "mapCinema" }[b.dataset.tp]));
  $$("#mapFiltroLista button").forEach(b => b.textContent = t(
    { todos: "mapAll", news: "mapNews", ev: "mapEvents", cine: "mapCinema" }[b.dataset.mf]));
  Object.assign(ROTULO_MF, { news: t("mapNews"), ev: t("mapEvents"), cine: t("mapCinema") });
  pintarFiltroMapa();
  const nav = [t("home"), t("map"), t("profile")];
  $$(".tab span").forEach((s, i) => s.textContent = nav[i]);
  $("#savedBtn .rowbtn__l").lastChild.textContent = " " + t("saved");
  $("#replayGuide .rowbtn__l").lastChild.textContent = " " + t("guideAgain");
  renderChips(); renderHome(); renderProfile();
}
