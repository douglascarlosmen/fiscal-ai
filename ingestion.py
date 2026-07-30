# ══════════════════════════════════════════════════════════════════════════════
# ingestion.py — Ingestão de Dados da API Pública
# ══════════════════════════════════════════════════════════════════════════════
#
# Este arquivo é o "mensageiro" do sistema — ele sai para a internet,
# conversa com a API oficial do Portal da Transparência do Governo Federal
# e traz os dados de volta para o banco de dados local.
#
# O Portal da Transparência (portaldatransparencia.gov.br) é operado pela
# Controladoria-Geral da União (CGU) e disponibiliza GRATUITAMENTE todos
# os gastos do governo federal em tempo real via API pública.
#
# Este arquivo cuida de:
#   1. Autenticar na API com a chave do usuário (lida do arquivo .env)
#   2. Paginar os resultados (a API retorna até 500 itens por página)
#   3. Converter valores monetários do formato brasileiro (R$ 1.252,55)
#      para número decimal (1252.55) que o Python consegue calcular
#   4. Salvar os dados no banco SQLite local (via database.py)
#   5. Carregar dados do banco para o dashboard analisar
# ══════════════════════════════════════════════════════════════════════════════

import calendar  # Biblioteca para calcular quantos dias tem cada mês
import os        # Biblioteca para ler variáveis de ambiente do sistema

import pandas as pd  # Biblioteca para manipulação de tabelas de dados
import requests      # Biblioteca para fazer requisições HTTP (chamar APIs)
from dotenv import load_dotenv  # Carrega variáveis do arquivo .env

# Importa funções do nosso arquivo de banco de dados
from database import get_connection, init_db

# Carrega o arquivo .env — é aqui que a chave da API é lida.
# Sem essa linha, os segredos do .env não estariam disponíveis para o os.getenv().
load_dotenv()

# Endereço base da API do Portal da Transparência.
# Todos os endpoints (URLs de cada funcionalidade) partem deste endereço.
API_BASE = "https://api.portaldatransparencia.gov.br/api-de-dados"

# Limite máximo de páginas que buscamos por requisição.
# Segurança: sem esse limite, um loop poderia rodar infinitamente em casos de erro.
_MAX_PAGES = 50

# Quantidade máxima de registros por página (limite da API).
# Quando a API retorna menos de 500 itens, sabemos que é a última página.
_PAGE_SIZE = 500


# ──────────────────────────────────────────────────────────────────────────────
# Funções Auxiliares (Helpers)
# ──────────────────────────────────────────────────────────────────────────────

def _get_headers() -> dict:
    # Lê a chave de API do arquivo .env e monta o cabeçalho HTTP que a API exige.
    # A API do Portal da Transparência requer que toda requisição inclua
    # o campo "chave-api-dados" no cabeçalho HTTP — sem ele, a requisição é recusada.
    key = os.getenv("CHAVE_API_DADOS", "").strip()

    if not key:
        # Se a chave não foi configurada, interrompe tudo com uma mensagem clara.
        # Isso evita erros enigmáticos de "401 Unauthorized" que confundem o usuário.
        raise ValueError(
            "Chave de API não encontrada.\n"
            "Crie um arquivo .env com: CHAVE_API_DADOS=sua_chave_aqui"
        )
    return {"accept": "application/json", "chave-api-dados": key}


def parse_brl_value(raw: str) -> float:
    # A API retorna valores monetários no formato BRASILEIRO: "1.252,55"
    # O Python não entende esse formato — ele usa ponto como decimal (1252.55)
    # Esta função converte de um formato para o outro.
    #
    # Exemplo passo a passo:
    #   Entrada:   "1.252,55"
    #   Passo 1:   Remove o ponto separador de milhar → "1252,55"
    #   Passo 2:   Troca a vírgula decimal por ponto  → "1252.55"
    #   Passo 3:   Converte para número decimal       → 1252.55
    #
    # Também lida com valores negativos (reembolsos, estornos).
    if not raw:
        return 0.0
    s = str(raw).strip()
    negative = s.startswith("-")  # Detecta se é negativo antes de remover o sinal
    s = s.lstrip("-").strip()
    s = s.replace(".", "").replace(",", ".")  # Remove pontos de milhar, converte vírgula
    try:
        result = float(s)
        return -result if negative else result  # Reaplicar o sinal negativo, se havia
    except (ValueError, TypeError):
        return 0.0  # Se ainda assim não conseguir converter, retorna zero


def _fetch_all_pages(endpoint: str, params: dict) -> list:
    # A API retorna os dados em "páginas" de até 500 registros cada.
    # Para um mês inteiro de gastos, podem existir várias páginas.
    # Esta função vai buscando página por página até acabar os dados.
    #
    # Analogia: é como folhear um livro de registros, página por página,
    # copiando todas as linhas para uma lista, até chegar à última página.
    headers = _get_headers()
    all_records: list = []  # Lista que vai acumulando todos os registros

    for page in range(1, _MAX_PAGES + 1):
        params["pagina"] = page  # Diz para a API qual página queremos

        try:
            resp = requests.get(
                f"{API_BASE}/{endpoint}",  # URL completa do endpoint
                headers=headers,           # Cabeçalho com a chave de API
                params=params,             # Filtros da busca (mês, ano, etc.)
                timeout=30,               # Aguarda no máximo 30 segundos por resposta
            )
            resp.raise_for_status()  # Lança exceção se a API retornar erro (4xx, 5xx)
            data = resp.json()       # Converte a resposta JSON para lista Python
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                break  # Status 404 = não há mais páginas — saímos do loop normalmente
            raise ConnectionError(f"Erro HTTP ao acessar a API: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            raise ConnectionError(f"Falha ao conectar à API: {exc}") from exc

        # Se a API retornou uma lista vazia, chegamos ao final dos dados
        if not isinstance(data, list) or len(data) == 0:
            break

        all_records.extend(data)  # Adiciona os registros desta página à lista geral

        if len(data) < _PAGE_SIZE:
            break  # Página incompleta = última página, não precisa buscar mais

    return all_records  # Retorna todos os registros de todas as páginas combinados


# ──────────────────────────────────────────────────────────────────────────────
# Busca e Transformação dos Dados da API
# ──────────────────────────────────────────────────────────────────────────────

def fetch_corporate_cards(month: int, year: int) -> pd.DataFrame:
    # Busca todos os gastos do Cartão de Pagamento do Governo Federal (CPGF)
    # para um determinado mês e ano.
    #
    # O CPGF é o "cartão corporativo" dos servidores públicos federais,
    # usado para pequenas despesas do dia a dia (combustível, hospedagem,
    # material de escritório, etc.).
    month_str = f"{month:02d}/{year}"  # Formata como "01/2026", "12/2025" etc.
    params = {
        "mesExtratoInicio": month_str,  # Início do período do extrato
        "mesExtratoFim": month_str,     # Fim do período (mesmo mês = apenas 1 mês)
    }

    raw = _fetch_all_pages("cartoes", params)  # Busca todas as páginas do endpoint "cartoes"
    if not raw:
        return pd.DataFrame()  # Se não encontrou nada, retorna tabela vazia

    records = []
    for item in raw:
        # Cada registro da API é um dicionário aninhado — precisamos "achatar" os dados
        # acessando sub-objetos como "estabelecimento", "portador", "unidadeGestora"
        estab = item.get("estabelecimento") or {}  # Sub-objeto do estabelecimento

        # Prefere o CNPJ (empresa); se não tiver, usa o CPF (pessoa física)
        doc = estab.get("cnpjFormatado") or estab.get("cpfFormatado") or ""

        records.append(
            {
                "id": item.get("id"),                                         # ID único da transação
                "date": item.get("dataTransacao", ""),                        # Data da compra
                "month_year": item.get("mesExtrato", ""),                     # Mês/ano do extrato
                "value": parse_brl_value(item.get("valorTransacao", "0")),    # Valor convertido para float
                "establishment_name": estab.get("nome", ""),                  # Nome do estabelecimento
                "establishment_doc": doc,                                      # CNPJ ou CPF
                "unit_name": (item.get("unidadeGestora") or {}).get("nome", ""),  # Órgão responsável
                "cardholder_name": (item.get("portador") or {}).get("nome", ""), # Portador do cartão
            }
        )

    return pd.DataFrame(records)  # Converte a lista de dicionários para uma tabela


def fetch_executive_expenses(month: int, year: int) -> pd.DataFrame:
    # Busca os documentos de pagamento (Ordens Bancárias) emitidos pelo Poder Executivo.
    #
    # As Despesas do Executivo são ordens de pagamento formais (OBs) —
    # documentos contábeis que registram transferências de recursos federais
    # para fornecedores, beneficiários, estados, municípios, etc.
    #
    # Parâmetros fixos desta consulta:
    #   fase=3            → Fase de Pagamento (dinheiro realmente saiu)
    #   unidadeGestora=110001 → Ministério da Fazenda (UG central do Tesouro Nacional)
    last_day = calendar.monthrange(year, month)[1]  # Calcula quantos dias tem o mês
    params = {
        "dataEmissao": f"01/{month:02d}/{year}",  # Data de emissão do documento (início do mês)
        "fase": 3,             # Fase 3 = Pagamento efetivo (dinheiro saiu do caixa)
        "unidadeGestora": 110001  # Código da Unidade Gestora consultada
    }

    raw = _fetch_all_pages("despesas/documentos", params)  # Busca o endpoint de despesas
    if not raw:
        return pd.DataFrame()

    records = []
    for item in raw:
        records.append(
            {
                "document_id": item.get("documentoResumido", ""),         # Código do documento (ex: "2026OB000049")
                "date": item.get("data", ""),                              # Data de emissão
                "observation": item.get("observacao", ""),                 # Descrição da despesa
                "value": parse_brl_value(item.get("valor", "0")),         # Valor convertido para float
                "favored_name": item.get("nomeFavorecido", ""),           # Nome de quem recebeu
                "favored_doc": item.get("codigoFavorecido", ""),          # CNPJ/CPF do favorecido
                "category": item.get("categoria", ""),                     # Categoria orçamentária
                "unit_name": item.get("ug", ""),                          # Código da unidade gestora
            }
        )

    return pd.DataFrame(records)


# ──────────────────────────────────────────────────────────────────────────────
# Persistência no Banco de Dados SQLite
# ──────────────────────────────────────────────────────────────────────────────
#
# Após buscar os dados da API, os salvamos localmente.
# Isso serve para duas coisas:
#   1. Velocidade: na próxima abertura, os dados já estão no banco — sem nova chamada de API
#   2. Histórico: podemos comparar diferentes períodos sem depender da internet
#
# Usamos "INSERT OR REPLACE" (um "upsert"):
#   - Se o registro ainda não existe no banco → insere normalmente
#   - Se já existe (mesma chave primária) → substitui com os dados mais recentes
# Isso evita duplicatas sem complicar o código com verificações manuais.
# ──────────────────────────────────────────────────────────────────────────────

def save_corporate_cards(df: pd.DataFrame) -> int:
    # Salva todos os registros de cartão corporativo no banco de dados local.
    # Retorna quantos registros foram salvos com sucesso.
    if df.empty:
        return 0
    saved = 0
    with get_connection() as conn:
        for _, row in df.iterrows():
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO corporate_cards
                        (id, date, month_year, value, establishment_name,
                         establishment_doc, unit_name, cardholder_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["id"],
                        row["date"],
                        row["month_year"],
                        row["value"],
                        row["establishment_name"],
                        row["establishment_doc"],
                        row["unit_name"],
                        row["cardholder_name"],
                    ),
                )
                saved += 1
            except Exception:
                continue  # Se um registro falhar, ignora e tenta o próximo
        conn.commit()  # Confirma todas as inserções no arquivo do banco
    return saved


def save_executive_expenses(df: pd.DataFrame) -> int:
    # Salva todos os documentos de despesas do executivo no banco de dados local.
    # Retorna quantos registros foram salvos com sucesso.
    if df.empty:
        return 0
    saved = 0
    with get_connection() as conn:
        for _, row in df.iterrows():
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO executive_expenses
                        (document_id, date, observation, value, favored_name,
                         favored_doc, category, unit_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["document_id"],
                        row["date"],
                        row["observation"],
                        row["value"],
                        row["favored_name"],
                        row["favored_doc"],
                        row["category"],
                        row["unit_name"],
                    ),
                )
                saved += 1
            except Exception:
                continue
        conn.commit()
    return saved


# ──────────────────────────────────────────────────────────────────────────────
# Leitura do Banco (Load)
# ──────────────────────────────────────────────────────────────────────────────
#
# Após salvar, o sistema lê do banco — não dos dados brutos da API.
# Isso garante consistência e permite filtrar pelo período selecionado.
# ──────────────────────────────────────────────────────────────────────────────

def load_corporate_cards(month: int, year: int) -> pd.DataFrame:
    # Lê do banco apenas os cartões do mês/ano selecionado.
    # O filtro é feito diretamente em SQL, que é muito eficiente para isso.
    month_year = f"{month:02d}/{year}"  # Ex: "01/2026"
    with get_connection() as conn:
        return pd.read_sql_query(
            "SELECT * FROM corporate_cards WHERE month_year = ?",
            conn,
            params=(month_year,),
        )


def load_executive_expenses(month: int, year: int) -> pd.DataFrame:
    # Lê do banco todas as despesas e depois filtra pelo mês/ano em Python (via pandas).
    #
    # Por que não filtra direto no SQL (como no cartão)?
    # As datas de despesas estão armazenadas como texto "DD/MM/YYYY".
    # Filtrar texto de data no SQLite é mais complexo que fazer em pandas,
    # então carregamos tudo e filtramos com a biblioteca que é especialista nisso.
    last_day = calendar.monthrange(year, month)[1]  # Último dia do mês (28, 29, 30 ou 31)
    with get_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM executive_expenses", conn)

    if df.empty:
        return df

    # Converte a coluna de data (texto "DD/MM/YYYY") para tipo data do pandas
    # errors="coerce" → se a data for inválida, converte para NaT (Not a Time) sem travar
    df["_date_parsed"] = pd.to_datetime(df["date"], format="%d/%m/%Y", errors="coerce")

    # Define o intervalo de datas do mês selecionado (do dia 1 ao último dia)
    start = pd.Timestamp(year=year, month=month, day=1)
    end   = pd.Timestamp(year=year, month=month, day=last_day)

    # Filtra apenas as linhas cujas datas caem dentro do intervalo do mês
    df = df[(df["_date_parsed"] >= start) & (df["_date_parsed"] <= end)]

    # Remove a coluna auxiliar de data que criamos para o filtro
    # e reinicia os índices para que fiquem de 0 a N (sem saltos)
    return df.drop(columns=["_date_parsed"]).reset_index(drop=True)
