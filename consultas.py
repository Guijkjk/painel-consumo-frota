"""Consultas somente de leitura para o painel da frota."""
from datetime import date


def frota(conexao, inicio=None, fim=None):
    clausulas, parametros = periodo(inicio, fim)
    filtro = " WHERE " + " AND ".join(clausulas) if clausulas else ""
    with conexao.cursor() as cursor:
        cursor.execute(
            "WITH diarios AS (SELECT a.veiculo_id,a.data_referencia AS data, "
            "SUM(a.km_total) AS km_total,SUM(a.litros) AS litros_total, "
            "SUM(a.km_total)/NULLIF(SUM(a.litros),0) AS km_por_litro "
            "FROM abastecimentos a" + filtro + " GROUP BY a.veiculo_id,a.data_referencia), "
            "comparados AS (SELECT diarios.*, "
            "LAG(km_por_litro) OVER (PARTITION BY veiculo_id ORDER BY data) AS anterior, "
            "LAG(data) OVER (PARTITION BY veiculo_id ORDER BY data) AS data_anterior, "
            "ROW_NUMBER() OVER (PARTITION BY veiculo_id ORDER BY data DESC) AS posicao "
            "FROM diarios) SELECT v.prefixo,c.data,c.km_total,c.litros_total,"
            "c.km_por_litro,c.anterior,c.data_anterior FROM comparados c "
            "JOIN veiculos v ON v.id=c.veiculo_id WHERE c.posicao=1 ORDER BY v.prefixo",
            parametros,
        )
        itens = cursor.fetchall()
    for item in itens:
        item.update(comparar(item["km_por_litro"], item["anterior"]))
    return {"itens": itens}


def comparar(atual, anterior):
    if atual is None or anterior is None or anterior <= 0:
        return {"variacao_percentual": None, "situacao": "sem_historico"}
    variacao = (atual / anterior - 1) * 100
    return {"variacao_percentual": variacao,
            "situacao": "queda" if variacao < -1 else "melhora" if variacao > 1 else "estavel"}


def periodo(inicio=None, fim=None):
    if inicio and fim and inicio > fim:
        raise ValueError("A data inicial deve ser anterior ou igual a data final.")
    clausulas, parametros = [], []
    if inicio:
        clausulas.append("a.data_referencia >= %s")
        parametros.append(inicio)
    if fim:
        clausulas.append("a.data_referencia <= %s")
        parametros.append(fim)
    return clausulas, parametros


def resumo(conexao, inicio=None, fim=None):
    clausulas, parametros = periodo(inicio, fim)
    filtro = " WHERE " + " AND ".join(clausulas) if clausulas else ""
    with conexao.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS abastecimentos, COUNT(DISTINCT a.veiculo_id) AS veiculos, "
            "MIN(a.data_referencia) AS primeira_data, MAX(a.data_referencia) AS ultima_data, "
            "COALESCE(SUM(a.km_total),0) AS km_total, COALESCE(SUM(a.litros),0) AS litros_total, "
            "ROUND(SUM(a.km_total)/NULLIF(SUM(a.litros),0),4) AS km_por_litro "
            "FROM abastecimentos a" + filtro, parametros,
        )
        return cursor.fetchone()


def veiculos(conexao, prefixo=None, limite=100, offset=0):
    # Busca exata para nao confundir prefixos; nenhum valor entra no texto SQL.
    filtro = " WHERE prefixo = %s" if prefixo else ""
    parametros = [prefixo] if prefixo else []
    with conexao.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM veiculos" + filtro, parametros)
        total = cursor.fetchone()["total"]
        cursor.execute(
            "SELECT id,prefixo,modelo,ativo FROM veiculos" + filtro + " ORDER BY prefixo LIMIT %s OFFSET %s",
            parametros + [limite, offset],
        )
        return {"total": total, "limite": limite, "offset": offset, "itens": cursor.fetchall()}


def historico(conexao, prefixo, inicio=None, fim=None, limite=366, offset=0):
    clausulas, parametros = periodo(inicio, fim)
    with conexao.cursor() as cursor:
        cursor.execute("SELECT id,prefixo,modelo FROM veiculos WHERE prefixo=%s", (prefixo,))
        veiculo = cursor.fetchone()
        if not veiculo:
            return None
        clausulas.insert(0, "a.veiculo_id=%s")
        parametros.insert(0, veiculo["id"])
        filtro = " WHERE " + " AND ".join(clausulas)
        cursor.execute(
            "SELECT COUNT(DISTINCT a.data_referencia) AS total FROM abastecimentos a" + filtro,
            parametros,
        )
        total = cursor.fetchone()["total"]
        cursor.execute(
            "SELECT a.data_referencia AS data, COUNT(*) AS abastecimentos, "
            "SUM(a.km_total) AS km_total, SUM(a.litros) AS litros_total, "
            "ROUND(SUM(a.km_total)/NULLIF(SUM(a.litros),0),4) AS km_por_litro "
            "FROM abastecimentos a" + filtro +
            " GROUP BY a.data_referencia ORDER BY a.data_referencia DESC LIMIT %s OFFSET %s",
            parametros + [limite, offset],
        )
        return {"veiculo": veiculo, "total_dias": total, "limite": limite,
                "offset": offset, "itens": cursor.fetchall()}
