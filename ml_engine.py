import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# Minimum records needed for meaningful anomaly detection
_MIN_RECORDS = 10

# ---------------------------------------------------------------------------
# Aggregate ML — IsolationForest
# ---------------------------------------------------------------------------

def run_anomaly_detection(
    df: pd.DataFrame,
    contamination: float = 0.05,
    audit_type: str = "cards",
) -> pd.DataFrame:
    """
    Detect anomalies using IsolationForest on engineered features.

    Features:
      1. value_float          — raw transaction amount
      2. vendor_frequency     — how often this vendor appears (high freq + variance = suspicious)
      3. value_vs_vendor_mean — ratio of this transaction to the vendor's average
                                (a sudden spike flags as anomaly)

    Returns the original DataFrame enriched with:
      - Anomaly_Score  (float, higher = more suspicious)
      - Is_Anomaly     (bool)
    """
    df = df.copy()

    # Fallback when there is not enough data to train the model
    if df.empty or len(df) < _MIN_RECORDS:
        df["Anomaly_Score"] = 0.0
        df["Is_Anomaly"] = False
        return df

    vendor_col = "establishment_name" if audit_type == "cards" else "favored_name"

    # --- Feature 1: raw value ---
    df["value_float"] = pd.to_numeric(df["value"], errors="coerce").fillna(0.0)

    # --- Feature 2: vendor frequency encoding ---
    freq_map = df[vendor_col].value_counts().to_dict()
    df["vendor_frequency"] = df[vendor_col].map(freq_map).fillna(1).astype(float)

    # --- Feature 3: value vs vendor mean ratio ---
    vendor_mean = df.groupby(vendor_col)["value_float"].transform("mean")
    # Add epsilon to avoid division by zero for vendors with mean ≈ 0
    df["value_vs_vendor_mean"] = df["value_float"] / (vendor_mean + 1e-9)

    feature_cols = ["value_float", "vendor_frequency", "value_vs_vendor_mean"]
    X = df[feature_cols].values

    # Replace any residual NaN/Inf introduced by edge cases
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    # --- Preprocessing ---
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # --- Model ---
    model = IsolationForest(
        contamination=contamination,
        n_estimators=150,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_scaled)

    # decision_function: lower (more negative) → more anomalous
    # We invert the sign so higher score = more suspicious (more intuitive for the UI)
    raw_scores = model.decision_function(X_scaled)
    predictions = model.predict(X_scaled)  # -1 = anomaly, 1 = normal

    df["Anomaly_Score"] = -raw_scores
    df["Is_Anomaly"] = predictions == -1

    # Drop helper features — keep the dataframe clean for the UI
    df.drop(columns=["value_float", "vendor_frequency", "value_vs_vendor_mean"], inplace=True)

    return df


# ---------------------------------------------------------------------------
# Item-level auditor — deterministic rule-based
# ---------------------------------------------------------------------------

# Blacklist: categories that are never acceptable on government cards/expenses
_BLACKLISTED_CATEGORIES: set = {
    "Bebida Alcoólica",
    "Artigos de Luxo",
    "Entretenimento Pessoal",
    "Itens Pessoais",
    "Tabagismo",
    "Jogos de Azar",
}

# Flag item if unit_price exceeds market_avg_price by more than this fraction (1.0 = 100%)
_OVERPRICING_THRESHOLD = 1.0


def audit_invoice_items(items_df: pd.DataFrame) -> list:
    """
    Run deterministic rule-based audit on a set of invoice item rows.

    Rules applied per item:
      1. Overpricing — unit_price > market_avg_price × (1 + threshold)
      2. Scope violation — category belongs to the blacklist

    Returns a list of finding dicts, one per triggered rule per item.
    Each dict has keys: type, severity, item_name, message, and rule-specific extras.
    """
    findings = []

    for _, item in items_df.iterrows():
        item_name = str(item.get("item_name") or "Item desconhecido")
        unit_price = float(item.get("unit_price") or 0.0)
        market_avg = float(item.get("market_avg_price") or 0.0)
        category = str(item.get("category") or "")

        # --- Rule 1: Overpricing ---
        if market_avg > 0 and unit_price > market_avg * (1.0 + _OVERPRICING_THRESHOLD):
            markup_pct = ((unit_price - market_avg) / market_avg) * 100.0
            findings.append(
                {
                    "type": "SUPERFATURAMENTO",
                    "severity": "CRITICAL",
                    "item_name": item_name,
                    "overpricing_pct": markup_pct,
                    "unit_price": unit_price,
                    "market_avg": market_avg,
                    "message": (
                        f"Superfaturamento de {markup_pct:,.0f}% "
                        f"detectado no item '{item_name}'!"
                    ),
                }
            )

        # --- Rule 2: Scope violation ---
        if category in _BLACKLISTED_CATEGORIES:
            findings.append(
                {
                    "type": "FORA_DO_ESCOPO",
                    "severity": "HIGH",
                    "item_name": item_name,
                    "category": category,
                    "message": (
                        f"Item '{item_name}' fora do escopo de compras "
                        f"da Administração Pública!"
                    ),
                }
            )

    return findings
