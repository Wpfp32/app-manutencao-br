import psycopg2
import streamlit as st
import pandas as pd
from datetime import date
import warnings

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
        else: st.error("Credenciais inválidas.")
else:
    st.sidebar.title("Navegação")
    menu = st.sidebar.radio("Menu", ["Dashboard de Revisões", "Cadastrar Máquina", "Registrar Manutenção (Dar Baixa)"])
    
    if menu == "Dashboard de Revisões":
        st.header("Status da Frota")
        query = """SELECT tag, modelo, tipo_medidor, medidor_ultima_revisao FROM equipamentos"""
        df = pd.read_sql_query(query, conn)
        st.dataframe(df, use_container_width=True)

    elif menu == "Cadastrar Máquina":
        st.header("Cadastrar Novo Equipamento")
        with st.form("cadastro"):
            tag = st.text_input("TAG").upper()
            modelo = st.text_input("Modelo")
            tipo = st.selectbox("Tipo de Medição", ["Horímetro", "Hodômetro"])
            medidor_base = st.number_input("Valor na Última Revisão", min_value=0.0)
            data_base = st.date_input("Data da Última Revisão")
            if st.form_submit_button("Salvar no Banco"):
                with conn.cursor() as cur:
                    cur.execute("""INSERT INTO equipamentos (tag, modelo, tipo_medidor, medidor_ultima_revisao, data_ultima_revisao) VALUES (%s, %s, %s, %s, %s)""", 
                                (tag, modelo, tipo, medidor_base, data_base))
                st.success(f"Equipamento {tag} cadastrado!")

    elif menu == "Registrar Manutenção (Dar Baixa)":
        st.header("Registrar Manutenção")
        with conn.cursor() as cur:
            cur.execute("SELECT tag FROM equipamentos")
            tags = [r[0] for r in cur.fetchall()]
        
        tag_sel = st.selectbox("Selecione a Máquina", tags)
        novo_valor = st.number_input("Valor atual no medidor", min_value=0.0)
        data_manut = st.date_input("Data da Manutenção")
        
        if st.button("Confirmar Baixa"):
            with conn.cursor() as cur:
                cur.execute("UPDATE equipamentos SET medidor_ultima_revisao = %s, data_ultima_revisao = %s WHERE tag = %s", 
                            (novo_valor, data_manut, tag_sel))
                cur.execute("INSERT INTO historico_manutencoes (tag_equipamento, data_manutencao, valor_execucao) VALUES (%s, %s, %s)", 
                            (tag_sel, data_manut, novo_valor))
            st.success("Revisão registrada com sucesso!")