"""Extrai o Relatorio de Abastecimento por Bomba (RDprint)."""
import argparse
import csv
import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pdfplumber

NUMERO = r"(?:\d{1,3}(?:\.\d{3})+|\d+),\d+"
LINHA = re.compile(
    rf"^(\d{{2}}/\d{{2}}/\d{{4}})\s+(\d{{2}}:\d{{2}})\s+(\S+)"
    rf"\s+({NUMERO})\s+({NUMERO})\s+({NUMERO})(?:\s+(.*))?$"
)
TOTAL = re.compile(rf"Total da Bomba\s+(\S+)\s*=>\s*({NUMERO})\s+({NUMERO})\s+({NUMERO})")
BOMBA = re.compile(r"Bomba:\s*(\S+)")


def decimal_br(valor):
    return Decimal(valor.replace(".", "").replace(",", "."))


def analisar_paginas(paginas):
    registros, erros, avisos, totais = [], [], [], []
    bomba = None
    for pagina, texto in enumerate(paginas, 1):
        if not texto.strip():
            erros.append(f"Pagina {pagina}: sem texto extraivel; pode exigir OCR.")
        for linha in texto.splitlines():
            linha = linha.strip()
            cabecalho = BOMBA.search(linha)
            if cabecalho:
                bomba = cabecalho[1]
            total = TOTAL.search(linha)
            if total:
                totais.append((total[1], decimal_br(total[2]), decimal_br(total[3])))
                continue
            if not re.match(r"^\d{2}/\d{2}/\d{4}\b", linha):
                continue
            match = LINHA.fullmatch(linha)
            if not match:
                erros.append(f"Pagina {pagina}: linha de dados nao reconhecida: {linha}")
                continue
            data, hora, prefixo, litros, km, rendimento, obs = match.groups()
            try:
                instante = datetime.strptime(f"{data} {hora}", "%d/%m/%Y %H:%M")
            except ValueError:
                erros.append(f"Pagina {pagina}: data/hora invalida: {data} {hora}")
                continue
            litros, km, rendimento = map(decimal_br, (litros, km, rendimento))
            if litros <= 0 or km < 0 or rendimento < 0:
                erros.append(f"Pagina {pagina}, prefixo {prefixo}: valores invalidos.")
            elif abs(km / litros - rendimento) > Decimal("0.011"):
                erros.append(f"Pagina {pagina}, prefixo {prefixo}: km/l diverge de km / litros.")
            if not bomba:
                erros.append(f"Pagina {pagina}, prefixo {prefixo}: bomba nao identificada.")
            registros.append({
                "data": instante.date().isoformat(), "hora": hora,
                "prefixo": prefixo, "bomba": bomba, "litros": litros,
                "km_total": km, "km_litro_informado": rendimento,
                "observacoes": obs or "", "pagina": pagina,
            })
    if not registros:
        erros.append("Nenhum registro encontrado no formato esperado.")
    if not totais:
        erros.append("Total da bomba ausente: nao foi possivel conferir a integridade.")
    for codigo in {r["bomba"] for r in registros}:
        encontrados = [t for t in totais if t[0] == codigo]
        if len(encontrados) != 1:
            erros.append(f"Bomba {codigo}: esperado um total, encontrados {len(encontrados)}.")
    for codigo, litros, km in totais:
        itens = [r for r in registros if r["bomba"] == codigo]
        if not itens:
            erros.append(f"Bomba {codigo}: total sem registros correspondentes.")
        if sum((r["litros"] for r in itens), Decimal(0)) != litros:
            erros.append(f"Bomba {codigo}: soma dos litros diverge do total impresso.")
        if sum((r["km_total"] for r in itens), Decimal(0)) != km:
            erros.append(f"Bomba {codigo}: soma dos km diverge do total impresso.")
    chaves = set()
    for r in registros:
        chave = tuple(str(r[c]) for c in ("data", "hora", "prefixo", "bomba", "litros", "km_total"))
        if chave in chaves:
            erros.append(f"Possivel registro duplicado: {r['data']} {r['hora']} {r['prefixo']}.")
        chaves.add(chave)
    avisos.append("KM Total foi preservado como informado; confirme o periodo que a quilometragem representa.")
    return registros, erros, avisos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="Caminho do PDF")
    parser.add_argument("--saida", type=Path, default=Path("resultado"))
    args = parser.parse_args()
    conteudo = args.pdf.read_bytes()
    identificador = hashlib.sha256(conteudo).hexdigest()
    with pdfplumber.open(args.pdf) as pdf:
        # RDprint pode imprimir os mesmos caracteres sobrepostos (efeito negrito).
        paginas = [p.dedupe_chars().extract_text() or "" for p in pdf.pages]
    registros, erros, avisos = analisar_paginas(paginas)
    litros = sum((r["litros"] for r in registros), Decimal(0))
    km = sum((r["km_total"] for r in registros), Decimal(0))
    relatorio = {
        "arquivo": args.pdf.name, "sha256": identificador,
        "valido": not erros, "paginas": len(paginas), "registros": len(registros),
        "prefixos": len({r["prefixo"] for r in registros}),
        "datas": sorted({r["data"] for r in registros}),
        "litros_total": str(litros), "km_total": str(km),
        "km_litro_consolidado": str((km / litros).quantize(Decimal("0.01"))) if litros else None,
        "erros": erros, "avisos": avisos,
    }
    # Cada execucao tem uma pasta propria; um resultado invalido nao reutiliza CSV antigo.
    from tempfile import mkdtemp
    args.saida.mkdir(parents=True, exist_ok=True)
    destino = Path(mkdtemp(prefix=identificador[:12] + "-", dir=args.saida))
    (destino / "validacao.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    if not erros:
        for r in registros:
            r["arquivo_sha256"] = identificador
        (destino / "registros.json").write_text(json.dumps(registros, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        with (destino / "registros.csv").open("w", encoding="utf-8-sig", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=list(registros[0]), delimiter=";")
            escritor.writeheader()
            escritor.writerows(registros)
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    print(f"\nArquivos: {destino.resolve()}")
    return 1 if erros else 0


if __name__ == "__main__":
    raise SystemExit(main())
