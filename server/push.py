"""Notificação push (Web Push) sem payload.

A mensagem enviada ao navegador vai vazia de propósito: o service worker
recebe o aviso e busca /api/feed para montar a notificação. Isso dispensa a
criptografia de conteúdo (aes128gcm mais ECDH), que é a parte complicada do
protocolo, e deixa só o cabeçalho VAPID, que é um JWT assinado em ES256.

As chaves vêm de VAPID_PUBLIC e VAPID_PRIVATE (base64url, sem padding). Sem
elas o módulo fica desligado e o resto do app segue normal: `disponivel()`
responde False e nada é enviado.

Gerar um par uma vez e guardar nas variáveis de ambiente do serviço:

    python server/push.py
"""
import base64
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, utils as asym_utils
    TEM_CRYPTO = True
except ImportError:                       # servidor sem a dependência instalada
    TEM_CRYPTO = False

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))
ARQUIVO = os.path.join(DATA_DIR, "subs.json")

VAPID_PUBLIC = os.environ.get("VAPID_PUBLIC", "").strip()
VAPID_PRIVATE = os.environ.get("VAPID_PRIVATE", "").strip()
VAPID_SUB = os.environ.get("VAPID_SUB", "mailto:contato@rpcultural.app").strip()

# O disco do Render free é apagado a cada restart, e o serviço hiberna sozinho
# quando fica sem tráfego. Sem uma cópia fora do container, toda inscrição some
# e ninguém mais recebe nada. app.py injeta aqui a leitura e a gravação remotas.
_backup_ler = None
_backup_gravar = None

def configurar_backup(ler, gravar):
    global _backup_ler, _backup_gravar
    _backup_ler, _backup_gravar = ler, gravar

_lock = threading.Lock()
_subs = {}          # endpoint -> {"endpoint":..., "criado":...}
_avisos = {}        # endpoint -> {"titulo":..., "corpo":..., "url":...}
_ultimo_erro = None


# ---------------------------------------------------------------- base64url
def b64d(txt):
    return base64.urlsafe_b64decode(txt + "=" * (-len(txt) % 4))


def b64e(dados):
    return base64.urlsafe_b64encode(dados).decode().rstrip("=")


# ---------------------------------------------------------------- inscrições
def carregar():
    """Disco primeiro; se estiver vazio, tenta a cópia remota."""
    global _subs
    try:
        with open(ARQUIVO, encoding="utf-8") as f:
            _subs = {s["endpoint"]: s for s in json.load(f)}
    except Exception:
        _subs = {}
    if not _subs and _backup_ler:
        try:
            _subs = {s["endpoint"]: s for s in (_backup_ler("subs.json") or [])}
            if _subs:
                print(f"[push] {len(_subs)} inscrições recuperadas do backup", flush=True)
        except Exception as e:
            print("[push] backup:", e, flush=True)


def _gravar():
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = f"{ARQUIVO}.{threading.get_ident()}.tmp"   # evita corrida entre threads
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(list(_subs.values()), f, ensure_ascii=False)
    os.replace(tmp, ARQUIVO)
    if _backup_gravar:
        try:
            _backup_gravar("subs.json", list(_subs.values()))
        except Exception as e:
            print("[push] backup:", e, flush=True)


def inscrever(sub):
    """Guarda a inscrição do navegador. Repetida apenas atualiza."""
    endpoint = (sub or {}).get("endpoint")
    if not endpoint or not endpoint.startswith("https://"):
        return False
    with _lock:
        _subs[endpoint] = {"endpoint": endpoint, "criado": time.time()}
        _gravar()
    return True


def sair(endpoint):
    with _lock:
        existia = _subs.pop(endpoint, None) is not None
        if existia:
            _gravar()
    return existia


def quantos():
    return len(_subs)


def guardar_aviso(endpoint, titulo, corpo, url="./"):
    """Texto que o service worker vai buscar quando o push chegar.

    A mensagem enviada continua vazia; o conteúdo fica aqui e é entregue pela
    própria origem. Assim o lembrete diz qual evento é, sem que o serviço de
    push do navegador veja nada.
    """
    with _lock:
        _avisos[endpoint] = {"titulo": titulo, "corpo": corpo, "url": url}


def pegar_aviso(endpoint):
    """Lê e consome. Sem aviso guardado, o worker cai no texto genérico."""
    with _lock:
        return _avisos.pop(endpoint, None)


def avisar_um(endpoint, ttl=3600):
    """Cutuca uma inscrição só. Devolve True quando o envio foi aceito."""
    global _ultimo_erro
    if not disponivel():
        return False
    try:
        _enviar_um(endpoint, ttl)
        return True
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            sair(endpoint)
        else:
            _ultimo_erro = f"HTTP {e.code}"
    except Exception as e:
        _ultimo_erro = str(e)[:120]
    return False


def avisar_todos(titulo, corpo, url="./", ttl=3600):
    """Mesma mensagem para todo mundo. Devolve (enviados, falhas).

    O texto é guardado por inscrição e buscado pelo service worker, igual ao
    lembrete: o push em si continua vazio.
    """
    if not disponivel():
        return 0, 0
    with _lock:
        alvos = list(_subs)
    enviados = 0
    for endpoint in alvos:
        guardar_aviso(endpoint, titulo, corpo, url)
        if avisar_um(endpoint, ttl):
            enviados += 1
        else:
            pegar_aviso(endpoint)          # não deixa texto pendente sem push
    return enviados, len(alvos) - enviados


def disponivel():
    return bool(TEM_CRYPTO and VAPID_PUBLIC and VAPID_PRIVATE)


def estado():
    """Resumo para /api/health, sem expor a chave privada."""
    return {
        "ativo": disponivel(),
        "inscritos": quantos(),
        "motivo": (None if disponivel() else
                   "cryptography não instalado" if not TEM_CRYPTO else
                   "VAPID_PUBLIC e VAPID_PRIVATE não configurados"),
        "ultimo_erro": _ultimo_erro,
    }


# ---------------------------------------------------------------- VAPID
def _chave_privada():
    valor = int.from_bytes(b64d(VAPID_PRIVATE), "big")
    return ec.derive_private_key(valor, ec.SECP256R1())


def _jwt(origem):
    """JWT ES256 exigido pelo VAPID, válido por 12h."""
    cabecalho = b64e(json.dumps({"typ": "JWT", "alg": "ES256"},
                                separators=(",", ":")).encode())
    corpo = b64e(json.dumps({"aud": origem, "exp": int(time.time()) + 12 * 3600,
                             "sub": VAPID_SUB}, separators=(",", ":")).encode())
    assinado = f"{cabecalho}.{corpo}".encode()
    der = _chave_privada().sign(assinado, ec.ECDSA(hashes.SHA256()))
    r, s = asym_utils.decode_dss_signature(der)
    # o VAPID pede a assinatura crua de 64 bytes, não o DER que o OpenSSL devolve
    bruta = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return f"{cabecalho}.{corpo}.{b64e(bruta)}"


def _enviar_um(endpoint, ttl=3600):
    partes = urllib.parse.urlsplit(endpoint)
    origem = f"{partes.scheme}://{partes.netloc}"
    req = urllib.request.Request(endpoint, data=b"", method="POST", headers={
        "TTL": str(ttl),
        "Content-Length": "0",
        "Urgency": "normal",
        "Authorization": f"vapid t={_jwt(origem)}, k={VAPID_PUBLIC}",
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status


def avisar(ttl=3600):
    """Cutuca todo mundo. Devolve (enviados, removidos).

    404 e 410 significam inscrição morta: o navegador desinstalou o app ou
    limpou os dados. Guardar esses endpoints só faria o envio ficar mais lento
    a cada rodada, então eles saem da lista.
    """
    global _ultimo_erro
    if not disponivel():
        return 0, 0
    with _lock:
        alvos = list(_subs)
    enviados, mortos = 0, []
    for endpoint in alvos:
        try:
            _enviar_um(endpoint, ttl)
            enviados += 1
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                mortos.append(endpoint)
            else:
                _ultimo_erro = f"HTTP {e.code}"
        except Exception as e:
            _ultimo_erro = str(e)[:120]
    for endpoint in mortos:
        sair(endpoint)
    if enviados:
        _ultimo_erro = None
    return enviados, len(mortos)


def gerar_par():
    """Par de chaves VAPID para colar nas variáveis de ambiente."""
    chave = ec.generate_private_key(ec.SECP256R1())
    publica = chave.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    privada = chave.private_numbers().private_value.to_bytes(32, "big")
    return b64e(publica), b64e(privada)


if __name__ == "__main__":
    if not TEM_CRYPTO:
        raise SystemExit("instale a dependência: pip install cryptography")
    pub, priv = gerar_par()
    print("VAPID_PUBLIC=" + pub)
    print("VAPID_PRIVATE=" + priv)
