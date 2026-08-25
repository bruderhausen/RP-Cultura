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

import eventos as plataformas

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
STORE = os.path.join(DATA_DIR, "news.json")
STORE_VERSION = 3      # muda quando o formato/regra muda: histórico é refeito

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
    {"key": "acidadeon", "name": "A Cidade ON", "site": "https://www.acidadeon.com/ribeiraopreto",
     "url": "https://www.acidadeon.com/ribeiraopreto/feed/", "regional": True},
    {"key": "cbn",     "name": "CBN Ribeirão",  "site": "https://cbnribeirao.com.br",
     "url": "https://cbnribeirao.com.br/feed/", "regional": True},
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
POLICIA_TERMS = ["acidente", "batida", "colisao", "capotamento", "atropelamento", "morre", "morreu",
                 "morte", "mortes", "morto", "morta", "assalto", "roubo", "furto", "homicidio",
                 "assassinato", "tiro", "tiros", "preso", "presa", "policia", "pm", "incendio",
                 "operacao", "apreensao", "vitima", "vitimas", "feridos", "ferida", "ferido"]

CATEGORY_RULES = [
    ("Cidade",      POLICIA_TERMS),
    ("Show",        ["show", "banda", "cantor", "cantora", "turne", "turnê", "rock", "sertanejo", "rap", "samba", "dj ", "concerto"]),
    ("Festival",    ["festival", "lollapalooza", "carnaval", "expo", "festa", "rodeio", "peao", "peoes"]),
    ("Gastronomia", ["gastronom", "restaurante", "chef", "culinar", "cerveja", "food", "feira de produtores", "bar "]),
    ("Cultura",     ["teatro", "museu", "exposi", "cinema", "livro", "arte", "cultural", "sarau", "danca", "dança", "biblioteca", "espetaculo", "espetáculo"]),
    ("Cidade",      ["prefeitura", "transito", "trânsito", "obra", "onibus", "ônibus", "saude", "saúde", "escola", "policia", "polícia", "chuva", "clima", "agua", "água"]),
]
NOISE_TERMS = ["siga o ", "veja fotos", "veja as fotos", "assista ao vivo", "confira a programacao da tv",
               "resumo do dia", "boletim", "horoscopo", "horóscopo"]

# ------------------------------------------------- lugares -> pin no mapa
# (label, termos que aparecem no texto, consulta enviada ao geocodificador)
PLACES = [
    ("Parque do Peão",          ["parque do peao", "festa do peao", "liga nacional de rodeio", "peao de barretos", "barretao", "os independentes"], "Parque do Peao, Barretos, Sao Paulo", "Barretos"),
    # o OSM não tem a Vila do Jon; ela fica no recinto da Festa do Peão
    ("Vila do Jon",             ["vila do jon"],                              "Parque do Peao, Barretos, Sao Paulo", "Barretos"),
    ("Centro Cultural Palace",  ["centro cultural palace", "palace hotel"],   "Centro Cultural Palace, Ribeirao Preto", "Ribeirão Preto"),
    ("Casa da Cultura",         ["casa da cultura"],                          "Casa da Cultura, Ribeirao Preto", "Ribeirão Preto"),
    ("Paço Municipal",          ["prefeitura de ribeirao", "paco municipal", "paço municipal"], "Palacio Rio Branco, Ribeirao Preto", "Ribeirão Preto"),
    ("Mercado Municipal",       ["mercado municipal"],                        "Mercado Municipal, Ribeirao Preto", "Ribeirão Preto"),
    ("Biblioteca Municipal",    ["biblioteca municipal", "biblioteca sinha junqueira"], "Biblioteca Municipal Altino Arantes, Ribeirao Preto", "Ribeirão Preto"),
    ("Museu de Arte (MARP)",    ["marp", "museu de arte de ribeirao"],        "Museu de Arte de Ribeirao Preto", "Ribeirão Preto"),
    ("Parque Maurilio Biagi",   ["maurilio biagi", "maurílio biagi"],         "Parque Maurilio Biagi, Ribeirao Preto", "Ribeirão Preto"),
    ("Parque Curupira",         ["curupira"],                                 "Parque Curupira, Ribeirao Preto", "Ribeirão Preto"),
    ("Parque Prefeito Luiz Roberto Jábali", ["parque do morro", "luiz roberto jabali"], "Parque Prefeito Luiz Roberto Jabali, Ribeirao Preto", "Ribeirão Preto"),
    ("Teatro Municipal",        ["teatro municipal"],                         "Teatro Municipal, Ribeirao Preto", "Ribeirão Preto"),
    ("Esplanada do Theatro",    ["esplanada do theatro", "esplanada do teatro"], "Esplanada do Theatro Pedro II, Ribeirao Preto", "Ribeirão Preto"),
    ("Câmara Municipal",        ["camara municipal de ribeirao", "câmara municipal de ribeirão"], "Camara Municipal de Ribeirao Preto", "Ribeirão Preto"),
    ("Rodoviária",              ["rodoviaria de ribeirao", "terminal rodoviario"], "Terminal Rodoviario, Ribeirao Preto", "Ribeirão Preto"),
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
    ],
    "Avenida Patriarca, Ribeirão Preto, SP|Ribeirão Preto": [
        -21.179329,
        -47.830237
    ],
    "Escola Egydio Pedreschi, Ribeirão Preto, SP|Ribeirão Preto": [
        -21.20284,
        -47.777887
    ],
    "Prefeitura de Ribeirao Preto": [
        -21.164816,
        -47.857608
    ],
    "Centro Cultural Palace, Ribeirao Preto": [
        -21.174125,
        -47.809539
    ],
    "Parque Maurilio Biagi, Ribeirao Preto": [
        -21.176049,
        -47.817588
    ],
    "Avenida Presidente Vargas, 1234, Ribeirão Preto, SP|Ribeirão Preto": [
        -21.199259,
        -47.808308
    ]
}

GEO_CACHE = os.path.join(DATA_DIR, "geo.json")
_geo = {}
_geo_lock = threading.Lock()

# diagnóstico dos coletores de evento. Fica fora de _state de propósito:
# é estado da última execução, não conteúdo, e não deve ir para o arquivo.
_diag = {"fontes": {}, "checado": None, "erro_geral": None}

def load_geo():
    global _geo
    _geo = dict(DEFAULT_GEO)
    try:
        with open(GEO_CACHE, encoding="utf-8") as f:
            _geo.update({k: v for k, v in json.load(f).items() if v})
    except Exception:
        pass

RP_CENTRO = [-21.177632, -47.810098]

# Sobe quando as regras de localização mudam. Itens gravados por uma versão
# anterior voltam para a fila: sem isso, um pin colocado no lugar errado por
# uma regra antiga ficaria errado para sempre.
GEO_VERSAO = 2

_geo_falhas = {}            # chave -> instante em que vale a pena tentar de novo
TTL_FALHA = 6 * 3600        # recusa de rede: o serviço pode voltar
TTL_VAZIO = 7 * 86400       # o serviço respondeu e não conhece o lugar

# Tipos que representam a cidade inteira ou algo maior. Quando se pede uma
# rua e o geocodificador devolve um destes, ele não achou o endereço e caiu
# no centroide administrativo: aceitar isso é o que colocava o pin longe do
# lugar da notícia.
TIPOS_AMPLOS = {"city", "municipality", "town", "administrative", "state",
                "county", "country", "region", "province", "postcode"}

def _tokens(txt):
    return {w for w in re.findall(r"[a-z0-9]+", norm(txt)) if len(w) > 3}

def _nome_bate(query, nome):
    """O nome devolvido precisa conter o que foi pedido.

    Sem isto, uma consulta que o geocodificador não entende volta com o
    primeiro palpite dele e o pin vai parar em outro lugar da cidade.
    """
    pedido = _tokens(query.split(",")[0])
    if not pedido:
        return False
    achou = _tokens(nome)
    return len(pedido & achou) >= max(1, (len(pedido) + 1) // 2)

def _bairro_bate(pedido, achado):
    """Rua homônima em outro bairro é o erro mais comum aqui.

    Ribeirão Preto tem Centro e o distrito de Bonfim Paulista, entre outros,
    com ruas de mesmo nome. Sem conferir o bairro, o geocodificador escolhe
    qualquer uma e o pin vai parar do outro lado da cidade.
    """
    if not pedido or not achado:
        return True                      # nada a conferir
    p, a = norm(pedido), norm(achado)
    return p in a or a in p

def _nominatim(query, confere, granular, bairro=None):
    url = ("https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&"
           "addressdetails=1&countrycodes=br&q=" + urllib.parse.quote(query))
    data = json.loads(fetch(url, timeout=15).decode("utf-8"))
    if not data:
        return None, True
    achado = data[0]
    display = achado.get("display_name", "")
    if confere and norm(confere) not in norm(display):
        return None, True
    if granular:
        tipo = (achado.get("addresstype") or achado.get("type") or "").lower()
        if tipo in TIPOS_AMPLOS:
            return None, True
        if not _nome_bate(query, achado.get("name") or display.split(",")[0]):
            return None, True
        end = achado.get("address") or {}
        achado_bairro = (end.get("suburb") or end.get("neighbourhood")
                         or end.get("city_district") or end.get("village")
                         or end.get("town") or "")
        if not _bairro_bate(bairro, achado_bairro):
            return None, True
    return [round(float(achado["lat"]), 6), round(float(achado["lon"]), 6)], True

def _photon(query, confere, granular, bairro=None):
    """Segunda opção. O Nominatim recusa tráfego de datacenter com frequência,
    e sem alternativa o app inteiro ficava sem pin nenhum."""
    url = ("https://photon.komoot.io/api/?limit=1&lat=%f&lon=%f&q=" % tuple(RP_CENTRO)
           + urllib.parse.quote(query))
    feicoes = (json.loads(fetch(url, timeout=15).decode("utf-8")).get("features") or [])
    if not feicoes:
        return None, True
    f = feicoes[0]
    props = f["properties"]
    lon, lat = f["geometry"]["coordinates"][:2]
    if confere:
        campos = " ".join(str(props.get(k, ""))
                          for k in ("city", "county", "state", "name", "district"))
        if norm(confere) not in norm(campos):
            return None, True
    if granular:
        if (props.get("type") or "").lower() in TIPOS_AMPLOS:
            return None, True
        if not _nome_bate(query, " ".join(str(props.get(k, ""))
                                          for k in ("name", "street", "district"))):
            return None, True
        if not _bairro_bate(bairro, props.get("district") or props.get("locality") or ""):
            return None, True
    return [round(lat, 6), round(lon, 6)], True

def geocode(query, confere=None, so_cache=False, granular=False, bairro=None):
    """Coordenadas reais, com cache em disco.

    `confere` exige que a cidade apareça no endereço devolvido.
    `so_cache` responde apenas pelo que já está em cache, sem tocar na rede.
    É o modo usado na leitura dos feeds: cada consulta custa uma pausa de
    1,1s por política de uso, e em série isso prendia o ciclo por minutos.
    O trabalho de rede fica para o worker em segundo plano.
    """
    if not query:
        return None
    chave = (query + ("|" + confere if confere else "")
             + ("|g" if granular else "") + ("|b" + bairro if bairro else ""))
    with _geo_lock:
        if chave in _geo:
            return _geo[chave]
        espera = _geo_falhas.get(chave, 0)
    if so_cache or time.time() < espera:
        return None

    resultado, definitivo = None, False
    for tentar in (_nominatim, _photon):
        try:
            resultado, definitivo = tentar(query, confere, granular, bairro)
        except Exception as e:
            resultado, definitivo = None, False      # rede, não ausência do lugar
            print(f"[geo] {tentar.__name__} {query}: {e}", flush=True)
        time.sleep(1.1)                              # política de uso dos dois serviços
        if resultado:
            break

    # resultado colado no centro da cidade quando se pediu um ponto fino é
    # fallback administrativo do geocodificador, não o lugar da notícia
    if resultado and granular and confere:
        centro = _geo.get(CIDADE_QUERY.get(confere, ""))
        if centro and haversine(resultado, centro) < 0.3:
            resultado, definitivo = None, True

    with _geo_lock:
        if resultado:
            # só sucesso vai para o cache. Guardar None fazia uma recusa
            # temporária virar resposta definitiva até o processo reiniciar
            _geo[chave] = resultado
            _geo_falhas.pop(chave, None)
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(GEO_CACHE, "w", encoding="utf-8") as f:
                json.dump(_geo, f, ensure_ascii=False)
        else:
            _geo_falhas[chave] = time.time() + (TTL_VAZIO if definitivo else TTL_FALHA)
    return resultado

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
DATA_EXT_RE = re.compile(r"\b(\d{1,2})\s+de\s+([a-zç]+)", re.I)
DATA_NUM_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")
DIA_PAR_RE  = re.compile(r"\((\d{1,2})\)")

def tem_termo(n, termos):
    return any(re.search(r"\b" + re.escape(t).replace(r"\ ", " ") + r"\b", n) for t in termos)

def guess_category(text):
    n = norm(text)
    for cat, terms in CATEGORY_RULES:
        if tem_termo(n, terms):
            return cat
    return "Cidade"

# Só estas fontes produzem evento: têm data, local e página de ingresso.
FONTES_EVENTO = {"sympla", "eventim"}

def normaliza_kind(it):
    """Rebaixa a evento vindo de jornal, inclusive o que já está no histórico."""
    if it.get("kind") == "evento" and it.get("src") not in FONTES_EVENTO:
        it["kind"] = "noticia"
        it["when"] = None
    return it

PREFIXO_RE = re.compile(r"^(fotos|video|videos|v[ií]deo|ao vivo|urgente|exclusivo|an[aá]lise)\s*:\s*", re.I)

def assinatura(titulo):
    t = PREFIXO_RE.sub("", titulo or "")
    palavras = [w for w in re.findall(r"[a-z0-9]+", norm(t)) if len(w) > 3]
    return frozenset(palavras[:12])

def parecidos(a, b):
    if not a or not b:
        return False
    return len(a & b) / max(len(a), len(b)) >= 0.6

def is_noise(text):
    n = norm(text)
    return any(t in n for t in NOISE_TERMS)

CIDADES = list(CIDADE_QUERY.keys())

# Bairros sem prefixo, que o regex de via não alcança. Sem eles a notícia
# cai no centro da cidade e todos os pins se empilham no mesmo ponto.
BAIRROS_RP = [
    "Campos Elíseos", "Ipiranga", "Sumarezinho", "Higienópolis", "Ribeirânia",
    "Lagoinha", "Bonfim Paulista", "Alto do Ipiranga", "Monte Alegre",
    "Quintino Facci", "Castelo Branco", "Presidente Dutra", "Adelino Simioni",
    "Recreio Anhanguera", "Nova Aliança", "City Ribeirão", "Planalto Verde",
    "Geraldo de Carvalho", "Avelino Palma", "Heitor Rigon", "Manoel Penna",
    "Jóquei Clube", "Independência", "Palmares", "Simioni", "Vila Virgínia",
    "Vila Tibério", "Vila Seixas", "Vila Amélia", "Vila Abranches", "Vila Elisa",
    "Vila Lobato", "Vila Carvalho", "Vila Albertina", "Vila Mariana",
    "Jardim Paulista", "Jardim Sumaré", "Jardim Irajá", "Jardim Canadá",
    "Jardim Botânico", "Jardim Juliana", "Jardim América", "Jardim Antártica",
    "Jardim Salgado Filho", "Jardim Aeroporto", "Jardim Macedo", "Jardim Zara",
    "Jardim Progresso", "Jardim Interlagos", "Jardim Piratininga",
    "Jardim Marchesi", "Jardim das Palmeiras", "Jardim Mosteiro",
    "Parque Ribeirão Preto", "Parque dos Servidores", "Parque Bandeirantes",
    "Parque Industrial Lagoinha", "Alto da Boa Vista", "Núcleo Branca Salles",
    "Bonfim Paulista", "Centro",
]
BAIRROS_RE = re.compile(
    r"\b(?:no |na |do |da |em |bairro |zona )?"
    r"(Jardim|Jd\.?|Vila|Vl\.?|Parque|Pq\.?|Residencial|Núcleo|Nucleo|Conjunto|Chácara|Chacara|Recanto|Recreio|City|Alto)\s+"
    r"((?:(?:de|da|do|dos|das)\s+)?[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ'.-]*"
    r"(?:\s+(?:(?:de|da|do|dos|das|e)\b|[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ'.-]*)){0,3})")

# Os conectivos levam limite de palavra no fim: sem isso o "e" casava com
# o "em" de "em Ribeirão Preto" e o nome da via saía com um "e" pendurado.
VIA_RE = re.compile(
    r"\b(Rua|Avenida|Av\.|Praça|Praca|Alameda|Rodovia|Estrada|Largo|Parque|Teatro|Theatro|Museu|"
    r"Jardim|Vila|Bairro|Terminal|Igreja|Escola|Colégio|Colegio|Faculdade|Sesc|Senac)\s+"
    r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ'.-]*"
    r"(?:\s+(?:(?:de|da|do|dos|das|e)\b|[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ'.-]*)){0,4})"
    r"(?:\s*,?\s*(?:n[ºo°.]?\s*)?(\d{1,5})\b)?")

def haversine(a, b):
    from math import radians, sin, cos, asin, sqrt
    la1, lo1, la2, lo2 = map(radians, [a[0], a[1], b[0], b[1]])
    h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * asin(sqrt(h))

ABREV_BAIRRO = {"Jd": "Jardim", "Jd.": "Jardim", "Vl": "Vila", "Vl.": "Vila",
                "Pq": "Parque", "Pq.": "Parque"}

def bairro_do_texto(text):
    """Bairro citado na notícia, usado para desempatar ruas de mesmo nome."""
    n = norm(text)
    for b in BAIRROS_RP:
        if re.search(r"\b" + re.escape(norm(b)) + r"\b", n):
            return b
    m = BAIRROS_RE.search(text)
    if m:
        pref = ABREV_BAIRRO.get(m.group(1), m.group(1))
        return f"{pref} {m.group(2)}".strip(" .,;")
    return None

def dentro(coords, limite_km=140):
    """Coordenada plausível para a região que o app cobre."""
    return bool(coords) and haversine(coords, RP_CENTRO) <= limite_km

# Apelidos e lugares que identificam a cidade sozinhos. Sem isto, uma notícia
# sobre o Barretão ou a Vila do Jon que não escreve "Barretos" era tratada como
# de Ribeirão Preto, e o nome do lugar acabava geocodificado como bairro daqui.
APELIDOS_CIDADE = {
    "barretao": "Barretos", "festa do peao": "Barretos",
    "parque do peao": "Barretos", "vila do jon": "Barretos",
    "os independentes": "Barretos",
}

def cidade_do_texto(text):
    n = norm(text)
    for c in CIDADES:
        if re.search(r"\b" + re.escape(norm(c)) + r"\b", n):
            return c
    for termo, cidade in APELIDOS_CIDADE.items():
        if re.search(r"\b" + re.escape(termo) + r"\b", n):
            return cidade
    return None

def perto_da_cidade(coords, cidade, limite_km=35, so_cache=False):
    centro = geocode(CIDADE_QUERY.get(cidade, ""), so_cache=so_cache)
    return bool(coords and centro and haversine(coords, centro) <= limite_km)

def guess_place(text, regional=False, so_cache=False):
    """Devolve o local mais fino que der para confirmar.

    A chave `preciso` diz se o ponto é de fato o lugar da notícia ou apenas
    o centro da cidade. Sem ela, o item ficava com coordenada preenchida e
    nunca entrava na fila do worker, então a busca fina no corpo da matéria
    jamais rodava e todos os pins empilhavam no mesmo ponto do centro.
    """
    n = norm(text)
    cidade = cidade_do_texto(text)

    # 1) lugar conhecido — precisa bater com a cidade citada (ou vir de feed regional sem outra cidade)
    for name, terms, query, cid in PLACES:
        if not any(re.search(r"" + re.escape(t) + r"", n) for t in terms):
            continue
        if cidade and cidade != cid:
            continue
        if not cidade and not regional:
            continue
        c = geocode(query, confere=cid, so_cache=so_cache, granular=True)
        if c and perto_da_cidade(c, cid, 25, so_cache):
            return {"place": name, "lat": c[0], "lng": c[1], "preciso": True}
        # não deu para confirmar o lugar conhecido: segue para rua, bairro e
        # centro. Um `return None` aqui tirava a notícia do mapa por inteiro,
        # justamente as que citam um ponto famoso da cidade
        break

    # feed nacional só chega aqui se passou pelo filtro de termos da região,
    # mas nem sempre cita a cidade: sem este segundo caso a notícia ficava sem
    # nenhum ponto de partida e saía do mapa
    alvo = cidade or ("Ribeirão Preto" if regional or is_regional(text) else None)
    if not alvo:
        return None
    # o bairro entra na consulta e também é conferido no resultado: é ele que
    # separa a Rua Sete de Setembro do Centro da homônima em Bonfim Paulista
    bai = bairro_do_texto(text)
    sufixo = f", {bai}" if bai else ""

    # 2) rua com número: é o que localiza a quadra
    tentativas = 0
    for m in VIA_RE.finditer(text):
        via = f"{m.group(1)} {m.group(2)}".strip(" .,;")
        numero = m.group(3)
        if len(via) < 9 or not numero or tentativas >= 3:
            continue
        tentativas += 1
        c = geocode(f"{via}, {numero}{sufixo}, {alvo}, SP", confere=alvo,
                    so_cache=so_cache, granular=True, bairro=bai)
        if c and perto_da_cidade(c, alvo, so_cache=so_cache):
            rotulo = f"{via}, {numero}" + (f" - {bai}" if bai else "")
            return {"place": rotulo, "lat": c[0], "lng": c[1], "preciso": True}

    # 3) bairro com prefixo (Jardim, Vila, Parque...)
    tentativas = 0
    for m in BAIRROS_RE.finditer(text):
        pref = {"Jd": "Jardim", "Jd.": "Jardim", "Vl": "Vila", "Vl.": "Vila",
                "Pq": "Parque", "Pq.": "Parque"}.get(m.group(1), m.group(1))
        bairro = f"{pref} {m.group(2)}".strip(" .,;")
        if len(bairro) < 9 or tentativas >= 3:
            continue
        tentativas += 1
        c = geocode(f"{bairro}, {alvo}, SP", confere=alvo, so_cache=so_cache, granular=True)
        if c and perto_da_cidade(c, alvo, 30, so_cache):
            return {"place": bairro, "lat": c[0], "lng": c[1], "preciso": True}

    # 4) bairro sem prefixo, pela lista da cidade
    if alvo == "Ribeirão Preto":
        for b in BAIRROS_RP:
            if not re.search(r"" + re.escape(norm(b)) + r"", n):
                continue
            c = geocode(f"{b}, Ribeirao Preto, SP", confere=alvo, so_cache=so_cache, granular=True)
            if c and perto_da_cidade(c, alvo, 30, so_cache):
                return {"place": b, "lat": c[0], "lng": c[1], "preciso": True}

    # 5) rua sem número: fica na via, que já é melhor que o centro
    tentativas = 0
    for m in VIA_RE.finditer(text):
        via = f"{m.group(1)} {m.group(2)}".strip(" .,;")
        if len(via) < 9 or tentativas >= 3:
            continue
        tentativas += 1
        c = geocode(f"{via}{sufixo}, {alvo}, SP", confere=alvo,
                    so_cache=so_cache, granular=True, bairro=bai)
        if c and perto_da_cidade(c, alvo, so_cache=so_cache):
            rotulo = via + (f" - {bai}" if bai else "")
            return {"place": rotulo, "lat": c[0], "lng": c[1], "preciso": True}

    # 6) sem referência fina: centro da cidade, marcado como impreciso
    c = geocode(CIDADE_QUERY.get(alvo, ""), so_cache=so_cache)
    if c:
        return {"place": alvo, "lat": c[0], "lng": c[1], "preciso": False}
    return None

def is_regional(text):
    return tem_termo(norm(text), REGION_TERMS)

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
    # Feed de jornal não produz evento. Notícia sobre show é notícia com
    # categoria Show; evento é item de plataforma de ingresso, com data,
    # local e página de compra. Misturar os dois embaralhava a agenda.
    # só cache aqui: o worker em segundo plano resolve o resto sem prender o ciclo
    place = guess_place(text, feed["regional"], so_cache=True)
    return {
        "id": iid,
        "kind": "noticia",
        "cat": guess_category(text),
        "title": raw_item["title"],
        "lead": raw_item["summary"] or raw_item["title"],
        "img": raw_item["img"],
        "url": raw_item["link"],
        "src": feed["key"],
        "srcName": feed["name"],
        "srcSite": feed["site"],
        "published": raw_item["published"] or datetime.now(timezone.utc).isoformat(),
        "when": None,
        "place": (place or {}).get("place"),
        "lat": (place or {}).get("lat"),
        "lng": (place or {}).get("lng"),
        "preciso": bool((place or {}).get("preciso")),
        "geov": GEO_VERSAO if (place or {}).get("preciso") else 0,
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
        if data.get("version") != STORE_VERSION:
            raise ValueError("formato antigo")
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
        json.dump({"version": STORE_VERSION, "updated": _state["updated"], "items": _state["items"]}, f, ensure_ascii=False)
    os.replace(tmp, STORE)
    if GIST_ID and GIST_TOKEN:
        try:
            gist("PATCH", {"files": {"news.json": {"content": json.dumps(
                {"updated": _state["updated"], "items": _state["items"][:200]}, ensure_ascii=False)}}})
        except Exception as e:
            print("[gist]", e, flush=True)

def prune(items):
    items = [normaliza_kind(i) for i in items]
    limit = datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)
    kept = []
    agora = datetime.now(timezone.utc)
    for it in items:
        try:
            if it.get("when") and datetime.fromisoformat(it["when"]) >= agora:
                kept.append(it); continue
            if datetime.fromisoformat(it["published"]) >= limit:
                kept.append(it)
        except Exception:
            kept.append(it)
    kept.sort(key=lambda i: i["published"], reverse=True)
    return kept[:MAX_ITEMS]

# o fechamento era "</>", que não existe em HTML: o regex nunca casava e o
# texto da matéria seguia com todo o JSON-LD e o CSS embutidos da página
SCRIPT_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.S | re.I)
P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.S | re.I)
LD_RE = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)
OG_IMG_RE = re.compile(
    "property=[\"']og:image[\"'][^>]*content=[\"']([^\"']+)", re.I)
OG_IMG2_RE = re.compile(
    "content=[\"']([^\"']+)[\"'][^>]*property=[\"']og:image[\"']", re.I)
CREDITO_RE = re.compile(
    "(?:Foto|Imagem|Cr[\u00e9\u00ea]dito)s?\\s*[:/]\\s*([A-Z\u00c0-\u00da][^<>|\\\"\\r\\n]{2,60}?)\\s*(?:<|\\||\\\"|$)")

GEO_META_RE = re.compile(r'name=["\']geo.position["\'][^>]*content=["\']([-0-9.]+)[;,]\s*([-0-9.]+)', re.I)

def artigo_texto(url, limite=400000):
    """Baixa a matéria e devolve o texto limpo (para achar rua, bairro, local)."""
    try:
        raw = fetch(url, timeout=15)[:limite]
    except Exception:
        return "", None, {}
    page = raw.decode("utf-8", "ignore")

    m = GEO_META_RE.search(page)
    coords = None
    if m:
        try:
            coords = [round(float(m.group(1)), 6), round(float(m.group(2)), 6)]
        except ValueError:
            coords = None

    # endereço declarado no JSON-LD costuma ser o dado mais confiável da página
    do_ld = []
    for bloco in LD_RE.findall(page)[:3]:
        for chave in ("streetAddress", "addressLocality", "name"):
            achado = re.search(r'"%s"\s*:\s*"([^"]{4,80})"' % chave, bloco)
            if achado:
                do_ld.append(achado.group(1))

    extra = {}
    m = OG_IMG_RE.search(page) or OG_IMG2_RE.search(page)
    if m:
        extra["img"] = html.unescape(m.group(1))
    m = CREDITO_RE.search(page)
    if m:
        extra["credit"] = clean(m.group(1), 60)

    # os parágrafos são o texto da notícia; o resto da página é menu e rodapé
    limpo = SCRIPT_RE.sub(" ", page)
    paragrafos = " ".join(P_RE.findall(limpo))
    corpo = paragrafos if len(paragrafos) > 500 else limpo
    texto = clean(html.unescape(TAG_RE.sub(" ", corpo)), 6000)
    if do_ld:
        # na frente: localizar() só olha o começo do corpo
        texto = clean(html.unescape(" ".join(do_ld)), 300) + " " + texto
    return texto, coords, extra

def localizar(item):
    """Procura o local no corpo da matéria. Devolve True se achou coordenada.
    Itens que já vêm com coordenada da plataforma (Sympla, Eventim) ficam como estão."""
    # centro da cidade não conta como local encontrado: é justamente o caso
    # que precisa da busca no corpo da matéria
    ja_tem_local = (item.get("lat") is not None and item.get("preciso")
                    and item.get("geov") == GEO_VERSAO)
    if ja_tem_local and item.get("img"):
        return False                       # nada a refinar nem a completar
    regional = any(f["key"] == item["src"] and f["regional"] for f in FEEDS)
    texto, coords, extra = artigo_texto(item["url"])
    mudou = False
    with _lock:
        for i in _state["items"]:
            if i["id"] != item["id"]:
                continue
            if extra.get("img") and not i.get("img"):
                i["img"] = extra["img"]; mudou = True
            if extra.get("credit") and not i.get("credit"):
                i["credit"] = extra["credit"]; mudou = True
    if ja_tem_local or not texto:
        return mudou
    marca = re.compile(r"ribeirao preto e franca|g1 ribeirao|eptv", re.I)
    cabeca = f"{item['title']} {item['lead']}"
    corpo = marca.sub(" ", texto)[:4000]
    # O `or` curto-circuitava: o título sozinho já devolvia o centro da cidade,
    # que é truthy, e o corpo da matéria (onde estão rua e bairro) nunca era
    # lido. Era isso que empilhava quase todos os pins no mesmo ponto.
    place = guess_place(cabeca, regional)
    if not (place or {}).get("preciso"):
        place = guess_place(f"{cabeca} {corpo}", regional) or place
    if coords and dentro(coords):
        place = {"place": (place or {}).get("place") or cidade_do_texto(cabeca) or "Ribeirão Preto",
                 "lat": coords[0], "lng": coords[1], "preciso": True}
    if not place or place.get("lat") is None:
        return mudou
    if not place.get("preciso") and item.get("lat") is not None and item.get("geov") == GEO_VERSAO:
        return mudou                      # já estava no centro, nada mudou
    with _lock:
        for i in _state["items"]:
            if i["id"] == item["id"]:
                i.update(place)
                i["fino"] = True
                i["geov"] = GEO_VERSAO
                return True
    return mudou

_fila = queue.Queue()
_ultimo_aviso_pins = 0.0

def worker_local():
    while True:
        item = _fila.get()
        try:
            if localizar(item):
                save_store()
                global _ultimo_aviso_pins
                agora = time.time()
                if agora - _ultimo_aviso_pins > 12:
                    _ultimo_aviso_pins = agora
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

    # Sympla e Eventim são raspados dentro de buscar(), cada um com seu próprio
    # tratamento de erro; aqui só resta o caso de o módulo inteiro falhar
    try:
        eventos, relatorio = plataformas.buscar()
        erro_eventos = None
    except Exception as e:
        eventos, relatorio, erro_eventos = [], {}, str(e)
        print("[eventos]", e, flush=True)
    for ev in eventos:
        ev["cat"] = guess_category(ev["title"] + " " + ev["lead"])
        ev["tone"] = int(hashlib.sha1(ev["id"].encode()).hexdigest()[:2], 16) % TONES
        # A plataforma informa a coordenada do local do evento. É melhor do que
        # qualquer coisa que se consiga geocodificando o texto, então o item já
        # nasce fino e nunca entra na fila de refino. Sem isto, um evento no
        # Centro era regeocodificado e ia parar numa rua homônima de outro
        # bairro.
        if ev.get("lat") is not None:
            ev["preciso"] = True
            ev["geov"] = GEO_VERSAO
        collected.append(ev)
    _diag.update(fontes=relatorio, erro_geral=erro_eventos,
                 checado=datetime.now(timezone.utc).isoformat())
    for nome, f in relatorio.items():
        if not f.get("ok"):
            print(f"[eventos] {nome} sem resultado: {f.get('erro') or 'zero itens'}", flush=True)

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
        # separar por tipo: antes todo item novo chegava no app anunciado
        # como notícia, inclusive evento
        n_ev = sum(1 for i in fresh if i.get("kind") == "evento")
        broadcast({"type": "feed", "news": len(fresh) - n_ev, "events": n_ev,
                   "count": len(fresh), "updated": _state["updated"]})
    for i in fresh:                       # localização fina roda em segundo plano
        if (not i.get("preciso") or i.get("geov") != GEO_VERSAO
                or not i.get("img")) and i.get("url", "").startswith("http"):
            _fila.put(i)
    print(f"[refresh] {len(collected)} lidas, {len(fresh)} novas, {len(_state['items'])} no histórico", flush=True)
    return len(fresh)

KEEPALIVE_URL = os.environ.get("KEEPALIVE_URL") or os.environ.get("RENDER_EXTERNAL_URL", "")

def keepalive_loop():
    """Um toque a cada 10 min no proprio endereco publico: o servico nao hiberna."""
    if not KEEPALIVE_URL:
        return
    alvo = KEEPALIVE_URL.rstrip("/") + "/api/health"
    while True:
        time.sleep(600)
        try:
            urllib.request.urlopen(urllib.request.Request(alvo, headers=UA), timeout=20).read(64)
        except Exception as e:
            print("[keepalive]", e, flush=True)

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
    # Um pin por local E por tipo. Antes a chave era só a coordenada e o tipo
    # vinha do primeiro item do grupo: bastava um evento chegar primeiro para
    # um monte de notícia virar pin amarelo de evento no mesmo balão.
    grupos = {}
    for i in items:
        if i.get("lat") is None:
            continue
        tipo = "ev" if i["kind"] == "evento" else "news"
        key = (round(i["lat"], 5), round(i["lng"], 5), tipo)
        g = grupos.setdefault(key, {"id": i["id"], "lat": key[0], "lng": key[1],
                                    "label": i["place"], "n": 0, "more": [],
                                    "type": tipo})
        g["n"] += 1
        if g["id"] != i["id"] and len(g["more"]) < 24:
            g["more"].append(i["id"])

    # dois tipos no mesmo ponto se sobrepõem e um esconde o outro
    porponto = {}
    for g in grupos.values():
        porponto.setdefault((g["lat"], g["lng"]), []).append(g)
    for juntos in porponto.values():
        if len(juntos) < 2:
            continue
        juntos.sort(key=lambda g: g["type"])
        for k, g in enumerate(juntos):
            ang = 2 * math.pi * k / len(juntos)
            g["lat"] = round(g["lat"] + 0.00040 * math.cos(ang), 6)
            g["lng"] = round(g["lng"] + 0.00043 * math.sin(ang), 6)

    # `n` é o total real do local e alimenta o balão; `more` segue limitado
    # apenas para o payload não inchar
    todos = list(grupos.values())
    pins = todos[:120]
    if len(todos) > len(pins):
        print(f"[pins] {len(todos) - len(pins)} locais fora do limite de 120", flush=True)
    sources = {f["key"]: {"name": f["name"], "url": f["site"]} for f in FEEDS}
    sources["sympla"] = {"name": "Sympla", "url": "https://www.sympla.com.br"}
    sources["eventim"] = {"name": "Eventim", "url": "https://www.eventim.com.br"}
    return {"updated": updated, "days": HISTORY_DAYS, "refresh": REFRESH_SECONDS,
            "sources": sources, "news": news, "events": events, "pins": pins,
            "total": len(items)}

def build_stamp():
    """Carimbo do build: muda sempre que css/js/html mudam, matando cache antigo."""
    h = hashlib.sha1()
    for rel in ("index.html", "css/styles.css", "js/app.js", "js/data.js", "js/i18n.js", "js/live.js",
                "manifest.json", "assets/icon-192.png", "assets/icon-512.png", "assets/favicon-32.png"):
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
        if path == "/manifest.json":
            # carimbo nos ícones: o Android vê o manifest mudado e troca o ícone sozinho
            with open(os.path.join(ROOT, "manifest.json"), encoding="utf-8") as f:
                texto = f.read().replace(".png\"", f".png?v={BUILD}\"")
            corpo = texto.encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/manifest+json; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(corpo)
            return
        if path == "/api/feed":
            return self._json(feed_payload())
        if path == "/api/health":
            # sempre 200: o Render usa esta rota como healthCheck e derrubaria
            # o serviço por causa de uma raspagem de evento quebrada
            alertas = []
            if _diag["erro_geral"]:
                alertas.append("eventos: " + _diag["erro_geral"])
            for nome, f in (_diag["fontes"] or {}).items():
                if not f.get("ok"):
                    alertas.append(f"{nome}: {f.get('erro') or 'zero itens'}")
            return self._json({"ok": True, "items": len(_state["items"]),
                               "events": sum(1 for i in _state["items"]
                                             if i.get("kind") == "evento"),
                               "sources": _diag, "alerts": alertas,
                               "updated": _state["updated"]})
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
    threading.Thread(target=keepalive_loop, daemon=True).start()
    print(f"RP Cultural em http://localhost:{PORT}  (atualiza a cada {REFRESH_SECONDS}s, histórico de {HISTORY_DAYS} dias)", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

if __name__ == "__main__":
    main()
