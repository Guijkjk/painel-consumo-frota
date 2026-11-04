/* Adaptador para publicar os indicadores sem executar Python na hospedagem.
 * O mesmo calculo atende ao painel, filtros, tabela e historico.
 */
(function (raiz) {
  "use strict";

  function consultar(pacote, caminho) {
    if (pacote.versao !== 1 || !Array.isArray(pacote.diarios)) {
      throw new Error("Arquivo de dados incompatível. Gere uma nova exportação.");
    }
    const url = new URL(caminho, "https://frota.invalid");
    const inicio = url.searchParams.get("inicio");
    const fim = url.searchParams.get("fim");
    const dias = pacote.diarios
      .filter((r) => (!inicio || r.data >= inicio) && (!fim || r.data <= fim))
      .map((r) => ({ ...r, km_total: Number(r.km_total), litros_total: Number(r.litros_total),
        km_por_litro: Number(r.litros_total) > 0 ? Number(r.km_total) / Number(r.litros_total) : null }));
    const somar = (campo) => dias.reduce((total, r) => total + Number(r[campo]), 0);

    if (url.pathname === "/painel") {
      const datas = dias.map((r) => r.data).sort();
      const litros = somar("litros_total"), km = somar("km_total");
      return { abastecimentos: somar("abastecimentos"), veiculos: new Set(dias.map((r) => r.prefixo)).size,
        primeira_data: datas[0] || null, ultima_data: datas[datas.length - 1] || null,
        km_total: km, litros_total: litros, km_por_litro: litros > 0 ? km / litros : null };
    }
    if (url.pathname === "/frota") {
      const grupos = new Map();
      for (const registro of dias) {
        if (!grupos.has(registro.prefixo)) grupos.set(registro.prefixo, []);
        grupos.get(registro.prefixo).push(registro);
      }
      const itens = [];
      for (const registros of grupos.values()) {
        registros.sort((a, b) => b.data.localeCompare(a.data));
        const atual = registros[0], anterior = registros[1];
        const variacao = anterior?.km_por_litro > 0 && atual.km_por_litro !== null
          ? (atual.km_por_litro / anterior.km_por_litro - 1) * 100 : null;
        itens.push({ ...atual, anterior: anterior?.km_por_litro ?? null,
          data_anterior: anterior?.data ?? null, variacao_percentual: variacao,
          situacao: variacao === null ? "sem_historico" : variacao < -1 - 1e-9 ? "queda"
            : variacao > 1 + 1e-9 ? "melhora" : "estavel" });
      }
      return { itens: itens.sort((a, b) => a.prefixo.localeCompare(b.prefixo)) };
    }
    const historico = url.pathname.match(/^\/veiculos\/([^/]+)\/historico$/);
    if (historico) {
      const prefixo = decodeURIComponent(historico[1]);
      const registros = dias.filter((r) => r.prefixo === prefixo).sort((a, b) => b.data.localeCompare(a.data));
      const limite = Number(url.searchParams.get("limite") || 366);
      const offset = Number(url.searchParams.get("offset") || 0);
      return { veiculo: { prefixo }, total_dias: registros.length, limite, offset,
        itens: registros.slice(offset, offset + limite) };
    }
    throw new Error("Consulta não disponível no modo de dados publicados.");
  }

  let carregamento = null;
  async function api(caminho) {
    if (!carregamento) {
      const arquivo = raiz.FROTA_CONFIG?.dadosUrl || "./dados/frota.json";
      carregamento = fetch(arquivo, { cache: "no-store" }).then(async (resposta) => {
        if (!resposta.ok) throw new Error("Dados ainda não publicados. Exporte o MySQL e envie a pasta dados pelo FileZilla.");
        const pacote = await resposta.json();
        if (raiz.document) {
          const indicador = raiz.document.getElementById("atualizacao-dados");
          if (indicador) indicador.textContent = `Dados exportados em ${new Date(pacote.exportado_em).toLocaleString("pt-BR")}`;
        }
        return pacote;
      });
    }
    return consultar(await carregamento, caminho);
  }

  const adaptador = { consultar, api, limparCache: () => { carregamento = null; } };
  raiz.FrotaDados = adaptador;
  if (typeof module !== "undefined" && module.exports) module.exports = adaptador;
})(typeof window !== "undefined" ? window : globalThis);
