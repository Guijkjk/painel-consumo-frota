"""Prepara os arquivos publicos sem copiar banco, PDFs ou credenciais."""
import shutil
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

PASTA = Path(__file__).resolve().parent


def preparar():
    origem, destino = PASTA / "web", PASTA / "publicar-frontend"
    destino.mkdir(exist_ok=True)
    html = (origem / "index.html").read_text(encoding="utf-8").replace('/assets/', './')
    (destino / "index.html").write_text(html, encoding="utf-8")
    for nome in ("style.css", "app.js", "dados-estaticos.js"):
        shutil.copyfile(origem / nome, destino / nome)
    (destino / "config.js").write_text(
        '/* Configuracao publica. Nao incluir senhas. */\n'
        'window.FROTA_CONFIG = Object.freeze({\n'
        '  modo: "estatico",\n  dadosUrl: "./dados/frota.json"\n});\n', encoding="utf-8")
    with ZipFile(PASTA / "frontend-filezilla.zip", "w", ZIP_DEFLATED) as pacote:
        for nome in ("index.html", "style.css", "app.js", "config.js", "dados-estaticos.js"):
            pacote.write(destino / nome, nome)
    # A pasta dados ja existente e preservada. O ZIP contem somente o frontend.


if __name__ == "__main__":
    preparar()
    print("Frontend preparado. Exporte o MySQL com exportar_site.py para gerar a pasta dados.")
