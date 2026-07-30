# ══════════════════════════════════════════════════════════════════════════════
# ml_engine.py — Motor de Inteligência Artificial e Auditoria
# ══════════════════════════════════════════════════════════════════════════════
#
# Este arquivo é o "cérebro" do sistema. Ele contém dois mecanismos distintos:
#
#   1. DETECÇÃO ESTATÍSTICA (IsolationForest):
#      Um algoritmo de aprendizado de máquina que analisa padrões numéricos
#      e detecta transações "que fogem do normal" — sem precisar de exemplos
#      de fraudes anteriores. Ele aprende como é o comportamento normal e
#      isola o que é diferente.
#
#   2. AUDITORIA DE REGRAS (Rule-Based):
#      Um conjunto de regras fixas e determinísticas que verificam se um item
#      de nota fiscal está superfaturado ou se é de uma categoria proibida
#      para compras com dinheiro público.
#
# Os dois mecanismos se complementam: a IA encontra padrões incomuns no volume
# de dados; as regras garantem que infrações óbvias nunca passem despercebidas.
# ══════════════════════════════════════════════════════════════════════════════

import numpy as np  # Biblioteca para cálculos numéricos eficientes
import pandas as pd  # Biblioteca para manipulação de tabelas de dados

# IsolationForest: o algoritmo de detecção de anomalias (explicado abaixo)
from sklearn.ensemble import IsolationForest

# StandardScaler: normaliza as variáveis para que tenham a mesma escala
# (sem isso, uma coluna de R$ 100.000 dominaria uma de frequência 1-50)
from sklearn.preprocessing import StandardScaler

# Número mínimo de registros para o modelo poder aprender padrões.
# Com menos de 10 transações, não há dados suficientes para detectar o que é "normal".
_MIN_RECORDS = 10


# ══════════════════════════════════════════════════════════════════════════════
# BLOCO 1: Detecção de Anomalias com IsolationForest
# ══════════════════════════════════════════════════════════════════════════════
#
# O QUE É O ISOLATION FOREST?
#
# Imagine que você tem uma floresta de árvores de decisão aleatórias.
# Cada árvore tenta "isolar" (separar) uma transação do resto usando cortes
# aleatórios no espaço de dados.
#
# Transações NORMAIS: ficam no meio do grupo → difíceis de isolar →
#   precisam de muitos cortes para ficarem sozinhas → profundidade ALTA.
#
# Transações ANÔMALAS: são raras e muito diferentes das demais →
#   fáceis de isolar → poucos cortes as separam → profundidade BAIXA.
#
# O algoritmo não precisa de "exemplos de fraudes" — ele aprende apenas com
# os dados normais e sinaliza o que é raro e diferente.
# ══════════════════════════════════════════════════════════════════════════════

def run_anomaly_detection(
    df: pd.DataFrame,
    contamination: float = 0.05,
    audit_type: str = "cards",
) -> pd.DataFrame:
    # ── O que esta função recebe: ─────────────────────────────────────────────
    #   df           → tabela com as transações do período
    #   contamination → estimativa de quantas transações são suspeitas (0.05 = 5%)
    #   audit_type   → "cards" para cartão corporativo, "expenses" para despesas
    #
    # ── O que ela retorna: ───────────────────────────────────────────────────
    #   A mesma tabela, agora com duas colunas novas:
    #     Anomaly_Score → quanto maior o número, mais suspeita a transação
    #     Is_Anomaly    → True se for anomalia, False se for normal

    df = df.copy()  # Trabalha em uma cópia para não modificar os dados originais

    # Proteção: se a tabela estiver vazia ou com poucos registros,
    # o modelo não tem dados suficientes para aprender — retorna tudo como "Normal"
    if df.empty or len(df) < _MIN_RECORDS:
        df["Anomaly_Score"] = 0.0
        df["Is_Anomaly"] = False
        return df

    # Define qual coluna identifica o fornecedor dependendo do tipo de auditoria:
    # - cartões corporativos → nome do estabelecimento
    # - despesas do executivo → nome do favorecido (quem recebeu o dinheiro)
    vendor_col = "establishment_name" if audit_type == "cards" else "favored_name"

    # ── FEATURE 1: Valor bruto da transação ──────────────────────────────────
    # Converte o valor para número. Se não conseguir, usa 0,0.
    # Transações com valores muito altos em relação ao grupo serão suspeitas.
    df["value_float"] = pd.to_numeric(df["value"], errors="coerce").fillna(0.0)

    # ── FEATURE 2: Frequência do fornecedor ──────────────────────────────────
    # Conta quantas vezes cada fornecedor aparece no período.
    # Um fornecedor que aparece apenas 1 vez com valor alto é mais suspeito
    # do que um que aparece 100 vezes (tem histórico estabelecido).
    freq_map = df[vendor_col].value_counts().to_dict()
    df["vendor_frequency"] = df[vendor_col].map(freq_map).fillna(1).astype(float)

    # ── FEATURE 3: Desvio em relação à média do fornecedor ───────────────────
    # Para cada fornecedor, calcula qual é a sua média histórica de gastos.
    # Depois divide o valor desta transação pela média:
    #   ratio = 1.0 → transação igual à média (normal)
    #   ratio = 5.0 → transação 5x acima da média (muito suspeito!)
    # Exemplo: fornecedor costuma gastar R$ 200 → de repente aparece R$ 20.000
    #          ratio = 100 → flagrado como anomalia
    vendor_mean = df.groupby(vendor_col)["value_float"].transform("mean")
    # + 1e-9 evita divisão por zero quando o fornecedor tem média próxima de 0
    df["value_vs_vendor_mean"] = df["value_float"] / (vendor_mean + 1e-9)

    # Agrupa as 3 features em uma matriz (tabela de números) para o modelo
    feature_cols = ["value_float", "vendor_frequency", "value_vs_vendor_mean"]
    X = df[feature_cols].values

    # Garante que não há valores NaN ou infinitos na matriz
    # (podem surgir em casos extremos de dados corrompidos)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    # ── Normalização (StandardScaler) ────────────────────────────────────────
    # Coloca todas as features na mesma escala (média 0, desvio padrão 1).
    # Sem isso, "valor em R$" (ex: 10.000) dominaria "frequência" (ex: 5)
    # e o modelo ficaria enviesado.
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # ── Treinamento e Predição do IsolationForest ────────────────────────────
    model = IsolationForest(
        contamination=contamination,  # Percentual esperado de anomalias (configurável pelo usuário)
        n_estimators=150,             # 150 árvores de decisão na floresta (mais árvores = mais preciso)
        random_state=42,              # Semente aleatória para resultados reproduzíveis
        n_jobs=-1,                    # Usa todos os núcleos do processador disponíveis (mais rápido)
    )
    model.fit(X_scaled)  # Treina o modelo com os dados normalizados

    # decision_function retorna a "distância da normalidade":
    #   mais negativo → mais anômalo
    # Invertemos o sinal (com "-") para que MAIOR = MAIS SUSPEITO (mais intuitivo na UI)
    raw_scores = model.decision_function(X_scaled)
    predictions = model.predict(X_scaled)  # -1 = anomalia, +1 = normal (padrão do sklearn)

    df["Anomaly_Score"] = -raw_scores  # Score invertido: quanto maior, mais suspeito
    df["Is_Anomaly"] = predictions == -1  # Converte -1/+1 para True/False

    # Remove as colunas auxiliares criadas para o modelo — elas não devem aparecer
    # na tabela final do dashboard, são apenas ferramentas de cálculo
    df.drop(columns=["value_float", "vendor_frequency", "value_vs_vendor_mean"], inplace=True)

    return df


# ══════════════════════════════════════════════════════════════════════════════
# BLOCO 2: Auditor de Regras por Item de Nota Fiscal
# ══════════════════════════════════════════════════════════════════════════════
#
# Enquanto o IsolationForest analisa o PADRÃO das transações,
# este auditor analisa os ITENS INDIVIDUAIS dentro de uma nota fiscal.
#
# Funciona com duas regras claras e determinísticas:
#
#   REGRA 1 — SUPERFATURAMENTO:
#     Se o preço unitário pago for mais de 100% acima do preço médio de mercado,
#     é superfaturamento. Exemplo: vassoura vendida por R$ 19.046 (mercado: R$ 30).
#
#   REGRA 2 — FORA DO ESCOPO:
#     Se a categoria do item estiver na "lista negra", é compra irregular.
#     Exemplo: garrafa de vinho comprada com cartão do governo federal.
# ══════════════════════════════════════════════════════════════════════════════

# Lista de categorias de itens que NUNCA são aceitáveis em compras públicas.
# Qualquer item cujo "category" bata com um destes será flagrado.
_BLACKLISTED_CATEGORIES: set = {
    "Bebida Alcoólica",        # Vinho, cerveja, destilados...
    "Artigos de Luxo",         # Relógios, joias, bolsas de grife...
    "Entretenimento Pessoal",  # Shows, jogos, filmes...
    "Itens Pessoais",          # Roupas, cosméticos, calçados...
    "Tabagismo",               # Cigarros, charutos...
    "Jogos de Azar",           # Apostas, cassino...
}

# Limiar de superfaturamento: 1.0 = 100% acima do preço de mercado.
# Exemplo: se o mercado cobra R$ 30, qualquer preço acima de R$ 60 dispara o alerta.
# (preço_pago > preço_mercado × (1 + 1.0) → preço_pago > 2 × preço_mercado)
_OVERPRICING_THRESHOLD = 1.0


def audit_invoice_items(items_df: pd.DataFrame) -> list:
    # Esta função recebe uma tabela de itens de nota fiscal e retorna uma lista
    # de "achados" (findings) — cada irregularidade encontrada vira um dicionário
    # com o tipo, a gravidade, o item afetado e uma mensagem explicativa.
    #
    # Se não encontrar nada de errado, retorna uma lista vazia [].
    findings = []

    # Percorre cada linha (item) da nota fiscal
    for _, item in items_df.iterrows():
        # Extrai os campos de cada item com segurança (usa padrões se o campo estiver vazio)
        item_name  = str(item.get("item_name") or "Item desconhecido")
        unit_price = float(item.get("unit_price") or 0.0)        # Preço que o governo pagou
        market_avg = float(item.get("market_avg_price") or 0.0)  # Preço médio de mercado
        category   = str(item.get("category") or "")             # Categoria do item

        # ── REGRA 1: Superfaturamento ─────────────────────────────────────────
        # Só aplica se tivermos um preço de mercado para comparar (market_avg > 0)
        if market_avg > 0 and unit_price > market_avg * (1.0 + _OVERPRICING_THRESHOLD):
            # Calcula o percentual de superfaturamento para exibir no alerta
            markup_pct = ((unit_price - market_avg) / market_avg) * 100.0
            findings.append(
                {
                    "type": "SUPERFATURAMENTO",     # Código interno da irregularidade
                    "severity": "CRITICAL",         # Gravidade máxima — alerta vermelho pulsante
                    "item_name": item_name,
                    "overpricing_pct": markup_pct,  # Ex: 63387.0 → "63.387% acima do mercado"
                    "unit_price": unit_price,        # Preço pago pelo governo
                    "market_avg": market_avg,        # Preço médio de mercado
                    "message": (
                        f"Superfaturamento de {markup_pct:,.0f}% "
                        f"detectado no item '{item_name}'!"
                    ),
                }
            )

        # ── REGRA 2: Categoria Fora do Escopo ────────────────────────────────
        # Verifica se a categoria do item está na lista de categorias proibidas
        if category in _BLACKLISTED_CATEGORIES:
            findings.append(
                {
                    "type": "FORA_DO_ESCOPO",    # Código interno da irregularidade
                    "severity": "HIGH",          # Gravidade alta — alerta âmbar
                    "item_name": item_name,
                    "category": category,        # Qual categoria foi flagrada
                    "message": (
                        f"Item '{item_name}' fora do escopo de compras "
                        f"da Administração Pública!"
                    ),
                }
            )

    # Retorna a lista de irregularidades. Se vazia, a compra está dentro dos padrões.
    return findings
