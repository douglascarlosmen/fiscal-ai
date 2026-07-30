import calendar
import os

import pandas as pd
import requests
from dotenv import load_dotenv

from database import get_connection, init_db

load_dotenv()

API_BASE = "https://api.portaldatransparencia.gov.br/api-de-dados"
# Maximum pages to fetch per request — safety cap to avoid runaway loops
_MAX_PAGES = 50
# Portal da Transparência returns up to 500 records per page
_PAGE_SIZE = 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_headers() -> dict:
    key = os.getenv("CHAVE_API_DADOS", "").strip()
    if not key:
        raise ValueError(
            "Chave de API não encontrada.\n"
            "Crie um arquivo .env com: CHAVE_API_DADOS=sua_chave_aqui"
        )
    return {"accept": "application/json", "chave-api-dados": key}


def parse_brl_value(raw: str) -> float:
    """Convert Brazilian currency string ('1.252,55') to float (1252.55)."""
    if not raw:
        return 0.0
    s = str(raw).strip()
    negative = s.startswith("-")
    s = s.lstrip("-").strip()
    # Remove thousand-separator dots, then swap decimal comma → dot
    s = s.replace(".", "").replace(",", ".")
    try:
        result = float(s)
        return -result if negative else result
    except (ValueError, TypeError):
        return 0.0


def _fetch_all_pages(endpoint: str, params: dict) -> list:
    """Paginate through the API until an empty page or the safety cap."""
    headers = _get_headers()
    all_records: list = []

    for page in range(1, _MAX_PAGES + 1):
        params["pagina"] = page
        try:
            resp = requests.get(
                f"{API_BASE}/{endpoint}",
                headers=headers,
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                break  # No more pages
            raise ConnectionError(f"Erro HTTP ao acessar a API: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            raise ConnectionError(f"Falha ao conectar à API: {exc}") from exc

        if not isinstance(data, list) or len(data) == 0:
            break

        all_records.extend(data)

        if len(data) < _PAGE_SIZE:
            break  # Last partial page

    return all_records


# ---------------------------------------------------------------------------
# Fetch & parse
# ---------------------------------------------------------------------------

def fetch_corporate_cards(month: int, year: int) -> pd.DataFrame:
    """Fetch corporate card (CPGF) transactions for the given month/year."""
    month_str = f"{month:02d}/{year}"
    params = {
        "mesExtratoInicio": month_str,
        "mesExtratoFim": month_str,
    }

    raw = _fetch_all_pages("cartoes", params)
    if not raw:
        return pd.DataFrame()

    records = []
    for item in raw:
        estab = item.get("estabelecimento") or {}
        # Prefer CNPJ; fall back to CPF (individual person)
        doc = estab.get("cnpjFormatado") or estab.get("cpfFormatado") or ""
        records.append(
            {
                "id": item.get("id"),
                "date": item.get("dataTransacao", ""),
                "month_year": item.get("mesExtrato", ""),
                "value": parse_brl_value(item.get("valorTransacao", "0")),
                "establishment_name": estab.get("nome", ""),
                "establishment_doc": doc,
                "unit_name": (item.get("unidadeGestora") or {}).get("nome", ""),
                "cardholder_name": (item.get("portador") or {}).get("nome", ""),
            }
        )

    return pd.DataFrame(records)


def fetch_executive_expenses(month: int, year: int) -> pd.DataFrame:
    """Fetch executive-branch payment documents for the given month/year."""
    last_day = calendar.monthrange(year, month)[1]
    params = {
        "dataEmissao": f"01/{month:02d}/{year}",        
        "fase": 3,  # Phase 3 = Pagamento (actual payment, not just commitment)
        "unidadeGestora": 110001
    }

    raw = _fetch_all_pages("despesas/documentos", params)
    if not raw:
        return pd.DataFrame()

    records = []
    for item in raw:
        records.append(
            {
                "document_id": item.get("documentoResumido", ""),
                "date": item.get("data", ""),
                "observation": item.get("observacao", ""),
                "value": parse_brl_value(item.get("valor", "0")),
                "favored_name": item.get("nomeFavorecido", ""),
                "favored_doc": item.get("codigoFavorecido", ""),
                "category": item.get("categoria", ""),
                "unit_name": item.get("ug", ""),
            }
        )

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Persist to SQLite
# ---------------------------------------------------------------------------

def save_corporate_cards(df: pd.DataFrame) -> int:
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
                continue
        conn.commit()
    return saved


def save_executive_expenses(df: pd.DataFrame) -> int:
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


# ---------------------------------------------------------------------------
# Load from SQLite (filtered by period)
# ---------------------------------------------------------------------------

def load_corporate_cards(month: int, year: int) -> pd.DataFrame:
    month_year = f"{month:02d}/{year}"
    with get_connection() as conn:
        return pd.read_sql_query(
            "SELECT * FROM corporate_cards WHERE month_year = ?",
            conn,
            params=(month_year,),
        )


def load_executive_expenses(month: int, year: int) -> pd.DataFrame:
    last_day = calendar.monthrange(year, month)[1]
    # Dates are stored as DD/MM/YYYY strings; compare lexicographically via SUBSTR
    # Easier: load all and filter in pandas (small dataset per month)
    with get_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM executive_expenses", conn)

    if df.empty:
        return df

    # Parse date for filtering
    df["_date_parsed"] = pd.to_datetime(df["date"], format="%d/%m/%Y", errors="coerce")
    start = pd.Timestamp(year=year, month=month, day=1)
    end = pd.Timestamp(year=year, month=month, day=last_day)
    df = df[(df["_date_parsed"] >= start) & (df["_date_parsed"] <= end)]
    return df.drop(columns=["_date_parsed"]).reset_index(drop=True)
