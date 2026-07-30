import calendar
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from database import (
    get_all_refs_with_items,
    get_invoice_items,
    init_db,
    seed_invoice_items,
)
from ingestion import (
    fetch_corporate_cards,
    fetch_executive_expenses,
    load_corporate_cards,
    load_executive_expenses,
    save_corporate_cards,
    save_executive_expenses,
)
from ml_engine import audit_invoice_items, run_anomaly_detection

# ---------------------------------------------------------------------------
# Page config — must be the very first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Fiscal.AI — O Auditor Implacável",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS — includes pulse animation for the WOW-effect critical alert
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
        /* ── Hero header ─────────────────────────────── */
        .fiscalai-hero { text-align:center; padding:1.2rem 0 0.4rem; }
        .fiscalai-hero h1 {
            font-size:2.6rem; font-weight:800; color:#0d3b66;
            margin:0; letter-spacing:-0.5px;
        }
        .fiscalai-hero p { font-size:1.05rem; color:#5a6a7a; margin:0.3rem 0 0; }

        /* ── Warning banner ──────────────────────────── */
        .alert-anomaly {
            background:linear-gradient(135deg,#fff3cd 0%,#ffe6a0 100%);
            border-left:5px solid #e6a817; border-radius:6px;
            padding:0.75rem 1rem; margin:0.5rem 0 1rem; font-size:0.95rem;
        }

        /* ── Section title ───────────────────────────── */
        .section-title {
            font-size:1.1rem; font-weight:700; color:#0d3b66;
            border-bottom:2px solid #e0e9f5;
            padding-bottom:0.3rem; margin-bottom:0.8rem;
        }

        /* ── Raio-X container ────────────────────────── */
        .raio-x-panel {
            border:2px solid #1e40af; border-radius:12px; padding:1.5rem;
            background:linear-gradient(180deg,#eff6ff 0%,#ffffff 100%);
            margin-top:1rem;
        }
        .raio-x-title {
            font-size:1.4rem; font-weight:800; color:#1e3a8a;
            letter-spacing:-0.3px; margin-bottom:0.4rem;
        }

        /* ── Pulse animation for critical alert ──────── */
        @keyframes fiscalai-pulse {
            0%   { box-shadow:0 0 0 0 rgba(220,38,38,0.85); transform:scale(1); }
            55%  { box-shadow:0 0 0 22px rgba(220,38,38,0); transform:scale(1.012); }
            100% { box-shadow:0 0 0 0 rgba(220,38,38,0); transform:scale(1); }
        }

        /* ── SUPERFATURAMENTO box (red, pulsing) ──────── */
        .anomaly-critical-box {
            background:linear-gradient(135deg,#dc2626 0%,#7f1d1d 100%);
            color:white; padding:1.8rem 2rem; border-radius:12px;
            text-align:center; font-size:1.45rem; font-weight:900;
            letter-spacing:-0.3px; text-shadow:0 2px 6px rgba(0,0,0,0.5);
            animation:fiscalai-pulse 1.8s ease-in-out infinite;
            margin:1.2rem 0; line-height:1.6;
        }
        .anomaly-critical-box span {
            font-size:0.85rem; font-weight:400; opacity:0.92;
        }

        /* ── FORA DO ESCOPO box (amber) ──────────────── */
        .anomaly-scope-box {
            background:linear-gradient(135deg,#d97706 0%,#78350f 100%);
            color:white; padding:1.4rem 2rem; border-radius:12px;
            text-align:center; font-size:1.2rem; font-weight:700;
            margin:1rem 0; line-height:1.6;
        }
        .anomaly-scope-box span { font-size:0.85rem; font-weight:400; opacity:0.92; }

        /* ── Normal / OK box (green) ─────────────────── */
        .normal-ok-box {
            background:linear-gradient(135deg,#16a34a 0%,#14532d 100%);
            color:white; padding:1.2rem 2rem; border-radius:12px;
            text-align:center; font-size:1.1rem; font-weight:600;
            margin:1rem 0;
        }

        /* ── Misc ────────────────────────────────────── */
        #MainMenu { visibility:hidden; }
        footer     { visibility:hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def fmt_brl(value) -> str:
    """Float → Brazilian currency string, e.g. 1252.55 → 'R$ 1.252,55'."""
    try:
        s = f"{float(value):,.2f}"
        return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "R$ 0,00"


def fmt_int(value) -> str:
    return f"{int(value):,}".replace(",", ".")


def _month_label(m: int) -> str:
    months_pt = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    ]
    return months_pt[m - 1]


def _safe_str(value, placeholder: str = "NÃO ENCONTRADO") -> str:
    """Return a clean string; replace NaN/None/empty with placeholder."""
    s = str(value).strip() if value is not None else ""
    return placeholder if s.lower() in ("nan", "none", "nat", "") else s


# ---------------------------------------------------------------------------
# Session-state bootstrap
# ---------------------------------------------------------------------------

def _init_state() -> None:
    defaults = {
        "df_raw": None,
        "df_result": None,
        "audit_key": None,
        "query_label": "",
        "last_contamination": 0.05,
        # Incremented on every new data fetch so the table widget resets its
        # row selection when the underlying dataset changes.
        "data_version": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ---------------------------------------------------------------------------
# Raio-X drill-down renderer (called from the main dashboard)
# ---------------------------------------------------------------------------

def _render_raio_x(transaction_ref: str, vendor_name: str) -> None:
    """Render the item-level audit panel for one transaction."""
    items_df = get_invoice_items(transaction_ref)
    if items_df.empty:
        return

    st.markdown("---")
    st.markdown(
        '<div class="raio-x-panel">',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="raio-x-title">🔎 Raio-X da Nota Fiscal</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        f"Transação: `{transaction_ref}`  |  Fornecedor: **{vendor_name[:80]}**"
    )

    # Build enriched items display
    display_rows = []
    for _, item in items_df.iterrows():
        unit_price = float(item.get("unit_price") or 0)
        market_avg = float(item.get("market_avg_price") or 0)

        if market_avg > 0:
            variacao_pct = ((unit_price - market_avg) / market_avg) * 100
            variacao_str = (
                f"+{variacao_pct:,.1f}%"
                if variacao_pct >= 0
                else f"{variacao_pct:,.1f}%"
            )
        else:
            variacao_str = "—"

        display_rows.append(
            {
                "Item": str(item.get("item_name", "")),
                "Qtd": int(item.get("quantity") or 0),
                "Preço Unit. (R$)": fmt_brl(unit_price),
                "Média Mercado (R$)": fmt_brl(market_avg),
                "Variação": variacao_str,
                "Total (R$)": fmt_brl(float(item.get("total_price") or 0)),
                "Categoria": str(item.get("category", "")),
            }
        )

    st.dataframe(
        pd.DataFrame(display_rows),
        use_container_width=True,
        hide_index=True,
    )

    # Run rule-based audit
    findings = audit_invoice_items(items_df)

    if not findings:
        st.markdown(
            '<div class="normal-ok-box">'
            "✅ Itens dentro do padrão de mercado. Nenhuma irregularidade detectada."
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        for f in findings:
            if f["type"] == "SUPERFATURAMENTO":
                st.markdown(
                    f'<div class="anomaly-critical-box">'
                    f"🚨 ANOMALIA: Superfaturamento de {f['overpricing_pct']:,.0f}% "
                    f"detectado no item '{f['item_name']}'!<br>"
                    f"<span>Preço pago: {fmt_brl(f['unit_price'])}"
                    f"&nbsp;&nbsp;|&nbsp;&nbsp;"
                    f"Média de mercado: {fmt_brl(f['market_avg'])}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            elif f["type"] == "FORA_DO_ESCOPO":
                st.markdown(
                    f'<div class="anomaly-scope-box">'
                    f"🚨 ANOMALIA: Item '{f['item_name']}' fora do escopo "
                    f"de compras da Administração Pública!<br>"
                    f"<span>Categoria flagrada: <strong>{f['category']}</strong></span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main() -> None:
    init_db()
    seed_invoice_items()  # idempotent — safe on every startup
    _init_state()

    # ── Hero header ────────────────────────────────────────────────────────
    st.markdown(
        """
        <div class="fiscalai-hero">
            <h1>🔍 Fiscal.AI — O Auditor Implacável</h1>
            <p>Detecção de Anomalias em Gastos Públicos Federais com Inteligência Artificial</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Sidebar ────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## ⚙️ Painel de Controle")
        st.markdown("---")

        st.markdown("### 📥 Ingestão de Dados")

        audit_label = st.selectbox(
            "Tipo de Auditoria",
            options=["Cartões Corporativos (CPGF)", "Despesas do Executivo"],
            help=(
                "**Cartões Corporativos**: gastos do Cartão de Pagamento do Governo Federal.\n\n"
                "**Despesas do Executivo**: ordens de pagamento emitidas pelo Poder Executivo."
            ),
        )
        audit_key = "cards" if "Cartões" in audit_label else "expenses"

        col_m, col_y = st.columns(2)
        with col_m:
            month = st.selectbox(
                "Mês",
                options=list(range(1, 13)),
                format_func=_month_label,
                index=0,
            )
        with col_y:
            year = st.selectbox(
                "Ano",
                options=list(range(2024, 2027)),
                index=2,
            )

        st.markdown("---")

        st.markdown("### 🤖 Configuração do Modelo de IA")

        contamination = st.slider(
            "Sensibilidade (Taxa de Contaminação)",
            min_value=0.01,
            max_value=0.30,
            value=st.session_state.last_contamination,
            step=0.01,
            help=(
                "Percentual estimado de anomalias no dataset.\n\n"
                "**Menor** → modelo mais conservador (menos alertas).\n"
                "**Maior** → modelo mais agressivo (mais alertas).\n\n"
                "Padrão recomendado: 5%."
            ),
        )

        st.markdown("---")

        fetch_btn = st.button(
            "🔎 Buscar e Analisar Dados",
            use_container_width=True,
            type="primary",
        )

        st.markdown("---")
        st.caption(
            "Fonte: [Portal da Transparência](https://portaldatransparencia.gov.br/) "
            "— CGU"
        )

    # ── Button handler: fetch → save → load → ML ──────────────────────────
    if fetch_btn:
        query_label = f"{_month_label(month)}/{year} — {audit_label}"

        with st.spinner(f"⏳ Buscando dados: {query_label}..."):
            try:
                if audit_key == "cards":
                    df_fetched = fetch_corporate_cards(month, year)
                    if not df_fetched.empty:
                        save_corporate_cards(df_fetched)
                    df_raw = load_corporate_cards(month, year)
                else:
                    df_fetched = fetch_executive_expenses(month, year)
                    if not df_fetched.empty:
                        save_executive_expenses(df_fetched)
                    df_raw = load_executive_expenses(month, year)

                if df_raw.empty:
                    st.warning(
                        "⚠️ **Nenhum registro encontrado** para o período selecionado.\n\n"
                        "Verifique se a chave de API é válida ou tente outro mês."
                    )
                    st.stop()

            except ValueError as exc:
                st.error(f"❌ **Erro de configuração:** {exc}")
                st.stop()
            except ConnectionError as exc:
                st.error(f"❌ **Erro de conexão com a API:** {exc}")
                st.stop()
            except Exception as exc:
                st.error(f"❌ **Erro inesperado:** {exc}")
                st.stop()

        with st.spinner("🤖 Executando modelo de Inteligência Artificial..."):
            df_result = run_anomaly_detection(df_raw, contamination, audit_key)

        st.session_state.df_raw = df_raw
        st.session_state.df_result = df_result
        st.session_state.audit_key = audit_key
        st.session_state.query_label = query_label
        st.session_state.last_contamination = contamination
        # Bump version so the table widget resets its row selection
        st.session_state.data_version = st.session_state.data_version + 1

        n_anom = int(df_result["Is_Anomaly"].sum())
        st.success(
            f"✅ **Análise concluída!** {fmt_int(len(df_result))} registros processados, "
            f"**{n_anom} anomalia(s)** detectada(s)."
        )

    # ── Re-run ML when contamination slider changes ────────────────────────
    elif (
        st.session_state.df_raw is not None
        and contamination != st.session_state.last_contamination
    ):
        with st.spinner("🔄 Recalibrando modelo com nova sensibilidade..."):
            st.session_state.df_result = run_anomaly_detection(
                st.session_state.df_raw,
                contamination,
                st.session_state.audit_key,
            )
        st.session_state.last_contamination = contamination

    # ── No data yet — onboarding screen ───────────────────────────────────
    df = st.session_state.df_result
    audit_key_cur = st.session_state.audit_key

    if df is None or df.empty:
        st.markdown("---")
        st.info(
            "👆 **Como começar:** use o painel lateral para selecionar o tipo de auditoria, "
            "o período e clique em **Buscar e Analisar Dados**."
        )
        with st.expander("ℹ️ Como o Fiscal.AI funciona?"):
            st.markdown(
                """
                ### Pipeline de Análise

                | Etapa | Descrição |
                |-------|-----------|
                | 📥 **Ingestão** | Conecta à API do Portal da Transparência (CGU) |
                | 🗄️ **Armazenamento** | Persiste em banco SQLite local |
                | 🧠 **Engenharia de Features** | Frequência de fornecedor + desvio da média histórica |
                | 🤖 **Isolation Forest** | Isola transações atípicas sem rótulos |
                | 🔎 **Drill-Down** | Abre o Raio-X da Nota Fiscal para transações auditáveis |
                | 📊 **Dashboard** | Gráficos interativos e tabela destacada |
                """
            )
        return

    # ── Dashboard ──────────────────────────────────────────────────────────
    vendor_col = "establishment_name" if audit_key_cur == "cards" else "favored_name"

    total_spent     = df["value"].sum()
    total_records   = len(df)
    total_anomalies = int(df["Is_Anomaly"].sum())
    anomaly_pct     = (total_anomalies / total_records * 100) if total_records > 0 else 0.0
    anomaly_value   = df.loc[df["Is_Anomaly"], "value"].sum()

    # Pre-load which refs have invoice items (used for table decoration + drill-down)
    refs_with_items: set = get_all_refs_with_items()

    # Determine which of those refs actually contain rule-based anomalies so we
    # can promote the "Status IA" of those transactions in the main table.
    refs_with_item_anomalies: set = set()
    for _ref in refs_with_items:
        _items = get_invoice_items(_ref)
        if not _items.empty and audit_invoice_items(_items):
            refs_with_item_anomalies.add(_ref)

    st.markdown(
        f"<div style='text-align:center;color:#5a6a7a;font-size:.9rem;margin-top:.2rem;'>"
        f"Período analisado: <strong>{st.session_state.query_label}</strong></div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # ── Top metrics ────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("💰 Total Gasto", fmt_brl(total_spent),
                  help="Soma de todos os valores no período")
    with c2:
        st.metric("📋 Registros Analisados", fmt_int(total_records),
                  help="Total de transações / documentos processados")
    with c3:
        st.metric(
            "🚨 Anomalias Detectadas",
            fmt_int(total_anomalies),
            delta=f"{anomaly_pct:.1f}% do total",
            delta_color="inverse",
            help="Transações classificadas como suspeitas pelo Isolation Forest",
        )
    with c4:
        st.metric("⚠️ Valor em Risco", fmt_brl(anomaly_value),
                  help="Soma dos valores das transações anômalas")

    if total_anomalies > 0:
        st.markdown(
            f'<div class="alert-anomaly">🚨 <strong>Atenção!</strong> O modelo de IA detectou '
            f"<strong>{total_anomalies} transação(ões) suspeita(s)</strong>, totalizando "
            f"<strong>{fmt_brl(anomaly_value)}</strong> em gastos potencialmente anômalos.</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Charts ─────────────────────────────────────────────────────────────
    col_scatter, col_bar = st.columns([3, 2])

    with col_scatter:
        st.markdown('<div class="section-title">📈 Transações ao Longo do Tempo</div>',
                    unsafe_allow_html=True)

        df_plot = df.copy()
        df_plot["date_ts"] = pd.to_datetime(
            df_plot["date"], format="%d/%m/%Y", errors="coerce"
        )
        df_plot = df_plot.dropna(subset=["date_ts"]).sort_values("date_ts")

        df_normal = df_plot[~df_plot["Is_Anomaly"]]
        df_anom   = df_plot[df_plot["Is_Anomaly"]]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_normal["date_ts"], y=df_normal["value"],
            mode="markers", name="✅ Normal",
            marker=dict(color="rgba(59,130,246,0.45)", size=8),
            customdata=df_normal[vendor_col].fillna("NÃO ENCONTRADO").str[:40],
            hovertemplate=(
                "<b>Data:</b> %{x|%d/%m/%Y}<br>"
                "<b>Valor:</b> R$ %{y:,.2f}<br>"
                "<b>Fornecedor:</b> %{customdata}<extra></extra>"
            ),
        ))
        if not df_anom.empty:
            fig.add_trace(go.Scatter(
                x=df_anom["date_ts"], y=df_anom["value"],
                mode="markers", name="🚨 Anomalia",
                marker=dict(color="rgba(220,38,38,0.9)", size=14,
                            line=dict(color="#7f1d1d", width=2)),
                customdata=df_anom[vendor_col].fillna("NÃO ENCONTRADO").str[:40],
                hovertemplate=(
                    "<b>🚨 ANOMALIA</b><br>"
                    "<b>Data:</b> %{x|%d/%m/%Y}<br>"
                    "<b>Valor:</b> R$ %{y:,.2f}<br>"
                    "<b>Fornecedor:</b> %{customdata}<extra></extra>"
                ),
            ))
        fig.update_layout(
            xaxis_title="Data", yaxis_title="Valor (R$)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            hovermode="closest", height=380,
            margin=dict(l=0, r=0, t=10, b=0),
        )
        fig.update_xaxes(gridcolor="rgba(180,180,180,0.2)", zeroline=False)
        fig.update_yaxes(gridcolor="rgba(180,180,180,0.2)", zeroline=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_bar:
        st.markdown('<div class="section-title">🏴‍☠️ Top 5 Fornecedores Anômalos</div>',
                    unsafe_allow_html=True)
        df_anom_all = df[df["Is_Anomaly"]]
        if df_anom_all.empty:
            st.info("Nenhuma anomalia detectada para exibir no ranking.")
        else:
            top5 = (
                df_anom_all.groupby(vendor_col)["value"]
                .sum().nlargest(5).reset_index()
            )
            top5.columns = ["Fornecedor", "Total"]
            top5["Label"] = top5["Fornecedor"].apply(
                lambda x: x[:28] + "…" if len(x) > 28 else x
            )
            fig_bar = go.Figure(go.Bar(
                x=top5["Total"], y=top5["Label"], orientation="h",
                marker=dict(color="rgba(220,38,38,0.75)",
                            line=dict(color="rgba(127,29,29,0.9)", width=1)),
                customdata=top5["Fornecedor"],
                hovertemplate="<b>%{customdata}</b><br>Total: R$ %{x:,.2f}<extra></extra>",
            ))
            fig_bar.update_layout(
                xaxis_title="Total (R$)", yaxis=dict(autorange="reversed"),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                height=380, margin=dict(l=0, r=0, t=10, b=0),
            )
            fig_bar.update_xaxes(gridcolor="rgba(180,180,180,0.2)", zeroline=False)
            fig_bar.update_yaxes(gridcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_bar, use_container_width=True)

    # ── Data table with row-selection drill-down ───────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-title">📋 Detalhamento dos Registros</div>',
                unsafe_allow_html=True)

    # Filter control
    col_f1, col_f2, _ = st.columns([2, 2, 6])
    with col_f1:
        view_filter = st.selectbox(
            "Exibir",
            ["Todos os Registros", "Apenas Anomalias 🚨", "Apenas Normais ✅"],
            label_visibility="collapsed",
        )

    df_view = df.copy()
    if "Anomalias" in view_filter:
        df_view = df_view[df_view["Is_Anomaly"]]
    elif "Normais" in view_filter:
        df_view = df_view[~df_view["Is_Anomaly"]]
    df_view = df_view.reset_index(drop=True)

    # Parallel lists used to map selected row index → transaction ref + vendor
    transaction_refs_order: list[str] = []
    vendor_labels_order:    list[str] = []

    rows = []
    for _, row in df_view.iterrows():
        is_anom = bool(row.get("Is_Anomaly", False))

        if audit_key_cur == "cards":
            raw_id = row.get("id")
            t_ref  = str(int(raw_id)) if pd.notna(raw_id) else ""
            vendor = _safe_str(row.get("establishment_name"))
        else:
            t_ref  = str(row.get("document_id", ""))
            vendor = _safe_str(row.get("favored_name"))

        transaction_refs_order.append(t_ref)
        vendor_labels_order.append(vendor)

        has_items = t_ref in refs_with_items
        # Promote to anomaly if the transaction's invoice items have rule-based findings
        is_anomaly_final = is_anom or (t_ref in refs_with_item_anomalies)

        base: dict = {
            "Status IA": "🚨 Anomalia" if is_anomaly_final else "✅ Normal",
            # Visual cue — tells user this row has invoice item data to inspect
            "📑": "📑 Raio-X" if has_items else "",
            "Data": row.get("date", ""),
            "Valor (R$)": fmt_brl(row.get("value", 0)),
            "Score IA": f"{row.get('Anomaly_Score', 0.0):.4f}",
        }
        if audit_key_cur == "cards":
            base["Estabelecimento"] = vendor
            base["CNPJ/CPF"]        = _safe_str(row.get("establishment_doc"), "")
            base["Unidade Gestora"] = _safe_str(row.get("unit_name"), "")
            base["Portador"]        = _safe_str(row.get("cardholder_name"), "")
        else:
            base["Documento"]       = t_ref
            base["Favorecido"]      = vendor  # already sanitised via _safe_str above
            base["CNPJ/CPF"]        = _safe_str(row.get("favored_doc"), "")
            base["Categoria"]       = _safe_str(row.get("category"), "")
            base["Unidade Gestora"] = _safe_str(row.get("unit_name"), "")
        rows.append(base)

    df_table = pd.DataFrame(rows)

    def _highlight(row: pd.Series):
        if "🚨" in str(row.get("Status IA", "")):
            return ["background-color:rgba(220,38,38,0.08)"] * len(row)
        return [""] * len(row)

    styled = df_table.style.apply(_highlight, axis=1)

    with col_f2:
        st.caption(f"{fmt_int(len(df_table))} registro(s) exibido(s)")

    # Render table with single-row selection enabled.
    # The key includes data_version so any new fetch resets the selection.
    table_key = f"main_table_v{st.session_state.data_version}"

    event = st.dataframe(
        styled,
        on_select="rerun",
        selection_mode="single-row",
        key=table_key,
        use_container_width=True,
        height=420,
        hide_index=True,
    )

    # Resolve selected row → transaction ref
    selected_ref: str | None = None
    selected_vendor: str = ""

    selection = getattr(event, "selection", None)
    if selection and selection.rows:
        sel_idx = selection.rows[0]
        if 0 <= sel_idx < len(transaction_refs_order):
            selected_ref    = transaction_refs_order[sel_idx]
            selected_vendor = vendor_labels_order[sel_idx]

    # Download
    csv_bytes = df_view.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="⬇️ Exportar Relatório Completo (CSV)",
        data=csv_bytes,
        file_name=f"fiscal_ai_{audit_key_cur}_{datetime.now():%Y%m%d_%H%M%S}.csv",
        mime="text/csv",
    )

    # ── Drill-down: Raio-X da Nota Fiscal ─────────────────────────────────
    if selected_ref is None:
        # No row selected — show a gentle hint if auditável rows exist in current view
        auditable_in_view = [r for r in transaction_refs_order if r in refs_with_items]
        if auditable_in_view:
            st.markdown("---")
            st.info(
                f"💡 **Dica:** {len(auditable_in_view)} transação(ões) marcada(s) com **📑 Raio-X** "
                "possuem itens de nota fiscal cadastrados. Clique em uma dessas linhas na tabela "
                "acima para abrir a análise detalhada."
            )
    elif selected_ref in refs_with_items:
        _render_raio_x(selected_ref, selected_vendor)
    else:
        st.markdown("---")
        st.info(
            f"ℹ️ A transação `{selected_ref}` não possui itens de nota fiscal cadastrados "
            "para auditoria detalhada."
        )


if __name__ == "__main__":
    main()
