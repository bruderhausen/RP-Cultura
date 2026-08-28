/* Medidor de fluidez do mapa, carregado só com #fps na URL.

   No computador o mapa vai bem e no celular trava, então medir no aparelho é a
   única forma de saber onde dói. O teste arrasta o mapa quadro a quadro no
   centro de Ribeirão e conta quantos quadros o aparelho entrega.

   Mede em quatro zooms, do amontoado ao vazio, porque a quantidade de pin na
   tela muda com o zoom e medir só num deles esconde o pior caso. No zoom mais
   pesado repete sem os pins: se ali continuar ruim, o custo é do mapa vetorial
   e mexer em pin não resolve; se melhorar bastante, o custo é dos pins.

   O resultado sai como texto para copiar, porque quem lê está no aparelho e
   quem precisa do número não está.

   Não entra no app normal: index.html só carrega este arquivo com #fps na URL.
*/
(function () {
  const CENTRO_RP = [-21.1775, -47.8103];   // Praça XV, centro de Ribeirão
  const ZOOMS = [12, 13, 14, 15];
  const SEGUNDOS = 3;

  const painel = document.createElement("div");
  painel.id = "perfPainel";
  painel.innerHTML = `<b>Medidor do mapa</b>
    <p id="perfTexto">Abra a aba Mapa e toque em medir. Leva uns 15 s.</p>
    <button id="perfIr">medir no centro de Ribeirão</button>
    <button id="perfCopiar" hidden>copiar resultado</button>`;
  document.body.appendChild(painel);

  const estilo = document.createElement("style");
  estilo.textContent = `#perfPainel{position:fixed;left:10px;right:10px;bottom:86px;z-index:9999;
    background:#fff;border-radius:14px;padding:12px 14px;font:13px/1.45 system-ui;
    box-shadow:0 10px 30px rgba(0,0,0,.3)}
    #perfPainel p{margin:6px 0 8px;white-space:pre-line;color:#333;font-variant-numeric:tabular-nums}
    #perfPainel button{width:100%;padding:10px;border-radius:10px;border:0;margin-top:6px;
      background:#4B2ED4;color:#fff;font-weight:700}
    #perfPainel button[hidden]{display:none}`;
  document.head.appendChild(estilo);

  const texto = t => { document.getElementById("perfTexto").textContent = t; };

  /* Arrasta o mapa um pouco a cada quadro e conta os quadros entregues. Um
     arrasto de verdade faz o mesmo: reprojeta as marcas a cada quadro. */
  function mede() {
    return new Promise(resolve => {
      let quadros = 0, pior = 0, anterior = performance.now(), dx = 3, pronto = false;
      const inicio = anterior;
      const fim = r => { if (!pronto) { pronto = true; resolve(r); } };
      // Com o app em segundo plano o navegador para de entregar quadros e a
      // medição ficaria presa em "medindo" para sempre. Uma tela sem quadro
      // nenhum também é um resultado: o teste precisa da tela acesa e à vista.
      setTimeout(() => fim({ fps: 0, pior: 0, parado: true }), SEGUNDOS * 1000 + 3000);
      function passo(agora) {
        if (pronto) return;
        if (quadros > 2) pior = Math.max(pior, agora - anterior);
        anterior = agora;
        quadros++;
        _map.panBy([dx, 0], { animate: false });
        if (quadros % 40 === 0) dx = -dx;          // vai e volta, sem sair da área
        if (agora - inicio < SEGUNDOS * 1000) requestAnimationFrame(passo);
        else fim({ fps: +(quadros / ((agora - inicio) / 1000)).toFixed(1),
                   pior: +pior.toFixed(0) });
      }
      requestAnimationFrame(passo);
    });
  }

  const espera = ms => new Promise(r => setTimeout(r, ms));

  async function medeNoZoom(z) {
    _map.setView(CENTRO_RP, z, { animate: false });
    renderMap();
    await espera(500);
    const marcas = document.querySelectorAll(".pinwrap .pin, .cidmarca").length;
    texto(`Medindo zoom ${z} (${marcas} marcas)…`);
    const r = await mede();
    return { z, marcas, ...r };
  }

  let relatorio = "";

  document.getElementById("perfIr").addEventListener("click", async () => {
    if (typeof _map === "undefined" || !_map) { texto("Abra a aba Mapa primeiro."); return; }
    document.getElementById("perfIr").disabled = true;

    const linhas = [];
    for (const z of ZOOMS) linhas.push(await medeNoZoom(z));

    // o zoom com mais marcas é onde vale perguntar de quem é a culpa
    const pesado = linhas.reduce((a, b) => (b.marcas > a.marcas ? b : a));
    _map.setView(CENTRO_RP, pesado.z, { animate: false });
    renderMap();
    await espera(400);
    texto(`Medindo zoom ${pesado.z} sem os pins…`);
    _map.removeLayer(_pinLayer);
    await espera(300);
    const semPin = await mede();
    _map.addLayer(_pinLayer);

    const ganho = +(semPin.fps - pesado.fps).toFixed(1);
    relatorio = [
      "MEDIDOR RP CULTURAL — centro de Ribeirão",
      `tela ${innerWidth}x${innerHeight} · densidade ${devicePixelRatio} · ` +
        `${navigator.hardwareConcurrency || "?"} núcleos`,
      `mapa: ${L.maplibreGL ? "vetorial (MapLibre GL)" : "raster"}`,
      "",
      ...linhas.map(l => `zoom ${l.z}: ${l.fps} fps · pior quadro ${l.pior} ms · ${l.marcas} marcas`),
      "",
      `zoom ${pesado.z} sem pin: ${semPin.fps} fps · pior quadro ${semPin.pior} ms`,
      `ganho ao tirar os pins: ${ganho} fps`,
      "",
      linhas.some(l => l.parado)
        ? "MEDIÇÃO INVÁLIDA: o aparelho parou de entregar quadros. Refaça com a "
          + "tela acesa e o app à vista."
        : ganho < 8 ? "VEREDITO: o gargalo é o mapa base, não os pins."
                    : "VEREDITO: os pins pesam; atacar a sombra vale a pena.",
    ].join("\n");

    texto(relatorio);
    document.getElementById("perfIr").hidden = true;
    document.getElementById("perfCopiar").hidden = false;
  });

  document.getElementById("perfCopiar").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(relatorio);
      document.getElementById("perfCopiar").textContent = "copiado";
    } catch (e) {
      // sem permissão de área de transferência: selecionar na mão ainda funciona
      document.getElementById("perfCopiar").textContent = "copie o texto acima na mão";
    }
  });
})();
