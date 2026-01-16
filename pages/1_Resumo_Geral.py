"""
Resumo Geral - Visão consolidada das operações.
"""
import sys
sys.path.append('..')

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from utils.data_loader import carregar_dados_sheets, preparar_dados

st.set_page_config(layout="wide", page_title="Resumo Geral", page_icon="◼")

# Atualiza automaticamente a cada 1 hora
st_autorefresh(interval=60 * 60 * 1000, key="auto_refresh_resumo")

# Estilo para testar atualização: sidebar laranja
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        background-color: #f28c28;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# === FUNÇÕES ===

def criar_pivot_por_operacao(df: pd.DataFrame):
    """Cria pivot table agrupando por operação e status."""
    df_agrupado = df.groupby(["operacao_origem", "status_agrupado"]).agg(
        trip_number=("trip_number", "count")
    ).reset_index()
    
    df_pivot = df_agrupado.pivot_table(
        index="operacao_origem",
        columns="status_agrupado",
        values="trip_number",
        aggfunc="sum",
        fill_value=0
    )
    
    df_pivot["Total"] = df_pivot.sum(axis=1)
    status_cols = [col for col in df_pivot.columns if col != "Total"]
    
    for status in status_cols:
        df_pivot[f"% {status}"] = (df_pivot[status] / df_pivot["Total"] * 100).round(2)
    
    return df_pivot, status_cols


def exibir_metricas(df_pivot: pd.DataFrame, operacao: str, container):
    """Exibe métricas principais de uma operação."""
    if operacao not in df_pivot.index:
        container.warning(f"Sem dados para {operacao}")
        return
    
    total = int(df_pivot.loc[operacao, "Total"])
    fechada = df_pivot.loc[operacao, "% FECHADA"] if "% FECHADA" in df_pivot.columns else 0
    cancelado = df_pivot.loc[operacao, "% CANCELADO"] if "% CANCELADO" in df_pivot.columns else 0
    
    container.metric("Total de Viagens", f"{total:,}".replace(",", "."))
    
    c1, c2 = container.columns(2)
    c1.metric("Fechadas", f"{fechada:.1f}%")
    c2.metric("Canceladas", f"{cancelado:.1f}%", delta=None)


def exibir_tabela_resumo(df_pivot: pd.DataFrame, operacao: str, status_cols: list, container):
    """Exibe tabela resumo de uma operação."""
    if operacao not in df_pivot.index:
        return
    
    dados = []
    for status in status_cols:
        dados.append({
            "Status": status,
            "Quantidade": int(df_pivot.loc[operacao, status]),
            "Percentual": df_pivot.loc[operacao, f"% {status}"]
        })
    
    df_exibir = pd.DataFrame(dados).set_index("Status")
    
    container.dataframe(
        df_exibir.style
            .format({"Quantidade": "{:,.0f}", "Percentual": "{:.2f}%"})
            .background_gradient(cmap='Blues', subset=["Quantidade"]),
        use_container_width=True
    )


def criar_tabela_detalhada_por_grupo(
    df: pd.DataFrame,
    status_cols: list,
    grupo_col: str,
    grupo_label: str
):
    """Cria tabela detalhada por agrupamento."""
    if grupo_col not in df.columns:
        return pd.DataFrame(columns=["Operação", grupo_label]), []

    df_agrupado = df.groupby(["operacao_origem", grupo_col, "status_agrupado"]).agg(
        trip_number=("trip_number", "count")
    ).reset_index()
    
    df_pivot = df_agrupado.pivot_table(
        index=["operacao_origem", grupo_col],
        columns="status_agrupado",
        values="trip_number",
        aggfunc="sum",
        fill_value=0
    ).reset_index()
    
    colunas_status = [col for col in df_pivot.columns if col not in ["operacao_origem", grupo_col]]
    df_pivot["Total"] = df_pivot[colunas_status].sum(axis=1)
    
    for status in colunas_status:
        df_pivot[f"% {status}"] = (df_pivot[status] / df_pivot["Total"] * 100).round(2)

    def normalizar_nome_coluna(nome: str) -> str:
        return (
            nome.strip()
            .lower()
            .replace("_", "")
            .replace(" ", "")
        )

    def obter_coluna(df_base: pd.DataFrame, candidatos: list) -> str | None:
        mapa = {normalizar_nome_coluna(col): col for col in df_base.columns}
        for candidato in candidatos:
            if candidato in mapa:
                return mapa[candidato]
        return None

    col_aderencia = obter_coluna(
        df,
        [
            "aderenciacancelamento",
            "aderenciacancelamentook"
        ]
    )
    col_contagem = obter_coluna(
        df,
        [
            "contagemcancelamentos",
            "contagemcancelamento",
            "qtdcancelamentos",
            "quantidadecancelamentos"
        ]
    )

    if col_aderencia and col_contagem:
        df_cancelamento = df.groupby(["operacao_origem", grupo_col]).agg(
            soma_aderencia_cancelamento=(col_aderencia, "sum"),
            contagem_cancelamentos=(col_contagem, "sum")
        ).reset_index()

        df_cancelamento["%Cancel Nok"] = (
            df_cancelamento["soma_aderencia_cancelamento"]
            / df_cancelamento["contagem_cancelamentos"].replace(0, pd.NA)
        ).fillna(0.0).round(2)

        df_pivot = df_pivot.merge(
            df_cancelamento[["operacao_origem", grupo_col, "%Cancel Nok"]],
            on=["operacao_origem", grupo_col],
            how="left"
        )
        df_pivot["%Cancel Nok"] = df_pivot["%Cancel Nok"].fillna(0.0)
    else:
        df_pivot["%Cancel Nok"] = 0.0

    if "cpt_origin_realized" in df.columns and "status_cpt" in df.columns:
        df_cpt = df[
            df["cpt_origin_realized"].notna() & (df["cpt_origin_realized"] != "")
        ].copy()
        df_cpt_agrupado = df_cpt.groupby(["operacao_origem", grupo_col]).agg(
            cpt_delay=("status_cpt", lambda s: (s == "DELAY").sum()),
            total_trip=("trip_number", "count")
        ).reset_index()

        df_cpt_agrupado["CPT Delay"] = df_cpt_agrupado["cpt_delay"]
        df_cpt_agrupado["CPT Trips"] = df_cpt_agrupado["total_trip"]

        df_cpt_agrupado["% CPT"] = (
            df_cpt_agrupado["cpt_delay"]
            / df_cpt_agrupado["total_trip"].replace(0, pd.NA)
        ).mul(100).fillna(0.0).round(2)

        df_pivot = df_pivot.merge(
            df_cpt_agrupado[["operacao_origem", grupo_col, "% CPT", "CPT Delay", "CPT Trips"]],
            on=["operacao_origem", grupo_col],
            how="left"
        )
        df_pivot["% CPT"] = df_pivot["% CPT"].fillna(0.0)
        df_pivot["CPT Delay"] = df_pivot["CPT Delay"].fillna(0.0)
        df_pivot["CPT Trips"] = df_pivot["CPT Trips"].fillna(0.0)
    else:
        df_pivot["% CPT"] = 0.0
        df_pivot["CPT Delay"] = 0.0
        df_pivot["CPT Trips"] = 0.0

    if "eta_origin_realized" in df.columns and "status_eta" in df.columns:
        df_eta = df[
            df["eta_origin_realized"].notna() & (df["eta_origin_realized"] != "")
        ].copy()
        df_eta_agrupado = df_eta.groupby(["operacao_origem", grupo_col]).agg(
            eta_delay=("status_eta", lambda s: (s == "DELAY").sum()),
            total_trip=("trip_number", "count")
        ).reset_index()

        df_eta_agrupado["% ETA"] = (
            df_eta_agrupado["eta_delay"]
            / df_eta_agrupado["total_trip"].replace(0, pd.NA)
        ).mul(100).fillna(0.0).round(2)

        df_pivot = df_pivot.merge(
            df_eta_agrupado[["operacao_origem", grupo_col, "% ETA"]],
            on=["operacao_origem", grupo_col],
            how="left"
        )
        df_pivot["% ETA"] = df_pivot["% ETA"].fillna(0.0)
    else:
        df_pivot["% ETA"] = 0.0
    
    df_pivot = df_pivot.rename(columns={"operacao_origem": "Operação", grupo_col: grupo_label})
    colunas_pct = [f"% {s}" for s in colunas_status] + ["%Cancel Nok", "% CPT", "% ETA"]
    
    return df_pivot.sort_values(["Operação", grupo_label]), colunas_pct


def criar_tabela_detalhada(df: pd.DataFrame, status_cols: list):
    """Cria tabela detalhada por estação."""
    return criar_tabela_detalhada_por_grupo(df, status_cols, "origin_station_code", "Estação")


# === CARREGAR DADOS ===

df = preparar_dados(carregar_dados_sheets())

# === FILTROS ===
st.sidebar.header("Filtros")
operacoes_disponiveis = sorted(df["operacao_origem"].dropna().unique())
estacoes_disponiveis = sorted(df["origin_station_code"].dropna().unique())

operacao_selecionada = st.sidebar.selectbox("Operação", ["Todas"] + operacoes_disponiveis)
estacao_selecionada = st.sidebar.selectbox("Estação", ["Todas"] + estacoes_disponiveis)

df_filtrado = df.copy()
if operacao_selecionada != "Todas":
    df_filtrado = df_filtrado[df_filtrado["operacao_origem"] == operacao_selecionada]
if estacao_selecionada != "Todas":
    df_filtrado = df_filtrado[df_filtrado["origin_station_code"] == estacao_selecionada]

df_pivot, status_cols = criar_pivot_por_operacao(df_filtrado)

# === INTERFACE ===

st.title("Resumo Geral")
st.caption("Visão consolidada das operações SOC e FMH")

st.divider()

# Métricas principais
col1, col2 = st.columns(2)

with col1:
    st.subheader("SOC")
    exibir_metricas(df_pivot, "SOC", col1)
    exibir_tabela_resumo(df_pivot, "SOC", status_cols, col1)

with col2:
    st.subheader("FMH")
    exibir_metricas(df_pivot, "FMH", col2)
    exibir_tabela_resumo(df_pivot, "FMH", status_cols, col2)

# Tabela detalhada
st.divider()
st.subheader("Detalhamento por Estação")

df_detalhado, colunas_pct = criar_tabela_detalhada(df_filtrado, status_cols)
df_regional, colunas_pct_regional = criar_tabela_detalhada_por_grupo(
    df_filtrado, status_cols, "regional", "Regional"
)

ordem_colunas = [
    "Estação",
    "Total",
    "Created",
    "Assigning",
    "Assigned",
    "cancelado",
    "% cancelado",
    "%Cancel Nok",
    "Arrived",
    "Loading",
    "Departed",
    "Seal",
    "fechada",
    "% fechada",
    "% ETA",
    "CPT Trips",
    "CPT Delay",
    "% CPT",
]

ordem_colunas_regional = [
    "Regional",
    "Total",
    "Created",
    "Assigning",
    "Assigned",
    "cancelado",
    "% cancelado",
    "%Cancel Nok",
    "Arrived",
    "Loading",
    "Departed",
    "Seal",
    "fechada",
    "% fechada",
    "% ETA",
    "CPT Trips",
    "CPT Delay",
    "% CPT",
]

colunas_ordenadas = (
    ["Operação"]
    + [col for col in ordem_colunas if col in df_detalhado.columns]
    + [col for col in df_detalhado.columns if col not in ordem_colunas + ["Operação"]]
)
df_detalhado = df_detalhado[colunas_ordenadas]

colunas_ordenadas_regional = (
    ["Operação"]
    + [col for col in ordem_colunas_regional if col in df_regional.columns]
    + [col for col in df_regional.columns if col not in ordem_colunas_regional + ["Operação"]]
)
df_regional = df_regional[colunas_ordenadas_regional]

format_dict = {"Total": "{:,.0f}"}
for col in df_detalhado.columns:
    if col.startswith("%"):
        format_dict[col] = "{:.2f}%"
    elif col not in ["Operação", "Estação", "Total"]:
        format_dict[col] = "{:,.0f}"

colunas_pct_exibir = [col for col in df_detalhado.columns if col.startswith("%")]
colunas_pct_exibir_regional = [col for col in df_regional.columns if col.startswith("%")]

def exibir_detalhamento_por_regional(
    df_tabela: pd.DataFrame,
    operacao: str,
    height_multiplier: float = 1.0
):
    if "Operação" not in df_tabela.columns or "Regional" not in df_tabela.columns:
        st.info("Coluna 'regional' não encontrada nos dados.")
        return

    df_filtrado = df_tabela[df_tabela["Operação"] == operacao].drop(columns=["Operação"])

    if df_filtrado.empty:
        st.info(f"Sem dados para {operacao} por Regional")
        return

    altura_base = max(1, len(df_filtrado) + 1) * 35
    altura = int(altura_base * height_multiplier)
    st.subheader(f"Detalhamento por Regional - {operacao}")
    st.dataframe(
        df_filtrado.style
            .format(format_dict)
            .background_gradient(cmap="Reds", axis=0, subset=colunas_pct_exibir_regional),
        use_container_width=True,
        hide_index=True,
        height=altura
    )

def exibir_detalhamento_por_operacao(
    df_tabela: pd.DataFrame,
    operacao: str,
    height_multiplier: float = 1.0
):
    df_filtrado = df_tabela[df_tabela["Operação"] == operacao].drop(columns=["Operação"])
    altura_base = max(1, len(df_filtrado) + 1) * 35
    altura = int(altura_base * height_multiplier)
    st.subheader(f"Detalhamento por Estação - {operacao}")
    st.dataframe(
        df_filtrado.style
            .format(format_dict)
            .background_gradient(cmap="Reds", axis=0, subset=colunas_pct_exibir),
        use_container_width=True,
        hide_index=True,
        height=altura
    )

exibir_detalhamento_por_regional(df_regional, "SOC", height_multiplier=1.15)
exibir_detalhamento_por_operacao(df_detalhado, "SOC", height_multiplier=1.15)
exibir_detalhamento_por_operacao(df_detalhado, "FMH")
