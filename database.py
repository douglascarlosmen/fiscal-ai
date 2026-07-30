# ══════════════════════════════════════════════════════════════════════════════
# database.py — Camada de Persistência de Dados
# ══════════════════════════════════════════════════════════════════════════════
#
# Este arquivo é responsável por tudo que envolve o banco de dados local.
# Pense nele como o "arquivista" do sistema: ele cria as gavetas (tabelas),
# guarda os documentos (registros) e os recupera quando necessário.
#
# Usamos o SQLite, um banco de dados que funciona como um único arquivo no
# computador — sem precisar instalar nada extra, sem servidor, sem internet.
# Perfeito para um projeto que roda localmente na máquina do usuário.
# ══════════════════════════════════════════════════════════════════════════════

import sqlite3  # Biblioteca nativa do Python para banco de dados SQLite

import pandas as pd  # Biblioteca para manipulação de tabelas de dados (DataFrames)

# Nome do arquivo de banco de dados que será criado na pasta do projeto.
# Se o arquivo não existir, o SQLite o cria automaticamente na primeira execução.
DB_PATH = "fiscal_ai.db"


# ──────────────────────────────────────────────────────────────────────────────
# Conexão com o banco de dados
# ──────────────────────────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    # Abre (ou cria) o arquivo de banco de dados e retorna uma "conexão" —
    # pense nisso como abrir uma pasta de arquivos para poder ler e escrever nela.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    # check_same_thread=False permite que o Streamlit (que usa múltiplas threads)
    # acesse o banco sem travar. É seguro porque controlamos o acesso manualmente.

    # Row factory faz com que cada linha retornada do banco se comporte como
    # um dicionário, permitindo acessar colunas pelo nome: row["value"]
    conn.row_factory = sqlite3.Row
    return conn


# ──────────────────────────────────────────────────────────────────────────────
# Criação das tabelas (estrutura do banco)
# ──────────────────────────────────────────────────────────────────────────────

def init_db() -> None:
    # Esta função é chamada toda vez que o sistema inicia.
    # O "IF NOT EXISTS" garante que as tabelas só são criadas na primeira vez —
    # nas próximas execuções, elas já existem e não são sobrescritas.
    with get_connection() as conn:
        conn.executescript("""

            -- TABELA 1: Gastos com Cartão Corporativo (CPGF)
            -- Armazena cada transação realizada com o Cartão de Pagamento
            -- do Governo Federal. Cada linha é uma compra em um estabelecimento.
            CREATE TABLE IF NOT EXISTS corporate_cards (
                id              INTEGER PRIMARY KEY,  -- Identificador único da transação (vem da API)
                date            TEXT,                 -- Data em que a compra foi realizada
                month_year      TEXT,                 -- Mês/ano do extrato (ex: "01/2026")
                value           REAL,                 -- Valor da compra em reais (número decimal)
                establishment_name TEXT,              -- Nome do estabelecimento onde foi comprado
                establishment_doc  TEXT,              -- CNPJ ou CPF do estabelecimento
                unit_name       TEXT,                 -- Órgão público responsável pelo cartão
                cardholder_name TEXT                  -- Nome do servidor que usou o cartão
            );

            -- TABELA 2: Despesas do Poder Executivo
            -- Armazena ordens de pagamento oficiais emitidas pelo governo federal.
            -- São documentos contábeis (Ordens Bancárias) que registram transferências de dinheiro.
            CREATE TABLE IF NOT EXISTS executive_expenses (
                document_id TEXT PRIMARY KEY,  -- Código único do documento (ex: "2024OB000049")
                date        TEXT,              -- Data de emissão do documento
                observation TEXT,             -- Descrição do que foi pago
                value       REAL,             -- Valor transferido em reais
                favored_name TEXT,            -- Nome de quem recebeu o pagamento
                favored_doc  TEXT,            -- CNPJ/CPF de quem recebeu
                category    TEXT,             -- Categoria orçamentária da despesa
                unit_name   TEXT              -- Unidade gestora que emitiu o pagamento
            );

            -- TABELA 3: Itens da Nota Fiscal (Raio-X)
            -- Armazena o detalhamento interno de uma transação — os itens
            -- individuais que compõem aquela compra. É aqui que detectamos
            -- superfaturamento item a item.
            -- Essa tabela não vem da API: é alimentada manualmente (seeder abaixo).
            CREATE TABLE IF NOT EXISTS invoice_items (
                id               INTEGER PRIMARY KEY AUTOINCREMENT, -- Gerado automaticamente pelo banco
                transaction_ref  TEXT NOT NULL,   -- Referência à transação-mãe (cartão ou despesa)
                item_name        TEXT,            -- Nome do item comprado
                quantity         INTEGER,         -- Quantidade comprada
                unit_price       REAL,            -- Preço unitário pago
                total_price      REAL,            -- Valor total (quantidade × preço unitário)
                market_avg_price REAL,            -- Preço médio de mercado para comparação
                category         TEXT             -- Categoria do item (ex: "Material de Escritório")
            );
        """)


# ══════════════════════════════════════════════════════════════════════════════
# SEEDER — Dados de Demonstração ("Data Theater")
# ══════════════════════════════════════════════════════════════════════════════
#
# Para o vídeo de demonstração, precisamos mostrar o Raio-X da Nota Fiscal
# funcionando com dados reais de itens. Como a API pública não fornece esse
# nível de detalhe, criamos três cenários fictícios que ilustram situações
# reais de irregularidades em compras públicas.
#
# Os IDs das transações (transaction_ref) correspondem a transações reais
# que aparecem na API — os itens foram criados para fins didáticos.
# ══════════════════════════════════════════════════════════════════════════════

_MOCK_ITEMS = [
    # ── Cenário A: Compra Normal e Justificada ─────────────────────────────
    # Uma compra de papel sulfite para escritório, com preço justo.
    # O preço pago (R$ 21,11) está levemente acima da média de mercado (R$ 20,00)
    # — variação normal, dentro da margem aceitável.
    {
        "transaction_ref": "476259837",          # ID do cartão corporativo na API
        "item_name": "Resma de Papel Sulfite A4",
        "quantity": 20,                          # 20 resmas compradas
        "unit_price": 21.11,                     # Preço unitário pago
        "total_price": 422.20,                   # 20 × R$ 21,11 = R$ 422,20
        "market_avg_price": 20.00,               # Preço médio encontrado no mercado
        "category": "Material de Escritório",
    },

    # ── Cenário B: Superfaturamento Absurdo ────────────────────────────────
    # Uma vassoura comprada por R$ 19.046,11 — quando o preço de mercado é R$ 30,00.
    # Isso representa um superfaturamento de mais de 63.000%.
    # Exatamente o tipo de irregularidade que o Fiscal.AI foi feito para detectar.
    {
        "transaction_ref": "2026DF801373",       # ID do documento de despesa na API
        "item_name": "Vassoura de Pelo Sintético",
        "quantity": 2,                           # 2 vassouras compradas
        "unit_price": 19_046.11,                 # Preço absurdo pago por unidade
        "total_price": 38_092.22,                # 2 × R$ 19.046,11 = R$ 38.092,22
        "market_avg_price": 30.00,               # Preço real de mercado de uma vassoura
        "category": "Material de Limpeza",
    },

    # ── Cenário C: Item Fora do Escopo da Administração Pública ───────────
    # Uma garrafa de vinho importado comprada com cartão corporativo do governo.
    # O preço pode estar dentro do mercado, mas o item em si é proibido —
    # bebidas alcoólicas não fazem parte das compras permitidas pelo governo.
    {
        "transaction_ref": "476260285",          # ID do cartão corporativo na API
        "item_name": "Garrafa de Vinho Tinto Importado",
        "quantity": 1,
        "unit_price": 1_257.00,
        "total_price": 1_257.00,
        "market_avg_price": 1_257.00,            # Preço compatível com o mercado...
        "category": "Bebida Alcoólica",          # ...mas a CATEGORIA é proibida!
    },
]


def seed_invoice_items() -> None:
    # Esta função "planta" os dados de demonstração no banco.
    # É chamada toda vez que o sistema inicia, mas o "if not already_exists"
    # garante que cada item só seja inserido uma única vez — nunca duplicado.
    # Isso se chama "idempotência": executar várias vezes produz o mesmo resultado.
    with get_connection() as conn:
        for item in _MOCK_ITEMS:
            # Verifica se este item já existe no banco antes de tentar inserir
            already_exists = conn.execute(
                "SELECT 1 FROM invoice_items WHERE transaction_ref = ? AND item_name = ?",
                (item["transaction_ref"], item["item_name"]),
            ).fetchone()

            if not already_exists:
                # Insere o item apenas se ainda não estiver cadastrado
                conn.execute(
                    """
                    INSERT INTO invoice_items
                        (transaction_ref, item_name, quantity, unit_price,
                         total_price, market_avg_price, category)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["transaction_ref"],
                        item["item_name"],
                        item["quantity"],
                        item["unit_price"],
                        item["total_price"],
                        item["market_avg_price"],
                        item["category"],
                    ),
                )
        conn.commit()  # Confirma e salva todas as inserções no arquivo do banco


# ──────────────────────────────────────────────────────────────────────────────
# Funções de Consulta aos Itens de Nota Fiscal
# ──────────────────────────────────────────────────────────────────────────────

def get_invoice_items(transaction_ref: str) -> pd.DataFrame:
    # Busca todos os itens de nota fiscal de uma transação específica.
    # Recebe o ID da transação e retorna uma tabela (DataFrame) com os itens.
    # Se a transação não tiver itens cadastrados, retorna uma tabela vazia.
    with get_connection() as conn:
        return pd.read_sql_query(
            "SELECT * FROM invoice_items WHERE transaction_ref = ?",
            conn,
            params=(transaction_ref,),
        )


def get_all_refs_with_items() -> set:
    # Retorna o conjunto de todos os IDs de transações que possuem
    # itens de nota fiscal cadastrados. Usado pelo dashboard para exibir
    # o ícone "📑 Raio-X" apenas nas linhas auditáveis.
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT transaction_ref FROM invoice_items"
        ).fetchall()
        return {row[0] for row in rows}  # Converte para um conjunto (set) de strings
