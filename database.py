import sqlite3

import pandas as pd

DB_PATH = "fiscal_ai.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS corporate_cards (
                id              INTEGER PRIMARY KEY,
                date            TEXT,
                month_year      TEXT,
                value           REAL,
                establishment_name TEXT,
                establishment_doc  TEXT,
                unit_name       TEXT,
                cardholder_name TEXT
            );

            CREATE TABLE IF NOT EXISTS executive_expenses (
                document_id TEXT PRIMARY KEY,
                date        TEXT,
                observation TEXT,
                value       REAL,
                favored_name TEXT,
                favored_doc  TEXT,
                category    TEXT,
                unit_name   TEXT
            );

            CREATE TABLE IF NOT EXISTS invoice_items (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_ref  TEXT NOT NULL,
                item_name        TEXT,
                quantity         INTEGER,
                unit_price       REAL,
                total_price      REAL,
                market_avg_price REAL,
                category         TEXT
            );
        """)


# ---------------------------------------------------------------------------
# Mock invoice-item data for the "Data Theater" demo scenarios
# ---------------------------------------------------------------------------

_MOCK_ITEMS = [
    # Scenario A — Normal: office supplies at fair market price
    {
        "transaction_ref": "476259837",
        "item_name": "Resma de Papel Sulfite A4",
        "quantity": 20,
        "unit_price": 21.11,
        "total_price": 422.20,
        "market_avg_price": 20.00,
        "category": "Material de Escritório",
    },
    # Scenario B — Critical: cleaning supply at 63,387% above market price
    {
        "transaction_ref": "2026DF801373",
        "item_name": "Vassoura de Pelo Sintético",
        "quantity": 2,
        "unit_price": 19_046.11,
        "total_price": 38_092.22,
        "market_avg_price": 30.00,
        "category": "Material de Limpeza",
    },
    # Scenario C — Scope violation: alcoholic beverage on government card
    {
        "transaction_ref": "476260285",
        "item_name": "Garrafa de Vinho Tinto Importado",
        "quantity": 1,
        "unit_price": 1_257.00,
        "total_price": 1_257.00,
        "market_avg_price": 1_257.00,
        "category": "Bebida Alcoólica",
    },
]


def seed_invoice_items() -> None:
    """Insert demo invoice items once; idempotent — safe to call on every startup."""
    with get_connection() as conn:
        for item in _MOCK_ITEMS:
            already_exists = conn.execute(
                "SELECT 1 FROM invoice_items WHERE transaction_ref = ? AND item_name = ?",
                (item["transaction_ref"], item["item_name"]),
            ).fetchone()
            if not already_exists:
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
        conn.commit()


# ---------------------------------------------------------------------------
# Invoice-item query helpers
# ---------------------------------------------------------------------------

def get_invoice_items(transaction_ref: str) -> pd.DataFrame:
    """Return all invoice items for the given transaction reference."""
    with get_connection() as conn:
        return pd.read_sql_query(
            "SELECT * FROM invoice_items WHERE transaction_ref = ?",
            conn,
            params=(transaction_ref,),
        )


def get_all_refs_with_items() -> set:
    """Return the set of transaction_ref values that have invoice items seeded."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT transaction_ref FROM invoice_items"
        ).fetchall()
        return {row[0] for row in rows}
