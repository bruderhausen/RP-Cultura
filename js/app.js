/* =========================================================
   RP Cultural — lógica do protótipo
   ========================================================= */
const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

/* ---------------- estado ---------------- */
const KEY = "rpcultural.v1";
const S = Object.assign({
  cat: "Todos", q: "", lang: "pt", screen: "home",
  saved: [], prefs: { noticias: true, eventos: true, alertas: false },
  interests: [], geo: null, user: null, avatar: null, guideSeen: false
}, JSON.parse(localStorage.getItem(KEY) || "{}"));

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
  const g = "g" + item.id + Math.random().toString(36).slice(2, 6);
  const glyph = {
    Festival: '<path d="M22 78 L50 22 L78 78 Z" fill="none" stroke="#fff" stroke-width="3"/><circle cx="50" cy="46" r="8" fill="#fff"/>',
    Show:     '<path d="M38 70V32l30-7v38" fill="none" stroke="#fff" stroke-width="3.5" stroke-linejoin="round"/><circle cx="32" cy="70" r="7" fill="#fff"/><circle cx="62" cy="63" r="7" fill="#fff"/>',
    Cultura:  '<path d="M24 74h52M30 74V38M46 74V38M62 74V38M70 74V38M22 34l28-14 28 14z" fill="none" stroke="#fff" stroke-width="3.2" stroke-linejoin="round"/>',
    Cidade:   '<path d="M20 78V44l16-10v44M44 78V30l18-12v60M66 78V48l14 8v22" fill="none" stroke="#fff" stroke-width="3.2" stroke-linejoin="round"/>',
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
  return isSaved(id);
}
const paintSavedCount = () => { $("#savedCount").textContent = S.saved.length; };

/* =========================================================
   SPLASH → GUIA → APP
   ========================================================= */
window.addEventListener("load", () => {
  setTimeout(() => {
    $("#splash").classList.add("is-out");
    setTimeout(() => {
      $("#splash").remove();
      if (S.guideSeen) startApp(); else openGuide();
    }, 520);
  }, 3250);
});

/* ---------------- guia ---------------- */
let gi = 0;
function openGuide() {
  gi = 0;
  const g = $("#guide");
  g.hidden = false;
  $("#guideTrack").scrollTo({ left: 0 });
  paintGuide();
}
function closeGuide() {
  S.guideSeen = true; save();
  const g = $("#guide");
  g.style.transition = "opacity .3s"; g.style.opacity = "0";
  setTimeout(() => { g.hidden = true; g.style.opacity = ""; }, 300);
  startApp();
}
function paintGuide() {
  $$("#guideDots i").forEach((d, i) => d.classList.toggle("on", i === gi));
  $("#guideNext").textContent = gi === 2 ? "Começar" : "Continuar";
}
$("#guideNext").addEventListener("click", () => {
  if (gi === 2) return closeGuide();
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
  renderChips(); renderHome(); renderMap(); renderProfile(); paintSavedCount(); applyLang();
  if (window.paintLiveBadge) paintLiveBadge();
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
$("#regionBtn").addEventListener("click", () => pedirLocalizacao(false));

function match(i) {
  if (i.kind === "noticia" && !S.prefs.noticias) return false;
  if (i.kind === "evento" && !S.prefs.eventos) return false;
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

function porPerto(lista) {
  if (!S.geo) return lista;
  lista.forEach(i => { i.dist = (i.lat != null) ? km(S.geo, [i.lat, i.lng]) : null; });
  return [...lista].sort((a, b) => (a.dist ?? 999) - (b.dist ?? 999));
}

function renderHome() {
  // interesses só mudam a ordem: nada some da lista
  const porInteresse = l => {
    if (S.cat !== "Todos" || !S.interests.length) return l;
    return [...l].sort((a, b) =>
      (S.interests.includes(b.cat) ? 1 : 0) - (S.interests.includes(a.cat) ? 1 : 0));
  };
  const news = porInteresse(NEWS.filter(match));
  const evs  = porPerto(porInteresse(EVENTS.filter(match)));
  const hero = news[0] || evs[0];

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

  const rest = news.slice(hero && hero.kind === "noticia" ? 1 : 0);
  $("#newsList").innerHTML = rest.length ? rest.slice(0, 3).map(cardHTML).join("")
    : `<div class="empty">${t("emptyFeed")}</div>`;
  $("#verTodas").hidden = rest.length <= 3;
  $("#verTodas").firstChild.textContent = `Ver todas as notícias (${news.length}) `;

  $("#eventRail").innerHTML = evs.map(e => {
    const L = loc(e);
    return `<button class="ev" data-open="${e.id}">
      <div class="ev__img">${art(e, `<span class="ev__date"><b>${e.day}</b><i>${e.month}</i></span>`)}</div>
      <div class="ev__in"><div class="ev__t">${L.title}</div>
        <div class="ev__p"><svg viewBox="0 0 24 24" class="svg-ico"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"></path><circle cx="12" cy="10" r="3"></circle></svg> ${e.place}</div>
        <div class="ev__foot">${e.price ? `<span class="tag tag--price">${e.price}</span>`
          : e.src === "sympla" ? `<span class="tag tag--ghost2">Ingressos</span>` : ""}
          ${e.dist != null ? `<span class="ev__dist">${e.dist} km</span>` : ""}</div></div>
    </button>`;
  }).join("") || `<div class="empty">${t("emptyFeed")}</div>`;

}

function cardHTML(i) {
  const L = loc(i);
  return `<button class="card" data-open="${i.id}">
    <div class="card__thumb">${art(i)}</div>
    <div class="card__body">
      <div class="card__cat">${catLabel(i.cat)}</div>
      <div class="card__title">${L.title}</div>
      <div class="card__meta"><span class="src">${SOURCES[i.src].name}</span><i class="dot-sep"></i>${i.time}</div>
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

$("#verTodas").addEventListener("click", () => {
  const news = NEWS.filter(match);
  const dias = [...new Set(news.map(i => diaChave(i.published)))].sort().reverse();
  let diaAtivo = dias[0];

  const listar = () => {
    const doDia = news.filter(i => diaChave(i.published) === diaAtivo);
    $("#listaDia").innerHTML = doDia.length ? doDia.map(cardHTML).join("")
      : `<div class="empty">${t("emptyFeed")}</div>`;
    $$("#chipsDia .chip").forEach(c => c.classList.toggle("is-on", c.dataset.dia === diaAtivo));
  };

  openPage($("#pageSaved"), `
    <div class="page__bar">
      <button class="circbtn" data-back aria-label="Voltar"><svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7"/></svg></button>
      <h1>Todas as notícias</h1><span style="width:38px"></span>
    </div>
    <div class="chips" id="chipsDia">
      ${dias.map(d => `<button class="chip" data-dia="${d}">${rotuloDia(d)}
        <b>${news.filter(i => diaChave(i.published) === d).length}</b></button>`).join("")}
    </div>
    <div class="saved-list"><div class="list" id="listaDia" style="padding-bottom:24px"></div></div>`);

  $("#chipsDia").addEventListener("click", e => {
    const b = e.target.closest("[data-dia]"); if (!b) return;
    diaAtivo = b.dataset.dia; listar();
  });
  listar();
});

/* clique em qualquer card */
document.addEventListener("click", e => {
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
        <div class="art__meta"><span class="src">${src.name}</span><i class="dot-sep"></i>${i.time}${i.place ? `<i class="dot-sep"></i><svg viewBox="0 0 24 24" class="svg-ico"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"></path><circle cx="12" cy="10" r="3"></circle></svg> ${i.place}` : ""} ${badge}</div>
        <p class="art__lead">${L.lead}</p>
        ${i.body.slice(0, 2).map(p => `<p>${p}</p>`).join("")}
        ${i.body.length ? `<figure class="art__fig">${art(i)}</figure>
        <p class="art__figcap">${i.figcap}</p>` : ""}
        ${i.body.slice(2).map(p => `<p>${p}</p>`).join("")}
        <a class="art__src" href="${i.url || src.url}" target="_blank" rel="noopener">
          <span><small>${t("source")}</small><b>${src.name}</b></span>
          <span class="sourcelink">${t("openSource")}
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
const RP = [-21.1775, -47.8103];

function renderMap() {
  if (!window.L) return;
  if (!_map) {
    _map = L.map("map", { zoomControl: false, attributionControl: true }).setView(RP, 13);
    setTimeout(() => _map.invalidateSize(), 300);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
      maxZoom: 20, subdomains: "abcd", detectRetina: true,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
    }).addTo(_map);
    L.control.zoom({ position: "bottomright" }).addTo(_map);
    _pinLayer = L.layerGroup().addTo(_map);
    _map.on("zoomend", () => renderMap());
    // arrastar o mapa é o usuário dizendo que quer olhar outro lugar
    _map.on("dragstart", () => { _seguindo = false; });
  }
  _pinLayer.clearLayers();
  marcarUsuario(false);
  const longe = _map.getZoom() < 10;   // só bem afastado é que filtra
  PINS.forEach(p => {
    if (p.lat == null) return;
    // afastado demais, só os favoritos, para o mapa não virar um amontoado
    if (longe && !isSaved(p.id) && !(p.more || []).some(isSaved)) return;
    const icon = L.divIcon({
      className: "pinwrap", iconSize: [36, 46], iconAnchor: [18, 40],
      html: `<span class="pin pin--${p.type}"><span class="pin__pulse"></span>
        <svg viewBox="0 0 32 40" class="pin__svg">
          <path class="pin__shape" d="M16 2C8.268 2 2 8.268 2 16c0 9.5 14 22 14 22s14-12.5 14-22C30 8.268 23.732 2 16 2z"/>
          <circle class="pin__hole" cx="16" cy="15" r="5"/></svg>
        <span class="pin__label">${p.label}</span>
        ${(p.more || []).length ? `<b class="pin__n">${Math.min(99, (p.more || []).length + 1)}</b>` : ""}</span>`
    });
    L.marker([p.lat, p.lng], { icon, zIndexOffset: (p.more || []).length ? 600 : 0 }).addTo(_pinLayer).on("click", () => openSheet(p.id, p.more));
  });
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

function openSheet(id, more = []) {
  const i = byId(id); if (!i) return;
  if ($("#mapSheet").hidden) pushLayer();
  const L = loc(i), src = SOURCES[i.src];
  $("#mapSheetBody").innerHTML = `
    <div class="sheet__img">${art(i)}</div>
    <div class="sheet__row"><span class="tag">${catLabel(i.cat)}</span>${i.price ? `<span class="tag tag--price">${i.price}</span>` : ""}<span class="ev__p"><svg viewBox="0 0 24 24" class="svg-ico"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"></path><circle cx="12" cy="10" r="3"></circle></svg> ${i.place}</span></div>
    <h3>${L.title}</h3>
    <div class="sheet__quando">${i.kind === "evento" && i.when ? `<svg viewBox="0 0 24 24" class="svg-ico"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg> ${dataLonga(i.when)}` : i.time}</div>
    <p class="sheet__sum">${L.lead}</p>
    <a class="sourcelink" href="${i.url || src.url}" target="_blank" rel="noopener">
      ${t("readAt")}: <b>${src.name}</b>
      <svg viewBox="0 0 24 24"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>
    </a>
    <div class="sheet__acts" style="margin-top:14px">
      <button class="btn btn--ghost" id="sheetSave">${isSaved(i.id) ? t("saved2") + " ✓" : t("save")}</button>
      <button class="btn btn--primary" data-open="${i.id}">${t("openSource")}</button>
    </div>
    ${(more || []).map(byId).filter(Boolean).length ? `<div class="sheet__more">
      <b>Também aqui</b>
      ${(more || []).map(byId).filter(Boolean).map(m => `<button data-open="${m.id}">${loc(m).title}</button>`).join("")}
    </div>` : ""}`;
  $("#mapSheet").hidden = false;
  $("#mapScrim").hidden = false;
  $("#mapLegend").classList.add("is-hidden");
  $("#sheetSave").addEventListener("click", () => {
    $("#sheetSave").textContent = toggleSave(i.id) ? t("saved2") + " ✓" : t("save");
  });
}
function closeSheet() {
  $("#mapSheet").classList.remove("is-tall");
  $("#mapSheet").style.transform = "";
  $("#mapSheet").hidden = true; $("#mapScrim").hidden = true;
  $("#mapLegend").classList.remove("is-hidden");
  $$(".pin").forEach(p => p.classList.remove("is-on"));
}
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
function renderProfile() {
  $("#profName").textContent = S.user ? S.user : t("visitor");
  $("#profSub").textContent  = "Suas preferências ficam salvas neste aparelho";
  $$("[data-pref]").forEach(c => { c.checked = !!S.prefs[c.dataset.pref]; });
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
$$("[data-pref]").forEach(c => c.addEventListener("change", () => {
  S.prefs[c.dataset.pref] = c.checked; save(); renderHome();
  toast(`${c.parentElement.querySelector("b").textContent}: ${c.checked ? "ativado" : "desativado"}`);
}));
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
  $(".sec-head__hint").textContent = t("swipe");
  const P = $$(".sec-head h2", $('[data-screen="perfil"]'));
  if (P[0]) P[0].textContent = t("receive");
  if (P[1]) P[1].textContent = t("interests");
  $("#mapLegend").textContent = t("mapHint");
  const nav = [t("home"), t("map"), t("profile")];
  $$(".tab span").forEach((s, i) => s.textContent = nav[i]);
  $("#savedBtn .rowbtn__l").lastChild.textContent = " " + t("saved");
  $("#replayGuide .rowbtn__l").lastChild.textContent = " " + t("guideAgain");
  renderChips(); renderHome(); renderProfile();
}
