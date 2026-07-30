<div align="center">

# 🔍 Fiscal.AI — O Auditor Implacável

### Sistema de Detecção de Anomalias em Gastos Públicos Federais com Inteligência Artificial

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-IsolationForest-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)](https://scikit-learn.org)
[![License: MIT](https://img.shields.io/badge/Licença-MIT-22c55e?style=for-the-badge)](LICENSE)

[![GitHub stars](https://img.shields.io/github/stars/seu-usuario/fiscal-ai?style=social)](https://github.com/douglascarlosmen/fiscal-ai/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/seu-usuario/fiscal-ai?style=social)](https://github.com/douglascarlosmen/fiscal-ai/network/members)

</div>

---

## 🇧🇷 Por que este projeto existe?

Em 2023, o Brasil registrou mais de **R$ 2 trilhões** em despesas do Governo Federal. A maior parte desses dados é pública, disponível no [Portal da Transparência](https://portaldatransparencia.gov.br/) — mas ninguém tem tempo (ou ferramentas) para analisar tudo.

**Resultado:** superfaturamentos, compras fora do escopo e irregularidades passam despercebidos no volume gigantesco de transações diárias.

O **Fiscal.AI** nasce como resposta a esse problema. É uma ferramenta de código aberto que usa **Inteligência Artificial** para conectar automaticamente à API oficial do Governo Federal, varrer transações de cartões corporativos e despesas do Executivo, e sinalizar comportamentos estatisticamente anômalos — tudo rodando no computador do usuário, sem custos de nuvem.

> *"A transparência sem análise é apenas ruído. O Fiscal.AI transforma dados públicos em fiscalização real."*

Este projeto é uma contribuição à sociedade civil, ao jornalismo investigativo e a qualquer cidadão que acredite que **tecnologia e democracia andam juntas**.

---

## ✨ Funcionalidades

| Recurso | Descrição |
|---|---|
| 📥 **Ingestão Dinâmica** | Busca dados em tempo real da API do Portal da Transparência por mês e ano |
| 🗄️ **Banco Local** | Persiste tudo em SQLite — sem dependência de nuvem ou internet após o download |
| 🤖 **Isolation Forest** | Detecta anomalias estatísticas com 3 features engenheiradas (valor, frequência do fornecedor, desvio da média) |
| 🔎 **Raio-X da Nota Fiscal** | Drill-down por item de nota fiscal com regras determinísticas de superfaturamento e escopo |
| 🚨 **Alertas Visuais** | Alerta pulsante vermelho para superfaturamento; banner âmbar para itens fora do escopo da Administração Pública |
| 📊 **Dashboard Interativo** | Scatter plot temporal + ranking dos 5 maiores fornecedores anômalos em Plotly |
| ⚙️ **Sensibilidade Ajustável** | Slider de contaminação do modelo — do conservador ao agressivo |
| ⬇️ **Exportação CSV** | Relatório completo para análise externa em Excel ou qualquer BI |

---

## 🖥️ Demonstração

O dashboard possui três painéis principais:

```
┌─────────────────────────────────────────────────────────┐
│  💰 Total Gasto  │  📋 Registros  │  🚨 Anomalias  │  ⚠️ Valor em Risco  │
├─────────────────────────────────────────────────────────┤
│  📈 Transações ao Longo do Tempo  │  🏴‍☠️ Top 5 Anômalos  │
├─────────────────────────────────────────────────────────┤
│  📋 Detalhamento dos Registros (com seleção de linha)   │
├─────────────────────────────────────────────────────────┤
│  🔎 Raio-X da Nota Fiscal (drill-down por item)         │
│     ┌─────────────────────────────────────────────┐    │
│     │ 🚨 ANOMALIA: Superfaturamento de 63.387%!   │    │  ← pulsa em vermelho
│     └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| **Interface** | [Streamlit](https://streamlit.io) + [Plotly](https://plotly.com/python/) |
| **Machine Learning** | [Scikit-Learn](https://scikit-learn.org) — `IsolationForest` + `StandardScaler` |
| **Dados** | [Pandas](https://pandas.pydata.org) + SQLite3 |
| **API** | [Portal da Transparência — CGU](https://portaldatransparencia.gov.br/api-de-dados) |
| **Configuração** | [python-dotenv](https://pypi.org/project/python-dotenv/) |

---

## 🚀 Como Executar

### Pré-requisitos

- Python **3.9 ou superior**
- Uma chave gratuita da API do Portal da Transparência ([cadastre-se aqui](https://portaldatransparencia.gov.br/api-de-dados/cadastrar-email))

### Passo a passo

**1. Clone o repositório**

```bash
git https://github.com/douglascarlosmen/fiscal-ai.git
cd fiscal-ai
```

**2. Crie e ative um ambiente virtual** *(recomendado)*

```bash
# Linux / macOS
python -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

**3. Instale as dependências**

```bash
pip install -r requirements.txt
```

**4. Configure sua chave de API**

Copie o arquivo de exemplo e preencha com sua chave:

```bash
cp .env.example .env
```

Edite o `.env`:

```env
CHAVE_API_DADOS=sua_chave_aqui
```

> 💡 A chave é gratuita e pode ser obtida em menos de 1 minuto no [Portal da Transparência](https://portaldatransparencia.gov.br/api-de-dados/cadastrar-email).

**5. Execute o dashboard**

```bash
streamlit run app.py
```

O navegador abrirá automaticamente em `http://localhost:8501`.

### Uso básico

1. No painel lateral, selecione **Cartões Corporativos** ou **Despesas do Executivo**
2. Escolha o **mês** e o **ano** que deseja auditar
3. Ajuste a **sensibilidade do modelo** (padrão: 5%)
4. Clique em **🔎 Buscar e Analisar Dados**
5. Clique em qualquer linha marcada com **📑 Raio-X** para o drill-down por item

---

## 📂 Estrutura do Projeto

```
fiscal-ai/
│
├── app.py              # Dashboard Streamlit — toda a interface em pt-BR
├── database.py         # Schema SQLite, seeder de dados demo e queries
├── ingestion.py        # Client da API, paginação, parsing de moeda BR
├── ml_engine.py        # IsolationForest + auditor de regras por item
│
├── requirements.txt    # Dependências Python
├── .env.example        # Template da variável de ambiente
└── README.md           # Este arquivo
```

---

## 🧠 Como Funciona a IA

### 1. Engenharia de Features (IsolationForest)

O modelo não usa apenas o valor da transação. Três features são computadas:

| Feature | Lógica | O que detecta |
|---|---|---|
| `value_float` | Valor bruto da transação | Gastos absolutos fora da curva |
| `vendor_frequency` | Quantas vezes o fornecedor aparece no período | Fornecedor desconhecido com gasto alto único |
| `value_vs_vendor_mean` | Razão: valor atual ÷ média histórica do fornecedor | Spike pontual — ex: R$ 200 vira R$ 20.000 |

As três features passam pelo `StandardScaler` antes de entrar no `IsolationForest`.

### 2. Auditor de Regras (Raio-X da Nota Fiscal)

Para transações com itens cadastrados, duas regras determinísticas são aplicadas:

| Regra | Critério | Severidade |
|---|---|---|
| **Superfaturamento** | `preço_unitário > média_mercado × 2` (markup > 100%) | 🔴 CRÍTICO |
| **Fora do Escopo** | Categoria em lista negra: *Bebida Alcoólica, Artigos de Luxo...* | 🟠 ALTO |

### 3. Promoção de Status

Se um item da nota fiscal dispara qualquer regra, a transação-pai é marcada como `🚨 Anomalia` na tabela principal — independente do resultado do Isolation Forest.

---

## 🎭 Cenários de Demonstração

O projeto vem com 3 cenários pré-carregados para demonstração:

| Ref | Fornecedor | Cenário | Veredito |
|---|---|---|---|
| `476259837` | KALUNGA SA | 20x Resma de Papel A4 — R$ 21,11 un. (mercado: R$ 20,00) | ✅ Normal |
| `2026DF801373` | REAL JG FACILITIES | 2x Vassoura Sintética — R$ 19.046,11 un. (mercado: R$ 30,00) | 🚨 +63.387% |
| `476260285` | EASYTECH RR LTDA | 1x Garrafa de Vinho Tinto Importado | 🚨 Fora do escopo |

---

## 🤝 Como Contribuir

Contribuições são muito bem-vindas! Este projeto tem potencial de impacto social real e precisa de mãos.

### Ideias de contribuição

- 🔌 **Novos endpoints** — adicionar suporte a contratos, empenhos, diárias e passagens
- 🧠 **Modelos alternativos** — testar DBSCAN, Autoencoder ou LOF como complemento ao Isolation Forest
- 📊 **Novas visualizações** — mapa geográfico dos gastos, linha do tempo de fornecedor específico
- 🌐 **Internacionalização** — adaptar para outros países com APIs de transparência abertas
- 🧪 **Testes automatizados** — cobertura de testes para `ingestion.py` e `ml_engine.py`
- 📖 **Documentação** — tutoriais, exemplos de uso, guias de interpretação dos resultados

### Fluxo de contribuição

```bash
# 1. Faça um fork do repositório
# 2. Crie uma branch para sua feature
git checkout -b feature/minha-contribuicao

# 3. Faça suas alterações e escreva testes se aplicável
# 4. Commit com mensagem descritiva
git commit -m "feat: adiciona suporte a contratos licitatórios"

# 5. Abra um Pull Request detalhando o que foi feito e por quê
```

Por favor, siga o estilo existente: comentários em inglês, interface em pt-BR, sem dependências desnecessárias.

---

## ⭐ Apoie o Projeto

Se o **Fiscal.AI** foi útil para você — seja para aprender sobre IA, para fiscalizar gastos públicos ou só para se inspirar —, considere:

<div align="center">

### 🌟 [Dar uma estrela no GitHub](https://github.com/douglascarlosmen/fiscal-ai) 🌟

*Estrelas ajudam outros cidadãos e desenvolvedores a encontrar este projeto.*

</div>

Você também pode contribuir de outras formas:

- 🐛 **Reportar um bug** → [Abrir uma issue](https://github.com/douglascarlosmen/fiscal-ai/issues/new?template=bug_report.md)
- 💡 **Sugerir uma feature** → [Abrir um pull request](https://github.com/douglascarlosmen/fiscal-ai/pulls)
- 📢 **Compartilhar** → Poste nas redes sociais com `#FiscalAI` e marque o projeto
- 🎥 **Assistir ao vídeo** → Veja a demonstração completa no YouTube *(link em breve)*

> Cada estrela, cada fork e cada PR é um voto pela transparência pública no Brasil. Obrigado. 🇧🇷

---

## 📋 Roadmap

- [x] Ingestão de Cartões Corporativos (CPGF)
- [x] Ingestão de Despesas do Executivo
- [x] Detecção de anomalias com Isolation Forest
- [x] Drill-down por item de nota fiscal
- [x] Exportação CSV
- [ ] Suporte a contratos e licitações
- [ ] Alertas por e-mail para anomalias recorrentes
- [ ] Comparação histórica entre períodos
- [ ] Deploy em nuvem com autenticação
- [ ] API REST para integração com outros sistemas

---

## ⚠️ Aviso Legal

Os dados utilizados são **públicos**, obtidos diretamente do [Portal da Transparência do Governo Federal](https://portaldatransparencia.gov.br/), operado pela Controladoria-Geral da União (CGU). Este projeto não armazena, vende ou distribui dados pessoais.

As anomalias detectadas pela IA são **indicações estatísticas** para investigação, não acusações. Toda irregularidade deve ser apurada pelos órgãos competentes (CGU, TCU, MPF).

---

## 📄 Licença

Distribuído sob a licença **MIT**. Veja o arquivo [LICENSE](LICENSE) para detalhes.

---

<div align="center">

Feito com ❤️ e indignação construtiva por quem acredita que **dados públicos são poder público**.

**[⬆ Voltar ao topo](#-fiscalai--o-auditor-implacável)**

</div>
