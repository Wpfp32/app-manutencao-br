import psycopg2
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
import math
import io
from dateutil.relativedelta import relativedelta
import warnings

warnings.filterwarnings('ignore')

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Manutenção | BR Construções", page_icon="🚜", layout="wide")

# --- BANCO DE DADOS (CONEXÃO SEGURA VIA SECRETS) ---
@st.cache_resource
def conectar_banco():
    conn = psycopg2.connect(st.secrets["DATABASE_URL"])
    conn.autocommit = True 
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipamentos (
            id SERIAL PRIMARY KEY,
            tag TEXT UNIQUE,
            modelo TEXT,
            tipo_medidor TEXT, 
            medidor_ultima_revisao REAL,
            data_ultima_revisao DATE,
            tipo_ultima_revisao INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leituras (
            id SERIAL PRIMARY KEY,
            tag_equipamento TEXT,
            data_leitura DATE,
            valor_medidor REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico_manutencoes (
            id SERIAL PRIMARY KEY,
            tag_equipamento TEXT,
            data_manutencao DATE,
            valor_execucao REAL,
            tipo_revisao TEXT
        )
    ''')
    return conn

conn = conectar_banco()

# --- GERENCIAMENTO DE SESSÃO (LOGIN) ---
if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.perfil = ""

if not st.session_state.logado:
    st.title("🚜 BR Construções - Portal de Manutenção")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar", use_container_width=True):
            if usuario == "operador" and senha == "123":
                st.session_state.logado = True
                st.session_state.perfil = "Operador"
                st.rerun()
            elif usuario == "gestor" and senha == "admin":
                st.session_state.logado = True
                st.session_state.perfil = "Gestão"
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
else:
    # --- NAVEGAÇÃO LATERAL ---
    st.sidebar.title("🚜 BR Construções")
    st.sidebar.write(f"👤 Logado como: **{st.session_state.perfil}**")
    if st.sidebar.button("Sair"):
        st.session_state.logado = False
        st.rerun()
    
    opcoes = ["Apontamento Diário"] if st.session_state.perfil == "Operador" else ["Dashboard de Revisões", "Apontamento Diário", "Upload em Lote (Offline)", "Registrar Manutenção (Dar Baixa)", "Cadastrar Máquina"]
    menu = st.sidebar.radio("Navegação", opcoes)

    # --- TELA: APONTAMENTO ---
    if menu == "Apontamento Diário":
        st.header("Lançamento de Uso Diário")
        cursor = conn.cursor()
        cursor.execute("SELECT tag, tipo_medidor FROM equipamentos ORDER BY tag")
        equipamentos = cursor.fetchall()
        
        if equipamentos:
            tag_sel = st.selectbox("Selecione o Equipamento", [e[0] for e in equipamentos])
            tipo = next(e[1] for e in equipamentos if e[0] == tag_sel)
            unid = "h" if tipo == "Horímetro" else "km"
            
            cursor.execute("SELECT COALESCE(MAX(valor_medidor), 0) FROM leituras WHERE tag_equipamento = %s", (tag_sel,))
            ultimo = cursor.fetchone()[0]
            st.info(f"Última leitura: {ultimo} {unid}")
            
            val = st.number_input(f"Novo valor ({unid})", min_value=float(ultimo), value=float(ultimo))
            if st.button("Registrar"):
                cursor.execute("INSERT INTO leituras (tag_equipamento, data_leitura, valor_medidor) VALUES (%s, %s, %s)", (tag_sel, date.today(), val))
                st.success("Registrado!")
        else: st.warning("Cadastre uma máquina primeiro.")

    # --- TELA: DASHBOARD (GESTÃO) ---
    elif menu == "Dashboard de Revisões":
        st.header("Status da Frota")
        query = """SELECT e.tag, e.modelo, e.tipo_medidor, e.medidor_ultima_revisao, COALESCE(MAX(l.valor_medidor), 0) as atual 
                   FROM equipamentos e LEFT JOIN leituras l ON e.tag = l.tag_equipamento GROUP BY e.tag, e.modelo, e.tipo_medidor, e.medidor_ultima_revisao"""
        df = pd.read_sql_query(query, conn)
        st.dataframe(df, use_container_width=True)
        with st.expander("Histórico de Manutenções"):
            df_hist = pd.read_sql_query("SELECT * FROM historico_manutencoes ORDER BY id DESC", conn)
            st.dataframe(df_hist)

    # --- TELA: REGISTRAR MANUTENÇÃO ---
    elif menu == "Registrar Manutenção (Dar Baixa)":
        st.header("Dar Baixa em Revisão")
        cursor = conn.cursor()
        cursor.execute("SELECT tag FROM equipamentos")
        tags = [r[0] for r in cursor.fetchall()]
        tag_sel = st.selectbox("Máquina", tags)
        val = st.number_input("Valor de fechamento da revisão")
        if st.button("Confirmar Baixa"):
            cursor.execute("UPDATE equipamentos SET medidor_ultima_revisao = %s WHERE tag = %s", (val, tag_sel))
            cursor.execute("INSERT INTO historico_manutencoes (tag_equipamento, data_manutancao, valor_execucao, tipo_revisao) VALUES (%s, %s, %s, %s)", 
                           (tag_sel, date.today(), val, "Revisão Periódica"))
            st.success("Baixa realizada!")

    # --- TELA: CADASTRO ---
    elif menu == "Cadastrar Máquina":
        st.header("Novo Ativo")
        with st.form("cad"):
            tag = st.text_input("TAG").upper()
            mod = st.text_input("Modelo")
            tipo = st.selectbox("Medição", ["Horímetro", "Hodômetro"])
            if st.form_submit_button("Salvar"):
                cursor = conn.cursor()
                cursor.execute("INSERT INTO equipamentos (tag, modelo, tipo_medidor, medidor_ultima_revisao) VALUES (%s, %s, %s, %s)", (tag, mod, tipo, 0.0))
                st.success("Salvo!")

    # --- UPLOAD EM LOTE ---
    elif menu == "Upload em Lote (Offline)":
        st.header("Importação Lote")
        st.file_uploader("Upload Planilha", type=["xlsx"])