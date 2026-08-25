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
    ("Parque do Peão",          ["parque do peao", "festa do peao", "liga nacional de rodeio", "peao de barretos"], "Parque do Peao, Barretos, Sao Paulo", "Barretos"),
    ("Theatro Pedro II",        ["theatro pedro", "teatro pedro"],            "Theatro Pedro II, Ribeirao Preto", "Ribeirão Preto"),
    ("Bosque Municipal",        ["bosque municipal", "zoologico de ribeirao", "bosque fabio barreto"], "Bosque Municipal Fabio Barreto, Ribeirao Preto", "Ribeirão Preto"),
    ("Parque Permanente",       ["parque permanente", "recinto de exposicoes"], "Parque Permanente de Exposicoes, Ribeirao Preto", "Ribeirão Preto"),
    ("Choperia Pinguim",        ["choperia pinguim"],                         "Choperia Pinguim, Ribeirao Preto", "Ribeirão Preto"),
    ("Museu do Café",           ["museu do cafe", "museu do café"],           "Museu do Cafe, Ribeirao Preto", "Ribeirão Preto"),
    ("Praça XV",                ["praca xv", "praça xv", "quarteirao paulista", "quarteirão paulista"], "Praca XV de Novembro, Ribeirao Preto", "Ribeirão Preto"),
    ("Campus da USP",           ["usp de ribeirao", "campus da usp", "usp ribeirao"], "Universidade de Sao Paulo, Ribeirao Preto", "Ribeirão Preto"),
    ("Hospital das Clínicas",   ["hospital das clinicas de ribeirao", "hc de ribeirao", "hcrp"], "Hospital das Clinicas de Ribeirao Preto", "Ribeirão Preto"),
    ("Santa Casa",              ["santa casa de ribeirao"],                   "Santa Casa de Misericordia de Ribeirao Preto", "Ribeirão Preto"),
    ("Arena Eurobike",          ["arena eurobike"],                           "Arena Eurobike, Ribeirao Preto", "Ribeirão Preto"),
    ("Estádio Santa Cruz",      ["estadio santa cruz", "botafogo-sp", "botafogo de ribeirao"], "Estadio Doutor Oswaldo Scatena, Ribeirao Preto", "Ribeirão Preto"),
    ("Aeroporto Leite Lopes",   ["aeroporto leite lopes", "aeroporto de ribeirao"], "Aeroporto Leite Lopes, Ribeirao Preto", "Ribeirão Preto"),
    ("Prefeitura de RP",        ["prefeitura de ribeirao", "paco municipal de ribeirao"], "Prefeitura de Ribeirao Preto", "Ribeirão Preto"),
    ("Câmara Municipal",        ["camara municipal de ribeirao"],             "Camara Municipal de Ribeirao Preto", "Ribeirão Preto"),
    ("Sesc Ribeirão",           ["sesc ribeirao", "sesc ribeirão"],           "Sesc Ribeirao Preto", "Ribeirão Preto"),
    ("Unaerp",                  ["unaerp"],                                   "UNAERP, Ribeirao Preto", "Ribeirão Preto"),
    ("RibeirãoShopping",        ["ribeirao shopping", "ribeirãoshopping"],    "RibeiraoShopping, Ribeirao Preto", "Ribeirão Preto"),
    ("Shopping Santa Úrsula",   ["shopping santa ursula", "shopping santa úrsula"], "Shopping Santa Ursula, Ribeirao Preto", "Ribeirão Preto"),
    ("Terminal Central",        ["terminal central", "rodoviaria de ribeirao"], "Terminal Rodoviario, Ribeirao Preto", "Ribeirão Preto"),
]

# centro de cada cidade, usado só para conferir se o resultado do geocoder faz sentido
CIDADE_QUERY = {
    "Ribeirão Preto": "Ribeirao Preto, Sao Paulo", "Franca": "Franca, Sao Paulo",
    "Sertãozinho": "Sertaozinho, Sao Paulo", "Barretos": "Barretos, Sao Paulo",
    "Batatais": "Batatais, Sao Paulo", "Cravinhos": "Cravinhos, Sao Paulo",
    "Jardinópolis": "Jardinopolis, Sao Paulo", "Brodowski": "Brodowski, Sao Paulo",
    "Serrana": "Serrana, Sao Paulo", "Araraquara": "Araraquara, Sao Paulo",
    "São Carlos": "Sao Carlos, Sao Paulo",
}

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
    ],
    "Sesc Ribeirao Preto": [
        -21.172876,
        -47.807168
    ],
    "Camara Municipal de Ribeirao Preto": [
        -21.177331,
        -47.817676
    ],
    "Parque do Peao, Barretos, Sao Paulo": [
        -20.508142,
        -48.595081
    ],
    "Arena Eurobike, Ribeirao Preto": [
        -21.202392,
        -47.790141
    ],
    "Aeroporto Leite Lopes, Ribeirao Preto": [
        -21.133302,
        -47.774683
    ],
    "Colégio Itamarati, Ribeirão Preto, SP|Ribeirão Preto": [
        -21.208645,
        -47.799529
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

def geocode(query, confere=None):
    """Coordenadas reais via Nominatim (OpenStreetMap), com cache em disco.
    `confere` exige que a cidade apareça no endereço devolvido."""
    if not query:
        return None
    chave = query + ("|" + confere if confere else "")
    with _geo_lock:
        if chave in _geo:
            return _geo[chave]
    url = ("https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=br&q="
           + urllib.parse.quote(query))
    result = None
    try:
        data = json.loads(fetch(url, timeout=15).decode("utf-8"))
        if data:
            achado = data[0]
            nome = norm(achado.get("display_name", ""))
            if not confere or norm(confere) in nome:
                result = [round(float(achado["lat"]), 6), round(float(achado["lon"]), 6)]
    except Exception as e:
        print(f"[geo] {query}: {e}", flush=True)
    with _geo_lock:
        _geo[chave] = result
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
MESES_PT = {"janeiro":1,"fevereiro":2,"marco":3,"abril":4,"maio":5,"junho":6,"julho":7,
            "agosto":8,"setembro":9,"outubro":10,"novembro":11,"dezembro":12}
DATA_EXT_RE = re.compile(r"(\d{1,2})\s+de\s+([a-zç]+)", re.I)
DATA_NUM_RE = re.compile(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?")
DIA_PAR_RE  = re.compile(r"\((\d{1,2})\)")

def data_do_evento(text, publicado):
    """Quando o evento acontece, lido do texto. Sem pista, devolve None."""
    base = datetime.fromisoformat(publicado)
    n = norm(text)
    m = DATA_EXT_RE.search(n)
    if m and norm(m.group(2)) in MESES_PT:
        dia, mes = int(m.group(1)), MESES_PT[norm(m.group(2))]
    else:
        m = DATA_NUM_RE.search(text)
        if m:
            dia, mes = int(m.group(1)), int(m.group(2))
        else:
            m = DIA_PAR_RE.search(text)
            if not m:
                return None
            dia, mes = int(m.group(1)), base.month
    try:
        ano = base.year + (1 if mes < base.month - 6 else 0)
        return datetime(ano, mes, min(dia, 28 if mes == 2 else 30), 12, tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None

def guess_category(text):
    n = norm(text)
    for cat, terms in CATEGORY_RULES:
        if any(t in n for t in terms):
            return cat
    return "Cidade"

def is_event(text):
    n = norm(text)
    return any(t in n for t in EVENT_TERMS)

PREFIXO_RE = re.compile(r"^(fotos|video|videos|v[ií]deo|ao vivo|urgente|exclusivo|an[aá]lise)\s*:\s*", re.I)

def assinatura(titulo):
    t = PREFIXO_RE.sub("", titulo or "")
    palavras = [w for w in re.findall(r"[a-z0-9]+", norm(t)) if len(w) > 3]
    return frozenset(palavras[:12])

def parecidos(a, b):
    if not a or not b:
        return False
    return len(a & b) / max(len(a), len(b)) >= 0.7

def is_noise(text):
    n = norm(text)
    return any(t in n for t in NOISE_TERMS)

CIDADES = list(CIDADE_QUERY.keys())

VIA_RE = re.compile(
    r"\b(Rua|Avenida|Av\.|Praça|Praca|Alameda|Rodovia|Estrada|Largo|Parque|Teatro|Theatro|Museu|"
    r"Jardim|Vila|Bairro|Distrito|Terminal|Igreja|Escola|Colégio|Colegio|Faculdade|Sesc|Senac)\s+"
    r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ'.-]*(?:\s+(?:de|da|do|dos|das|e|[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ'.-]*)){0,4})")

def haversine(a, b):
    from math import radians, sin, cos, asin, sqrt
    la1, lo1, la2, lo2 = map(radians, [a[0], a[1], b[0], b[1]])
    h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * asin(sqrt(h))

def cidade_do_texto(text):
    n = norm(text)
    for c in CIDADES:
        if re.search(r"\b" + re.escape(norm(c)) + r"\b", n):
            return c
    return None

def perto_da_cidade(coords, cidade, limite_km=35):
    centro = geocode(CIDADE_QUERY.get(cidade, ""))
    return bool(coords and centro and haversine(coords, centro) <= limite_km)

def guess_place(text, regional=False):
    """Só devolve local quando dá para confirmar. Sem confirmação, sem pin."""
    n = norm(text)
    cidade = cidade_do_texto(text)

    # 1) lugar conhecido — precisa bater com a cidade citada (ou vir de feed regional sem outra cidade)
    for name, terms, query, cid in PLACES:
        if not any(re.search(r"\b" + re.escape(t) + r"\b", n) for t in terms):
            continue
        if cidade and cidade != cid:
            continue
        if not cidade and not regional:
            continue
        c = geocode(query)
        if c and perto_da_cidade(c, cid, 25):
            return {"place": name, "lat": c[0], "lng": c[1]}
        return None

    # 2) rua / bairro / equipamento citado no texto, dentro da cidade citada
    alvo = cidade
    if not alvo:
        return None
    tentativas = 0
    for m in VIA_RE.finditer(text):
        via = f"{m.group(1)} {m.group(2)}".strip(" .,;")
        if len(via) < 9 or tentativas >= 3:
            continue
        tentativas += 1
        c = geocode(f"{via}, {alvo}, SP", confere=alvo)
        if c and perto_da_cidade(c, alvo):
            return {"place": via, "lat": c[0], "lng": c[1]}

    # 3) sem referência fina: fica no centro da cidade citada, com o nome dela
    c = geocode(CIDADE_QUERY.get(alvo, ""))
    if c:
        return {"place": alvo, "lat": c[0], "lng": c[1]}
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
    quando = data_do_evento(text, raw_item["published"] or datetime.now(timezone.utc).isoformat()) if is_event(text) else None
    place = guess_place(text, feed["regional"])
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
        "when": quando,
        "place": (place or {}).get("place"),
        "lat": (place or {}).get("lat"),
        "lng": (place or {}).get("lng"),
        "tone": int(iid[:2], 16) % TONES,
    }

# ---------------------------------------------------------------- store
_lock = threading.Lock()
_state = {"items": [], "updated": None}
_subscribers = []

GIST_ID = os.environ.get("GIST_ID", "")
GIST_TOKEN = os.environ.get("GIST_TOKEN", "")

def gist(metodo, corpo=None):
    req = urllib.request.Request(
        f"https://api.github.com/gists/{GIST_ID}", method=metodo,
        data=json.dumps(corpo).encode() if corpo else None,
        headers={**UA, "Authorization": f"Bearer {GIST_TOKEN}",
                 "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def load_store():
    try:
        with open(STORE, encoding="utf-8") as f:
            data = json.load(f)
        _state["items"] = data.get("items", [])
        _state["updated"] = data.get("updated")
    except Exception:
        pass
    if not _state["items"] and GIST_ID and GIST_TOKEN:
        try:                                   # historico guardado fora do disco efemero
            dados = json.loads(gist("GET")["files"]["news.json"]["content"])
            _state["items"] = dados.get("items", [])
            _state["updated"] = dados.get("updated")
            print(f"[gist] {len(_state['items'])} itens recuperados", flush=True)
        except Exception as e:
            print("[gist]", e, flush=True)

def save_store():
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"updated": _state["updated"], "items": _state["items"]}, f, ensure_ascii=False)
    os.replace(tmp, STORE)
    if GIST_ID and GIST_TOKEN:
        try:
            gist("PATCH", {"files": {"news.json": {"content": json.dumps(
                {"updated": _state["updated"], "items": _state["items"][:200]}, ensure_ascii=False)}}})
        except Exception as e:
            print("[gist]", e, flush=True)

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

SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</>", re.S | re.I)
LD_RE = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)
GEO_META_RE = re.compile(r'name=["\']geo.position["\'][^>]*content=["\']([-0-9.]+)[;,]\s*([-0-9.]+)', re.I)

def artigo_texto(url, limite=120000):
    """Baixa a matéria e devolve o texto limpo (para achar rua, bairro, local)."""
    try:
        raw = fetch(url, timeout=15)[:limite]
    except Exception:
        return "", None
    page = raw.decode("utf-8", "ignore")

    m = GEO_META_RE.search(page)
    coords = None
    if m:
        try:
            coords = [round(float(m.group(1)), 6), round(float(m.group(2)), 6)]
        except ValueError:
            coords = None

    for bloco in LD_RE.findall(page)[:3]:
        for chave in ("addressLocality", "streetAddress", "name"):
            achado = re.search(r'"%s"\s*:\s*"([^"]{4,80})"' % chave, bloco)
            if achado:
                page += " " + achado.group(1)

    texto = TAG_RE.sub(" ", SCRIPT_RE.sub(" ", page))
    return clean(html.unescape(texto), 6000), coords

def localizar(item):
    """Procura o local no corpo da matéria. Devolve True se achou coordenada."""
    regional = any(f["key"] == item["src"] and f["regional"] for f in FEEDS)
    texto, coords = artigo_texto(item["url"])
    if not texto:
        return False
    base = f"{item['title']} {item['lead']} {texto}"
    place = guess_place(base, regional)
    if coords and dentro(coords):
        place = {"place": (place or {}).get("place") or cidade_do_texto(base) or "Ribeirão Preto",
                 "lat": coords[0], "lng": coords[1]}
    if not place or place.get("lat") is None:
        return False
    with _lock:
        for i in _state["items"]:
            if i["id"] == item["id"]:
                i.update(place)
                i["fino"] = True
                return True
    return False

_fila = queue.Queue()

def worker_local():
    while True:
        item = _fila.get()
        try:
            if localizar(item):
                save_store()
                broadcast({"type": "pins"})
        except Exception as e:
            print("[local]", e, flush=True)
        finally:
            _fila.task_done()

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
        assinaturas = [assinatura(i["title"]) for i in _state["items"]]
        fresh = []
        for i in collected:
            a = assinatura(i["title"])
            if i["id"] in known or any(parecidos(a, b) for b in assinaturas):
                continue
            known.add(i["id"]); assinaturas.append(a)
            fresh.append(i)
        merged = prune(fresh + _state["items"])
        _state["items"] = merged
        _state["updated"] = datetime.now(timezone.utc).isoformat()
        save_store()
    if fresh:
        broadcast({"type": "news", "count": len(fresh), "updated": _state["updated"]})
    for i in fresh:                       # localização fina roda em segundo plano
        if i.get("url", "").startswith("http"):
            _fila.put(i)
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
    # um pin por local, na coordenada exata; itens do mesmo lugar ficam juntos
    grupos = {}
    for i in items:
        if i.get("lat") is None:
            continue
        key = (round(i["lat"], 5), round(i["lng"], 5))
        g = grupos.setdefault(key, {"id": i["id"], "lat": key[0], "lng": key[1],
                                    "label": i["place"], "more": [],
                                    "type": "ev" if i["kind"] == "evento" else "news"})
        if g["id"] != i["id"] and len(g["more"]) < 12:
            g["more"].append(i["id"])
    pins = list(grupos.values())[:120]
    sources = {f["key"]: {"name": f["name"], "url": f["site"]} for f in FEEDS}
    return {"updated": updated, "days": HISTORY_DAYS, "refresh": REFRESH_SECONDS,
            "sources": sources, "news": news, "events": events, "pins": pins,
            "total": len(items)}

def build_stamp():
    """Carimbo do build: muda sempre que css/js/html mudam, matando cache antigo."""
    h = hashlib.sha1()
    for rel in ("index.html", "css/styles.css", "js/app.js", "js/data.js", "js/i18n.js", "js/live.js"):
        try:
            st = os.stat(os.path.join(ROOT, rel))
            h.update(f"{rel}{st.st_mtime_ns}{st.st_size}".encode())
        except OSError:
            pass
    return h.hexdigest()[:8]

BUILD = build_stamp()

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, *a):
        pass

    def end_headers(self):
        # o app é atualizado com frequência: nada de HTML/CSS/JS velho em cache
        if self.path.split("?")[0].endswith((".html", ".css", ".js", ".json", "/")):
            self.send_header("Cache-Control", "no-store, must-revalidate")
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

    def send_index(self):
        with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
            page = re.sub(r"\?v=[\w.]+", "?v=" + BUILD, f.read())
        body = page.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return self.send_index()
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
    for _ in range(3):
        threading.Thread(target=worker_local, daemon=True).start()
    print(f"RP Cultural em http://localhost:{PORT}  (atualiza a cada {REFRESH_SECONDS}s, histórico de {HISTORY_DAYS} dias)", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

if __name__ == "__main__":
    main()
