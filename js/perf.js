/* Medidor de fluidez do mapa, carregado só com #fps na URL.

   No computador o mapa vai bem e no celular trava, então medir no aparelho é a
   única forma de saber onde dói. O teste arrasta o mapa quadro a quadro e conta
   quantos quadros o aparelho entrega, duas vezes: com os pins e sem eles. Se
   sem pin continuar ruim, o custo é do mapa vetorial e mexer em pin não
   resolve; se melhorar muito, o custo é dos pins.

   Não entra no app normal: index.html só carrega este arquivo quando a URL
   termina em #fps.
*/
(function () {
  const CENTRO_RP = [-21.1775, -47.8103];   // Praça XV, centro de Ribeirão
  const SEGUNDOS = 4;

  const painel = document.createElement("div");
  painel.id = "perfPainel";
  painel.innerHTML = `<b>Medidor do mapa</b>
    <p id="perfTexto">Abra o Mapa e toque em medir.</p>
    <button id="perfIr">medir no centro de Ribeirão</button>`;
  document.body.appendChild(painel);

  const estilo = document.createElement("style");
  estilo.textContent = `#perfPainel{position:fixed;left:10px;right:10px;bottom:90px;z-index:9999;
    background:#fff;border-radius:14px;padding:12px 14px;font:13px/1.4 system-ui;
    box-shadow:0 10px 30px rgba(0,0,0,.3)}
    #perfPainel b{font-size:13px}
    #perfPainel p{margin:6px 0 8px;white-space:pre-line;color:#333}
    #perfPainel button{width:100%;padding:10px;border-radius:10px;border:0;
      background:#4B2ED4;color:#fff;font-weight:700}`;
  document.head.appendChild(estilo);

  const texto = t => { document.getElementById("perfTexto").textContent = t; };

  /* Arrasta o mapa um pouco a cada quadro e conta os quadros entregues. Um
     arrasto de verdade faz o mesmo: reprojeta as marcas a cada quadro. */
  function mede(rotulo) {
    return new Promise(resolve => {
      let quadros = 0, pior = 0, anterior = performance.now();
      const inicio = anterior;
      let dx = 3;
      function passo(agora) {
        const gasto = agora - anterior;
        if (quadros > 2) pior = Math.max(pior, gasto);
        anterior = agora;
        quadros++;
        _map.panBy([dx, 0], { animate: false });
        if (quadros % 40 === 0) dx = -dx;          // vai e volta, sem sair da área
        if (agora - inicio < SEGUNDOS * 1000) requestAnimationFrame(passo);
        else resolve({ rotulo, fps: +(quadros / ((agora - inicio) / 1000)).toFixed(1),
                       piorQuadroMs: +pior.toFixed(1) });
      }
      requestAnimationFrame(passo);
    });
  }

  document.getElementById("perfIr").addEventListener("click", async () => {
    if (typeof _map === "undefined" || !_map) { texto("Abra a aba Mapa primeiro."); return; }
    const camada = _pinLayer;
    _map.setView(CENTRO_RP, 15, { animate: false });
    renderMap();
    await new Promise(r => setTimeout(r, 600));
    const marcas = document.querySelectorAll(".pinwrap .pin, .cidmarca").length;

    texto("Medindo com os pins…");
    const comPin = await mede("com pin");

    texto("Medindo sem os pins…");
    _map.removeLayer(camada);
    await new Promise(r => setTimeout(r, 400));
    const semPin = await mede("sem pin");
    _map.addLayer(camada);

    const veredito = semPin.fps - comPin.fps < 8
      ? "Os pins não são o gargalo: sem eles o ganho é pequeno. O custo está no mapa vetorial."
      : "Os pins pesam: sem eles a fluidez sobe bastante.";
    texto(`marcas na tela: ${marcas}
com pin:  ${comPin.fps} fps · pior quadro ${comPin.piorQuadroMs} ms
sem pin:  ${semPin.fps} fps · pior quadro ${semPin.piorQuadroMs} ms
tela: ${innerWidth}x${innerHeight} · densidade ${devicePixelRatio}

${veredito}`);
  });
})();
