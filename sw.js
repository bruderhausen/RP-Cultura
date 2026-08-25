/* rede primeiro; o cache só entra quando o celular está sem conexão */
const CACHE = "rpcultural";
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET" || new URL(req.url).pathname.startsWith("/api/")) return;
  e.respondWith(
    fetch(req).then(res => {
      const copy = res.clone();
      caches.open(CACHE).then(c => c.put(req, copy)).catch(() => {});
      return res;
    }).catch(() => caches.match(req))
  );
});

/* ---------------- notificação ----------------
   O push chega vazio de propósito: o servidor só avisa que entrou coisa nova.
   O texto é montado aqui, a partir do feed, o que dispensa criptografar
   payload e evita mandar conteúdo para o serviço de push do navegador. */
async function montarAviso() {
  const padrao = { titulo: "RP Cultural", corpo: "Novidades na sua região", url: "./" };
  // lembrete de evento tem texto próprio guardado no servidor; o push em si
  // continua vazio, então nada de conteúdo passa pelo serviço do navegador
  try {
    const sub = await self.registration.pushManager.getSubscription();
    if (sub) {
      const r = await fetch("api/push/aviso", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ endpoint: sub.endpoint }),
      });
      const d = await r.json();
      if (d.aviso) return d.aviso;
    }
  } catch (e) { /* segue para o texto genérico */ }
  try {
    const r = await fetch("api/feed", { cache: "no-store" });
    const d = await r.json();
    const item = (d.news || [])[0] || (d.events || [])[0];
    if (!item) return padrao;
    const quantos = (d.news || []).length + (d.events || []).length;
    return {
      titulo: item.title,
      corpo: [item.place, quantos > 1 ? `e mais ${quantos - 1} no app` : null]
        .filter(Boolean).join(" · "),
      url: "./",
    };
  } catch (e) {
    return padrao;
  }
}

self.addEventListener("push", e => {
  e.waitUntil(montarAviso().then(a => self.registration.showNotification(a.titulo, {
    body: a.corpo,
    icon: "assets/icon-192.png",
    badge: "assets/favicon-64.png",
    tag: "rpcultural-feed",       // uma notificação por vez, sem empilhar
    renotify: true,
    data: { url: a.url },
  })));
});

self.addEventListener("notificationclick", e => {
  e.notification.close();
  const alvo = new URL(e.notification.data?.url || "./", self.location).href;
  e.waitUntil((async () => {
    const abas = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const aba of abas) {
      if (aba.url.startsWith(self.location.origin)) return aba.focus();
    }
    return self.clients.openWindow(alvo);
  })());
});
