# ══════════════════════════════════════════════════════════════════════════════
# app.py — Dashboard Interativo (Interface do Usuário)
# ══════════════════════════════════════════════════════════════════════════════
#
# Este arquivo é a "vitrine" do sistema — tudo que o usuário vê na tela.
# Ele é construído com Streamlit, uma biblioteca Python que transforma
# código Python em um dashboard web sem precisar escrever HTML/CSS/JavaScript.
#
# Ao executar "streamlit run app.py", o Streamlit:
#   1. Inicia um servidor web local (http://localhost:8501)
#   2. Abre automaticamente o navegador com o dashboard
#   3. Reexecuta este arquivo inteiro do início toda vez que o usuário
#      interage com a interface (clica em um botão, move um slider, etc.)
#
# O fluxo do dashboard é:
#   Sidebar (controles) → Botão de busca → API → Banco → IA → Tabela → Raio-X
# ══════════════════════════════════════════════════════════════════════════════

from datetime import datetime  # Para formatar o nome do arquivo CSV exportado

import pandas as pd  # Para manipulação de tabelas de dados
import plotly.graph_objects as go  # Para criar os gráficos interativos
import streamlit as st  # Framework do dashboard web

# Importações do nosso próprio sistema:
from database import (
    get_all_refs_with_items,  # Quais transações têm itens de nota fiscal cadastrados
    get_invoice_items,         # Busca os itens de uma nota fiscal específica
    init_db,                   # Cria as tabelas do banco (se ainda não existirem)
    seed_invoice_items,        # Planta os dados de demonstração no banco
)
from ingestion import (
    fetch_corporate_cards,     # Busca cartões corporativos da API
    fetch_executive_expenses,  # Busca despesas do executivo da API
    load_corporate_cards,      # Lê cartões do banco local
    load_executive_expenses,   # Lê despesas do banco local
    save_corporate_cards,      # Salva cartões no banco local
    save_executive_expenses,   # Salva despesas no banco local
)
from ml_engine import audit_invoice_items, run_anomaly_detection  # Motor de IA e auditoria


# ──────────────────────────────────────────────────────────────────────────────
# Configuração Inicial da Página
# ──────────────────────────────────────────────────────────────────────────────
# Esta deve ser a PRIMEIRA chamada do Streamlit — define título da aba do navegador,
# ícone, layout (wide = usa toda a largura da tela) e estado inicial do sidebar.

st.set_page_config(
    page_title="Fiscal.AI — O Auditor Implacável",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ──────────────────────────────────────────────────────────────────────────────
# CSS Personalizado — Estilo Visual do Dashboard
# ──────────────────────────────────────────────────────────────────────────────
# Injetamos CSS diretamente no HTML da página para:
#   - Criar o cabeçalho hero (título grande e centralizado)
#   - Definir o banner de alerta amarelo
#   - Criar as caixas de alerta coloridas do Raio-X
#   - Programar a animação pulsante vermelha (efeito WOW do superfaturamento)
#
# @keyframes fiscalai-pulse: define uma animação de "pulsação" —
#   a caixa de superfaturamento brilha e cresce levemente em loop infinito,
#   chamando atenção visual imediata do usuário para irregularidades críticas.

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
        #MainMenu { visibility:hidden; }  /* Oculta o menu hambúrguer do Streamlit */
        footer     { visibility:hidden; }  /* Oculta o rodapé padrão do Streamlit */
    </style>
    """,
    unsafe_allow_html=True,
)


# ──────────────────────────────────────────────────────────────────────────────
# Funções de Formatação e Auxiliares
# ──────────────────────────────────────────────────────────────────────────────

def fmt_brl(value) -> str:
    # Converte um número decimal para o formato de moeda brasileiro.
    # Exemplo: 1252.55 → "R$ 1.252,55"
    #
    # O Python formata como "1,252.55" (padrão americano).
    # Precisamos converter para "1.252,55" (padrão brasileiro):
    #   1. Formata com vírgula de milhar e ponto decimal: "1,252.55"
    #   2. Troca vírgula por "X" temporariamente:        "1X252.55"
    #   3. Troca ponto por vírgula:                      "1X252,55"
    #   4. Troca "X" de volta por ponto:                 "1.252,55"
    try:
        s = f"{float(value):,.2f}"
        return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "R$ 0,00"  # Fallback seguro se o valor não for numérico


def fmt_int(value) -> str:
    # Formata um número inteiro com separador de milhar no padrão brasileiro.
    # Exemplo: 1000 → "1.000", 50000 → "50.000"
    return f"{int(value):,}".replace(",", ".")


def _month_label(m: int) -> str:
    # Converte número do mês (1-12) para nome em português.
    # Usado para exibir "Janeiro", "Fevereiro" etc. no seletor de mês.
    months_pt = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    ]
    return months_pt[m - 1]


def _safe_str(value, placeholder: str = "NÃO ENCONTRADO") -> str:
    # Garante que nenhum valor "vazio" apareça como "nan" ou "None" na tabela.
    # O pandas usa "NaN" (Not a Number) para células vazias, mas isso ficaria
    # feio e confuso para o usuário final.
    # Esta função substitui qualquer variação de vazio pelo placeholder.
    s = str(value).strip() if value is not None else ""
    return placeholder if s.lower() in ("nan", "none", "nat", "") else s


# ──────────────────────────────────────────────────────────────────────────────
# Session State — Memória do Dashboard
# ──────────────────────────────────────────────────────────────────────────────
#
# O Streamlit reexecuta o arquivo inteiro a cada interação do usuário.
# O "session_state" é como a "memória" do dashboard — guarda informações
# entre essas reexecuções para que os dados não se percam quando o usuário
# muda o slider ou clica em uma linha da tabela.
#
# Sem o session_state, ao mover o slider de sensibilidade, os dados
# buscados da API seriam perdidos e o usuário precisaria buscar novamente.

def _init_state() -> None:
    # Define os valores iniciais do session_state na primeira execução.
    # "if k not in st.session_state" garante que não sobrescreve valores
    # existentes em execuções subsequentes.
    defaults = {
        "df_raw": None,               # Tabela bruta vinda do banco (sem análise de IA)
        "df_result": None,            # Tabela enriquecida com scores e flags de anomalia
        "audit_key": None,            # "cards" ou "expenses" — tipo de auditoria ativa
        "query_label": "",            # Texto descritivo da busca atual (ex: "Janeiro/2026 — Cartões")
        "last_contamination": 0.05,   # Última sensibilidade usada no modelo (para detectar mudanças)
        # data_version é incrementado a cada nova busca.
        # Usado como sufixo na key da tabela para forçar o Streamlit a resetar
        # a seleção de linha quando os dados mudam.
        "data_version": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ──────────────────────────────────────────────────────────────────────────────
# Raio-X da Nota Fiscal — Painel de Drill-Down por Item
# ──────────────────────────────────────────────────────────────────────────────
#
# Quando o usuário clica em uma linha da tabela que tem o ícone "📑 Raio-X",
# esta função é chamada para renderizar o painel de auditoria detalhada.
#
# Ela mostra uma tabela com os itens individuais da nota fiscal e, em seguida,
# exibe alertas visuais para cada irregularidade encontrada.

def _render_raio_x(transaction_ref: str, vendor_name: str) -> None:
    # Busca os itens de nota fiscal desta transação no banco de dados
    items_df = get_invoice_items(transaction_ref)
    if items_df.empty:
        return  # Transação sem itens cadastrados — nada a exibir

    st.markdown("---")

    # Abre o container visual do Raio-X (borda azul, fundo gradiente)
    st.markdown(
        '<div class="raio-x-panel">',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="raio-x-title">🔎 Raio-X da Nota Fiscal</div>',
        unsafe_allow_html=True,
    )

    # Exibe a referência da transação e o nome do fornecedor
    st.caption(
        f"Transação: `{transaction_ref}`  |  Fornecedor: **{vendor_name[:80]}**"
    )

    # ── Constrói a tabela enriquecida de itens ──────────────────────────────
    # Para cada item, calcula a "Variação" — quanto o preço pago difere
    # do preço médio de mercado, em percentual.
    display_rows = []
    for _, item in items_df.iterrows():
        unit_price = float(item.get("unit_price") or 0)
        market_avg = float(item.get("market_avg_price") or 0)

        if market_avg > 0:
            variacao_pct = ((unit_price - market_avg) / market_avg) * 100
            variacao_str = (
                f"+{variacao_pct:,.1f}%"  # Positivo = acima do mercado
                if variacao_pct >= 0
                else f"{variacao_pct:,.1f}%"  # Negativo = abaixo do mercado (bom negócio)
            )
        else:
            variacao_str = "—"  # Sem preço de mercado para comparar

        display_rows.append(
            {
                "Item": str(item.get("item_name", "")),
                "Qtd": int(item.get("quantity") or 0),
                "Preço Unit. (R$)": fmt_brl(unit_price),
                "Média Mercado (R$)": fmt_brl(market_avg),
                "Variação": variacao_str,           # Coluna principal de comparação
                "Total (R$)": fmt_brl(float(item.get("total_price") or 0)),
                "Categoria": str(item.get("category", "")),
            }
        )

    # Exibe a tabela de itens na interface
    st.dataframe(
        pd.DataFrame(display_rows),
        use_container_width=True,
        hide_index=True,
    )

    # ── Executa o Auditor de Regras e exibe os alertas ──────────────────────
    # audit_invoice_items retorna uma lista de irregularidades encontradas.
    # Cada irregularidade é renderizada como uma caixa colorida diferente.
    findings = audit_invoice_items(items_df)

    if not findings:
        # Nenhuma irregularidade → caixa verde com mensagem positiva
        st.markdown(
            '<div class="normal-ok-box">'
            "✅ Itens dentro do padrão de mercado. Nenhuma irregularidade detectada."
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        for f in findings:
            if f["type"] == "SUPERFATURAMENTO":
                # CAIXA VERMELHA PULSANTE — máxima urgência visual
                # Exibe o percentual de superfaturamento e os preços comparados
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
                # CAIXA ÂMBAR — alta gravidade, não crítica como superfaturamento
                st.markdown(
                    f'<div class="anomaly-scope-box">'
                    f"🚨 ANOMALIA: Item '{f['item_name']}' fora do escopo "
                    f"de compras da Administração Pública!<br>"
                    f"<span>Categoria flagrada: <strong>{f['category']}</strong></span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    st.markdown("</div>", unsafe_allow_html=True)  # Fecha o container do Raio-X


# ══════════════════════════════════════════════════════════════════════════════
# FUNÇÃO PRINCIPAL — main()
# ══════════════════════════════════════════════════════════════════════════════
#
# Todo o fluxo do dashboard acontece aqui, em ordem:
#   1. Inicializa banco e session_state
#   2. Renderiza o cabeçalho hero
#   3. Renderiza o sidebar com controles
#   4. Processa o clique no botão de busca
#   5. Detecta mudança no slider e recalibra a IA
#   6. Exibe métricas, gráficos e tabela
#   7. Mostra o Raio-X quando o usuário seleciona uma linha
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    # ── Inicialização ──────────────────────────────────────────────────────────
    init_db()            # Cria as tabelas do banco se não existirem
    seed_invoice_items() # Planta os dados de demonstração (idempotente — seguro chamar sempre)
    _init_state()        # Inicializa o session_state com valores padrão

    # ── Cabeçalho Hero ─────────────────────────────────────────────────────────
    # Título grande e centralizado no topo do dashboard
    st.markdown(
        """
        <div class="fiscalai-hero">
            <h1>🔍 Fiscal.AI — O Auditor Implacável</h1>
            <p>Detecção de Anomalias em Gastos Públicos Federais com Inteligência Artificial</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Sidebar — Painel de Controle ───────────────────────────────────────────
    # O "with st.sidebar:" coloca todos os elementos dentro da barra lateral esquerda
    with st.sidebar:
        st.markdown("## ⚙️ Painel de Controle")
        st.markdown("---")

        st.markdown("### 📥 Ingestão de Dados")

        # Seletor do tipo de auditoria: cartões ou despesas
        audit_label = st.selectbox(
            "Tipo de Auditoria",
            options=["Cartões Corporativos (CPGF)", "Despesas do Executivo"],
            help=(
                "**Cartões Corporativos**: gastos do Cartão de Pagamento do Governo Federal.\n\n"
                "**Despesas do Executivo**: ordens de pagamento emitidas pelo Poder Executivo."
            ),
        )
        # Converte o texto selecionado para uma chave interna simples
        audit_key = "cards" if "Cartões" in audit_label else "expenses"

        # Seletores de mês e ano lado a lado (usando duas colunas)
        col_m, col_y = st.columns(2)
        with col_m:
            month = st.selectbox(
                "Mês",
                options=list(range(1, 13)),  # 1 a 12
                format_func=_month_label,     # Exibe "Janeiro", "Fevereiro" etc.
                index=0,                      # Padrão: Janeiro
            )
        with col_y:
            year = st.selectbox(
                "Ano",
                options=list(range(2024, 2027)),  # 2024, 2025, 2026
                index=2,                           # Padrão: 2026
            )

        st.markdown("---")

        st.markdown("### 🤖 Configuração do Modelo de IA")

        # Slider de sensibilidade do IsolationForest.
        # "contamination" = estimativa de quantas transações são anômalas (em %).
        # Menor valor = modelo mais conservador (menos alertas, apenas os mais óbvios).
        # Maior valor = modelo mais agressivo (mais alertas, pode gerar falsos positivos).
        contamination = st.slider(
            "Sensibilidade (Taxa de Contaminação)",
            min_value=0.01,   # Mínimo: 1% de anomalias esperadas
            max_value=0.30,   # Máximo: 30% de anomalias esperadas
            value=st.session_state.last_contamination,  # Preserva o último valor usado
            step=0.01,
            help=(
                "Percentual estimado de anomalias no dataset.\n\n"
                "**Menor** → modelo mais conservador (menos alertas).\n"
                "**Maior** → modelo mais agressivo (mais alertas).\n\n"
                "Padrão recomendado: 5%."
            ),
        )

        st.markdown("---")

        # Botão principal — dispara todo o pipeline de busca e análise
        fetch_btn = st.button(
            "🔎 Buscar e Analisar Dados",
            use_container_width=True,  # Ocupa toda a largura do sidebar
            type="primary",            # Estilo destacado (azul)
        )

        st.markdown("---")
        # Link para a fonte oficial dos dados
        st.caption(
            "Fonte: [Portal da Transparência](https://portaldatransparencia.gov.br/) "
            "— CGU"
        )

    # ── Manipulador do Botão: Busca → Salva → Carrega → IA ───────────────────
    # Este bloco executa quando o usuário clica em "Buscar e Analisar Dados"
    if fetch_btn:
        query_label = f"{_month_label(month)}/{year} — {audit_label}"

        # st.spinner exibe um indicador de carregamento enquanto o código interno executa
        with st.spinner(f"⏳ Buscando dados: {query_label}..."):
            try:
                if audit_key == "cards":
                    df_fetched = fetch_corporate_cards(month, year)  # 1. Busca da API
                    if not df_fetched.empty:
                        save_corporate_cards(df_fetched)             # 2. Salva no banco
                    df_raw = load_corporate_cards(month, year)       # 3. Lê do banco
                else:
                    df_fetched = fetch_executive_expenses(month, year)
                    if not df_fetched.empty:
                        save_executive_expenses(df_fetched)
                    df_raw = load_executive_expenses(month, year)

                if df_raw.empty:
                    # Aviso amigável se não encontrar dados no período
                    st.warning(
                        "⚠️ **Nenhum registro encontrado** para o período selecionado.\n\n"
                        "Verifique se a chave de API é válida ou tente outro mês."
                    )
                    st.stop()  # Interrompe a execução sem travar o app

            except ValueError as exc:
                # Erro de configuração (chave de API ausente)
                st.error(f"❌ **Erro de configuração:** {exc}")
                st.stop()
            except ConnectionError as exc:
                # Erro de rede (sem internet, API fora do ar)
                st.error(f"❌ **Erro de conexão com a API:** {exc}")
                st.stop()
            except Exception as exc:
                # Qualquer outro erro inesperado
                st.error(f"❌ **Erro inesperado:** {exc}")
                st.stop()

        # Após buscar os dados, executa a IA com outro spinner
        with st.spinner("🤖 Executando modelo de Inteligência Artificial..."):
            df_result = run_anomaly_detection(df_raw, contamination, audit_key)

        # Salva os resultados no session_state para que persistam nas próximas renderizações
        st.session_state.df_raw = df_raw
        st.session_state.df_result = df_result
        st.session_state.audit_key = audit_key
        st.session_state.query_label = query_label
        st.session_state.last_contamination = contamination
        # Incrementa a versão dos dados — isso reseta a seleção de linha na tabela
        st.session_state.data_version = st.session_state.data_version + 1

        n_anom = int(df_result["Is_Anomaly"].sum())
        st.success(
            f"✅ **Análise concluída!** {fmt_int(len(df_result))} registros processados, "
            f"**{n_anom} anomalia(s)** detectada(s)."
        )

    # ── Recalibração Automática da IA ao Mover o Slider ─────────────────────
    # Se o usuário mover o slider de sensibilidade SEM clicar no botão de busca,
    # reprocessamos os dados já carregados com a nova configuração.
    # Assim o usuário pode experimentar diferentes sensibilidades instantaneamente.
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

    # ── Tela Inicial (sem dados ainda) ─────────────────────────────────────────
    # Recupera os dados do session_state para renderizar o dashboard
    df = st.session_state.df_result
    audit_key_cur = st.session_state.audit_key

    if df is None or df.empty:
        # Se não há dados ainda, exibe instruções de como começar
        st.markdown("---")
        st.info(
            "👆 **Como começar:** use o painel lateral para selecionar o tipo de auditoria, "
            "o período e clique em **Buscar e Analisar Dados**."
        )
        # Painel expansível explicando como o sistema funciona
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
        return  # Encerra a renderização aqui — não há dados para mostrar

    # ══════════════════════════════════════════════════════════════════════════
    # DASHBOARD PRINCIPAL — exibido apenas quando há dados carregados
    # ══════════════════════════════════════════════════════════════════════════

    # Define a coluna de fornecedor correta dependendo do tipo de auditoria
    vendor_col = "establishment_name" if audit_key_cur == "cards" else "favored_name"

    # ── Cálculo das métricas globais ──────────────────────────────────────────
    total_spent     = df["value"].sum()             # Soma total de todos os gastos
    total_records   = len(df)                        # Número total de transações
    total_anomalies = int(df["Is_Anomaly"].sum())   # Quantas foram flagradas como anômalas
    anomaly_pct     = (total_anomalies / total_records * 100) if total_records > 0 else 0.0
    anomaly_value   = df.loc[df["Is_Anomaly"], "value"].sum()  # Soma dos valores das anomalias

    # ── Pre-computa quais transações têm itens de nota fiscal ─────────────────
    # refs_with_items: IDs das transações com itens cadastrados no banco
    refs_with_items: set = get_all_refs_with_items()

    # refs_with_item_anomalies: subconjunto de refs_with_items cujos itens
    # disparam pelo menos uma regra de auditoria (superfaturamento ou escopo).
    # Usado para "promover" transações ao status 🚨 Anomalia na tabela,
    # mesmo que o IsolationForest não as tenha flagrado.
    refs_with_item_anomalies: set = set()
    for _ref in refs_with_items:
        _items = get_invoice_items(_ref)
        if not _items.empty and audit_invoice_items(_items):
            refs_with_item_anomalies.add(_ref)

    # Exibe o período analisado em texto discreto abaixo do cabeçalho
    st.markdown(
        f"<div style='text-align:center;color:#5a6a7a;font-size:.9rem;margin-top:.2rem;'>"
        f"Período analisado: <strong>{st.session_state.query_label}</strong></div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # ── Métricas em Destaque (4 colunas) ──────────────────────────────────────
    # st.columns(4) divide a linha em 4 colunas iguais para os KPIs principais
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
            delta_color="inverse",  # Vermelho (delta "inverse" = pior quanto maior)
            help="Transações classificadas como suspeitas pelo Isolation Forest",
        )
    with c4:
        st.metric("⚠️ Valor em Risco", fmt_brl(anomaly_value),
                  help="Soma dos valores das transações anômalas")

    # Se há anomalias, exibe o banner de alerta amarelo
    if total_anomalies > 0:
        st.markdown(
            f'<div class="alert-anomaly">🚨 <strong>Atenção!</strong> O modelo de IA detectou '
            f"<strong>{total_anomalies} transação(ões) suspeita(s)</strong>, totalizando "
            f"<strong>{fmt_brl(anomaly_value)}</strong> em gastos potencialmente anômalos.</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Gráficos (2 colunas proporcionais) ────────────────────────────────────
    # [3, 2] = o scatter (esquerda) ocupa 60%, o bar chart (direita) ocupa 40%
    col_scatter, col_bar = st.columns([3, 2])

    with col_scatter:
        st.markdown('<div class="section-title">📈 Transações ao Longo do Tempo</div>',
                    unsafe_allow_html=True)

        # Prepara os dados para o gráfico de dispersão temporal
        df_plot = df.copy()
        df_plot["date_ts"] = pd.to_datetime(
            df_plot["date"], format="%d/%m/%Y", errors="coerce"
        )
        df_plot = df_plot.dropna(subset=["date_ts"]).sort_values("date_ts")

        # Separa transações normais (azul) das anômalas (vermelho)
        df_normal = df_plot[~df_plot["Is_Anomaly"]]
        df_anom   = df_plot[df_plot["Is_Anomaly"]]

        # Cria o gráfico com Plotly: cada ponto = uma transação
        fig = go.Figure()

        # Camada 1: pontos azuis translúcidos para transações normais
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

        # Camada 2: pontos vermelhos maiores para anomalias (se existirem)
        if not df_anom.empty:
            fig.add_trace(go.Scatter(
                x=df_anom["date_ts"], y=df_anom["value"],
                mode="markers", name="🚨 Anomalia",
                marker=dict(color="rgba(220,38,38,0.9)", size=14,
                            line=dict(color="#7f1d1d", width=2)),  # Borda escura para destaque
                customdata=df_anom[vendor_col].fillna("NÃO ENCONTRADO").str[:40],
                hovertemplate=(
                    "<b>🚨 ANOMALIA</b><br>"
                    "<b>Data:</b> %{x|%d/%m/%Y}<br>"
                    "<b>Valor:</b> R$ %{y:,.2f}<br>"
                    "<b>Fornecedor:</b> %{customdata}<extra></extra>"
                ),
            ))

        # Estilização do gráfico: fundo transparente, sem grades desnecessárias
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

        # Filtra apenas as transações anômalas para o ranking
        df_anom_all = df[df["Is_Anomaly"]]
        if df_anom_all.empty:
            st.info("Nenhuma anomalia detectada para exibir no ranking.")
        else:
            # Agrupa por fornecedor, soma os valores e pega os 5 maiores
            top5 = (
                df_anom_all.groupby(vendor_col)["value"]
                .sum().nlargest(5).reset_index()
            )
            top5.columns = ["Fornecedor", "Total"]

            # Trunca nomes longos para caber no gráfico (máximo 28 caracteres + "…")
            top5["Label"] = top5["Fornecedor"].apply(
                lambda x: x[:28] + "…" if len(x) > 28 else x
            )

            # Gráfico de barras horizontais (orientation="h") — mais legível para nomes
            fig_bar = go.Figure(go.Bar(
                x=top5["Total"], y=top5["Label"], orientation="h",
                marker=dict(color="rgba(220,38,38,0.75)",
                            line=dict(color="rgba(127,29,29,0.9)", width=1)),
                customdata=top5["Fornecedor"],  # Nome completo para o tooltip
                hovertemplate="<b>%{customdata}</b><br>Total: R$ %{x:,.2f}<extra></extra>",
            ))
            fig_bar.update_layout(
                xaxis_title="Total (R$)", yaxis=dict(autorange="reversed"),  # Maior no topo
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                height=380, margin=dict(l=0, r=0, t=10, b=0),
            )
            fig_bar.update_xaxes(gridcolor="rgba(180,180,180,0.2)", zeroline=False)
            fig_bar.update_yaxes(gridcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_bar, use_container_width=True)

    # ── Tabela de Detalhamento com Seleção de Linha ────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-title">📋 Detalhamento dos Registros</div>',
                unsafe_allow_html=True)

    # Filtro rápido: todos, apenas anomalias ou apenas normais
    col_f1, col_f2, _ = st.columns([2, 2, 6])
    with col_f1:
        view_filter = st.selectbox(
            "Exibir",
            ["Todos os Registros", "Apenas Anomalias 🚨", "Apenas Normais ✅"],
            label_visibility="collapsed",  # Esconde o label para economizar espaço
        )

    # Aplica o filtro selecionado
    df_view = df.copy()
    if "Anomalias" in view_filter:
        df_view = df_view[df_view["Is_Anomaly"]]
    elif "Normais" in view_filter:
        df_view = df_view[~df_view["Is_Anomaly"]]
    df_view = df_view.reset_index(drop=True)

    # Estas listas paralelas mapeiam o índice da linha selecionada na tabela
    # para a referência da transação (ID) e o nome do fornecedor.
    # São necessárias porque a tabela exibida ao usuário tem colunas diferentes
    # das colunas internas do DataFrame.
    transaction_refs_order: list[str] = []
    vendor_labels_order:    list[str] = []

    # ── Constrói as linhas da tabela exibida ao usuário ───────────────────────
    rows = []
    for _, row in df_view.iterrows():
        is_anom = bool(row.get("Is_Anomaly", False))

        # Extrai o ID de referência e o nome do fornecedor de acordo com o tipo de auditoria
        if audit_key_cur == "cards":
            raw_id = row.get("id")
            t_ref  = str(int(raw_id)) if pd.notna(raw_id) else ""  # ID numérico do cartão
            vendor = _safe_str(row.get("establishment_name"))
        else:
            t_ref  = str(row.get("document_id", ""))  # Código do documento (ex: "2026OB000049")
            vendor = _safe_str(row.get("favored_name"))

        # Registra as listas paralelas para o mapeamento de seleção
        transaction_refs_order.append(t_ref)
        vendor_labels_order.append(vendor)

        has_items = t_ref in refs_with_items  # Esta transação tem itens de nota fiscal?

        # Promoção de status: se a transação tem itens com irregularidades,
        # marca como 🚨 Anomalia MESMO QUE o IsolationForest não a tenha flagrado.
        # Isso garante que infrações detectadas pelas regras nunca passem despercebidas.
        is_anomaly_final = is_anom or (t_ref in refs_with_item_anomalies)

        # Constrói o dicionário de colunas comuns a ambos os tipos de auditoria
        base: dict = {
            "Status IA": "🚨 Anomalia" if is_anomaly_final else "✅ Normal",
            "📑": "📑 Raio-X" if has_items else "",  # Ícone que indica drill-down disponível
            "Data": row.get("date", ""),
            "Valor (R$)": fmt_brl(row.get("value", 0)),
            "Score IA": f"{row.get('Anomaly_Score', 0.0):.4f}",  # 4 casas decimais
        }

        # Adiciona colunas específicas de cada tipo de auditoria
        if audit_key_cur == "cards":
            base["Estabelecimento"] = vendor
            base["CNPJ/CPF"]        = _safe_str(row.get("establishment_doc"), "")
            base["Unidade Gestora"] = _safe_str(row.get("unit_name"), "")
            base["Portador"]        = _safe_str(row.get("cardholder_name"), "")
        else:
            base["Documento"]       = t_ref
            base["Favorecido"]      = vendor  # Já sanitizado por _safe_str acima
            base["CNPJ/CPF"]        = _safe_str(row.get("favored_doc"), "")
            base["Categoria"]       = _safe_str(row.get("category"), "")
            base["Unidade Gestora"] = _safe_str(row.get("unit_name"), "")
        rows.append(base)

    df_table = pd.DataFrame(rows)

    # ── Coloração das linhas anômalas ─────────────────────────────────────────
    # Aplica um fundo levemente avermelhado nas linhas que têm 🚨 no Status IA.
    # Isso dá uma dica visual imediata de quais linhas merecem atenção.
    def _highlight(row: pd.Series):
        if "🚨" in str(row.get("Status IA", "")):
            return ["background-color:rgba(220,38,38,0.08)"] * len(row)
        return [""] * len(row)

    styled = df_table.style.apply(_highlight, axis=1)

    with col_f2:
        st.caption(f"{fmt_int(len(df_table))} registro(s) exibido(s)")

    # ── Tabela Interativa com Seleção de Linha ────────────────────────────────
    # on_select="rerun" faz o Streamlit reexecutar o script quando uma linha é selecionada.
    # key inclui data_version para que o Streamlit crie um widget novo (sem seleção)
    # quando os dados mudam — evita que a seleção antiga persista com dados novos.
    table_key = f"main_table_v{st.session_state.data_version}"

    event = st.dataframe(
        styled,
        on_select="rerun",           # Reexecuta o app ao selecionar uma linha
        selection_mode="single-row", # Apenas uma linha selecionada por vez
        key=table_key,
        use_container_width=True,
        height=420,
        hide_index=True,
    )

    # ── Decodifica a linha selecionada ────────────────────────────────────────
    # event.selection.rows contém os índices das linhas selecionadas.
    # Usamos o índice para buscar o transaction_ref e vendor nas listas paralelas.
    selected_ref: str | None = None
    selected_vendor: str = ""

    selection = getattr(event, "selection", None)
    if selection and selection.rows:
        sel_idx = selection.rows[0]  # Índice da linha selecionada
        if 0 <= sel_idx < len(transaction_refs_order):
            selected_ref    = transaction_refs_order[sel_idx]
            selected_vendor = vendor_labels_order[sel_idx]

    # ── Botão de exportação CSV ───────────────────────────────────────────────
    # Exporta os dados filtrados (com ou sem anomalias, conforme o filtro ativo)
    # em UTF-8 com BOM para compatibilidade com Excel em português do Brasil.
    csv_bytes = df_view.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="⬇️ Exportar Relatório Completo (CSV)",
        data=csv_bytes,
        file_name=f"fiscal_ai_{audit_key_cur}_{datetime.now():%Y%m%d_%H%M%S}.csv",
        mime="text/csv",
    )

    # ── Drill-Down: Raio-X da Nota Fiscal ─────────────────────────────────────
    if selected_ref is None:
        # Nenhuma linha selecionada ainda — se houver linhas auditáveis na visão atual,
        # exibe uma dica informando o usuário que pode clicar nelas
        auditable_in_view = [r for r in transaction_refs_order if r in refs_with_items]
        if auditable_in_view:
            st.markdown("---")
            st.info(
                f"💡 **Dica:** {len(auditable_in_view)} transação(ões) marcada(s) com **📑 Raio-X** "
                "possuem itens de nota fiscal cadastrados. Clique em uma dessas linhas na tabela "
                "acima para abrir a análise detalhada."
            )
    elif selected_ref in refs_with_items:
        # Linha com itens cadastrados selecionada → renderiza o Raio-X completo
        _render_raio_x(selected_ref, selected_vendor)
    else:
        # Linha sem itens cadastrados selecionada → mensagem informativa
        st.markdown("---")
        st.info(
            f"ℹ️ A transação `{selected_ref}` não possui itens de nota fiscal cadastrados "
            "para auditoria detalhada."
        )


# ── Ponto de entrada do programa ──────────────────────────────────────────────
# "__main__" garante que main() só seja chamado quando o arquivo é executado
# diretamente (ex: streamlit run app.py), não quando é importado por outro módulo.
if __name__ == "__main__":
    main()
