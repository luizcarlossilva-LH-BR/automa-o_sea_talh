"""
Módulo para carregamento de dados do Google Sheets.
Centraliza a conexão e cache dos dados.
"""
import gspread
import pandas as pd
import streamlit as st

# URL da planilha Google Sheets
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1t1xG7KSqMEqn1sOw5ZYf6XkZhgCzAj3GG2ohLvaK3oE/edit?gid=1641678056#gid=1641678056"
WORKSHEET_NAME = "db"


@st.cache_data(ttl=300)  # Cache por 5 minutos
def carregar_dados_sheets() -> pd.DataFrame:
    """
    Carrega dados do Google Sheets com cache.
    
    Returns:
        DataFrame com os dados da planilha.
    """
    gc = gspread.service_account(filename='credentials.json')
    planilha = gc.open_by_url(SPREADSHEET_URL)
    aba = planilha.worksheet(WORKSHEET_NAME)
    dados = aba.get_all_records()
    return pd.DataFrame(dados)


def preparar_dados(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara e limpa os dados para análise.
    
    Args:
        df: DataFrame bruto do Google Sheets.
        
    Returns:
        DataFrame com colunas preparadas.
    """
    df = df.copy()
    df["total_orders"] = pd.to_numeric(df["total_orders"], errors="coerce")
    df["operacao_origem"] = df["origin_station_code"].str.split("-").str[0]
    return df
