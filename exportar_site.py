"""Exporta indicadores diarios do MySQL para o site estatico, sem credenciais."""
import argparse
import getpass
import json
import os
import tempfile
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pymysql

PASTA = Path(__file__).resolve().parent


def serializar(valor):
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    raise TypeError(f"Tipo nao suportado: {type(valor).__name__}")


def exportar(conexao, destino):
    # Uma unica consulta produz uma fotografia consistente, sem nomes de
    # motoristas, observacoes livres, arquivos PDF ou dados de conexao.
    with conexao.cursor() as cursor:
        cursor.execute(
            "SELECT v.prefixo,a.data_referencia AS data,COUNT(*) AS abastecimentos,"
            "SUM(a.km_total) AS km_total,SUM(a.litros) AS litros_total "
            "FROM abastecimentos a JOIN veiculos v ON v.id=a.veiculo_id "
            "GROUP BY v.prefixo,a.data_referencia ORDER BY v.prefixo,a.data_referencia"
        )
        diarios = cursor.fetchall()
    pacote = {"versao": 1, "exportado_em": datetime.now(timezone.utc).isoformat(), "diarios": diarios}
    texto = json.dumps(pacote, ensure_ascii=False, default=serializar, allow_nan=False)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    # Substitui somente depois de produzir o arquivo completo.
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destino.parent,
                                         suffix=".tmp", delete=False) as arquivo:
            temporario = Path(arquivo.name)
            arquivo.write(texto)
        os.replace(temporario, destino)
    finally:
        if temporario and temporario.exists():
            temporario.unlink()
    return len(diarios)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("FROTA_DB_HOST", "127.0.0.1"))
    parser.add_argument("--porta", type=int, default=int(os.environ.get("FROTA_DB_PORT", "3306")))
    parser.add_argument("--usuario", default=os.environ.get("FROTA_DB_USER", "root"))
    parser.add_argument("--banco", default=os.environ.get("FROTA_DB_NAME", "gestao_frota"))
    args = parser.parse_args()
    conexao = None
    try:
        senha = getpass.getpass(f"Senha MySQL de {args.usuario}: ")
        conexao = pymysql.connect(host=args.host, port=args.porta, user=args.usuario,
                                  password=senha, database=args.banco, charset="utf8mb4",
                                  cursorclass=pymysql.cursors.DictCursor,
                                  connect_timeout=10, read_timeout=60)
        destino = PASTA / "publicar-frontend" / "dados" / "frota.json"
        quantidade = exportar(conexao, destino)
        print(f"SUCESSO: {quantidade} registros diarios exportados.")
        print(f"Arquivo: {destino}")
        print("Envie a pasta dados pelo FileZilla para gestao-frota, substituindo o JSON anterior.")
        return 0
    except pymysql.MySQLError as erro:
        print(f"Falha MySQL (codigo {erro.args[0]}). Confira servidor, usuario, senha e banco.")
        return 1
    except (OSError, TypeError, ValueError) as erro:
        print(f"Nao foi possivel exportar: {erro}")
        return 1
    finally:
        if conexao:
            conexao.close()


if __name__ == "__main__":
    raise SystemExit(main())
