"""Valida o PDF original e importa todos os registros em uma unica transacao."""
import argparse
import getpass
import hashlib
import io
from pathlib import Path

import pdfplumber
import pymysql

from extrair_relatorio import analisar_paginas


def ler_pdf(conteudo):
    """Leitura compartilhada entre o terminal e o site."""
    if not conteudo.lstrip().startswith(b"%PDF-"):
        raise ValueError("O arquivo enviado nao e um PDF valido.")
    with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
        if len(pdf.pages) > 100:
            raise ValueError("O relatorio deve ter no maximo 100 paginas.")
        return analisar_paginas([
            pagina.dedupe_chars().extract_text() or "" for pagina in pdf.pages
        ])


def salvar(conexao, nome, sha256, registros):
    """Retorna False se o arquivo ja existe. Qualquer falha desfaz a importacao."""
    bloqueado = False
    try:
        # Serializa importacoes deste aplicativo, inclusive PDFs diferentes com
        # abastecimentos sobrepostos. Liberacao tambem ocorre ao fechar a conexao.
        with conexao.cursor() as cursor:
            cursor.execute("SELECT GET_LOCK('gestao_frota_importacao_v1', 10)")
            bloqueado = cursor.fetchone()[0] == 1
            if not bloqueado:
                raise ValueError("Outra importacao esta em andamento. Tente novamente.")
            conexao.begin()
            cursor.execute("SELECT id FROM importacoes WHERE arquivo_sha256 = %s", (sha256,))
            if cursor.fetchone():
                conexao.rollback()
                return False
            cursor.execute(
                "INSERT INTO importacoes (nome_arquivo, arquivo_sha256, quantidade_registros) VALUES (%s,%s,%s)",
                (nome, sha256, len(registros)),
            )
            importacao_id = cursor.lastrowid
            for r in registros:
                cursor.execute("SELECT id FROM veiculos WHERE prefixo = %s", (r["prefixo"],))
                veiculo = cursor.fetchone()
                if veiculo:
                    veiculo_id = veiculo[0]
                else:
                    cursor.execute("INSERT INTO veiculos (prefixo) VALUES (%s)", (r["prefixo"],))
                    veiculo_id = cursor.lastrowid
                cursor.execute(
                    "SELECT id FROM abastecimentos WHERE veiculo_id=%s AND data_referencia=%s AND hora=%s AND bomba=%s LIMIT 1",
                    (veiculo_id, r["data"], r["hora"], r["bomba"]),
                )
                if cursor.fetchone():
                    raise ValueError(
                        f"Ja existe abastecimento para {r['prefixo']} em {r['data']} "
                        f"as {r['hora']}, bomba {r['bomba']}. "
                        "Importacao cancelada para revisar sobreposicao ou correcao."
                    )
                cursor.execute(
                    "INSERT INTO abastecimentos "
                    "(veiculo_id,importacao_id,data_referencia,hora,bomba,litros,km_total,km_litro_informado,observacoes,pagina_pdf) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (veiculo_id, importacao_id, r["data"], r["hora"], r["bomba"],
                     r["litros"], r["km_total"], r["km_litro_informado"], r["observacoes"], r["pagina"]),
                )
        conexao.commit()
        return True
    except Exception:
        conexao.rollback()
        raise
    finally:
        if bloqueado:
            with conexao.cursor() as cursor:
                cursor.execute("SELECT RELEASE_LOCK('gestao_frota_importacao_v1')")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--porta", type=int, default=3306)
    parser.add_argument("--usuario", default="root")
    parser.add_argument("--banco", default="gestao_frota")
    parser.add_argument("--validar", action="store_true", help="Valida sem conectar ao MySQL")
    args = parser.parse_args()
    conexao = None
    try:
        conteudo = args.pdf.read_bytes()
        registros, erros, avisos = ler_pdf(conteudo)
        if erros:
            print("PDF rejeitado. Nenhum dado gravado:")
            for erro in erros:
                print(f"- {erro}")
            return 1
        print(f"PDF validado: {len(registros)} registros.")
        for aviso in avisos:
            print(f"Aviso: {aviso}")
        if args.validar:
            print("Validacao concluida; nenhuma conexao ao banco foi realizada.")
            return 0
        senha = getpass.getpass(f"Senha MySQL de {args.usuario}: ")
        conexao = pymysql.connect(
            host=args.host, port=args.porta, user=args.usuario, password=senha,
            database=args.banco, charset="utf8mb4", autocommit=False,
            connect_timeout=10,
        )
        sucesso = salvar(conexao, args.pdf.name, hashlib.sha256(conteudo).hexdigest(), registros)
        if sucesso:
            print(f"SUCESSO: {len(registros)} abastecimentos gravados no banco {args.banco}.")
        else:
            print("Este PDF ja foi importado. Nenhum registro foi duplicado.")
        return 0
    except pymysql.MySQLError as erro:
        codigo = erro.args[0] if erro.args else "desconhecido"
        orientacoes = {
            1045: "Usuario ou senha incorretos, ou usuario sem acesso.",
            1049: "Banco inexistente. Execute o SQL de criacao do banco gestao_frota.",
            1146: "Tabela inexistente. Execute o SQL de criacao das tres tabelas.",
            2003: "Nao foi possivel conectar. Confira servidor MySQL, host e porta.",
        }
        print(f"Erro MySQL {codigo}: {orientacoes.get(codigo, 'Falha na operacao; confira a estrutura e as permissoes do banco.')}")
        print("A importacao nao foi concluida. Alteracoes da transacao foram desfeitas.")
        return 1
    except (OSError, ValueError) as erro:
        print(f"Importacao cancelada: {erro}")
        return 1
    finally:
        if conexao:
            conexao.close()


if __name__ == "__main__":
    raise SystemExit(main())
