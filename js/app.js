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
  interests: ["Show", "Cultura"], user: null, avatar: null, guideSeen: false
}, JSON.parse(localStorage.getItem(KEY) || "{}"));

const save = () => localStorage.setItem(KEY, JSON.stringify(S));
const t = k => (UI[S.lang] || UI.pt)[k];

/* conteúdo traduzido (título e resumo) */
function loc(item) {
  const tr = CONTENT_I18N[S.lang] && CONTENT_I18N[S.lang][item.id];
  return tr ? { title: tr[0], lead: tr[1] } : { title: item.title, lead: item.lead };
}
const byId = id => ALL.find(i => i.id === id);

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
  }, 2500);
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
  if (name === "mapa") refreshMapSize();
}

/* páginas empilhadas — cada camada aberta vira um passo no histórico,
   para o botão voltar do celular fechar a camada em vez de sair do app */
const pushLayer = () => history.pushState({ layer: Date.now() }, "");

function openPage(el, html) {
  pushLayer();
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
  setTimeout(() => { el.hidden = true; el.classList.remove("is-closing"); el.innerHTML = ""; }, 220);
}

/* =========================================================
   HOME
   ========================================================= */
function renderChips() {
  $("#catChips").innerHTML = CATS.map(c =>
    `<button class="chip${c === S.cat ? " is-on" : ""}" data-cat="${c}">${c === "Todos" ? (S.lang === "en" ? "All" : S.lang === "es" ? "Todos" : "Todos") : c}</button>`
  ).join("");
}
$("#catChips").addEventListener("click", e => {
  const b = e.target.closest(".chip"); if (!b) return;
  S.cat = b.dataset.cat; save(); renderChips(); renderHome();
});
$("#searchInput").addEventListener("input", e => { S.q = e.target.value.trim().toLowerCase(); renderHome(); });
$("#regionBtn").addEventListener("click", () => toast("Ribeirão Preto e região · protótipo"));

function match(i) {
  const okCat = S.cat === "Todos" || i.cat === S.cat;
  const L = loc(i);
  const okQ = !S.q || (L.title + " " + L.lead + " " + (i.place || "")).toLowerCase().includes(S.q);
  return okCat && okQ;
}

function renderHome() {
  const news = NEWS.filter(match);
  const evs  = EVENTS.filter(match);
  const hero = news[0] || evs[0];

  $("#heroCard").hidden = !hero;
  if (hero) {
    const L = loc(hero);
    $("#heroCard").dataset.id = hero.id;
    $("#heroCard").innerHTML = `
      <div class="hero__bg">${art(hero)}</div><div class="hero__shade"></div>
      <div class="hero__in">
        <div class="hero__tags"><span class="tag">${hero.cat}</span><span class="tag tag--ghost">${hero.place || ""}</span></div>
        <h3>${L.title}</h3>
        <div class="hero__meta"><span class="src">${SOURCES[hero.src].name}</span><i class="dot-sep"></i>${hero.time}<i class="dot-sep"></i>${hero.read}</div>
      </div>`;
  }

  const rest = news.slice(hero && hero.kind === "noticia" ? 1 : 0);
  $("#newsList").innerHTML = rest.length ? rest.map(cardHTML).join("")
    : `<div class="empty">${t("emptyFeed")}</div>`;

  $("#eventRail").innerHTML = evs.map(e => {
    const L = loc(e);
    return `<button class="ev" data-open="${e.id}">
      <div class="ev__img">${art(e, `<span class="ev__date"><b>${e.day}</b><i>${e.month}</i></span>`)}</div>
      <div class="ev__in"><div class="ev__t">${L.title}</div>
        <div class="ev__p">📍 ${e.place}</div></div>
    </button>`;
  }).join("") || `<div class="empty">${t("emptyFeed")}</div>`;

  $("#updateList").innerHTML = UPDATES.map(u => `
    <div class="upd"><div class="upd__ic">${updIcon(u.ic)}</div>
      <div><div class="upd__t">${u.t}</div><div class="upd__s">${u.s}</div></div></div>`).join("");
}

function cardHTML(i) {
  const L = loc(i);
  return `<button class="card" data-open="${i.id}">
    <div class="card__thumb">${art(i)}</div>
    <div class="card__body">
      <div class="card__cat">${i.cat}</div>
      <div class="card__title">${L.title}</div>
      <div class="card__meta"><span class="src">${SOURCES[i.src].name}</span><i class="dot-sep"></i>${i.time}<i class="dot-sep"></i>${i.read}</div>
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
  const related = ALL.filter(x => x.id !== i.id && x.cat === i.cat).slice(0, 2);
  const badge = (S.lang !== "pt" && CONTENT_I18N[S.lang] && CONTENT_I18N[S.lang][i.id]) ? `<span class="tag tag--ghost" style="background:var(--surface-2);color:var(--ink-3)">${t("translated")}</span>` : "";

  openPage($("#pageArticle"), `
    <div class="page__bar">
      <button class="circbtn" data-back aria-label="Voltar"><svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7"/></svg></button>
      <h1>${i.kind === "evento" ? t("event") : t("news")}</h1>
      <button class="circbtn${isSaved(i.id) ? " is-on" : ""}" id="saveBtn" aria-label="${t("save")}">
        <svg viewBox="0 0 24 24"><path d="M7 4h10v16l-5-4-5 4z"/></svg></button>
    </div>
    <div class="art">
      <div class="art__hero">${art(i)}<span class="tag art__cat">${i.cat}</span></div>
      <div class="art__in">
        <h1>${L.title}</h1>
        <div class="art__meta"><span class="src">${src.name}</span><i class="dot-sep"></i>${i.time}<i class="dot-sep"></i>${i.read}${i.place ? `<i class="dot-sep"></i>📍 ${i.place}` : ""} ${badge}</div>
        <p class="art__lead">${L.lead}</p>
        ${i.body.slice(0, 2).map(p => `<p>${p}</p>`).join("")}
        <figure class="art__fig">${art(i)}</figure>
        <p class="art__figcap">${i.figcap}</p>
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
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      maxZoom: 20, subdomains: "abcd", detectRetina: true,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
    }).addTo(_map);
    L.control.zoom({ position: "bottomright" }).addTo(_map);
    _pinLayer = L.layerGroup().addTo(_map);
  }
  _pinLayer.clearLayers();
  PINS.forEach(p => {
    if (p.lat == null) return;
    const icon = L.divIcon({
      className: "pinwrap", iconSize: [30, 52], iconAnchor: [15, 44],
      html: `<span class="pin pin--${p.type}"><span class="pin__pulse"></span>
        <svg viewBox="0 0 26 36" class="pin__svg">
          <path class="pin__shape" d="M13 34.5S24 21.8 24 13A11 11 0 1 0 2 13c0 8.8 11 21.5 11 21.5z"/>
          <circle class="pin__hole" cx="13" cy="13" r="4.2"/></svg>
        <span class="pin__label">${p.label}</span></span>`
    });
    L.marker([p.lat, p.lng], { icon }).addTo(_pinLayer).on("click", () => openSheet(p.id, p.more));
  });
}

function refreshMapSize() {
  if (_map) setTimeout(() => _map.invalidateSize(), 80);
}

$("#mapRecenter").addEventListener("click", () => {
  closeSheet();
  if (_map) { _map.invalidateSize(); _map.setView(RP, 13); }
});

function openSheet(id, more = []) {
  const i = byId(id); if (!i) return;
  if ($("#mapSheet").hidden) pushLayer();
  const L = loc(i), src = SOURCES[i.src];
  $("#mapSheetBody").innerHTML = `
    <div class="sheet__img">${art(i)}</div>
    <div class="sheet__row"><span class="tag">${i.cat}</span><span class="ev__p">📍 ${i.place}</span></div>
    <h3>${L.title}</h3>
    <p class="sheet__sum">${L.lead}</p>
    <a class="sourcelink" href="${i.url || src.url}" target="_blank" rel="noopener">
      ${t("readAt")}: <b>${src.name}</b>
      <svg viewBox="0 0 24 24"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>
    </a>
    ${(more || []).map(byId).filter(Boolean).length ? `<div class="sheet__more">
      <b>Também aqui</b>
      ${(more || []).map(byId).filter(Boolean).map(m => `<button data-open="${m.id}">${loc(m).title}</button>`).join("")}
    </div>` : ""}
    <div class="sheet__acts" style="margin-top:14px">
      <button class="btn btn--ghost" id="sheetSave">${isSaved(i.id) ? t("saved2") + " ✓" : t("save")}</button>
      <button class="btn btn--primary" data-open="${i.id}">${t("openSource")}</button>
    </div>`;
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
    .map(c => `<button class="chip${S.interests.includes(c) ? " is-on" : ""}" data-int="${c}">${c}</button>`).join("");
  paintSavedCount();
}
$("#interestChips").addEventListener("click", e => {
  const b = e.target.closest("[data-int]"); if (!b) return;
  const c = b.dataset.int, i = S.interests.indexOf(c);
  i > -1 ? S.interests.splice(i, 1) : S.interests.push(c);
  save(); b.classList.toggle("is-on");
});
$$("[data-pref]").forEach(c => c.addEventListener("change", () => {
  S.prefs[c.dataset.pref] = c.checked; save();
  toast(`${c.parentElement.querySelector("b").textContent}: ${c.checked ? "ativado" : "desativado"}`);
}));
$("#avatarBtn").addEventListener("click", () => $("#avatarFile").click());
$("#avatarFile").addEventListener("change", e => {
  const f = e.target.files[0]; if (!f) return;
  const r = new FileReader();
  r.onload = () => {
    S.avatar = r.result; save();
    $("#avatarImg").src = r.result; $("#avatarImg").hidden = false;
    $(".avatar__ph").style.display = "none"; toast("Foto atualizada");
  };
  r.readAsDataURL(f);
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
