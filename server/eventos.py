"""Eventos reais das plataformas de ingresso (hoje: Sympla).

A página de cada cidade traz um JSON embutido com nome, data, local, endereço
e coordenadas de cada evento — é isso que lemos aqui. O preço não vem nesse
JSON, então tentamos achá-lo na página do evento (melhor esforço).
"""
import gzip, hashlib, html, json, re, urllib.request
from datetime import datetime, timedelta, timezone

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


# ---------------------------------------------------------------- ARQ
# O ARQ saiu do Sympla e vende em site próprio. O site é uma SPA, mas o backend
# dela é uma API REST aberta, que é o que lemos aqui. Cada unidade é uma casa;
# unit_id vem da URL que a própria página consulta.
ARQ_API = ("https://arq-backend-prod-191508435898.us-central1.run.app"
           "/api/v1/events/")
# Casa fixa, coordenada fixa: não existe evento do ARQ fora do ARQ, então o
# ponto vem daqui e não de geocodificação. Av. do Café, 1365, Vila Amélia.
ARQ_UNIDADES = [
    ("d1168e0f-4090-4ccc-9d8b-2391fcb7353a", "Arq Ribeirão Preto",
     "Ribeirão Preto", "https://ingresso.arqzin.com/ribeirao-preto",
     -21.175040, -47.830776, "Avenida do Café, 1365, Vila Amélia, Ribeirão Preto"),
]
ARQ_DIAS = 120


def _arq_preco(evento):
    """Menor valor entre os tipos de ingresso, no formato que o app mostra."""
    valores = [int(t["value_cents"]) for t in (evento.get("ticket_types") or [])
               if str(t.get("value_cents", "")).isdigit()]
    if not valores:
        return None
    return "R$ " + f"{min(valores) / 100:.2f}".replace(".", ",")


def buscar_arq():
    """Devolve (eventos, erro). Uma unidade fora do ar não derruba as outras."""
    hoje = datetime.now(timezone.utc).date()
    saida, erro = [], None
    for unit_id, casa, cidade, pagina, lat, lng, endereco in ARQ_UNIDADES:
        url = (f"{ARQ_API}?unit_id={unit_id}&start_date={hoje}"
               f"&end_date={hoje + timedelta(days=ARQ_DIAS)}&sale_status=OPEN")
        try:
            dados = json.loads(_get(url))
        except Exception as e:
            erro = erro or f"{casa}: {e}"
            print(f"[arq] {casa}: {e}", flush=True)
            continue
        itens = dados if isinstance(dados, list) else (
            dados.get("results") or dados.get("items") or dados.get("data") or [])
        for ev in itens:
            if ev.get("visibility") not in (None, "PUBLIC"):
                continue
            inicio = ev.get("start_date")
            if not ev.get("event_id") or not inicio:
                continue
            # a API devolve o horário em UTC sem sufixo; sem marcar, o app
            # mostraria 3 horas a mais e o lembrete dispararia na hora errada
            quando = inicio if inicio.endswith("Z") or "+" in inicio[10:] else inicio + "+00:00"
            saida.append({
                "id": "arq" + hashlib.sha1(ev["event_id"].encode()).hexdigest()[:10],
                "kind": "evento",
                "title": (ev.get("name") or "").strip(),
                "lead": (ev.get("description") or "").strip() or casa,
                "img": ev.get("main_image_url") or "",
                "url": pagina,
                "src": "arq",
                "srcName": "ARQ",
                "srcSite": "https://ingresso.arqzin.com",
                "published": quando,
                "when": quando,
                "place": casa,
                "address": endereco,
                "lat": lat,
                "lng": lng,
                "cidade": cidade,
                "price": _arq_preco(ev),
            })
    return saida, erro


# ---------------------------------------------------------------- Macumbox
# A Agenda da Encruzilhada serve HTML pronto, sem JavaScript, e cada evento é um
# <article class="card"> com data, hora, local e tipo em atributos próprios.
# Ler atributo é mais firme do que ler texto: eles existem para o filtro da
# própria página funcionar, então mudam menos que o desenho.
#
# A casa não vende ingresso por plataforma, então nada disso aparece na Sympla —
# é conteúdo que só existe aqui.
MACUMBOX_URL = "https://agenda.macumbox.app.br/"
MACUMBOX_CASA = "Macumbox"
MACUMBOX_ENDERECO = "Rua Américo Brasiliense, 1193, Centro, Ribeirão Preto"
MACUMBOX_LAT, MACUMBOX_LNG = None, None   # preenchidos pelo refino do app.py

MB_CARD_RE = re.compile(r'<article class="card"(.*?)</article>', re.S)
MB_ATTR_RE = re.compile(r'data-(type|date|datebr)="([^"]*)"')
MB_BANDA_RE = re.compile(r'class="coverTop">(.*?)</div>', re.S)
MB_TITULO_RE = re.compile(r'class="title">(.*?)</h3>', re.S)
MB_HORA_RE = re.compile(r'🕒\s*([0-9]{1,2}[:h][0-9]{2})')
MB_LOCAL_RE = re.compile(r'class="mapLink"[^>]*>(.*?)</a>', re.S)
MB_PROMO_RE = re.compile(r'class="promo">(.*?)</div>', re.S)
MB_CAPA_RE = re.compile(r"background-image:url\('([^']+)'\)")


def _mb_texto(m):
    """Tira marcação e espaço sobrando do trecho capturado."""
    if not m:
        return ""
    t = re.sub(r"<[^>]+>", " ", m.group(1))
    return re.sub(r"\s+", " ", html.unescape(t)).strip(" —·")


def buscar_macumbox():
    """Devolve (eventos, erro) da Agenda da Encruzilhada."""
    try:
        pagina = _get(MACUMBOX_URL)
    except Exception as e:
        print(f"[macumbox] {e}", flush=True)
        return [], str(e)

    hoje = datetime.now(timezone.utc).date()
    saida = []
    for bruto in MB_CARD_RE.findall(pagina):
        attrs = dict((k, v) for k, v in MB_ATTR_RE.findall(bruto))
        data, hora = attrs.get("date"), _mb_texto(MB_HORA_RE.search(bruto))
        if not data:
            continue
        try:
            dia = datetime.strptime(data, "%Y-%m-%d").date()
        except ValueError:
            continue
        if dia < hoje:
            continue

        # a página mostra o horário de Brasília; sem marcar o fuso o app somaria
        # 3 horas e o lembrete sairia na hora errada
        h, m = (hora.replace("h", ":").split(":") + ["00"])[:2] if hora else ("20", "00")
        try:
            local_dt = datetime(dia.year, dia.month, dia.day, int(h), int(m),
                                tzinfo=timezone(timedelta(hours=-3)))
        except ValueError:
            continue
        quando = local_dt.astimezone(timezone.utc).isoformat()

        banda = _mb_texto(MB_BANDA_RE.search(bruto))
        titulo = _mb_texto(MB_TITULO_RE.search(bruto))
        casa = _mb_texto(MB_LOCAL_RE.search(bruto)).replace("como chegar", "").strip(" —·")
        nome = " — ".join(x for x in [banda, titulo] if x) or titulo or banda
        if not nome:
            continue

        # A agenda leva a bares parceiros, não só à casa. O endereço fixo vale
        # apenas quando o evento é na própria Macumbox; nos outros o app
        # geocodifica pelo nome do lugar, como já faz com o resto.
        na_casa = MACUMBOX_CASA.lower() in casa.lower()
        saida.append({
            "id": "mb" + hashlib.sha1(f"{data}{nome}{casa}".encode()).hexdigest()[:10],
            "kind": "evento",
            "title": nome,
            "lead": " · ".join(x for x in [casa or MACUMBOX_CASA,
                                           attrs.get("datebr", ""), hora] if x),
            "img": (MB_CAPA_RE.search(bruto) or [None, ""])[1] if MB_CAPA_RE.search(bruto) else "",
            "url": MACUMBOX_URL,
            "src": "macumbox",
            "srcName": "Agenda da Encruzilhada",
            "srcSite": MACUMBOX_URL,
            "published": quando,
            "when": quando,
            "place": casa or MACUMBOX_CASA,
            "address": MACUMBOX_ENDERECO if na_casa or not casa else casa + ", Ribeirão Preto",
            "lat": MACUMBOX_LAT if na_casa else None,
            "lng": MACUMBOX_LNG if na_casa else None,
            "cidade": "Ribeirão Preto",
            "price": _mb_texto(MB_PROMO_RE.search(bruto)) or None,
            # a própria agenda classifica o evento; usar isso evita o palpite
            # por palavra, que mandava "PONTO DE QUARTA" para Cidade
            "editoria": [attrs.get("type", "")],
        })
    return saida, None


# ---------------------------------------------------------------- Linktree
# Casas que divulgam a agenda por link na bio. O Linktree entrega os links num
# JSON embutido, e cada link do Sympla leva a uma página que também traz o
# evento em JSON. Isso alcança evento que não aparece na listagem da cidade.
# Mesma ideia: a casa tem endereço fixo. Se o Sympla informar coordenada
# própria, ela ganha — a casa às vezes divulga evento que acontece em outro
# lugar, e nesse caso o ponto do Sympla é o certo.
LINKTREE_PERFIS = [
    ("eventos.hrcrp", "Hard Rock Cafe", "Ribeirão Preto",
     -21.201911, -47.789023, "Rua Edgar Rodrigues, 200, Santa Cruz, Ribeirão Preto"),
]
LINKTREE_MAX = 12          # uma requisição por link: não vale varrer sem limite


def _next_data(pagina):
    achado = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', pagina, re.S)
    return json.loads(achado.group(1)) if achado else None


def _cavar(objeto, chaves, prof=0):
    """Primeiro dicionário que tenha todas as chaves pedidas."""
    if prof > 9:
        return None
    if isinstance(objeto, dict):
        if all(k in objeto for k in chaves):
            return objeto
        for valor in objeto.values():
            achado = _cavar(valor, chaves, prof + 1)
            if achado:
                return achado
    elif isinstance(objeto, list):
        for valor in objeto[:60]:
            achado = _cavar(valor, chaves, prof + 1)
            if achado:
                return achado
    return None


def _sympla_por_url(url, cidade_padrao):
    """Evento a partir da página dele no Sympla."""
    dados = _next_data(_get(url))
    ev = _cavar(dados, ("name", "startDate", "eventsAddress")) if dados else None
    if not ev or not ev.get("startDate"):
        return None
    end = ev.get("eventsAddress") or {}
    rua = " ".join(x for x in [end.get("address"), end.get("addressNum")] if x).strip()
    endereco = ", ".join(x for x in [rua, end.get("neighborhood"), end.get("city")] if x)
    lat, lon = end.get("lat"), end.get("lon")
    return {
        "id": "sy" + hashlib.sha1(url.encode()).hexdigest()[:10],
        "kind": "evento",
        "title": (ev.get("name") or "").strip(),
        "lead": " · ".join(x for x in [end.get("name"), endereco] if x) or cidade_padrao,
        "img": (ev.get("images") or {}).get("logoUrl") or "",
        "url": url,
        "src": "sympla",
        "srcName": "Sympla",
        "srcSite": "https://www.sympla.com.br",
        # o Sympla escreve o horário local da casa, sem fuso
        "published": ev["startDate"].replace(" ", "T"),
        "when": ev["startDate"].replace(" ", "T"),
        "place": end.get("name") or endereco or cidade_padrao,
        "address": endereco,
        "lat": float(lat) if lat else None,
        "lng": float(lon) if lon else None,
        "cidade": end.get("city") or cidade_padrao,
        "price": None,
    }


def buscar_linktree():
    """Devolve (eventos, erro). Um perfil fora do ar não derruba os outros."""
    saida, erro = [], None
    for usuario, casa, cidade, lat, lng, endereco in LINKTREE_PERFIS:
        try:
            pagina = _get(f"https://linktr.ee/{usuario}")
            # varrer a página inteira é mais firme que caçar o campo certo:
            # o Linktree muda o formato do JSON embutido de tempos em tempos
            urls = []
            padrao = r'https:(?:\\u002F|/){2}www\.sympla\.com\.br(?:\\u002F|/)evento[^"\s\\]+'
            for achado in re.findall(padrao, pagina):
                limpa = achado.replace("\\u002F", "/").replace("\\/", "/")
                if limpa not in urls:
                    urls.append(limpa)
        except Exception as e:
            erro = erro or f"{casa}: {e}"
            print(f"[linktree] {casa}: {e}", flush=True)
            continue
        for url in urls[:LINKTREE_MAX]:
            try:
                ev = _sympla_por_url(url, cidade)
                if not ev:
                    continue
                if ev["lat"] is None:
                    ev["lat"], ev["lng"] = lat, lng
                    ev["place"] = ev["place"] or casa
                    ev["address"] = ev["address"] or endereco
                saida.append(ev)
            except Exception as e:
                print(f"[linktree] {url[:60]}: {e}", flush=True)
    return saida, erro


def buscar(limite_por_cidade=20, com_preco=False):
    """Devolve (eventos, relatorio) normalizados, prontos para o feed.

    O relatorio diz quanto cada plataforma entregou e qual foi o erro, se
    houve. Raspagem de JSON embutido quebra quando a plataforma mexe no
    markup, e sem esse retorno a falha ficava invisível: o app seguia
    servindo só notícias, sem sinal nenhum de que os eventos pararam.
    """
    vistos, eventos = set(), []
    rel = {"sympla": {"ok": False, "itens": 0, "cidades_ok": 0,
                      "cidades": len(CIDADES_SYMPLA), "erro": None},
           "arq":    {"ok": False, "itens": 0, "erro": None},
           "linktree": {"ok": False, "itens": 0, "erro": None},
           "macumbox": {"ok": False, "itens": 0, "erro": None}}

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

    do_arq, erro_arq = buscar_arq()
    rel["arq"]["erro"] = erro_arq
    for ev in do_arq:
        # o ARQ não tem coordenada, então a chave de repetição é o id do evento
        if ev["id"] not in vistos:
            vistos.add(ev["id"]); eventos.append(ev)
            rel["arq"]["itens"] += 1
    rel["arq"]["ok"] = erro_arq is None and rel["arq"]["itens"] > 0

    do_linktree, erro_linktree = buscar_linktree()
    rel["linktree"]["erro"] = erro_linktree
    for ev in do_linktree:
        if ev["id"] not in vistos and ev["url"] not in vistos:
            vistos.add(ev["id"]); eventos.append(ev)
            rel["linktree"]["itens"] += 1
    rel["linktree"]["ok"] = erro_linktree is None

    do_mb, erro_mb = buscar_macumbox()
    rel["macumbox"]["erro"] = erro_mb
    for ev in do_mb:
        if ev["id"] not in vistos:
            vistos.add(ev["id"]); eventos.append(ev)
            rel["macumbox"]["itens"] += 1
    rel["macumbox"]["ok"] = erro_mb is None

    if com_preco:
        for ev in eventos[:40]:          # melhor esforço, só nos primeiros
            ev["price"] = preco_do_evento(ev["url"])
    return eventos, rel
