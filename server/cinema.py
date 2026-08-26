"""Cartaz de cinema de Ribeirão Preto, lido da API de conteúdo da Ingresso.com.

A API responde sem chave nem cadastro: `nowplaying` devolve os filmes em cartaz
na cidade e `sessions` devolve as sessões de um filme, agrupadas por dia, por
casa e por sala. Ribeirão Preto é a cidade 27.

O item aqui é o par filme × cinema, não a sessão. Sessão vira item afogaria o
feed — são quatro casas com dezenas de horários por dia — e o mapa precisa de um
ponto por cinema, não por horário. Com o par, o agrupamento de pins que o
app.py já faz por coordenada junta sozinho os filmes de cada casa num pin só, e
a tela inicial junta por `movieId` para mostrar um cartão por filme.

As coordenadas das quatro casas são fixas no código. Elas não mudam, e o
geocodificador erra o número em duas delas: a Nominatim devolve o meio da rua
para o Iguatemi e para o Santa Úrsula. Foram conferidas uma a uma contra o
resultado que traz o nome do shopping.
"""
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api-content.ingresso.com/v0"
CIDADE = 27
UA = "Mozilla/5.0 (compatible; RPCultural/1.0)"

# id da casa na Ingresso -> (nome curto, endereço, lat, lng)
CASAS = {
    "346":  ("Cinemark Novo Shopping", "Av. Presidente Kennedy, 1500, Ribeirão Preto",
             -21.2062538, -47.7650177),
    "1127": ("Cinépolis Iguatemi", "Av. Luiz Eduardo de Toledo Prado, 900, Ribeirão Preto",
             -21.2256208, -47.8352633),
    "853":  ("Cinépolis Santa Úrsula", "Rua São José, 933, Ribeirão Preto",
             -21.1825477, -47.8082133),
    "621":  ("UCI RibeirãoShopping", "Av. Cel. Fernando Ferreira Leite, 1540, Ribeirão Preto",
             -21.2123921, -47.8167652),
}

DIAS_A_FRENTE = 3      # o cartaz além disso muda antes de a pessoa usar
TAG_RE = re.compile(r"<[^>]+>")


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _limpa(txt, limite=260):
    t = TAG_RE.sub(" ", txt or "").replace("\xa0", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t[:limite].rstrip(" .,;") + "…" if len(t) > limite else t


def _cartaz(filme):
    """A maior imagem disponível, para o cartão não sair borrado."""
    for img in filme.get("images") or []:
        u = img.get("url")
        if u:
            return u
    return filme.get("imageFeatured") or None


def _quando(dia, hora):
    """Sessão em horário de Brasília, guardada em UTC como o resto do feed."""
    try:
        d = datetime.strptime(dia[:10], "%Y-%m-%d")
        h, m = (int(x) for x in hora.split(":")[:2])
        local = d.replace(hour=h, minute=m, tzinfo=timezone(timedelta(hours=-3)))
        return local.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def ler(log=print):
    """Devolve um item por filme × cinema, pronto para entrar no feed."""
    try:
        filmes = _get(f"{API}/templates/nowplaying/{CIDADE}")
    except (urllib.error.URLError, ValueError, OSError) as e:
        log(f"[cinema] cartaz indisponível: {e}")
        return []

    limite = datetime.now(timezone.utc) + timedelta(days=DIAS_A_FRENTE)
    itens = {}
    for filme in filmes:
        mid = str(filme.get("id") or "")
        if not mid or filme.get("isComingSoon"):
            continue
        try:
            dias = _get(f"{API}/sessions/city/{CIDADE}/event/{mid}")
        except (urllib.error.URLError, ValueError, OSError) as e:
            log(f"[cinema] sessões de {mid}: {e}")
            continue

        for dia in dias:
            data = (dia.get("date") or "")[:10]
            for casa in dia.get("theaters") or []:
                cid = str(casa.get("id") or "")
                if cid not in CASAS:
                    continue
                nome, endereco, lat, lng = CASAS[cid]
                chave = f"cine{mid}-{cid}"
                for sala in casa.get("rooms") or []:
                    for s in sala.get("sessions") or []:
                        if not s.get("enabled", True):
                            continue
                        quando = _quando(data, s.get("time") or "")
                        if not quando or quando > limite.isoformat():
                            continue
                        it = itens.setdefault(chave, {
                            "id": chave,
                            "kind": "cinema",
                            "movieId": mid,
                            "title": (filme.get("title") or "").strip(),
                            "lead": _limpa(filme.get("synopsis")),
                            "img": _cartaz(filme),
                            "url": s.get("siteURL") or "",
                            "src": "ingresso",
                            "srcName": "Ingresso.com",
                            "srcSite": "https://www.ingresso.com",
                            "place": nome,
                            "address": endereco,
                            "lat": lat, "lng": lng,
                            "cidade": "Ribeirão Preto",
                            "cat": "Cultura",
                            "tone": int(mid) % 8,
                            "preciso": True,
                            "duracao": filme.get("duration") or None,
                            "classificacao": filme.get("contentRating") or None,
                            "generos": filme.get("genres") or [],
                            "sessoes": [],
                            "price": None,
                        })
                        it["sessoes"].append({
                            "quando": quando,
                            "hora": s.get("time"),
                            "sala": s.get("room") or sala.get("name"),
                            "tipo": sala.get("type") or "",
                            "url": s.get("siteURL") or "",
                            "preco": s.get("price"),
                        })

    agora = datetime.now(timezone.utc).isoformat()
    saida = []
    for it in itens.values():
        it["sessoes"].sort(key=lambda s: s["quando"])
        # `when` é a próxima sessão: é o que ordena o cartaz e o que o lembrete
        # de evento salvo usa para saber a hora do aviso
        it["when"] = it["sessoes"][0]["quando"]
        it["published"] = agora
        precos = [s["preco"] for s in it["sessoes"] if s.get("preco")]
        if precos:
            it["price"] = f"R$ {min(precos):.2f}".replace(".", ",")
        saida.append(it)

    saida.sort(key=lambda i: (i["when"], i["title"]))
    log(f"[cinema] {len(saida)} filmes em cartaz nas {len(CASAS)} casas")
    return saida
