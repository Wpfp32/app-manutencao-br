import psycopg2
import streamlit as st
import pandas as pd
import warnings
from datetime import date

# Configurações iniciais
warnings.filterwarnings('ignore')
st.set_page_config(page_title="BR Construções", layout="wide")

# Conexão definitiva
@st.cache_resource
def conectar_banco():
    # URL direta para evitar falhas de leitura do secrets no deploy
    url = "postgresql://postgres.iaslrpmmvbvxgrgldpbf:BrConstrucoes2026@aws-1-us-east-1.pooler.supabase.com:6543/postgres"
    try:
        conn = psycopg2.connect(url, sslmode='require')
        conn.autocommit = True
        return conn
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

conn = conectar_banco()

# --- LOGIN SIMPLIFICADO ---
if "logado" not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.title("🚜 BR Construções - Acesso")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if usuario == "gestor" and senha == "admin":
            st.session_state.logado = True
            st.rerun()
        else:
            st.error("Credenciais inválidas.")
else:
    st.sidebar.title("Navegação")
    menu = st.sidebar.radio("Menu", ["Dashboard", "Cadastrar Máquina"])
    
    if menu == "Dashboard":
        st.header("Status da Frota")
        if conn:
            try:
                # Consulta otimizada
                query = "SELECT tag, modelo, tipo_medidor, medidor_ultima_revisao FROM equipamentos"
                df = pd.read_sql_query(query, conn)
                
                if not df.empty:
                    st.dataframe(df, use_container_width=True)
                else:
                    st.warning("Tabela de equipamentos vazia. Cadastre algo primeiro.")
            except Exception as e:
                st.error(f"Erro ao buscar dados: {e}")
        else:
            st.error("Sem conexão com o banco de dados.")

    elif menu == "Cadastrar Máquina":
        st.header("Novo Equipamento")
        with st.form("cadastro"):
            tag = st.text_input("TAG")
            modelo = st.text_input("Modelo")
            tipo = st.selectbox("Tipo", ["Horímetro", "Hodômetro"])
            submit = st.form_submit_button("Salvar no Banco")
            
            if submit and tag:
                try:
                    with conn.cursor() as cur:
                        cur.execute("INSERT INTO equipamentos (tag, modelo, tipo_medidor, medidor_ultima_revisao, data_ultima_revisao) VALUES (%s, %s, %s, %s, %s)", 
                                    (tag.upper(), modelo, tipo, 0.0, date.today()))
                    st.success(f"Equipamento {tag} salvo!")
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")