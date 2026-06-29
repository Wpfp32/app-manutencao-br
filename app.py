import psycopg2
import streamlit as st
import pandas as pd
from datetime import date

st.set_page_config(layout="wide")

# Conexão com timeout para evitar o carregamento eterno
@st.cache_resource
def conectar_banco():
    try:
        # Aumentamos o timeout para 5 segundos
        conn = psycopg2.connect(
            st.secrets["DATABASE_URL"], 
            sslmode='require',
            connect_timeout=5
        )
        return conn
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

conn = conectar_banco()

# Se não conectou, para a execução antes de travar a UI
if conn is None:
    st.error("O banco de dados não respondeu. Verifique a URL no Streamlit Cloud.")
    st.stop()

# --- DASHBOARD ---
st.header("Status da Frota")
try:
    with conn.cursor() as cur:
        # Usando aspas triplas para garantir sintaxe SQL correta
        cur.execute("""
            SELECT tag, modelo, tipo_medidor, medidor_ultima_revisao 
            FROM equipamentos
        """)
        dados = cur.fetchall()
        colunas = ["TAG", "Modelo", "Medição", "Ultima Revisão"]
        
    if dados:
        df = pd.DataFrame(dados, columns=colunas)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Banco conectado, mas não há dados cadastrados.")
except Exception as e:
    st.error(f"Erro ao buscar dados: {e}")