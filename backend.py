"""API local da frota. Inicie por iniciar_backend.py."""
import logging
import hashlib
import os
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import pymysql
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

import consultas
from importar_mysql import ler_pdf, salvar

app = FastAPI(title="Gestão da Frota", version="0.1.0",
              description="Consultas de abastecimento. Valores km/l consolidados por km / litros.")
WEB = Path(__file__).resolve().parent / "web"
app.mount("/assets", StaticFiles(directory=WEB), name="assets")


@app.get("/", include_in_schema=False)
def inicio():
    return FileResponse(WEB / "index.html")


@app.get("/style.css", include_in_schema=False)
@app.get("/app.js", include_in_schema=False)
@app.get("/config.js", include_in_schema=False)
def arquivo_frontend(request: Request):
    # Rotas explicitas mantem os mesmos caminhos relativos usados via FTP.
    return FileResponse(WEB / request.url.path.rsplit("/", 1)[-1])


@app.get("/frota")
def frota(inicio: date | None = None, fim: date | None = None):
    validar_periodo(inicio, fim)
    with banco() as conexao:
        return consultas.frota(conexao, inicio, fim)


@contextmanager
def banco(escrita=False):
    conexao = None
    try:
        conexao = pymysql.connect(
            host=os.environ.get("FROTA_DB_HOST", "127.0.0.1"),
            port=int(os.environ.get("FROTA_DB_PORT", "3306")),
            user=os.environ.get("FROTA_DB_USER", "root"),
            password=os.environ["FROTA_DB_PASSWORD"],
            database=os.environ.get("FROTA_DB_NAME", "gestao_frota"),
            charset="utf8mb4", cursorclass=pymysql.cursors.Cursor if escrita else pymysql.cursors.DictCursor,
            autocommit=False, connect_timeout=5, read_timeout=15, write_timeout=15,
        )
        # Uma transacao de leitura por requisicao; nao altera os registros.
        if not escrita:
            with conexao.cursor() as cursor:
                cursor.execute("START TRANSACTION READ ONLY")
        yield conexao
    except pymysql.MySQLError:
        logging.getLogger(__name__).error("Falha de acesso ao MySQL; confira a conexao e as tabelas.")
        raise HTTPException(503, "Banco indisponivel. Confira servidor, credenciais e tabelas.") from None
    finally:
        if conexao:
            conexao.close()


def importar_conteudo(conteudo, nome):
    try:
        registros, erros, avisos = ler_pdf(conteudo)
    except Exception:
        # Erros do parser nao devem expor detalhes internos ou abrir o banco.
        raise HTTPException(422, "Nao foi possivel ler o PDF. Confira se esta valido, sem senha e tem ate 100 paginas.") from None
    if erros:
        raise HTTPException(422, {"mensagem": "PDF rejeitado. Nenhum dado gravado.", "erros": erros})
    sha256 = hashlib.sha256(conteudo).hexdigest()
    try:
        with banco(escrita=True) as conexao:
            gravado = salvar(conexao, nome, sha256, registros)
    except ValueError as erro:
        raise HTTPException(409, str(erro)) from None
    return {"status": "importado" if gravado else "ja_importado",
            "registros": len(registros), "datas": sorted({r["data"] for r in registros}),
            "avisos": avisos,
            "mensagem": f"{len(registros)} abastecimentos importados com sucesso." if gravado
            else "Este PDF ja foi importado. Nenhum registro foi duplicado."}


@app.post("/importacoes")
async def importar(request: Request, nome: str = Query(..., min_length=1, max_length=255)):
    # O navegador envia o arquivo diretamente, sem dependencia multipart.
    origem = request.headers.get("origin")
    if origem and origem != f"{request.url.scheme}://{request.url.netloc}":
        raise HTTPException(403, "Envie o PDF pelo site deste computador.")
    if request.headers.get("content-type", "").split(";")[0].lower() != "application/pdf":
        raise HTTPException(415, "Selecione um arquivo PDF.")
    nome = nome.replace("\\", "/").rsplit("/", 1)[-1]
    if not nome.lower().endswith(".pdf"):
        raise HTTPException(415, "O arquivo deve ter extensao .pdf.")
    limite = 10 * 1024 * 1024
    conteudo = bytearray()
    async for bloco in request.stream():
        if len(conteudo) + len(bloco) > limite:
            raise HTTPException(413, "O PDF deve ter no maximo 10 MB.")
        conteudo.extend(bloco)
    if not conteudo:
        raise HTTPException(422, "O arquivo esta vazio.")
    return await run_in_threadpool(importar_conteudo, bytes(conteudo), nome)


def validar_periodo(inicio, fim):
    try:
        consultas.periodo(inicio, fim)
    except ValueError as erro:
        raise HTTPException(422, str(erro)) from None


@app.get("/saude")
def saude():
    with banco() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    return {"status": "ok", "banco": "conectado"}


@app.get("/painel")
def painel(inicio: date | None = None, fim: date | None = None):
    validar_periodo(inicio, fim)
    with banco() as conexao:
        return consultas.resumo(conexao, inicio, fim)


@app.get("/veiculos")
def veiculos(prefixo: str | None = Query(None, min_length=1, max_length=30),
             limite: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    with banco() as conexao:
        return consultas.veiculos(conexao, prefixo, limite, offset)


@app.get("/veiculos/{prefixo}/historico")
def historico(prefixo: str, inicio: date | None = None, fim: date | None = None,
              limite: int = Query(366, ge=1, le=1000), offset: int = Query(0, ge=0)):
    if not 1 <= len(prefixo) <= 30:
        raise HTTPException(422, "Prefixo deve ter entre 1 e 30 caracteres.")
    validar_periodo(inicio, fim)
    with banco() as conexao:
        resultado = consultas.historico(conexao, prefixo, inicio, fim, limite, offset)
    if resultado is None:
        raise HTTPException(404, "Prefixo nao encontrado.")
    return resultado
