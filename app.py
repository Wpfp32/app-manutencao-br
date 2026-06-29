import psycopg2
import streamlit as st
import pandas as pd
import warnings
from datetime import date

warnings.filterwarnings('ignore')
st.set_page_config(page_title="BR Construções", layout="wide")

@st.cache_resource
def conectar_banco():
    # URL injetada via Secrets no Streamlit Cloud
    # Certifique-se de que DATABASE_URL esteja configurada nas "Settings > Secrets" do Streamlit Cloud
    return psycopg2.connect(st.secrets["DATABASE_URL"], sslmode='require')

try:
    conn = conectar_banco()
except Exception as e:
    st.error(f"Erro de conexão: {e}")
    st.stop()

# --- LOGIN ---
if "logado" not in st.session_state: st.session_state.logado = False
if not st.session_state.logado:
    st.title("🚜 BR Construções - Acesso")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if usuario == "gestor" and senha == "admin":
                st.session_state.logado = True; st.rerun()
            else:
                st.error("Credenciais inválidas.")
else:
    st.sidebar.title("Navegação")
    menu = st.sidebar.radio("Menu", ["Dashboard de Revisões", "Cadastrar Máquina"])
    
    if menu == "Dashboard de Revisões":
        st.header("Status da Frota")
        # ASPAS TRIPLAS AQUI PARA EVITAR ERROS
        query = """
            SELECT 
                e.tag AS "TAG", 
                e.modelo AS "Modelo", 
                e.tipo_medidor AS "Medição",
                e.medidor_ultima_revisao AS "Última Revisão"
            FROM equipamentos e
        """
        try:
            df = pd.read_sql_query(query, conn)
            if not df.empty:
                st.dataframe(df, use_container_width=True)
            else:
                st.info("Nenhum dado encontrado.")
            
            # BLOCO DO HISTÓRICO COM ASPAS TRIPLAS
            with st.expander("🔍 Ver Histórico de Manutenções"):
                query_hist = """
                    SELECT 
                        tag_equipamento AS 'TAG', 
                        data_manutencao AS 'Data', 
                        valor_execucao AS 'Medidor na Parada', 
                        tipo_revisao AS 'Tipo' 
                    FROM historico_manutencoes 
                    ORDER BY id DESC
                """
                st.dataframe(pd.read_sql_query(query_hist, conn), use_container_width=True)
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")

    elif menu == "Cadastrar Máquina":
        st.header("Novo Equipamento")
        with st.form("cadastro"):
            tag = st.text_input("TAG").upper()
            modelo = st.text_input("Modelo")
            tipo = st.selectbox("Tipo", ["Horímetro", "Hodômetro"])
            if st.form_submit_button("Salvar"):
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO equipamentos (tag, modelo, tipo_medidor, medidor_ultima_revisao, data_ultima_revisao) 
                            VALUES (%s, %s, %s, %s, %s)
                        """, (tag, modelo, tipo, 0.0, date.today()))
                    st.success(f"Equipamento {tag} salvo!")
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")