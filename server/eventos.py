"""Eventos reais das plataformas de ingresso (hoje: Sympla).

A página de cada cidade traz um JSON embutido com nome, data, local, endereço
e coordenadas de cada evento — é isso que lemos aqui. O preço não vem nesse
JSON, então tentamos achá-lo na página do evento (melhor esforço).
"""
import gzip, hashlib, json, re, urllib.request
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
ARQ_UNIDADES = [
    ("d1168e0f-4090-4ccc-9d8b-2391fcb7353a", "Arq Ribeirão Preto",
     "Ribeirão Preto", "https://ingresso.arqzin.com/ribeirao-preto"),
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
    for unit_id, casa, cidade, pagina in ARQ_UNIDADES:
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
                "address": casa,
                "lat": None,          # o site não publica endereço; o app resolve
                "lng": None,
                "cidade": cidade,
                "price": _arq_preco(ev),
            })
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
           "arq":    {"ok": False, "itens": 0, "erro": None}}

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

    if com_preco:
        for ev in eventos[:40]:          # melhor esforço, só nos primeiros
            ev["price"] = preco_do_evento(ev["url"])
    return eventos, rel
