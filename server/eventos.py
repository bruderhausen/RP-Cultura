"""Eventos reais das plataformas de ingresso (hoje: Sympla).

A página de cada cidade traz um JSON embutido com nome, data, local, endereço
e coordenadas de cada evento — é isso que lemos aqui. O preço não vem nesse
JSON, então tentamos achá-lo na página do evento (melhor esforço).
"""
import gzip, hashlib, json, re, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (compatible; RPCulturalBot/1.0)"}

CIDADES_SYMPLA = [
    ("ribeirao-preto-sp", "Ribeirão Preto"),
    ("franca-sp", "Franca"),
    ("sertaozinho-sp", "Sertãozinho"),
    ("barretos-sp", "Barretos"),
    ("araraquara-sp", "Araraquara"),
]

PRECO_RE = re.compile(r"R\$\s?(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)")


def _get(url, timeout=25):
    raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", "ignore")


def _objetos(texto, marcador='{"end_date":"'):
    """Recorta os objetos JSON dos eventos casando chaves."""
    saida, i = [], texto.find(marcador)
    while i != -1 and len(saida) < 120:
        nivel, j, dentro_str, escapa = 0, i, False, False
        while j < len(texto):
            c = texto[j]
            if escapa:
                escapa = False
            elif c == "\\":
                escapa = True
            elif c == '"':
                dentro_str = not dentro_str
            elif not dentro_str:
                if c == "{":
                    nivel += 1
                elif c == "}":
                    nivel -= 1
                    if nivel == 0:
                        break
            j += 1
        try:
            saida.append(json.loads(texto[i:j + 1]))
        except Exception:
            pass
        i = texto.find(marcador, j + 1)
    return saida


def preco_do_evento(url):
    try:
        m = PRECO_RE.search(_get(url, timeout=15))
        return f"R$ {m.group(1)}" if m else None
    except Exception:
        return None


RP = (-21.1775, -47.8103)
RAIO_KM = 90


def _dist(a, b):
    from math import radians, sin, cos, asin, sqrt
    la1, lo1, la2, lo2 = map(radians, [a[0], a[1], b[0], b[1]])
    h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * asin(sqrt(h))


EVENTIM_WEBID = __import__("os").environ.get("EVENTIM_WEBID", "web__eventim-br")
EVENTIM_KEY = __import__("os").environ.get("EVENTIM_KEY", "")
EVENTIM_CIDADES = ["Ribeirão Preto", "Franca", "Barretos"]


def _eventim_cidade(cidade):
    """API pública da Eventim (exploration). Sem credencial, ela recusa: seguimos sem."""
    import urllib.parse
    url = ("https://public-api.eventim.com/websearch/search/api/exploration/v2/productGroups"
           f"?webId={EVENTIM_WEBID}&language=pt&city={urllib.parse.quote(cidade)}&limit=30")
    req = urllib.request.Request(url, headers={**UA, "Accept": "application/json",
                                               **({"X-Api-Key": EVENTIM_KEY} if EVENTIM_KEY else {})})
    dados = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore"))
    saida = []
    for pg in (dados.get("productGroups") or []):
        nome = pg.get("name")
        link = pg.get("link") or pg.get("url")
        ev = (pg.get("typeAttributes") or {}).get("liveEntertainment") or {}
        local = ev.get("location") or {}
        geo = local.get("geoLocation") or {}
        if not nome or not link or geo.get("latitude") is None:
            continue
        rua = ", ".join(x for x in [local.get("street"), local.get("houseNumber"),
                                    local.get("city")] if x)
        saida.append({
            "id": "ev" + hashlib.sha1(link.encode()).hexdigest()[:10],
            "kind": "evento", "title": nome,
            "lead": " · ".join(x for x in [local.get("name"), rua] if x) or cidade,
            "img": (pg.get("image") or {}).get("url", ""), "url": link,
            "src": "eventim", "srcName": "Eventim", "srcSite": "https://www.eventim.com.br",
            "published": ev.get("startDate"), "when": ev.get("startDate"),
            "place": local.get("name") or rua or cidade, "address": rua,
            "lat": geo.get("latitude"), "lng": geo.get("longitude"),
            "cidade": local.get("city") or cidade,
            "price": (f"R$ {pg['price']['min']}" if (pg.get("price") or {}).get("min") else None),
        })
    return saida


def buscar_eventim():
    """Devolve (eventos, erro). O erro sobe até /api/health: sem isso, uma
    quebra na raspagem só apareceria no log do servidor."""
    saida, erro = [], None
    for cidade in EVENTIM_CIDADES:
        try:
            saida += _eventim_cidade(cidade)
        except Exception as e:
            erro = f"{cidade}: {e}"
            print(f"[eventim] {erro}", flush=True)
            break        # sem credencial não adianta insistir nas outras cidades
    return saida, erro


def buscar(limite_por_cidade=20, com_preco=False):
    """Devolve (eventos, relatorio) normalizados, prontos para o feed.

    O relatorio diz quanto cada plataforma entregou e qual foi o erro, se
    houve. Raspagem de JSON embutido quebra quando a plataforma mexe no
    markup, e sem esse retorno a falha ficava invisível: o app seguia
    servindo só notícias, sem sinal nenhum de que os eventos pararam.
    """
    vistos, eventos = set(), []
    rel = {"sympla":  {"ok": False, "itens": 0, "cidades_ok": 0,
                       "cidades": len(CIDADES_SYMPLA), "erro": None},
           "eventim": {"ok": False, "itens": 0, "erro": None}}

    for slug, cidade in CIDADES_SYMPLA:
        try:
            pagina = _get(f"https://www.sympla.com.br/eventos/{slug}").replace('\\"', '"')
        except Exception as e:
            rel["sympla"]["erro"] = rel["sympla"]["erro"] or f"{slug}: {e}"
            print(f"[sympla] {slug}: {e}", flush=True)
            continue
        rel["sympla"]["cidades_ok"] += 1

        for ev in _objetos(pagina)[:limite_por_cidade]:
            url = (ev.get("url") or "").rstrip("\\")
            nome = (ev.get("name") or "").strip()
            local = ev.get("location") or {}
            if not url or not nome or url in vistos:
                continue
            vistos.add(url)

            num = str(local.get("address_num") or "").strip()
            rua = (local.get("address") or "").strip()
            if rua and num and num not in ("0", "s/n") and num not in rua:
                rua = f"{rua}, {num}"
            endereco = ", ".join(x for x in [rua, local.get("neighborhood"),
                                             local.get("city")] if x)
            imagens = ev.get("images") or {}
            lat, lon = local.get("lat"), local.get("lon")
            if lat is None or lon is None or _dist((lat, lon), RP) > RAIO_KM:
                continue          # fora da região que o app cobre
            eventos.append({
                "id": "sy" + hashlib.sha1(url.encode()).hexdigest()[:10],
                "kind": "evento",
                "title": nome,
                "lead": " · ".join(x for x in [local.get("name"), endereco] if x) or cidade,
                "img": imagens.get("lg") or imagens.get("original") or imagens.get("xs") or "",
                "url": url,
                "src": "sympla",
                "srcName": "Sympla",
                "srcSite": "https://www.sympla.com.br",
                "published": ev.get("start_date"),
                "when": ev.get("start_date"),
                "place": local.get("name") or endereco or cidade,
                "address": endereco,
                "lat": local.get("lat"),
                "lng": local.get("lon"),
                "cidade": local.get("city") or cidade,
                "price": None,
            })

    rel["sympla"]["itens"] = len(eventos)
    # cidade que respondeu mas não rendeu evento nenhum é sinal de markup mudado
    rel["sympla"]["ok"] = rel["sympla"]["cidades_ok"] > 0 and len(eventos) > 0

    do_eventim, erro_eventim = buscar_eventim()
    rel["eventim"]["erro"] = erro_eventim
    for ev in do_eventim:
        if ev["url"] not in vistos and _dist((ev["lat"], ev["lng"]), RP) <= RAIO_KM:
            vistos.add(ev["url"]); eventos.append(ev)
            rel["eventim"]["itens"] += 1
    rel["eventim"]["ok"] = erro_eventim is None

    if com_preco:
        for ev in eventos[:40]:          # melhor esforço, só nos primeiros
            ev["price"] = preco_do_evento(ev["url"])
    return eventos, rel
