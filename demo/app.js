"use strict";

// 1. Configuracao e estado da interface
const $ = (id) => document.getElementById(id);
const apiBase = (window.FROTA_CONFIG?.apiBase || "").replace(/\/$/, "");
const apiUrl = (caminho) => `${apiBase}${caminho}`;
const nomes = {
  queda: "Em queda",
  melhora: "Em melhora",
  estavel: "Estável",
  sem_historico: "Sem comparação",
};

let itens = [];
let selecionado = null;
let versao = 0;
let detalheVersao = 0;

function fmt(valor, casas = 2) {
  if (valor === null || valor === undefined) return "—";
  return Number(valor).toLocaleString("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  });
}

function data(valor) {
  return valor ? valor.split("-").reverse().join("/") : "—";
}

function filtros() {
  const parametros = new URLSearchParams();
  for (const campo of ["inicio", "fim"]) {
    if ($(campo).value) parametros.set(campo, $(campo).value);
  }
  return parametros;
}

async function api(caminho) {
  if (window.FROTA_CONFIG?.modo === "estatico") return window.FrotaDados.api(caminho);
  const resposta = await fetch(apiUrl(caminho));
  if (!resposta.ok) {
    let corpo;
    try { corpo = await resposta.json(); } catch { /* Pode ser uma pagina de erro do servidor. */ }
    throw new Error(typeof corpo?.detail === "string"
      ? corpo.detail
      : `Não foi possível consultar os dados (HTTP ${resposta.status}). Confira se o backend está em execução e configurado neste servidor.`);
  }
  try {
    return await resposta.json();
  } catch {
    throw new Error("A API não respondeu com dados. Confira a configuração do backend na hospedagem.");
  }
}

// 2. Tabela de veiculos e resumo das situacoes
function celula(linha, valor, classe) {
  const elemento = document.createElement("td");
  elemento.textContent = valor;
  if (classe) elemento.className = classe;
  linha.append(elemento);
  return elemento;
}

function tabela() {
  const termo = $("busca").value.trim().toLowerCase();
  const estado = $("situacao").value;
  const ordem = $("ordem").value;
  const indicadores = {
    queda: "total-queda",
    melhora: "total-melhora",
    estavel: "total-estavel",
    sem_historico: "total-sem-historico",
  };
  for (const [situacao, id] of Object.entries(indicadores)) {
    $(id).textContent = fmt(itens.filter((r) => r.situacao === situacao).length, 0);
  }

  const visiveis = itens.filter((r) =>
    r.prefixo.toLowerCase().includes(termo) &&
    (estado === "todos" || r.situacao === estado));

  visiveis.sort((a, b) => {
    if (ordem === "prefixo") return a.prefixo.localeCompare(b.prefixo);
    const campo = ordem === "rendimento" ? "km_por_litro" : "variacao_percentual";
    return Number(a[campo] ?? Infinity) - Number(b[campo] ?? Infinity);
  });

  $("contagem").textContent = `${visiveis.length} de ${itens.length} veículos`;
  $("linhas").replaceChildren();
  for (const registro of visiveis) {
    const linha = document.createElement("tr");
    celula(linha, registro.prefixo);
    celula(linha, data(registro.data));
    celula(linha, fmt(registro.km_total));
    celula(linha, fmt(registro.litros_total, 3));
    celula(linha, fmt(registro.km_por_litro));

    const percentual = registro.variacao_percentual;
    const variacao = celula(linha, percentual === null
      ? "—"
      : `${Number(percentual) > 0 ? "+" : ""}${fmt(percentual)}%`);
    variacao.title = registro.data_anterior
      ? `Comparado com ${data(registro.data_anterior)}`
      : "Sem registro anterior no período";

    const situacao = celula(linha, "");
    const badge = document.createElement("span");
    badge.className = `badge ${registro.situacao}`;
    badge.textContent = nomes[registro.situacao];
    situacao.append(badge);

    const acao = celula(linha, "");
    const botao = document.createElement("button");
    botao.className = "link";
    botao.textContent = "Ver histórico ↗";
    botao.setAttribute("aria-label", `Ver histórico do prefixo ${registro.prefixo}`);
    botao.onclick = () => historico(registro.prefixo, true);
    acao.append(botao);
    $("linhas").append(linha);
  }

  if (!visiveis.length) {
    const linha = document.createElement("tr");
    celula(linha, "Nenhum veículo encontrado.", "empty").colSpan = 8;
    $("linhas").append(linha);
  }
}

// 3. Graficos SVG sem dependencias externas
function svgElemento(tag, atributos = {}, texto) {
  const elemento = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [chave, valor] of Object.entries(atributos)) elemento.setAttribute(chave, valor);
  if (texto !== undefined) elemento.textContent = texto;
  return elemento;
}

function grafico(id, registros, campo, cor) {
  const caixa = $(id);
  caixa.replaceChildren();
  const pontos = registros.filter((r) => r[campo] !== null && Number.isFinite(Number(r[campo])));
  if (!pontos.length) {
    const aviso = document.createElement("p");
    aviso.textContent = "Sem dados neste período.";
    caixa.append(aviso);
    return;
  }

  const esquerda = 58, direita = 58, topo = 28, base = 42;
  // Reserva espaco por dia para manter os valores e as datas legiveis.
  const largura = Math.max(600, (pontos.length - 1) * 95 + esquerda + direita);
  const altura = 260;
  const maximo = pontos.reduce((max, r) => Math.max(max, Number(r[campo])), 0) * 1.22 || 1;
  const x = (i) => pontos.length === 1
    ? (esquerda + largura - direita) / 2
    : esquerda + i * (largura - esquerda - direita) / (pontos.length - 1);
  const y = (valor) => altura - base - Number(valor) / maximo * (altura - topo - base);
  const svg = svgElemento("svg", {
    viewBox: `0 0 ${largura} ${altura}`,
    role: "img",
    "aria-label": `${campo === "km_total" ? "Quilometragem" : "Rendimento"} por data. Valores na tabela abaixo.`,
  });
  if (pontos.length > 6) svg.style.minWidth = `${largura}px`;

  for (let i = 0; i <= 4; i++) {
    const valor = maximo * i / 4;
    svg.append(svgElemento("line", {
      x1: esquerda, x2: largura - direita, y1: y(valor), y2: y(valor), stroke: "#e8eef1",
    }));
    svg.append(svgElemento("text", {
      x: esquerda - 9, y: y(valor) + 4, "text-anchor": "end", fill: "#7a8c96", "font-size": 11,
    }, fmt(valor, campo === "km_total" ? 0 : 1)));
  }

  if (pontos.length > 1) {
    const coordenadas = pontos.map((r, i) => `${x(i)},${y(r[campo])}`).join(" ");
    // Area transparente facilita acompanhar a linha sem inventar dados.
    svg.append(svgElemento("polygon", {
      points: `${x(0)},${altura - base} ${coordenadas} ${x(pontos.length - 1)},${altura - base}`,
      fill: cor, opacity: ".06",
    }));
    svg.append(svgElemento("polyline", {
      points: coordenadas, fill: "none", stroke: cor, "stroke-width": 2.5,
      "stroke-linejoin": "round", "stroke-linecap": "round",
    }));
  }

  pontos.forEach((registro, indice) => {
    const circulo = svgElemento("circle", { cx: x(indice), cy: y(registro[campo]), r: 4, fill: cor });
    circulo.append(svgElemento("title", {}, `${data(registro.data)}: ${fmt(registro[campo])}`));
    svg.append(circulo);
    svg.append(svgElemento("text", {
      x: x(indice), y: y(registro[campo]) - 13,
      "text-anchor": "middle", fill: cor, "font-size": 12, "font-weight": 700,
      stroke: "white", "stroke-width": 4, "paint-order": "stroke", "stroke-linejoin": "round",
      class: "valor-ponto",
    }, fmt(registro[campo])));
    svg.append(svgElemento("text", {
      x: x(indice), y: altura - 13, "text-anchor": "middle", fill: "#7a8c96", "font-size": 11,
    }, data(registro.data)));
  });
  caixa.append(svg);

  if (pontos.length === 1) {
    const aviso = document.createElement("p");
    aviso.textContent = "Apenas um dia disponível. Importe outros dias para acompanhar a evolução.";
    caixa.append(aviso);
  }
}

// 4. Consulta individual e tratamento de respostas fora de ordem
function limparHistorico(texto) {
  $("dados-historico").replaceChildren();
  for (const id of ["grafico-consumo", "grafico-km"]) {
    const aviso = document.createElement("p");
    aviso.textContent = texto;
    $(id).replaceChildren(aviso);
  }
  $("variacao-detalhe").textContent = "";
}

async function historico(prefixo, rolar = false) {
  selecionado = prefixo;
  const atualizacao = ++detalheVersao;
  $("titulo-historico").textContent = `Histórico · ${prefixo}`;
  limparHistorico("Carregando histórico…");
  $("descricao-historico").textContent = "Consultando o banco de dados.";
  if (rolar) $("historico").scrollIntoView({ behavior: "smooth" });

  try {
    const todos = [];
    let offset = 0, total;
    do {
      const parametros = filtros();
      parametros.set("limite", "1000");
      parametros.set("offset", offset);
      const resposta = await api(`/veiculos/${encodeURIComponent(prefixo)}/historico?${parametros}`);
      if (atualizacao !== detalheVersao) return;
      total = resposta.total_dias;
      todos.push(...resposta.itens);
      offset += resposta.itens.length;
      if (!resposta.itens.length) break;
    } while (offset < total);

    const ordenados = todos.sort((a, b) => a.data.localeCompare(b.data));
    $("descricao-historico").textContent = `${ordenados.length} dias registrados no período · valores acima de cada ponto.${ordenados.length > 6 ? " Deslize o gráfico para consultar todos os dias." : ""}`;
    grafico("grafico-consumo", ordenados, "km_por_litro", "#187c68");
    grafico("grafico-km", ordenados, "km_total", "#527cab");
    $("dados-historico").replaceChildren();
    for (const registro of [...ordenados].reverse()) {
      const linha = document.createElement("tr");
      for (const valor of [data(registro.data), fmt(registro.km_total), fmt(registro.litros_total, 3), fmt(registro.km_por_litro)]) {
        celula(linha, valor);
      }
      $("dados-historico").append(linha);
    }

    const ultimo = itens.find((r) => r.prefixo === prefixo);
    $("variacao-detalhe").textContent = ultimo?.data_anterior
      ? `Última comparação: ${data(ultimo.data_anterior)} → ${data(ultimo.data)} (${fmt(ultimo.variacao_percentual)}%)`
      : "Histórico insuficiente para comparação.";
  } catch (erro) {
    if (atualizacao !== detalheVersao) return;
    limparHistorico("Não foi possível carregar o histórico.");
    $("descricao-historico").textContent = erro.message;
  }
}

// 5. Atualizacao dos indicadores e da tabela
async function carregar() {
  if (window.FROTA_CONFIG?.modo === "estatico") window.FrotaDados.limparCache();
  const atualizacao = ++versao;
  ++detalheVersao;
  const parametros = filtros();
  $("mensagem").textContent = "Carregando dados…";
  itens = [];
  tabela();
  for (const id of ["k-veiculos", "k-km", "k-litros", "k-media"]) $(id).textContent = "—";
  limparHistorico("Selecione um veículo após a consulta.");
  $("descricao-historico").textContent = "";

  try {
    if ($("inicio").value && $("fim").value && $("inicio").value > $("fim").value) {
      throw new Error("A data inicial deve ser anterior ou igual à data final.");
    }
    const [resumo, frota] = await Promise.all([api(`/painel?${parametros}`), api(`/frota?${parametros}`)]);
    if (atualizacao !== versao) return;
    itens = frota.itens;
    $("k-veiculos").textContent = fmt(resumo.veiculos, 0);
    $("k-km").textContent = fmt(resumo.km_total, 0);
    $("k-litros").textContent = fmt(resumo.litros_total, 3);
    $("k-media").textContent = resumo.km_por_litro === null ? "—" : `${fmt(resumo.km_por_litro)} km/l`;
    $("periodo").textContent = resumo.primeira_data
      ? `${data(resumo.primeira_data)} a ${data(resumo.ultima_data)}` : "Sem registros";
    $("mensagem").textContent = itens.length ? "" : "Não há abastecimentos no período selecionado.";
    tabela();
    if (selecionado && itens.some((r) => r.prefixo === selecionado)) {
      await historico(selecionado);
    } else {
      $("titulo-historico").textContent = "Histórico do veículo";
      selecionado = null;
    }
  } catch (erro) {
    if (atualizacao !== versao) return;
    $("mensagem").textContent = erro.message;
    $("periodo").textContent = "Consulta não concluída";
    for (const id of ["total-queda", "total-melhora", "total-estavel", "total-sem-historico"]) $(id).textContent = "—";
  }
}

// 6. Envio de PDF, validacao e atualizacao apos a importacao
async function importar(evento) {
  evento.preventDefault();
  const arquivo = $("arquivo-pdf").files[0];
  const resultado = $("resultado-importacao");
  const botao = $("botao-importar");
  resultado.className = "";
  resultado.textContent = "";
  if (!arquivo) return;
  if (!arquivo.name.toLowerCase().endsWith(".pdf") || arquivo.size === 0 || arquivo.size > 10 * 1024 * 1024) {
    resultado.className = "erro";
    resultado.textContent = "Selecione um PDF não vazio de até 10 MB.";
    return;
  }

  botao.disabled = true;
  $("arquivo-pdf").disabled = true;
  botao.textContent = "Importando…";
  resultado.textContent = "Validando o relatório e conferindo o banco. Aguarde a conclusão.";
  try {
    const resposta = await fetch(apiUrl(`/importacoes?${new URLSearchParams({ nome: arquivo.name })}`), {
      method: "POST",
      headers: { "Content-Type": "application/pdf" },
      body: arquivo,
    });
    let corpo;
    try { corpo = await resposta.json(); } catch {
      throw new Error("Resposta inesperada do servidor. Confira a conexão e tente novamente.");
    }
    if (!resposta.ok) {
      const detalhe = corpo.detail;
      throw new Error(typeof detalhe === "string" ? detalhe : detalhe?.mensagem
        ? `${detalhe.mensagem}\n${(detalhe.erros || []).slice(0, 15).join("\n")}`
        : "Não foi possível importar o PDF. Confira o arquivo e tente novamente.");
    }
    resultado.textContent = corpo.mensagem;
    if (corpo.status === "importado") {
      const foraDoPeriodo = (corpo.datas || []).some((d) =>
        ($("inicio").value && d < $("inicio").value) || ($("fim").value && d > $("fim").value));
      if (foraDoPeriodo) {
        $("inicio").value = "";
        $("fim").value = "";
        resultado.textContent += " O período foi ampliado para mostrar os novos registros.";
      }
      $("arquivo-pdf").value = "";
    }
    await carregar();
  } catch (erro) {
    resultado.className = "erro";
    resultado.textContent = `${erro.message}\nSe a conexão caiu durante o envio, você pode reenviar o mesmo arquivo para conferir o resultado sem duplicar os dados.`;
  } finally {
    botao.disabled = false;
    $("arquivo-pdf").disabled = false;
    botao.textContent = "Importar PDF";
  }
}

// 7. Eventos da interface
$("filtros").onsubmit = (evento) => { evento.preventDefault(); carregar(); };
$("limpar").onclick = () => { $("inicio").value = ""; $("fim").value = ""; carregar(); };
$("importar-form").onsubmit = importar;
for (const id of ["busca", "situacao", "ordem"]) $(id).addEventListener("input", tabela);
document.querySelectorAll("nav a").forEach((link) => {
  link.addEventListener("click", () => {
    document.querySelectorAll("nav a").forEach((item) => item.classList.remove("active"));
    link.classList.add("active");
  });
});
if (window.FROTA_CONFIG?.modo === "estatico") {
  // A publicacao apenas consulta dados; a importacao continua no computador.
  $("importar-form").hidden = true;
  $("titulo-importacao").textContent = "Atualização dos dados publicados";
  document.querySelector(".upload-heading p").textContent = "Os relatórios são importados no computador da empresa. Este painel mostra a última exportação publicada.";
  document.querySelector(".file-tag").textContent = "Consulta";
  document.querySelectorAll('a[href="#importacao"]').forEach((link) => { link.textContent = "Atualização dos dados"; });
  setInterval(() => { if (!document.hidden) carregar(); }, 60000);
}
carregar();
