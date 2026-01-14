"""
Página inicial - Análise de dados do Spotify.
"""
import streamlit as st
import pandas as pd

st.set_page_config(layout="wide", page_title="Spotify", page_icon="◼")

st.title("Análise de Streams")
st.caption("Dados do Spotify")


@st.cache_data
def carregar_dados():
    """Carrega dados do Spotify."""
    return pd.read_csv("01 Spotify.csv")


df = carregar_dados()

# Top músicas
st.subheader("Top Músicas")
st.caption("Músicas com mais de 1 bilhão de streams")

df_top = df[df["Stream"] > 1_000_000_000]
st.dataframe(df_top, use_container_width=True, hide_index=True)

# Análise por artista
st.divider()
st.subheader("Por Artista")

artistas = df["Artist"].value_counts().index.tolist()
artista = st.selectbox("Selecione um artista", artistas)

df_artista = df[df["Artist"] == artista].copy()
df_artista = df_artista.set_index("Track")

if st.checkbox("Exibir gráfico"):
    st.bar_chart(df_artista["Stream"])
else:
    st.dataframe(df_artista, use_container_width=True)
