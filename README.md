# Painel de consumo de frota

Aplicação para transformar relatórios textuais de abastecimento em PDF em histórico de consumo e indicadores visuais. O código reúne extração e validação em Python, persistência MySQL, API local e interface web.

**Esta cópia é uma demonstração de portfólio. Todos os dados da pasta `demo` são fictícios. Não contém relatórios, indicadores ou credenciais de uma operação real.**

## Demonstração sem banco

Com Python instalado, abra um terminal na pasta do projeto:

```shell
python -m http.server 8080 --directory demo --bind 127.0.0.1
```

Abra http://127.0.0.1:8080/ . Os prefixos DEMO-A, DEMO-B e DEMO-C representam queda, melhora e estabilidade. A demonstração não importa PDFs nem exige instalação de bibliotecas. Não abra o HTML diretamente como arquivo, pois a interface utiliza fetch para ler o JSON.

## Funcionalidades

- Extrair registros de um layout textual específico de relatório de abastecimento.
- Padronizar números brasileiros e preservar identificadores como texto.
- Conferir totais e consistência entre quilômetros, litros e km/l.
- Identificar reenvios pelo SHA-256 e gravar em uma transação.
- Consultar indicadores por período, prefixo e situação.
- Visualizar histórico com valores em cada ponto dos gráficos SVG.
- Exportar dados agregados para hospedagem estática.

## Arquitetura

```text
PDF -> Python: leitura/validacao -> MySQL
                                   |
                   +---------------+----------------+
                   |                                |
              FastAPI local                   Exportacao JSON
                   |                                |
          Painel e importacao               Painel estatico
```

O backend local usa FastAPI e Uvicorn. A publicação estática lê uma exportação; o envio do JSON é manual. A página consulta atualizações a cada minuto quando está visível, sem acessar o banco diretamente.

## Tecnologias

| Camada | Tecnologias |
|---|---|
| Extração e regras | Python, pdfplumber, Decimal, expressões regulares |
| Persistência | MySQL/InnoDB, SQL, PyMySQL |
| API local | FastAPI, Uvicorn, Starlette |
| Frontend | HTML5, CSS3, JavaScript e SVG |
| Intercâmbio | JSON, CSV |
| Verificações desta cópia | unittest e node:assert |

Não utiliza React, pandas, SQLAlchemy, OCR ou aprendizado de máquina.

## Executar com MySQL

Requisitos: Python 3.10+, MySQL 8+ e banco de desenvolvimento separado. Execute `sql/schema.sql` no Workbench para criar as três tabelas vazias.

No Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:FROTA_DB_HOST = "127.0.0.1"
$env:FROTA_DB_PORT = "3306"
$env:FROTA_DB_USER = "SEU_USUARIO_LOCAL"
$env:FROTA_DB_NAME = "gestao_frota"
.\.venv\Scripts\python.exe iniciar_backend.py
```

Informe a senha quando solicitada e abra http://127.0.0.1:8000/ . A senha não é incluída no frontend. Mantenha o terminal aberto. A API não tem autenticação própria e deve permanecer local.

Para importar por terminal:

```powershell
.\.venv\Scripts\python.exe importar_mysql.py "caminho/relatorio.pdf" --usuario SEU_USUARIO_LOCAL
```

Não há PDF real de exemplo neste repositório. O leitor é específico para um relatório textual com cabeçalho de bomba, linhas com data/hora/prefixo/litros/km/km-l e total final por bomba. PDFs de outros layouts exigem adaptação.

## Publicação por JSON

```powershell
.\.venv\Scripts\python.exe preparar_frontend.py
.\.venv\Scripts\python.exe exportar_site.py --usuario SEU_USUARIO_LOCAL
```

O primeiro comando gera os arquivos de frontend em `publicar-frontend`. O segundo exporta indicadores diários para `publicar-frontend/dados/frota.json`. Envie esses arquivos somente a um ambiente autorizado. O JSON operacional não deve ser versionado; ele revela prefixos, datas e consumo, mesmo sem credenciais.

## Regras dos indicadores

```text
Rendimento = soma dos quilômetros / soma dos litros
Variação (%) = (rendimento atual / rendimento anterior - 1) × 100
```

Comparação entre os dois últimos dias registrados dentro do filtro: queda abaixo de -1%, melhora acima de +1% e estabilidade entre os limites. Sem referência válida, não há comparação. A queda não identifica defeito nem responsabilidade de motorista. A faixa de 1% é uma regra inicial de apresentação.

## Estrutura

```text
demo/                    Painel com dados inteiramente sintéticos
web/                     Interface para operação local
sql/schema.sql           Estrutura vazia do banco
extrair_relatorio.py      Extração e validação
importar_mysql.py         Gravação transacional
consultas.py              Consultas e classificação
backend.py                API e upload local
iniciar_backend.py        Inicialização do servidor
exportar_site.py          Exportação para publicação
preparar_frontend.py      Preparação dos arquivos estáticos
test_portfolio.py         Testes com entradas sintéticas
test_demo.cjs             Verificações da demonstração
```

## Verificação

```powershell
.\.venv\Scripts\python.exe -m unittest -v
node test_demo.cjs
```

Os testes desta cópia não precisam de MySQL ativo. O Node.js é necessário somente para o teste JavaScript, não para executar o painel.

## Limites e evolução

Sem OCR, autenticação integrada, backup automático, diagnóstico causal ou alertas de queda persistente. A publicação depende de exportação e envio. Para uso em rede, implementar controle de acesso, operação do serviço e procedimentos de recuperação.

## Direitos e publicação

A escolha da licença e a autorização para compartilhar o código devem ser confirmadas pelo responsável antes da publicação pública. Não há licença de código aberto concedida por este documento. A demonstração não identifica a empresa de origem nem aponta para o ambiente operacional.
