"""
Aderência - Análise de ETA e CPT.
"""
import sys
sys.path.append('..')

import pandas as pd
import streamlit as st
from utils.data_loader import carregar_dados_sheets, preparar_dados

st.set_page_config(layout="wide", page_title="Aderência", page_icon="◼")


# === FUNÇÕES ===

def calcular_aderencia(df: pd.DataFrame, coluna_filtro: str, coluna_status: str, nome_indicador: str) -> pd.DataFrame:
    """Calcula percentual de aderência (ON TIME) por estação."""
    df_filtrado = df[df[coluna_filtro] != ""].copy()
    
    df_agrupado = df_filtrado.groupby(["origin_station_code", "operacao_origem", coluna_status]).agg(
        trip_number=("trip_number", "count")
    ).reset_index()
    
    df_pivot = df_agrupado.pivot_table(
        index=["origin_station_code", "operacao_origem"],
        columns=coluna_status,
        values="trip_number",
        aggfunc="sum",
        fill_value=0
    ).reset_index()
    
    colunas_status = [col for col in df_pivot.columns if col not in ["origin_station_code", "operacao_origem"]]
    df_pivot["total_trip"] = df_pivot[colunas_status].sum(axis=1)
    
    if "ON TIME" in df_pivot.columns:
        df_pivot[nome_indicador] = (df_pivot["ON TIME"] / df_pivot["total_trip"] * 100).round(2)
    else:
        df_pivot[nome_indicador] = 0.0
    
    return df_pivot


def exibir_tabela_aderencia(df: pd.DataFrame, operacao: str, col_indicador: str, nome_indicador: str, container):
    """Exibe tabela de aderência (verde = bom, vermelho = ruim)."""
    df_filtrado = df[df["operacao_origem"] == operacao].copy()
    
    if df_filtrado.empty:
        container.info(f"Sem dados para {operacao}")
        return
    
    df_tabela = df_filtrado[["origin_station_code", "total_trip", col_indicador]].copy()
    df_tabela = df_tabela.sort_values(col_indicador, ascending=True)
    df_tabela.columns = ["Estação", "Viagens", nome_indicador]
    df_tabela = df_tabela.set_index("Estação")
    
    container.dataframe(
        df_tabela.style
            .format({"Viagens": "{:,.0f}", nome_indicador: "{:.2f}%"})
            .background_gradient(cmap='RdYlGn', axis=0, subset=[nome_indicador]),
        use_container_width=True
    )


def calcular_media_operacao(df: pd.DataFrame, col_indicador: str, operacao: str) -> float:
    """Calcula média de aderência de uma operação."""
    df_op = df[df["operacao_origem"] == operacao]
    if df_op.empty or col_indicador not in df_op.columns:
        return 0.0
    return df_op[col_indicador].mean()


# === CARREGAR DADOS ===

df = preparar_dados(carregar_dados_sheets())

# === INTERFACE ===

st.title("Aderência")
st.caption("Análise de pontualidade ETA e CPT | Quanto maior, melhor")

# ETA
st.divider()
st.subheader("ETA Origem")

df_eta = calcular_aderencia(df, "eta_origin_realized", "status_eta", "%_eta_on_time")

col1, col2 = st.columns(2)

with col1:
    media_soc = calcular_media_operacao(df_eta, "%_eta_on_time", "SOC")
    st.metric("SOC - Média ETA On Time", f"{media_soc:.1f}%")
    exibir_tabela_aderencia(df_eta, "SOC", "%_eta_on_time", "% On Time", col1)

with col2:
    media_fmh = calcular_media_operacao(df_eta, "%_eta_on_time", "FMH")
    st.metric("FMH - Média ETA On Time", f"{media_fmh:.1f}%")
    exibir_tabela_aderencia(df_eta, "FMH", "%_eta_on_time", "% On Time", col2)

# CPT
st.divider()
st.subheader("CPT Origem")

df_cpt = calcular_aderencia(df, "cpt_origin_realized", "status_cpt", "%_cpt_on_time")

col3, col4 = st.columns(2)

with col3:
    media_soc_cpt = calcular_media_operacao(df_cpt, "%_cpt_on_time", "SOC")
    st.metric("SOC - Média CPT On Time", f"{media_soc_cpt:.1f}%")
    exibir_tabela_aderencia(df_cpt, "SOC", "%_cpt_on_time", "% On Time", col3)

with col4:
    media_fmh_cpt = calcular_media_operacao(df_cpt, "%_cpt_on_time", "FMH")
    st.metric("FMH - Média CPT On Time", f"{media_fmh_cpt:.1f}%")
    exibir_tabela_aderencia(df_cpt, "FMH", "%_cpt_on_time", "% On Time", col4)
