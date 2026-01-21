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

# Atualiza automaticamente a cada 30 minutos
st_autorefresh(interval=30 * 60 * 1000, key="auto_refresh_resumo")

# Ajusta fonte das tabelas para melhorar legibilidade no print
st.markdown(
    """
    <style>
    [data-testid="stDataFrame"] {
        font-size: 14px;
    }
    [data-testid="stDataFrame"] thead tr th,
    [data-testid="stDataFrame"] tbody tr td {
        font-size: 14px !important;
        line-height: 1.2;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Remove sidebar para maximizar area util
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {display: none;}
    [data-testid="stSidebarNav"] {display: none;}
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

    df_base = df.copy()
    df_base[grupo_col] = (
        df_base[grupo_col]
        .fillna("Sem Regional")
        .replace("", "Sem Regional")
        .replace("#N/A", "Sem Regional") # Consolidando erros comuns
    )
    # Se o usuário quer Ocultar visualmente a linha especifica #N/A, talvez seja melhor garantir que ela não exista.
    # Mas se #N/A é lixo, melhor filtrar.
    # Vou filtrar explicitamente linhas que ficaram como #N/A se a substituição acima não pegou, ou melhor:
    # O user pediu para ocultar a linha "#N/A". Se ela está aparecendo, é porque é uma string "#N/A".
    # Se eu substituir por "Sem Regional", ela soma no "Sem Regional".
    # Se eu substituir por None e dar dropna, ela some.
    # Assumindo que o usuário não quer ver essa sujeira.
    
    # OPÇÃO MELHOR: Filtrar antes.
    df_base = df_base[df_base[grupo_col] != "#N/A"]

    df_agrupado = df_base.groupby(["operacao_origem", grupo_col, "status_agrupado"]).agg(
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
        df_base,
        [
            "aderenciacancelamento",
            "aderenciacancelamentook"
        ]
    )
    col_contagem = obter_coluna(
        df_base,
        [
            "contagemcancelamentos",
            "contagemcancelamento",
            "qtdcancelamentos",
            "quantidadecancelamentos"
        ]
    )

    if col_aderencia and col_contagem:
        df_cancelamento = df_base.groupby(["operacao_origem", grupo_col]).agg(
            soma_aderencia_cancelamento=(col_aderencia, "sum"),
            contagem_cancelamentos=(col_contagem, "sum")
        ).reset_index()

        df_cancelamento["%Cancel Nok"] = (
            df_cancelamento["soma_aderencia_cancelamento"]
            / df_cancelamento["contagem_cancelamentos"].replace(0, pd.NA)
        ).fillna(0.0).round(2)

        df_pivot = df_pivot.merge(
            df_cancelamento[["operacao_origem", grupo_col, "%Cancel Nok", "soma_aderencia_cancelamento", "contagem_cancelamentos"]],
            on=["operacao_origem", grupo_col],
            how="left"
        )
        df_pivot["%Cancel Nok"] = df_pivot["%Cancel Nok"].fillna(0.0)
        df_pivot["soma_aderencia_cancelamento"] = df_pivot["soma_aderencia_cancelamento"].fillna(0)
        df_pivot["contagem_cancelamentos"] = df_pivot["contagem_cancelamentos"].fillna(0)
    else:
        df_pivot["%Cancel Nok"] = 0.0
        df_pivot["soma_aderencia_cancelamento"] = 0
        df_pivot["contagem_cancelamentos"] = 0

    if "cpt_origin_realized" in df_base.columns and "status_cpt" in df_base.columns:
        df_cpt = df_base[
            df_base["cpt_origin_realized"].notna() & (df_base["cpt_origin_realized"] != "")
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

    if "eta_origin_realized" in df_base.columns and "status_eta" in df_base.columns:
        df_eta = df_base[
            df_base["eta_origin_realized"].notna() & (df_base["eta_origin_realized"] != "")
        ].copy()
        df_eta_agrupado = df_eta.groupby(["operacao_origem", grupo_col]).agg(
            eta_delay=("status_eta", lambda s: (s == "DELAY").sum()),
            total_trip=("trip_number", "count")
        ).reset_index()

        df_eta_agrupado["ETA Delay"] = df_eta_agrupado["eta_delay"]
        df_eta_agrupado["ETA Trips"] = df_eta_agrupado["total_trip"]

        df_eta_agrupado["% ETA"] = (
            df_eta_agrupado["eta_delay"]
            / df_eta_agrupado["total_trip"].replace(0, pd.NA)
        ).mul(100).fillna(0.0).round(2)

        df_pivot = df_pivot.merge(
            df_eta_agrupado[["operacao_origem", grupo_col, "% ETA", "ETA Delay", "ETA Trips"]],
            on=["operacao_origem", grupo_col],
            how="left"
        )
        df_pivot["% ETA"] = df_pivot["% ETA"].fillna(0.0)
        df_pivot["ETA Delay"] = df_pivot["ETA Delay"].fillna(0.0)
        df_pivot["ETA Trips"] = df_pivot["ETA Trips"].fillna(0.0)
    else:
        df_pivot["% ETA"] = 0.0
        df_pivot["ETA Delay"] = 0.0
        df_pivot["ETA Trips"] = 0.0
    
    df_pivot = df_pivot.rename(columns={"operacao_origem": "Operação", grupo_col: grupo_label})
    colunas_pct = [f"% {s}" for s in colunas_status] + ["%Cancel Nok", "% CPT", "% ETA"]
    
    return df_pivot.sort_values(["Operação", grupo_label]), colunas_pct


def criar_tabela_detalhada(df: pd.DataFrame, status_cols: list):
    """Cria tabela detalhada por estação."""
    return criar_tabela_detalhada_por_grupo(df, status_cols, "origin_station_code", "Estação")


# === CARREGAR DADOS ===

df = preparar_dados(carregar_dados_sheets())

# === FILTROS ===
operacoes_disponiveis = sorted(df["operacao_origem"].dropna().unique())
estacoes_disponiveis = sorted(df["origin_station_code"].dropna().unique())
regionais_disponiveis = (
    sorted(df["regional"].dropna().unique())
    if "regional" in df.columns
    else []
)

with st.expander("Filtros", expanded=False):
    f1, f2, f3 = st.columns(3)
    operacao_selecionada = f1.selectbox("Operação", ["Todas"] + operacoes_disponiveis)
    estacao_selecionada = f2.selectbox("Estação", ["Todas"] + estacoes_disponiveis)
    if regionais_disponiveis:
        regional_selecionada = f3.selectbox("Regional", ["Todas"] + regionais_disponiveis)
    else:
        regional_selecionada = "Todas"

df_filtrado = df.copy()
if operacao_selecionada != "Todas":
    df_filtrado = df_filtrado[df_filtrado["operacao_origem"] == operacao_selecionada]
if estacao_selecionada != "Todas":
    df_filtrado = df_filtrado[df_filtrado["origin_station_code"] == estacao_selecionada]
if regional_selecionada != "Todas" and "regional" in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado["regional"] == regional_selecionada]

df_pivot, status_cols = criar_pivot_por_operacao(df_filtrado)

# === INTERFACE ===

st.title("Resumo Geral")
st.caption("Visão consolidada das operações SOC e FMH")

# Tabela detalhada
st.divider()
st.subheader("Detalhamento por Estação")

df_detalhado, colunas_pct = criar_tabela_detalhada(df_filtrado, status_cols)
df_regional, colunas_pct_regional = criar_tabela_detalhada_por_grupo(
    df_filtrado, status_cols, "regional", "Regional"
)

colunas_excluir = [
    "% Created",
    "% Assigning",
    "% Assigned",
    "% Arrived",
    "% Loading",
    "% Departed",
    "% Seal",
    "% fechada",
    "% Unseal",
    "",
    "%",
]

ordem_colunas = [
    "Estação",
    "Total",
    "Created",
    "Assigning",
    "Assigned",
    "Arrived",
    "Loading",
    "Departed",
    "Seal",
    "fechada",
    "Cancelled",
    "No show",
    "% No show",
    "%cancelado",
    "%Cancel Nok",
    "% fechada",
    "% ETA",
    "ETA Trips",
    "ETA Delay",
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
    "Arrived",
    "Loading",
    "Departed",
    "Seal",
    "fechada",
    "No show",
    "% No show",
    "Cancelled",
    "%cancelado",
    "%Cancel Nok",
    "% fechada",
    "% ETA",
    "ETA Trips",
    "ETA Delay",
    "CPT Trips",
    "CPT Delay",
    "% CPT",
    "soma_aderencia_cancelamento",
    "contagem_cancelamentos",
]

def normalizar_coluna_exibicao(nome: str) -> str:
    return (
        nome.strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("%", "pct")
    )

def ordenar_colunas(df_base: pd.DataFrame, ordem: list) -> list:
    mapa = {normalizar_coluna_exibicao(col): col for col in df_base.columns}
    colunas = []
    for col in ordem:
        chave = normalizar_coluna_exibicao(col)
        if chave in mapa:
            colunas.append(mapa[chave])
    return colunas

colunas_ordenadas = ["Operação"] + ordenar_colunas(df_detalhado, ordem_colunas)
df_detalhado = df_detalhado[colunas_ordenadas]

colunas_ordenadas_regional = ["Operação"] + ordenar_colunas(
    df_regional, ordem_colunas_regional
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

    if operacao:
        df_filtrado = df_tabela[df_tabela["Operação"] == operacao].drop(columns=["Operação"])
        titulo_operacao = operacao
    else:
        # Agrupa por Regional somando todas as operações
        colunas_num = df_tabela.select_dtypes(include="number").columns
        
        # Garante que as colunas brutas de cancelamento estejam presentes para soma
        cols_extras = ["soma_aderencia_cancelamento", "contagem_cancelamentos"]
        for col in cols_extras:
            if col not in colunas_num and col in df_tabela.columns:
                 colunas_num = colunas_num.append(pd.Index([col]))

        df_filtrado = (
            df_tabela.groupby("Regional", as_index=False)[colunas_num]
            .sum()
        )
        
        # Recalcula as porcentagens baseadas nos totais somados
        # 1. Porcentagens de status (Created, Assigned, etc.)
        for col_pct in colunas_pct_exibir_regional:
             col_status = col_pct.replace("% ", "")
             if col_status in df_filtrado.columns and "Total" in df_filtrado.columns:
                 df_filtrado[col_pct] = (df_filtrado[col_status] / df_filtrado["Total"] * 100).fillna(0).round(2)
        
        # 2. Porcentagens específicas (CPT, ETA, Cancel)
        if "CPT Delay" in df_filtrado.columns and "CPT Trips" in df_filtrado.columns:
             df_filtrado["% CPT"] = (df_filtrado["CPT Delay"] / df_filtrado["CPT Trips"].replace(0, pd.NA)).mul(100).fillna(0.0).round(2)
             
        if "ETA Delay" in df_filtrado.columns and "ETA Trips" in df_filtrado.columns:
             df_filtrado["% ETA"] = (df_filtrado["ETA Delay"] / df_filtrado["ETA Trips"].replace(0, pd.NA)).mul(100).fillna(0.0).round(2)

        if "soma_aderencia_cancelamento" in df_filtrado.columns and "contagem_cancelamentos" in df_filtrado.columns:
             df_filtrado["%Cancel Nok"] = (df_filtrado["soma_aderencia_cancelamento"] / df_filtrado["contagem_cancelamentos"].replace(0, pd.NA)).mul(100).fillna(0.0).round(2)
        
        # Remove colunas auxiliares se desejar limpar a visualização
        cols_drop = ["soma_aderencia_cancelamento", "contagem_cancelamentos"]
        df_filtrado = df_filtrado.drop(columns=[c for c in cols_drop if c in df_filtrado.columns])

        titulo_operacao = "Todas"

    if df_filtrado.empty:
        st.info(f"Sem dados para {operacao} por Regional")
        return

    altura_base = max(1, len(df_filtrado) + 1) * 35
    altura = int(altura_base * height_multiplier)
    st.subheader(f"Detalhamento por Regional - {titulo_operacao}")
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
    height_multiplier: float = 1.0,
    ordenar_total_desc: bool = False
):
    df_filtrado = df_tabela[df_tabela["Operação"] == operacao].drop(columns=["Operação"])
    if ordenar_total_desc and "Total" in df_filtrado.columns:
        df_filtrado = df_filtrado.sort_values("Total", ascending=False)
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

exibir_detalhamento_por_regional(df_regional, "", height_multiplier=1)
exibir_detalhamento_por_operacao(df_detalhado, "SOC", height_multiplier=1)
exibir_detalhamento_por_operacao(df_detalhado, "FMH", ordenar_total_desc=True)
