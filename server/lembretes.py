"""Lembrete de evento, entregue por push pouco antes da hora.

O lembrete vive no servidor porque o navegador não roda nada com o app
fechado: quem precisa saber que chegou a hora é quem envia. Cada registro
guarda o endpoint da inscrição, o evento e o instante do disparo, mais o
título e o local congelados no momento da marcação. Congelar evita depender de
o evento ainda estar no histórico quando a hora chegar.

Nada aqui identifica a pessoa: o endpoint é o endereço de entrega que o próprio
navegador gerou e já está guardado em push.py.
"""
import json
import os
import threading
import time
from datetime import datetime, timezone

import push

DATA_DIR = push.DATA_DIR
ARQUIVO = os.path.join(DATA_DIR, "lembretes.json")

# quanto antes avisar, por rótulo escolhido no perfil
ANTECEDENCIA = {"30m": 1800, "1h": 3600, "3h": 10800, "1d": 86400}
PADRAO = "1h"

# depois disso o lembrete perdeu a graça: o evento já começou faz tempo
ATRASO_MAXIMO = 2 * 3600

_lock = threading.Lock()
_itens = {}          # (endpoint, id_evento) -> registro
_ultimo_erro = None


def _chave(endpoint, id_evento):
    # "|" não aparece em URL de endpoint nem em id de item
    return f"{endpoint}|{id_evento}"


def carregar():
    """Disco primeiro; se estiver vazio, tenta a cópia remota de push.py."""
    global _itens
    try:
        with open(ARQUIVO, encoding="utf-8") as f:
            _itens = {_chave(r["endpoint"], r["evento"]): r for r in json.load(f)}
    except Exception:
        _itens = {}
    if not _itens and push._backup_ler:
        try:
            _itens = {_chave(r["endpoint"], r["evento"]): r
                      for r in (push._backup_ler("lembretes.json") or [])}
        except Exception as e:
            print("[lembretes] backup:", e, flush=True)


def _gravar():
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = f"{ARQUIVO}.{threading.get_ident()}.tmp"   # evita corrida entre threads
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(list(_itens.values()), f, ensure_ascii=False)
    os.replace(tmp, ARQUIVO)
    if push._backup_gravar:
        try:
            push._backup_gravar("lembretes.json", list(_itens.values()))
        except Exception as e:
            print("[lembretes] backup:", e, flush=True)


def quando_avisar(inicio_iso, rotulo):
    """Instante do disparo, em segundos desde a época. None se já passou."""
    try:
        inicio = datetime.fromisoformat(inicio_iso)
    except (TypeError, ValueError):
        return None
    if inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=timezone.utc)
    alvo = inicio.timestamp() - ANTECEDENCIA.get(rotulo, ANTECEDENCIA[PADRAO])
    return alvo if alvo > time.time() else None


def marcar(endpoint, evento, antecedencia=PADRAO):
    """Agenda o lembrete. Marcar de novo só troca a antecedência.

    Devolve (ok, motivo). Evento sem data, ou cuja hora de aviso já passou,
    não é agendado: mandar push de algo que já começou só incomoda.
    """
    if not endpoint or not endpoint.startswith("https://"):
        return False, "inscrição inválida"
    if not evento or not evento.get("id"):
        return False, "evento inválido"
    alvo = quando_avisar(evento.get("when"), antecedencia)
    if alvo is None:
        return False, "sem data futura"
    registro = {
        "endpoint": endpoint,
        "evento": evento["id"],
        "quando": alvo,
        "antecedencia": antecedencia,
        # congelados: o evento pode sair do histórico antes da hora chegar
        "titulo": (evento.get("title") or "Evento")[:120],
        "local": (evento.get("place") or "")[:80],
    }
    with _lock:
        _itens[_chave(endpoint, evento["id"])] = registro
        _gravar()
    return True, None


def desmarcar(endpoint, id_evento):
    with _lock:
        saiu = _itens.pop(_chave(endpoint, id_evento), None) is not None
        if saiu:
            _gravar()
    return saiu


def marcados(endpoint):
    """Ids que este aparelho tem agendados, para a tela mostrar o botão certo."""
    with _lock:
        return sorted(r["evento"] for r in _itens.values() if r["endpoint"] == endpoint)


def sincronizar(endpoint, eventos, antecedencia=PADRAO):
    """Faz a lista do aparelho ser exatamente `eventos`.

    O app manda os eventos salvos inteiros a cada mudança, em vez de uma
    chamada por item: assim ligar o aviso, desligar, salvar e remover passam
    todos pelo mesmo caminho, e não sobra lembrete órfão de evento que a
    pessoa já tirou dos salvos.

    Tudo é reagendado do zero. Se a pessoa escolhe "1 dia antes" e o evento
    começa em 5 horas, ele sai da lista em vez de continuar com a
    antecedência anterior: avisar num prazo que ela não pediu é pior que não
    avisar.

    Devolve (marcados, removidos).
    """
    if not endpoint or not endpoint.startswith("https://"):
        return 0, 0
    with _lock:
        antes = {r["evento"] for r in _itens.values() if r["endpoint"] == endpoint}
    for id_evento in antes:
        desmarcar(endpoint, id_evento)
    marcados_agora = 0
    for evento in (eventos or []):
        if evento.get("id") and marcar(endpoint, evento, antecedencia)[0]:
            marcados_agora += 1
    with _lock:
        depois = {r["evento"] for r in _itens.values() if r["endpoint"] == endpoint}
    return marcados_agora, len(antes - depois)


def limpar(endpoint):
    """Tira tudo deste aparelho. Usado quando o aviso é desligado."""
    return sincronizar(endpoint, [])[1]


def quantos():
    return len(_itens)


def _texto(registro):
    quanto = {"30m": "em 30 minutos", "1h": "em 1 hora",
              "3h": "em 3 horas", "1d": "amanhã"}.get(registro["antecedencia"], "em breve")
    corpo = f"Começa {quanto}"
    if registro["local"]:
        corpo += f" · {registro['local']}"
    return registro["titulo"], corpo


def disparar(agora=None):
    """Envia os lembretes vencidos. Devolve (enviados, descartados).

    Descartado é o que ficou tempo demais na fila, por servidor parado ou
    aparelho fora do ar: avisar de um evento que já começou há horas é pior
    que não avisar.
    """
    global _ultimo_erro
    agora = agora if agora is not None else time.time()
    with _lock:
        vencidos = [r for r in _itens.values() if r["quando"] <= agora]
    enviados, descartados = 0, 0
    for registro in vencidos:
        atrasado = agora - registro["quando"] > ATRASO_MAXIMO
        if not atrasado and push.disponivel():
            titulo, corpo = _texto(registro)
            push.guardar_aviso(registro["endpoint"], titulo, corpo)
            if push.avisar_um(registro["endpoint"]):
                enviados += 1
            else:
                push.pegar_aviso(registro["endpoint"])   # não ficou pendente à toa
                _ultimo_erro = "falha ao enviar lembrete"
        elif atrasado:
            descartados += 1
        desmarcar(registro["endpoint"], registro["evento"])
    return enviados, descartados


def loop(intervalo=60):
    global _ultimo_erro
    while True:
        try:
            disparar()
        except Exception as e:
            _ultimo_erro = str(e)[:120]
            print("[lembretes]", e, flush=True)
        time.sleep(intervalo)


def estado():
    return {"agendados": quantos(), "ultimo_erro": _ultimo_erro,
            "antecedencias": sorted(ANTECEDENCIA)}


def reagendar(id_evento, novo_when, titulo=None, local=None):
    """Move os lembretes de um evento que mudou de horário.

    O lembrete nasce com a hora do evento no momento em que a pessoa o salvou,
    e quem reagenda é o app, ao abrir. Se o evento adia e a pessoa não abre o
    app até lá, o aviso saía na hora velha — que é o único momento em que ele
    não serve para nada. Agora a própria leitura das plataformas corrige, sem
    depender de o aparelho estar por perto.

    Cada aparelho mantém a antecedência que escolheu, e o evento que passou a
    começar antes da antecedência pedida sai da lista, como em sincronizar():
    avisar num prazo que ninguém pediu é pior que não avisar.

    Devolve (movidos, removidos).
    """
    movidos, removidos = 0, 0
    with _lock:
        alvos = [c for c, r in _itens.items() if r["evento"] == id_evento]
        for chave in alvos:
            r = _itens[chave]
            alvo = quando_avisar(novo_when, r.get("antecedencia", PADRAO))
            if alvo is None:
                del _itens[chave]
                removidos += 1
                continue
            if alvo == r["quando"]:
                continue
            r["quando"] = alvo
            if titulo:
                r["titulo"] = titulo[:120]
            if local is not None:
                r["local"] = local[:80]
            movidos += 1
        if movidos or removidos:
            _gravar()
    return movidos, removidos
