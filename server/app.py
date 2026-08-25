#!/usr/bin/env python3
"""
RP Cultural — backend de notícias reais.

- Lê feeds RSS dos veículos da região a cada REFRESH_SECONDS.
- Guarda um histórico de HISTORY_DAYS dias em data/news.json.
- Serve o app estático + API:
    GET /api/feed    -> JSON com notícias, eventos e pins do mapa
    GET /api/stream  -> SSE, avisa o app na hora em que entram notícias novas
    GET /api/health

Só usa a biblioteca padrão do Python (3.9+).
"""
import gzip, hashlib, html, io, json, math, os, queue, re, threading, time, unicodedata
import urllib.request, urllib.error, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
STORE = os.path.join(DATA_DIR, "news.json")

PORT = int(os.environ.get("PORT", "5173"))
REFRESH_SECONDS = int(os.environ.get("REFRESH_SECONDS", "300"))
HISTORY_DAYS = int(os.environ.get("HISTORY_DAYS", "7"))
MAX_ITEMS = 400

UA = {"User-Agent": "Mozilla/5.0 (compatible; RPCulturalBot/1.0)"}

# ---------------------------------------------------------------- feeds
# `regional` = feed já é da região; os demais passam pelo filtro de termos.
FEEDS = [
    {"key": "g1",      "name": "G1 Ribeirão",   "site": "https://g1.globo.com/sp/ribeirao-preto-franca/",
     "url": "https://g1.globo.com/rss/g1/sp/ribeirao-preto-franca/", "regional": True},
    {"key": "tribuna", "name": "Tribuna Ribeirão", "site": "https://tribunaribeirao.com.br/",
     "url": "https://tribunaribeirao.com.br/feed/", "regional": True},
    {"key": "g1sp",    "name": "G1 São Paulo",  "site": "https://g1.globo.com/sp/",
     "url": "https://g1.globo.com/rss/g1/sp/", "regional": False},
    {"key": "folha",   "name": "Folha",         "site": "https://www.folha.uol.com.br/cotidiano/",
     "url": "https://feeds.folha.uol.com.br/cotidiano/rss091.xml", "regional": False},
]

REGION_TERMS = [
    "ribeirao preto", "ribeirao-preto", "franca", "sertaozinho", "araraquara",
    "batatais", "jardinopolis", "cravinhos", "brodowski", "serrana", "barretos",
    "sao carlos", "bonfim paulista", "regiao de ribeirao",
]

# ------------------------------------------------- categorias e eventos
CATEGORY_RULES = [
    ("Show",        ["show", "banda", "cantor", "cantora", "turne", "turnê", "rock", "sertanejo", "rap", "samba", "dj ", "concerto"]),
    ("Festival",    ["festival", "lollapalooza", "carnaval", "expo", "feira de musica", "festa"]),
    ("Gastronomia", ["gastronom", "restaurante", "chef", "culinar", "cerveja", "food", "feira de produtores", "bar "]),
    ("Cultura",     ["teatro", "museu", "exposi", "cinema", "livro", "arte", "cultural", "sarau", "danca", "dança", "biblioteca", "espetaculo", "espetáculo"]),
    ("Cidade",      ["prefeitura", "transito", "trânsito", "obra", "onibus", "ônibus", "saude", "saúde", "escola", "policia", "polícia", "chuva", "clima", "agua", "água"]),
]
EVENT_TERMS = ["show", "festival", "exposi", "sarau", "espetaculo", "espetáculo", "concerto",
               "oficina", "workshop", "desfile", "feira de", "agenda cultural", "turne", "turnê"]
NOISE_TERMS = ["siga o ", "veja fotos", "veja as fotos", "assista ao vivo", "confira a programacao da tv",
               "resumo do dia", "boletim", "horoscopo", "horóscopo"]

# ------------------------------------------------- lugares -> pin no mapa
# (label, termos que aparecem no texto, consulta enviada ao geocodificador)
PLACES = [
    ("Theatro Pedro II",        ["theatro pedro", "teatro pedro"],            "Theatro Pedro II, Ribeirao Preto"),
    ("Bosque Municipal",        ["bosque", "zoologico", "zoológico"],         "Bosque Municipal Fabio Barreto, Ribeirao Preto"),
    ("Parque Permanente",       ["parque permanente", "recinto"],             "Parque Permanente de Exposicoes, Ribeirao Preto"),
    ("Choperia Pinguim",        ["pinguim", "choperia"],                      "Choperia Pinguim, Ribeirao Preto"),
    ("Museu do Café",           ["museu do cafe", "museu do café"],           "Museu do Cafe, Ribeirao Preto"),
    ("Praça XV",                ["praca xv", "praça xv", "quarteirao paulista", "quarteirão paulista"], "Praca XV de Novembro, Ribeirao Preto"),
    ("Campus da USP",           ["usp", "campus universitario"],              "Universidade de Sao Paulo, Ribeirao Preto"),
    ("Av. Independência",       ["independencia", "independência"],           "Avenida Independencia, Ribeirao Preto"),
    ("Av. Nove de Julho",       ["nove de julho"],                            "Avenida Nove de Julho, Ribeirao Preto"),
    ("Av. Francisco Junqueira", ["francisco junqueira"],                      "Avenida Francisco Junqueira, Ribeirao Preto"),
    ("Ribeirão Shopping",       ["ribeirao shopping", "ribeirãoshopping"],    "RibeiraoShopping, Ribeirao Preto"),
    ("Shopping Santa Úrsula",   ["santa ursula", "santa úrsula"],             "Shopping Santa Ursula, Ribeirao Preto"),
    ("Estádio Santa Cruz",      ["botafogo", "santa cruz", "estadio"],        "Estadio Doutor Oswaldo Scatena, Ribeirao Preto"),
    ("Terminal Central",        ["terminal central", "rodoviaria", "rodoviária"], "Terminal Rodoviario, Ribeirao Preto"),
    ("Hospital das Clínicas",   ["hospital das clinicas", "hc de ribeirao", "hcrp"], "Hospital das Clinicas de Ribeirao Preto"),
    ("Vila Virgínia",           ["vila virginia", "vila virgínia"],           "Vila Virginia, Ribeirao Preto"),
    ("Campos Elíseos",          ["campos eliseos", "campos elíseos"],         "Campos Eliseos, Ribeirao Preto"),
    ("Jardim Paulista",         ["jardim paulista"],                          "Jardim Paulista, Ribeirao Preto"),
    ("Centro",                  ["centro de ribeirao", "centro da cidade"],   "Centro, Ribeirao Preto"),
    ("Franca",                  ["franca"],                                   "Franca, Sao Paulo"),
    ("Sertãozinho",             ["sertaozinho", "sertãozinho"],               "Sertaozinho, Sao Paulo"),
    ("Barretos",                ["barretos"],                                 "Barretos, Sao Paulo"),
    ("Batatais",                ["batatais"],                                 "Batatais, Sao Paulo"),
    ("Cravinhos",               ["cravinhos"],                                "Cravinhos, Sao Paulo"),
    ("Jardinópolis",            ["jardinopolis", "jardinópolis"],             "Jardinopolis, Sao Paulo"),
    ("Brodowski",               ["brodowski"],                                "Brodowski, Sao Paulo"),
    ("Serrana",                 ["serrana"],                                  "Serrana, Sao Paulo"),
    ("Araraquara",              ["araraquara"],                               "Araraquara, Sao Paulo"),
    ("São Carlos",              ["sao carlos", "são carlos"],                 "Sao Carlos, Sao Paulo"),
    ("Ribeirão Preto",          ["ribeirao preto", "ribeirão preto"],         "Ribeirao Preto, Sao Paulo"),
]

DEFAULT_GEO = {
    "Universidade de Sao Paulo, Ribeirao Preto": [
        -21.159001,
        -47.856698
    ],
    "Ribeirao Preto, Sao Paulo": [
        -21.177632,
        -47.810098
    ],
    "Sertaozinho, Sao Paulo": [
        -21.137578,
        -47.991374
    ],
    "Barretos, Sao Paulo": [
        -20.553144,
        -48.569751
    ],
    "Franca, Sao Paulo": [
        -20.538177,
        -47.400979
    ],
    "Hospital das Clinicas de Ribeirao Preto": [
        -21.162303,
        -47.852801
    ],
    "Theatro Pedro II, Ribeirao Preto": [
        -21.174361,
        -47.809806
    ],
    "Museu do Cafe, Ribeirao Preto": [
        -21.170571,
        -47.84955
    ],
    "Praca XV de Novembro, Ribeirao Preto": [
        -21.175152,
        -47.808732
    ],
    "Avenida Independencia, Ribeirao Preto": [
        -21.21426,
        -47.828765
    ],
    "Avenida Nove de Julho, Ribeirao Preto": [
        -21.184859,
        -47.811549
    ],
    "Avenida Francisco Junqueira, Ribeirao Preto": [
        -21.173128,
        -47.806034
    ],
    "RibeiraoShopping, Ribeirao Preto": [
        -21.209342,
        -47.8151
    ],
    "Shopping Santa Ursula, Ribeirao Preto": [
        -21.182548,
        -47.808213
    ],
    "Terminal Rodoviario, Ribeirao Preto": [
        -21.173842,
        -47.814458
    ],
    "Vila Virginia, Ribeirao Preto": [
        -21.184517,
        -47.827666
    ],
    "Jardim Paulista, Ribeirao Preto": [
        -21.18078,
        -47.794269
    ],
    "Centro, Ribeirao Preto": [
        -21.178095,
        -47.809374
    ],
    "Batatais, Sao Paulo": [
        -20.892867,
        -47.592149
    ],
    "Cravinhos, Sao Paulo": [
        -21.340278,
        -47.729444
    ],
    "Jardinopolis, Sao Paulo": [
        -21.025513,
        -47.770681
    ],
    "Brodowski, Sao Paulo": [
        -20.98623,
        -47.657877
    ],
    "Serrana, Sao Paulo": [
        -21.204361,
        -47.604845
    ],
    "Araraquara, Sao Paulo": [
        -21.788671,
        -48.17731
    ],
    "Sao Carlos, Sao Paulo": [
        -22.01804,
        -47.891154
    ]
}

GEO_CACHE = os.path.join(DATA_DIR, "geo.json")
_geo = {}
_geo_lock = threading.Lock()

def load_geo():
    global _geo
    _geo = dict(DEFAULT_GEO)
    try:
        with open(GEO_CACHE, encoding="utf-8") as f:
            _geo.update({k: v for k, v in json.load(f).items() if v})
    except Exception:
        pass

def geocode(query):
    """Coordenadas reais via Nominatim (OpenStreetMap), com cache em disco."""
    with _geo_lock:
        if query in _geo:
            return _geo[query]
    url = ("https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=br&q="
           + urllib.parse.quote(query))
    result = None
    try:
        data = json.loads(fetch(url, timeout=15).decode("utf-8"))
        if data:
            result = [round(float(data[0]["lat"]), 6), round(float(data[0]["lon"]), 6)]
    except Exception as e:
        print(f"[geo] {query}: {e}", flush=True)
    with _geo_lock:
        _geo[query] = result
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(GEO_CACHE, "w", encoding="utf-8") as f:
            json.dump(_geo, f, ensure_ascii=False)
    time.sleep(1.1)  # política de uso do Nominatim
    return result

# ---------------------------------------------------------------- util
def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def norm(s):
    return strip_accents((s or "").lower())

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")

def clean(txt, limit=260):
    txt = html.unescape(TAG_RE.sub(" ", txt or ""))
    txt = WS_RE.sub(" ", txt).strip()
    if len(txt) > limit:
        cut = txt[:limit].rsplit(" ", 1)[0]
        txt = cut + "…"
    return txt

def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw

def to_iso(value):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except Exception:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()

def tag(el):
    return el.tag.split("}")[-1]

def first_text(item, names):
    for child in item:
        if tag(child) in names and (child.text or "").strip():
            return child.text.strip()
    return ""

def find_image(item):
    for child in item.iter():
        t = tag(child)
        if t in ("content", "thumbnail", "image") and child.get("url"):
            return child.get("url")
        if t == "enclosure" and (child.get("type") or "").startswith("image"):
            return child.get("url")
    body = first_text(item, ("encoded", "description", "summary"))
    m = re.search(r'<img[^>]+src="([^"]+)"', body or "")
    return m.group(1) if m else ""

def parse_feed(raw):
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        root = ET.fromstring(re.sub(rb"&(?!#?\w+;)", b"&amp;", raw))
    items = root.iter()
    out = []
    for el in root.iter():
        if tag(el) in ("item", "entry"):
            link = first_text(el, ("link", "guid", "id"))
            if not link:
                for c in el:
                    if tag(c) == "link" and c.get("href"):
                        link = c.get("href"); break
            out.append({
                "title": clean(first_text(el, ("title",)), 180),
                "link": link,
                "summary": clean(first_text(el, ("description", "summary", "subtitle", "encoded")), 260),
                "published": to_iso(first_text(el, ("pubDate", "published", "updated", "date"))),
                "img": find_image(el),
            })
    return out

# ---------------------------------------------------------------- regras
def guess_category(text):
    n = norm(text)
    for cat, terms in CATEGORY_RULES:
        if any(t in n for t in terms):
            return cat
    return "Cidade"

def is_event(text):
    n = norm(text)
    return any(t in n for t in EVENT_TERMS)

def is_noise(text):
    n = norm(text)
    return any(t in n for t in NOISE_TERMS)

def guess_place(text):
    n = norm(text)
    for name, terms, query in PLACES:
        if any(t in n for t in terms):
            coords = geocode(query)
            if coords:
                return {"place": name, "lat": coords[0], "lng": coords[1]}
            return {"place": name}
    return None

def is_regional(text):
    n = norm(text)
    return any(t in n for t in REGION_TERMS)

TONES = 6

def build_item(feed, raw_item):
    text = f"{raw_item['title']} {raw_item['summary']}"
    if not raw_item["title"] or not raw_item["link"]:
        return None
    if not feed["regional"] and not is_regional(text):
        return None
    if is_noise(raw_item["title"]):
        return None
    iid = hashlib.sha1(raw_item["link"].encode()).hexdigest()[:12]
    place = guess_place(text)
    return {
        "id": iid,
        "kind": "evento" if is_event(text) else "noticia",
        "cat": guess_category(text),
        "title": raw_item["title"],
        "lead": raw_item["summary"] or raw_item["title"],
        "img": raw_item["img"],
        "url": raw_item["link"],
        "src": feed["key"],
        "srcName": feed["name"],
        "srcSite": feed["site"],
        "published": raw_item["published"] or datetime.now(timezone.utc).isoformat(),
        "place": (place or {}).get("place"),
        "lat": (place or {}).get("lat"),
        "lng": (place or {}).get("lng"),
        "tone": int(iid[:2], 16) % TONES,
    }

# ---------------------------------------------------------------- store
_lock = threading.Lock()
_state = {"items": [], "updated": None}
_subscribers = []

def load_store():
    try:
        with open(STORE, encoding="utf-8") as f:
            data = json.load(f)
        _state["items"] = data.get("items", [])
        _state["updated"] = data.get("updated")
    except Exception:
        pass

def save_store():
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"updated": _state["updated"], "items": _state["items"]}, f, ensure_ascii=False)
    os.replace(tmp, STORE)

def prune(items):
    limit = datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)
    kept = []
    for it in items:
        try:
            if datetime.fromisoformat(it["published"]) >= limit:
                kept.append(it)
        except Exception:
            kept.append(it)
    kept.sort(key=lambda i: i["published"], reverse=True)
    return kept[:MAX_ITEMS]

def refresh():
    """Lê todos os feeds e devolve quantas notícias novas entraram."""
    collected = []
    for feed in FEEDS:
        try:
            for raw_item in parse_feed(fetch(feed["url"])):
                item = build_item(feed, raw_item)
                if item:
                    collected.append(item)
        except Exception as e:
            print(f"[feed] {feed['key']}: {e}", flush=True)

    with _lock:
        known = {i["id"] for i in _state["items"]}
        titles = {norm(i["title"]) for i in _state["items"]}
        fresh = []
        for i in collected:
            t = norm(i["title"])
            if i["id"] in known or t in titles:
                continue
            known.add(i["id"]); titles.add(t)
            fresh.append(i)
        merged = prune(fresh + _state["items"])
        _state["items"] = merged
        _state["updated"] = datetime.now(timezone.utc).isoformat()
        save_store()
    if fresh:
        broadcast({"type": "news", "count": len(fresh), "updated": _state["updated"]})
    print(f"[refresh] {len(collected)} lidas, {len(fresh)} novas, {len(_state['items'])} no histórico", flush=True)
    return len(fresh)

def refresh_loop():
    while True:
        try:
            refresh()
        except Exception as e:
            print("[refresh] erro:", e, flush=True)
        time.sleep(REFRESH_SECONDS)

def broadcast(payload):
    msg = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()
    for q in list(_subscribers):
        try:
            q.put_nowait(msg)
        except Exception:
            pass

# ---------------------------------------------------------------- API
def feed_payload():
    with _lock:
        items = list(_state["items"])
        updated = _state["updated"]
    news = [i for i in items if i["kind"] == "noticia"]
    events = [i for i in items if i["kind"] == "evento"]
    pins, usados = [], {}
    for i in items:
        if i.get("lat") is None:
            continue
        key = (i["lat"], i["lng"])
        n = usados.get(key, 0)
        usados[key] = n + 1
        ang, raio = n * 2.399, 0.0016 * (n ** 0.5)   # espiral, ~150 m por passo
        pins.append({"id": i["id"], "lat": i["lat"] + raio * math.cos(ang),
                     "lng": i["lng"] + raio * math.sin(ang), "label": i["place"],
                     "type": "ev" if i["kind"] == "evento" else "news"})
        if len(pins) >= 60:
            break
    sources = {f["key"]: {"name": f["name"], "url": f["site"]} for f in FEEDS}
    return {"updated": updated, "days": HISTORY_DAYS, "refresh": REFRESH_SECONDS,
            "sources": sources, "news": news, "events": events, "pins": pins,
            "total": len(items)}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, *a):
        pass

    def end_headers(self):
        # o app é atualizado com frequência: nada de HTML/CSS/JS velho em cache
        if self.path.split("?")[0].endswith((".html", ".css", ".js", ".json", "/")):
            self.send_header("Cache-Control", "no-cache, must-revalidate")
        super().end_headers()

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/feed":
            return self._json(feed_payload())
        if path == "/api/health":
            return self._json({"ok": True, "items": len(_state["items"]), "updated": _state["updated"]})
        if path == "/api/refresh":
            return self._json({"new": refresh(), "updated": _state["updated"]})
        if path == "/api/stream":
            return self.stream()
        return super().do_GET()

    def stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        q = queue.Queue(maxsize=20)
        _subscribers.append(q)
        try:
            self.wfile.write(b": conectado\n\n")
            self.wfile.flush()
            while True:
                try:
                    msg = q.get(timeout=20)
                except queue.Empty:
                    msg = b": ping\n\n"
                self.wfile.write(msg)
                self.wfile.flush()
        except Exception:
            pass
        finally:
            if q in _subscribers:
                _subscribers.remove(q)

def main():
    load_store()
    load_geo()
    threading.Thread(target=refresh_loop, daemon=True).start()
    print(f"RP Cultural em http://localhost:{PORT}  (atualiza a cada {REFRESH_SECONDS}s, histórico de {HISTORY_DAYS} dias)", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

if __name__ == "__main__":
    main()
