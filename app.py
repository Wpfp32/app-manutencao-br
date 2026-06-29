import psycopg2
import streamlit as st
import pandas as pd
import warnings
from datetime import date

warnings.filterwarnings('ignore')
st.set_page_config(page_title="BR Construções", layout="wide")

@st.cache_resource
def conectar_banco():
    url = "postgresql://postgres.iaslrpmmvbvxgrgldpbf:BrConstrucoes2026@aws-1-us-east-1.pooler.supabase.com:6543/postgres"
    return psycopg2.connect(url, sslmode='require')

conn = conectar_banco()

# --- LOGIN ---
if "logado" not in st.session_state: st.session_state.logado = False
if not st.session_state.logado:
    st.title("🚜 BR Construções - Acesso")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if usuario == "gestor" and senha == "admin":
            st.session_state.logado = True; st.rerun()
        else:
            st.error("Credenciais inválidas.")
else:
    st.sidebar.title("Navegação")
    menu = st.sidebar.radio("Menu", ["Dashboard", "Cadastrar Máquina"])
    
    if menu == "Dashboard":
        st.header("Status da Frota")
        # Query simplificada e sem aspas que causam erro
        query = "SELECT tag, modelo, tipo_medidor, medidor_ultima_revisao FROM equipamentos"
        df = pd.read_sql_query(query, conn)
        st.dataframe(df, use_container_width=True)

    elif menu == "Cadastrar Máquina":
        st.header("Novo Equipamento")
        with st.form("cadastro"):
            tag = st.text_input("TAG")
            modelo = st.text_input("Modelo")
            tipo = st.selectbox("Tipo", ["Horímetro", "Hodômetro"])
            if st.form_submit_button("Salvar"):
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO equipamentos (tag, modelo, tipo_medidor, medidor_ultima_revisao, data_ultima_revisao) VALUES (%s, %s, %s, %s, %s)", 
                                (tag.upper(), modelo, tipo, 0.0, date.today()))
                st.success("Salvo!")