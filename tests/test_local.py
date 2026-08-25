"""Testes das regras de localização, classificação e montagem do feed.

Rodam sem rede: o geocodificador é trocado por uma tabela fixa de lugares
conhecidos, e o download de página por um HTML sintético. O objetivo é travar
os comportamentos que já quebraram em produção, cada teste nomeando o defeito
que ele impede de voltar.

    python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import app  # noqa: E402


# Coordenadas reais, conferidas uma vez, para o geocodificador de mentira.
LUGARES = {
    "ribeirao preto": (-21.177632, -47.810098),
    "franca": (-20.538500, -47.400800),
    "barretos": (-20.553144, -48.569751),
    "sertaozinho": (-21.137578, -47.991374),
    "barrinha": (-21.191700, -48.163900),
    "pedregulho": (-20.250700, -47.480900),
    "sales oliveira": (-20.772000, -47.836000),
    "theatro pedro ii": (-21.174361, -47.809806),
    "parque do peao": (-20.508142, -48.595081),
    "vila seixas": (-21.176500, -47.797400),
    "vila tiberio": (-21.168424, -47.825503),
    "campos eliseos": (-21.150277, -47.799993),
    "bonfim paulista": (-21.263986, -47.816887),
    "centro": (-21.177000, -47.810000),
    "rua sao jose": (-21.185196, -47.811198),
    "rua sete de setembro": (-21.181963, -47.805753),
}


def geocode_falso(query, confere=None, so_cache=False, granular=False,
                  bairro=None, so_cidade=False):
    """Devolve coordenada quando o texto da consulta cita um lugar da tabela.

    Reproduz as recusas que importam: consulta sem lugar conhecido não vira
    palpite, e bairro pedido diferente do bairro do lugar é rejeitado.
    """
    n = app.norm(query)
    achado = None
    for nome, coord in sorted(LUGARES.items(), key=lambda kv: -len(kv[0])):
        if nome in n:
            achado = (nome, coord)
            break
    if not achado:
        return None
    nome, coord = achado
    if so_cidade and nome not in ("ribeirao preto", "franca", "barretos",
                                  "sertaozinho", "barrinha", "pedregulho",
                                  "sales oliveira"):
        return None
    if bairro and app.norm(bairro) not in n:
        return None
    return list(coord)


class Base(unittest.TestCase):
    def setUp(self):
        self._geocode = app.geocode
        app.geocode = geocode_falso
        self.addCleanup(setattr, app, "geocode", self._geocode)


class TestCidade(Base):
    """A cidade da notícia decide em que município o pin cai."""

    def test_editoria_no_rodape_nao_define_a_cidade(self):
        # "g1 Ribeirão Preto e Franca" aparece em toda matéria do G1 regional
        cidade = app.cidade_pontuada(
            "g1 Ribeirao Preto e Franca. O caso foi em Barrinha, na Rua Sao Jose.",
            "Acidente deixa dois feridos")
        self.assertEqual(cidade, "Barrinha")

    def test_titulo_pesa_mais_que_o_corpo(self):
        cidade = app.cidade_pontuada(
            "Em Franca o indice foi menor. Em Franca choveu.",
            "Entregador tem pedido furtado em Ribeirao Preto")
        self.assertEqual(cidade, "Ribeirão Preto")

    def test_regiao_de_x_no_titulo_e_escopo_nao_endereco(self):
        cidade = app.cidade_pontuada(
            "g1 Ribeirao Preto e Franca.",
            "Ribeirao Preto lidera ranking na regiao de Franca")
        self.assertEqual(cidade, "Ribeirão Preto")

    def test_nome_dentro_de_palavra_composta_nao_conta(self):
        # "lobo-guará" já foi lido como a cidade de Guará
        self.assertIsNone(app.cidade_pontuada(
            "fauna do cerrado brasileiro", "Entenda por que o lobo-guara ajuda"))

    def test_apelido_identifica_barretos(self):
        for texto in ("Show no Barretao neste sabado",
                      "Vila do Jon recebe show",
                      "Festa do Peao abre venda"):
            self.assertEqual(app.cidade_pontuada("", texto), "Barretos", texto)

    def test_cidade_fora_da_lista_e_descoberta_no_texto(self):
        self.assertEqual(app.cidade_provavel("Obra em Pedregulho comeca segunda"),
                         "Pedregulho")

    def test_capital_esta_fora_do_raio_da_regiao(self):
        self.assertIsNone(app.cidade_provavel("Reuniao em Sao Paulo discute verba"))


class TestLugar(Base):
    """guess_place devolve o ponto mais fino que consegue confirmar."""

    def test_lugar_conhecido(self):
        r = app.guess_place("Show no Theatro Pedro II em Ribeirao Preto", regional=True)
        self.assertTrue(r["preciso"])
        self.assertAlmostEqual(r["lat"], -21.174361, places=4)

    def test_bairro_separa_ruas_de_mesmo_nome(self):
        # a mesma rua existe no Centro e em Bonfim Paulista
        centro = app.guess_place(
            "Bar Dom Pedro - Rua Sete de Setembro, 2030, Centro, Ribeirao Preto",
            regional=True)
        self.assertAlmostEqual(centro["lat"], -21.181963, places=4)

    def test_sem_referencia_fica_no_centro_e_marca_impreciso(self):
        r = app.guess_place("Chuva forte atinge Ribeirao Preto", regional=True)
        self.assertFalse(r["preciso"])
        self.assertAlmostEqual(r["lat"], -21.177632, places=4)

    def test_lugar_conhecido_sem_confirmacao_nao_aborta_as_demais_passadas(self):
        # este return None tirava a notícia do mapa inteiro
        app.geocode = lambda q, **k: (None if "peao" in app.norm(q)
                                      else geocode_falso(q, **k))
        r = app.guess_place("Festa do Peao movimenta Barretos", regional=True)
        self.assertIsNotNone(r)

    def test_cidade_citada_manda_no_municipio(self):
        r = app.guess_place("Acidente na Rua Sao Jose em Barrinha", regional=True)
        self.assertAlmostEqual(r["lat"], -21.191700, places=3)


class TestRegex(unittest.TestCase):
    """Os padrões de via, bairro e cidade já erraram por limite de palavra."""

    def test_via_nao_arrasta_o_em_seguinte(self):
        achados = [m.groups() for m in app.VIA_RE.finditer(
            "Show no Theatro Pedro II em Ribeirao Preto")]
        self.assertEqual(achados[0][1], "Pedro II")

    def test_via_captura_numero(self):
        m = app.VIA_RE.search("na Rua Sao Sebastiao, 450, em Ribeirao Preto")
        self.assertEqual(m.group(3), "450")

    def test_bairro_aceita_conectivo_e_abreviacao(self):
        self.assertEqual(app.BAIRROS_RE.search("no Parque dos Servidores").group(2),
                         "dos Servidores")
        self.assertEqual(app.BAIRROS_RE.search("no Jd. Palmares").group(1), "Jd.")

    def test_distrito_federal_nao_e_bairro_nem_via(self):
        texto = "Lei no Distrito Federal e em Ribeirao Preto"
        self.assertFalse(app.VIA_RE.findall(texto))
        self.assertFalse(app.BAIRROS_RE.findall(texto))

    def test_script_e_style_sao_removidos(self):
        # o fechamento era "</>", que não existe: o regex nunca casava
        sujo = '<p>ok</p><script>var a=1</script><style>.a{color:red}</style><p>fim</p>'
        self.assertEqual(app.SCRIPT_RE.sub(" ", sujo).count("<script"), 0)
        self.assertEqual(app.SCRIPT_RE.sub(" ", sujo).count("<style"), 0)


class TestValidacaoGeocodificador(unittest.TestCase):
    """O serviço sempre responde algo; aceitar tudo põe o pin longe."""

    def test_nome_devolvido_precisa_bater_com_o_pedido(self):
        self.assertTrue(app._nome_bate("Vila Seixas, Ribeirao Preto", "Vila Seixas"))
        self.assertFalse(app._nome_bate("Fabrica de Extintores", "Rua Prudente de Morais"))

    def test_bairro_diferente_do_pedido_e_recusado(self):
        self.assertTrue(app._bairro_bate("Centro", "Centro"))
        self.assertFalse(app._bairro_bate("Centro", "Bonfim Paulista"))
        self.assertTrue(app._bairro_bate(None, "qualquer"))

    def test_coordenada_fora_da_regiao(self):
        self.assertTrue(app.dentro([-21.17, -47.81]))
        self.assertFalse(app.dentro([-22.90, -43.20]))   # Rio de Janeiro


class TestClassificacao(unittest.TestCase):
    """Evento é item de plataforma de ingresso; jornal produz notícia."""

    def test_manchete_de_show_e_noticia_com_categoria_show(self):
        feed = {"key": "g1", "name": "G1", "site": "s", "regional": True}
        item = app.build_item(feed, {
            "title": "Skank faz show no Theatro Pedro II em Ribeirao Preto",
            "summary": "", "link": "http://x/1",
            "published": "2026-08-20T10:00:00+00:00", "img": ""})
        self.assertEqual(item["kind"], "noticia")
        self.assertEqual(item["cat"], "Show")
        self.assertIsNone(item["when"])

    def test_evento_de_jornal_no_historico_e_rebaixado(self):
        velho = [{"id": "a", "kind": "evento", "src": "g1", "title": "x",
                  "when": "2099-12-01T20:00:00+00:00",
                  "published": "2099-11-01T10:00:00+00:00"},
                 {"id": "b", "kind": "evento", "src": "sympla", "title": "y",
                  "when": "2099-12-01T20:00:00+00:00",
                  "published": "2099-11-01T10:00:00+00:00"}]
        kinds = {i["id"]: i["kind"] for i in app.prune(velho)}
        self.assertEqual(kinds["a"], "noticia")
        self.assertEqual(kinds["b"], "evento")


class TestCidadeNoItem(Base):
    """O filtro de cidade só funciona se todo item souber a que município pertence."""

    def test_guess_place_devolve_a_cidade_resolvida(self):
        r = app.guess_place("Acidente na Rua Sao Jose em Barrinha", regional=True)
        self.assertEqual(r["cidade"], "Barrinha")
        r = app.guess_place("Chuva forte atinge Ribeirao Preto", regional=True)
        self.assertEqual(r["cidade"], "Ribeirão Preto")

    def test_item_antigo_ganha_cidade_sem_usar_a_rede(self):
        # o campo não existia; o histórico precisa entrar no filtro assim mesmo
        def sem_rede(*a, **k):
            raise AssertionError("consultou o geocodificador")
        app.geocode = sem_rede
        item = {"id": "a", "kind": "noticia", "src": "g1",
                "title": "Obra fecha avenida em Sertaozinho", "lead": "",
                "published": "2026-08-20T10:00:00+00:00"}
        self.assertEqual(app.completa_cidade(item)["cidade"], "Sertãozinho")

    def test_item_sem_cidade_identificavel_fica_sem(self):
        item = {"id": "b", "kind": "noticia", "src": "g1",
                "title": "Responsabilidade criminal do diretor", "lead": "",
                "published": "2026-08-20T10:00:00+00:00"}
        self.assertIsNone(app.completa_cidade(item).get("cidade"))

    def test_feed_lista_cidades_com_contagem(self):
        with app._lock:
            app._state["items"] = [
                {"id": "1", "kind": "noticia", "cidade": "Franca", "place": "Franca", "lat": -20.5,
                 "lng": -47.4, "preciso": True, "published": "2026-08-20T10:00:00+00:00"},
                {"id": "2", "kind": "noticia", "cidade": "Franca", "place": "Franca", "lat": -20.5,
                 "lng": -47.4, "preciso": True, "published": "2026-08-20T10:00:00+00:00"},
                {"id": "3", "kind": "noticia", "cidade": "Barrinha", "place": "Barrinha", "lat": -21.19,
                 "lng": -48.16, "preciso": True, "published": "2026-08-20T10:00:00+00:00"}]
            app._state["updated"] = "2026-08-25T12:00:00+00:00"
        self.assertEqual(app.feed_payload()["cidades"], [("Franca", 2), ("Barrinha", 1)])

    def test_pin_sem_place_nao_derruba_o_feed(self):
        # item gravado por versão antiga pode não ter o campo
        with app._lock:
            app._state["items"] = [{"id": "1", "kind": "noticia", "lat": -21.1,
                                    "lng": -47.8, "cidade": "Ribeirão Preto",
                                    "published": "2026-08-20T10:00:00+00:00"}]
            app._state["updated"] = "2026-08-25T12:00:00+00:00"
        self.assertEqual(app.feed_payload()["pins"][0]["label"], "Ribeirão Preto")


class TestPins(unittest.TestCase):
    """O agrupamento define cor, contagem e sobreposição no mapa."""

    def montar(self, itens):
        with app._lock:
            app._state["items"] = itens
            app._state["updated"] = "2026-08-25T12:00:00+00:00"
        return app.feed_payload()["pins"]

    def test_evento_e_noticia_no_mesmo_ponto_viram_pins_separados(self):
        centro = (-21.177632, -47.810098)
        itens = ([{"id": f"n{i}", "kind": "noticia", "lat": centro[0], "lng": centro[1],
                   "place": "Ribeirão Preto", "preciso": False,
                   "published": "2026-08-20T10:00:00+00:00"} for i in range(9)] +
                 [{"id": f"e{i}", "kind": "evento", "lat": centro[0], "lng": centro[1],
                   "place": "Ribeirão Preto", "preciso": True,
                   "published": "2026-08-20T10:00:00+00:00"} for i in range(4)])
        pins = self.montar(itens)
        por_tipo = {p["type"]: p for p in pins}
        self.assertEqual(sorted(por_tipo), ["ev", "news"])
        self.assertEqual(por_tipo["news"]["n"], 9)
        self.assertEqual(por_tipo["ev"]["n"], 4)
        # afastados, senão um esconde o outro
        self.assertNotEqual((por_tipo["ev"]["lat"], por_tipo["ev"]["lng"]),
                            (por_tipo["news"]["lat"], por_tipo["news"]["lng"]))

    def test_balao_mostra_o_total_real_e_nao_o_tamanho_da_lista(self):
        itens = [{"id": str(i), "kind": "noticia", "lat": -21.1, "lng": -47.8,
                  "place": "X", "preciso": True,
                  "published": "2026-08-20T10:00:00+00:00"} for i in range(30)]
        pin = self.montar(itens)[0]
        self.assertEqual(pin["n"], 30)
        self.assertLessEqual(len(pin["more"]), 24)

    def test_so_existem_dois_tipos_de_pin(self):
        itens = [{"id": "1", "kind": "noticia", "lat": -21.1, "lng": -47.8,
                  "place": "X", "preciso": False,
                  "published": "2026-08-20T10:00:00+00:00"}]
        self.assertEqual(self.montar(itens)[0]["type"], "news")


class TestArtigo(unittest.TestCase):
    """O corpo da matéria é a principal fonte de rua e bairro."""

    def test_texto_sai_dos_paragrafos_sem_script_nem_estilo(self):
        html_falso = (
            '<html><head><style>.x{color:red}</style>'
            '<script type="application/ld+json">'
            '{"streetAddress":"Rua Sao Jose, 100","addressLocality":"Ribeirao Preto"}'
            '</script></head><body><nav>menu inicio busca</nav>'
            '<p>' + ("O acidente aconteceu na Vila Seixas nesta terca-feira. " * 12) +
            '</p></body></html>')
        original = app.fetch
        app.fetch = lambda url, timeout=20: html_falso.encode("utf-8")
        try:
            texto, coords, _ = app.artigo_texto("http://exemplo/x")
        finally:
            app.fetch = original
        self.assertNotIn("color:red", texto)
        self.assertNotIn("streetAddress", texto)
        self.assertIn("Vila Seixas", texto)
        # o endereço do JSON-LD vai para a frente: localizar() só lê o começo
        self.assertIn("Rua Sao Jose", texto[:200])
        self.assertIsNone(coords)


class TestLocalizar(Base):
    """O worker refina quem está no centro e não mexe em quem já está fino."""

    def setUp(self):
        super().setUp()
        self._save = app.save_store
        app.save_store = lambda: None
        self.addCleanup(setattr, app, "save_store", self._save)

    def test_item_no_centro_e_refinado_pelo_corpo(self):
        item = {"id": "x1", "src": "g1", "url": "http://x", "title": "Obra interdita trecho",
                "lead": "em Ribeirao Preto", "lat": -21.177632, "lng": -47.810098,
                "preciso": False, "img": "i"}
        with app._lock:
            app._state["items"] = [dict(item)]
        app.artigo_texto = lambda u, limite=400000: (
            "A obra fica na Vila Tiberio, em Ribeirao Preto.", None, {})
        self.assertTrue(app.localizar(item))
        self.assertTrue(app._state["items"][0]["preciso"])

    def test_evento_de_plataforma_nao_e_regeocodificado(self):
        # a coordenada do Sympla é melhor que qualquer palpite sobre o texto
        item = {"id": "sy1", "src": "sympla", "url": "http://s/x", "title": "Show",
                "lead": "Bar Dom Pedro", "lat": -21.182, "lng": -47.8058,
                "preciso": True, "geov": app.GEO_VERSAO, "img": "i"}
        with app._lock:
            app._state["items"] = [dict(item)]

        def nao_pode(*a, **k):
            raise AssertionError("baixou a página de um evento de plataforma")

        app.artigo_texto = nao_pode
        self.assertFalse(app.localizar(item))
        self.assertEqual(app._state["items"][0]["lat"], -21.182)

    def test_item_de_versao_antiga_volta_para_a_fila(self):
        antigo = {"preciso": True, "img": "i", "url": "http://a"}
        atual = {"preciso": True, "geov": app.GEO_VERSAO, "img": "i", "url": "http://b"}
        refila = lambda i: (not i.get("preciso")
                            or i.get("geov") != app.GEO_VERSAO or not i.get("img"))
        self.assertTrue(refila(antigo))
        self.assertFalse(refila(atual))


class TestDiagnostico(unittest.TestCase):
    """O painel existe para mostrar quebra; se não alerta, não serve."""

    def montar(self, itens, fontes):
        with app._lock:
            app._state["items"] = itens
            app._state["updated"] = "2026-08-25T12:00:00+00:00"
        app._diag.update(fontes=fontes, erro_geral=None, checado=None)
        return app.health_payload()

    def test_plataforma_quebrada_vira_alerta(self):
        d = self.montar(
            [{"id": "1", "kind": "evento", "src": "sympla", "lat": -21.1, "lng": -47.8,
              "preciso": True, "published": "2026-08-20T10:00:00+00:00"}],
            {"sympla": {"ok": True, "itens": 1},
             "eventim": {"ok": False, "itens": 0, "erro": "HTTP Error 400"}})
        self.assertTrue(any("eventim" in a for a in d["alerts"]))
        self.assertFalse(any("sympla" in a for a in d["alerts"]))

    def test_conta_local_proprio_contra_centro_da_cidade(self):
        itens = [{"id": "a", "kind": "noticia", "src": "g1", "lat": -21.1, "lng": -47.8,
                  "preciso": True, "published": "2026-08-20T10:00:00+00:00"},
                 {"id": "b", "kind": "noticia", "src": "g1", "lat": -21.17, "lng": -47.81,
                  "preciso": False, "published": "2026-08-20T10:00:00+00:00"},
                 {"id": "c", "kind": "evento", "src": "sympla", "lat": None, "lng": None,
                  "preciso": False, "published": "2026-08-20T10:00:00+00:00"}]
        d = self.montar(itens, {"sympla": {"ok": True, "itens": 1}})
        self.assertEqual(d["local"], {"com_coordenada": 2, "proprio": 1,
                                      "centro_da_cidade": 1, "sem_coordenada": 1})
        self.assertEqual(d["feeds"], {"g1": 2, "sympla": 1})

    def test_avisa_quando_quase_nada_tem_local_proprio(self):
        itens = [{"id": str(i), "kind": "noticia", "src": "g1", "lat": -21.17,
                  "lng": -47.81, "preciso": False,
                  "published": "2026-08-20T10:00:00+00:00"} for i in range(20)]
        d = self.montar(itens, {"sympla": {"ok": True, "itens": 1}})
        self.assertTrue(any("local próprio" in a for a in d["alerts"]))

    def test_sem_evento_no_historico_vira_alerta(self):
        d = self.montar(
            [{"id": "a", "kind": "noticia", "src": "g1", "lat": -21.1, "lng": -47.8,
              "preciso": True, "published": "2026-08-20T10:00:00+00:00"}],
            {"sympla": {"ok": True, "itens": 0}})
        self.assertTrue(any("nenhum evento" in a for a in d["alerts"]))


class TestPush(unittest.TestCase):
    """O push assina um JWT ES256; assinatura errada é recusada em silêncio."""

    def setUp(self):
        import push
        self.push = push
        if not push.TEM_CRYPTO:
            self.skipTest("cryptography não instalado")

    def test_jwt_tem_formato_vapid_e_assinatura_valida(self):
        import json as _json
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec, utils
        pub, priv = self.push.gerar_par()
        self.push.VAPID_PUBLIC, self.push.VAPID_PRIVATE = pub, priv
        cab, corpo, ass = self.push._jwt("https://exemplo.push").split(".")
        self.assertEqual(_json.loads(self.push.b64d(cab))["alg"], "ES256")
        self.assertEqual(sorted(_json.loads(self.push.b64d(corpo))), ["aud", "exp", "sub"])
        bruta = self.push.b64d(ass)
        self.assertEqual(len(bruta), 64)   # r e s crus, não DER
        chave = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256R1(), self.push.b64d(pub))
        chave.verify(
            utils.encode_dss_signature(int.from_bytes(bruta[:32], "big"),
                                       int.from_bytes(bruta[32:], "big")),
            f"{cab}.{corpo}".encode(), ec.ECDSA(hashes.SHA256()))

    def test_inscricao_precisa_de_endpoint_https(self):
        self.push._subs = {}
        self.push._gravar = lambda: None
        self.assertFalse(self.push.inscrever({}))
        self.assertFalse(self.push.inscrever({"endpoint": "http://inseguro"}))
        self.assertTrue(self.push.inscrever({"endpoint": "https://push.exemplo/abc"}))
        self.assertEqual(self.push.quantos(), 1)
        self.assertTrue(self.push.sair("https://push.exemplo/abc"))
        self.assertEqual(self.push.quantos(), 0)

    def test_sem_chave_o_modulo_fica_desligado_sem_quebrar(self):
        self.push.VAPID_PUBLIC = self.push.VAPID_PRIVATE = ""
        self.assertFalse(self.push.disponivel())
        self.assertEqual(self.push.avisar(), (0, 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
