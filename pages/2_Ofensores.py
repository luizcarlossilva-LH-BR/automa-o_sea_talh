"""
Ofensores - Análise de indicadores negativos por estação.
"""
import sys
sys.path.append('..')

import pandas as pd
import streamlit as st
from utils.data_loader import carregar_dados_sheets, preparar_dados

st.set_page_config(layout="wide", page_title="Ofensores", page_icon="◼")

# Indicadores negativos (quanto maior, pior)
INDICADORES = {
    "%_cancelado": {"nome": "Cancelado", "descricao": "Viagens canceladas"},
    "%_no_show": {"nome": "No Show", "descricao": "Viagens com no show"},
    "%_infrutifera": {"nome": "Infrutífera", "descricao": "Viagens infrutíferas"},
    "%_nao_consumida": {"nome": "Não Consumida", "descricao": "Viagens não consumidas"}
}


# === FUNÇÕES ===

def criar_pivot_ofensores(df: pd.DataFrame) -> pd.DataFrame:
    """Cria pivot table com indicadores por estação."""
    df_agrupado = df.groupby(["origin_station_code", "operacao_origem", "status_agrupado"]).agg(
        trip_number=("trip_number", "count")
    ).reset_index()
    
    df_pivot = df_agrupado.pivot_table(
        index=["origin_station_code", "operacao_origem"],
        columns="status_agrupado",
        values="trip_number",
        aggfunc="sum",
        fill_value=0
    )
    
    df_pivot.columns = [col if isinstance(col, str) else col for col in df_pivot.columns]
    df_pivot["total_trip"] = df_pivot.sum(axis=1)
    
    mapeamento = {
        "CANCELADO": "%_cancelado",
        "NO SHOW": "%_no_show",
        "INFRUTÍFERA": "%_infrutifera",
        "NÃO CONSUMIDA": "%_nao_consumida",
        "FECHADA": "%_fechada"
    }
    
    for status, col_pct in mapeamento.items():
        if status in df_pivot.columns:
            df_pivot[col_pct] = (df_pivot[status] / df_pivot["total_trip"] * 100).round(2)
        else:
            df_pivot[col_pct] = 0.0
    
    return df_pivot.reset_index()


def exibir_tabela_indicador(df: pd.DataFrame, operacao: str, col_indicador: str, info: dict, container):
    """Exibe tabela de um indicador específico."""
    df_filtrado = df[df["operacao_origem"] == operacao].copy()
    
    if df_filtrado.empty:
        container.info(f"Sem dados para {operacao}")
        return
    
    df_tabela = df_filtrado[["origin_station_code", "total_trip", col_indicador]].copy()
    df_tabela = df_tabela.sort_values(col_indicador, ascending=False)
    df_tabela.columns = ["Estação", "Viagens", info["nome"]]
    df_tabela = df_tabela.set_index("Estação")
    
    container.caption(info["descricao"])
    container.dataframe(
        df_tabela.style
            .format({"Viagens": "{:,.0f}", info["nome"]: "{:.2f}%"})
            .background_gradient(cmap='OrRd', axis=0, subset=[info["nome"]]),
        use_container_width=True
    )


# === CARREGAR DADOS ===

df = preparar_dados(carregar_dados_sheets())
df_pivot = criar_pivot_ofensores(df)

# === INTERFACE ===

st.title("Ofensores")
st.caption("Indicadores negativos por estação | Ordenado do maior para o menor")

# SOC
st.divider()
st.subheader("SOC")

cols_soc = st.columns(4)
for i, (col_id, info) in enumerate(INDICADORES.items()):
    with cols_soc[i]:
        st.markdown(f"**{info['nome']}**")
        exibir_tabela_indicador(df_pivot, "SOC", col_id, info, cols_soc[i])

# FMH
st.divider()
st.subheader("FMH")

cols_fmh = st.columns(4)
for i, (col_id, info) in enumerate(INDICADORES.items()):
    with cols_fmh[i]:
        st.markdown(f"**{info['nome']}**")
        exibir_tabela_indicador(df_pivot, "FMH", col_id, info, cols_fmh[i])

# Tabela completa
st.divider()
st.subheader("Visão Consolidada")

colunas_exibir = ["origin_station_code", "operacao_origem", "total_trip"] + list(INDICADORES.keys())
df_completo = df_pivot[colunas_exibir].copy()
df_completo.columns = ["Estação", "Operação", "Total"] + [info["nome"] for info in INDICADORES.values()]

format_dict = {"Total": "{:,.0f}"}
for info in INDICADORES.values():
    format_dict[info["nome"]] = "{:.2f}%"

st.dataframe(
    df_completo.style
        .format(format_dict)
        .background_gradient(cmap='OrRd', axis=0, subset=[info["nome"] for info in INDICADORES.values()]),
    use_container_width=True,
    hide_index=True
)
