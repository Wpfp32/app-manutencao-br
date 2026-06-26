import sqlite3
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
import math
import io
from dateutil.relativedelta import relativedelta

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Manutenção | BR Construções", page_icon="🚜", layout="wide")

# --- BANCO DE DADOS ---
def conectar_banco():
    conn = sqlite3.connect('manutencao_frota.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag_equipamento TEXT,
            data_leitura DATE,
            valor_medidor REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico_manutencoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag_equipamento TEXT,
            data_manutencao DATE,
            valor_execucao REAL,
            tipo_revisao TEXT
        )
    ''')
    conn.commit()
    return conn

conn = conectar_banco()

# --- GERENCIAMENTO DE SESSÃO (LOGIN) ---
if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.perfil = ""

if not st.session_state.logado:
    st.title("🚜 BR Construções - Portal de Manutenção")
    st.write("Por favor, faça o login para acessar o sistema.")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("Acesso Restrito")
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
    
    if st.sidebar.button("Sair (Logout)"):
        st.session_state.logado = False
        st.session_state.perfil = ""
        st.rerun()
    
    st.sidebar.write("---")
    
    if st.session_state.perfil == "Operador":
        opcoes_menu = ["Apontamento Diário"]
    else: 
        opcoes_menu = ["Dashboard de Revisões", "Apontamento Diário", "Upload em Lote (Offline)", "Registrar Manutenção (Dar Baixa)", "Cadastrar Máquina"]

    menu = st.sidebar.radio("Navegação", opcoes_menu)

    # ==========================================
    # TELA 1: APONTAMENTO DIÁRIO (Individual)
    # ==========================================
    if menu == "Apontamento Diário":
        st.header("Lançamento de Uso Diário")
        
        cursor = conn.cursor()
        cursor.execute("SELECT tag, tipo_medidor FROM equipamentos ORDER BY tag")
        maquinas_no_banco = cursor.fetchall()
        
        if maquinas_no_banco:
            lista_tags = [m[0] for m in maquinas_no_banco]
            tag_selecionada = st.selectbox("Selecione o Equipamento/Veículo", lista_tags)
            
            tipo_medidor_atual = next(m[1] for m in maquinas_no_banco if m[0] == tag_selecionada)
            unidade = "h" if tipo_medidor_atual == "Horímetro" else "km"
            
            query_ultimo = """
                SELECT COALESCE(MAX(l.valor_medidor), e.medidor_ultima_revisao)
                FROM equipamentos e
                LEFT JOIN leituras l ON e.tag = l.tag_equipamento
                WHERE e.tag = ?
            """
            cursor.execute(query_ultimo, (tag_selecionada,))
            ultimo_medidor = cursor.fetchone()[0]
            
            st.info(f"Último registro ({tipo_medidor_atual}): **{ultimo_medidor} {unidade}**")
            data_hoje = st.date_input("Data da Leitura", date.today())
            
            medidor_novo = st.number_input(f"Valor Atual ({unidade})", min_value=float(ultimo_medidor), value=float(ultimo_medidor), format="%.1f", step=1.0)
            
            if st.button("Registrar Leitura"):
                if medidor_novo < ultimo_medidor:
                    st.error("Operação cancelada: O valor digitado é menor que o último registro.")
                else:
                    cursor.execute("INSERT INTO leituras (tag_equipamento, data_leitura, valor_medidor) VALUES (?, ?, ?)", (tag_selecionada, data_hoje, medidor_novo))
                    conn.commit()
                    st.success(f"Leitura de {medidor_novo}{unidade} registrada com sucesso!")
                    st.rerun()
        else:
            st.warning("Nenhum equipamento encontrado. Peça para a gestão cadastrar uma máquina.")

    # ==========================================
    # TELA NOVA: UPLOAD EM LOTE (Planilha Offline)
    # ==========================================
    elif menu == "Upload em Lote (Offline)":
        st.header("Lançamento em Lote (Planilha Offline)")
        st.write("Utilize esta ferramenta para importar várias leituras de horímetro/hodômetro coletadas em áreas sem sinal de internet.")
        
        st.write("---")
        st.subheader("1. Baixe a Planilha Modelo")
        st.write("Preencha as leituras seguindo exatamente este formato. Não altere os nomes das colunas.")
        
        df_template = pd.DataFrame(columns=["TAG_EQUIPAMENTO", "DATA_LEITURA", "VALOR_ATUAL"])
        buffer_template = io.BytesIO()
        with pd.ExcelWriter(buffer_template, engine='openpyxl') as writer:
            df_template.to_excel(writer, index=False, sheet_name='Lançamentos')
            
        st.download_button(
            label="📥 Baixar Modelo (Excel)",
            data=buffer_template.getvalue(),
            file_name="modelo_apontamentos_offline.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.write("---")
        st.subheader("2. Enviar Planilha Preenchida")
        arquivo_upload = st.file_uploader("Selecione o arquivo Excel (.xlsx)", type=["xlsx"])
        
        if arquivo_upload is not None:
            try:
                df_upload = pd.read_excel(arquivo_upload)
                df_upload['DATA_LEITURA'] = pd.to_datetime(df_upload['DATA_LEITURA']).dt.date
                
                st.write("Pré-visualização dos dados carregados:")
                st.dataframe(df_upload, use_container_width=True)
                
                if st.button("Processar e Salvar no Banco de Dados"):
                    cursor = conn.cursor()
                    sucessos = 0
                    erros = []
                    
                    for index, row in df_upload.iterrows():
                        tag = str(row['TAG_EQUIPAMENTO']).strip().upper()
                        data_leitura = row['DATA_LEITURA']
                        valor = float(row['VALOR_ATUAL'])
                        
                        cursor.execute("SELECT medidor_ultima_revisao FROM equipamentos WHERE tag = ?", (tag,))
                        equipamento = cursor.fetchone()
                        
                        if not equipamento:
                            erros.append(f"Linha {index + 2}: A máquina '{tag}' não está cadastrada no sistema.")
                            continue
                            
                        query_ultimo = """
                            SELECT COALESCE(MAX(l.valor_medidor), e.medidor_ultima_revisao)
                            FROM equipamentos e
                            LEFT JOIN leituras l ON e.tag = l.tag_equipamento
                            WHERE e.tag = ?
                        """
                        cursor.execute(query_ultimo, (tag,))
                        ultimo_medidor = cursor.fetchone()[0]
                        
                        if valor < ultimo_medidor:
                            erros.append(f"Linha {index + 2}: Valor de '{tag}' ({valor}) é MENOR que o último registro ({ultimo_medidor}). Ignorado.")
                            continue
                            
                        cursor.execute("INSERT INTO leituras (tag_equipamento, data_leitura, valor_medidor) VALUES (?, ?, ?)", (tag, data_leitura, valor))
                        sucessos += 1
                        
                    conn.commit()
                    
                    if sucessos > 0:
                        st.success(f"✅ Sucesso! {sucessos} leituras registradas no sistema.")
                    if erros:
                        st.warning("⚠️ Alguns registros não puderam ser salvos devido a erros de validação:")
                        for e in erros:
                            st.write(f"- {e}")
                            
            except Exception as e:
                st.error(f"Erro ao ler a planilha. Certifique-se de que está usando o modelo correto. Detalhe técnico: {e}")

    # ==========================================
    # TELA 2: DASHBOARD E ANALYTICS
    # ==========================================
    elif menu == "Dashboard de Revisões":
        st.header("Status da Frota e Próximas Revisões")
        
        cursor = conn.cursor()
        query = """
            SELECT 
                e.tag AS "TAG",
                e.modelo AS "Modelo",
                e.tipo_medidor AS "Medição",
                e.medidor_ultima_revisao AS "Última Revisão",
                e.data_ultima_revisao AS "Data Última Revisão",
                COALESCE(MAX(l.valor_medidor), e.medidor_ultima_revisao) AS "Uso Atual",
                MAX(l.data_leitura) AS "Último Apontamento",
                MIN(l.data_leitura) AS "Primeira Leitura",
                MIN(l.valor_medidor) AS "Uso Inicial"
            FROM equipamentos e
            LEFT JOIN leituras l ON e.tag = l.tag_equipamento
            GROUP BY e.tag
        """
        df_frota = pd.read_sql_query(query, conn)
        
        if not df_frota.empty:
            df_frota["Meta Uso"] = df_frota.apply(lambda row: row["Última Revisão"] + 500 if row["Medição"] == "Horímetro" else row["Última Revisão"] + 10000, axis=1)
            df_frota["Uso Restante"] = df_frota["Meta Uso"] - df_frota["Uso Atual"]
            
            def label_proxima(row):
                if row["Medição"] == "Horímetro":
                    return "🔧 1000h" if int(row["Meta Uso"]) % 1000 == 0 else "🛠️ 500h"
                else:
                    return "🚗 10.000km / 6 meses"
            df_frota["Próxima Revisão"] = df_frota.apply(label_proxima, axis=1)
            
            df_frota['Data Última Revisão'] = pd.to_datetime(df_frota['Data Última Revisão'])
            data_hoje_pd = pd.Timestamp(date.today())
            df_frota['Data Limite (6 meses)'] = df_frota['Data Última Revisão'].apply(lambda x: x + relativedelta(months=6) if pd.notnull(x) else pd.NaT)
            
            def definir_status(row):
                if row["Medição"] == "Horímetro":
                    if row["Uso Restante"] <= 0: return "🔴 Vencida"
                    elif row["Uso Restante"] <= 50: return "🟡 Atenção"
                    else: return "🟢 Normal"
                else: 
                    dias_para_vencer_tempo = (row["Data Limite (6 meses)"] - data_hoje_pd).days
                    if row["Uso Restante"] <= 0 or dias_para_vencer_tempo <= 0: return "🔴 Vencida"
                    elif row["Uso Restante"] <= 1000 or dias_para_vencer_tempo <= 30: return "🟡 Atenção"
                    else: return "🟢 Normal"
                    
            df_frota["Status"] = df_frota.apply(definir_status, axis=1)
            
            df_frota['Primeira Leitura'] = pd.to_datetime(df_frota['Primeira Leitura'])
            df_frota['Último Apontamento'] = pd.to_datetime(df_frota['Último Apontamento'])
            
            def calcular_previsao(row):
                if row["Status"] == "🔴 Vencida": return "Já Venceu", 0.0
                
                media_diaria = 8.0 if row["Medição"] == "Horímetro" else 50.0 
                
                if pd.notna(row['Primeira Leitura']) and pd.notna(row['Último Apontamento']):
                    dias_operados = (row['Último Apontamento'] - row['Primeira Leitura']).days
                    if dias_operados > 0:
                        trabalhado = row['Uso Atual'] - row['Uso Inicial']
                        media_diaria = max(trabalhado / dias_operados, 1.0)
                
                dias_restantes_uso = math.ceil(row["Uso Restante"] / media_diaria)
                data_prevista_uso = date.today() + timedelta(days=dias_restantes_uso)
                
                if row["Medição"] == "Hodômetro":
                    data_limite_tempo = row["Data Limite (6 meses)"].date()
                    data_final = min(data_prevista_uso, data_limite_tempo)
                else:
                    data_final = data_prevista_uso
                    
                return data_final.strftime("%d/%m/%Y"), round(media_diaria, 1)

            previsoes = df_frota.apply(calcular_previsao, axis=1)
            df_frota['Previsão Parada'] = [p[0] for p in previsoes]
            df_frota['Média/Dia'] = [p[1] for p in previsoes]
            
            df_frota['Último Apontamento'] = df_frota['Último Apontamento'].dt.strftime('%d/%m/%Y').fillna('-')
            df_frota['Data Última Revisão'] = df_frota['Data Última Revisão'].dt.strftime('%d/%m/%Y')
            
            colunas_ordenadas = [
                "Status", "TAG", "Modelo", "Medição", "Uso Atual", 
                "Próxima Revisão", "Uso Restante", 
                "Previsão Parada", "Último Apontamento"
            ]
            df_frota_tela = df_frota[colunas_ordenadas]
            
            vencidas = df_frota[df_frota["Status"] == "🔴 Vencida"].shape[0]
            atencao = df_frota[df_frota["Status"] == "🟡 Atenção"].shape[0]
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Frota Total", len(df_frota))
            col2.metric("Revisões Vencidas", vencidas, delta=vencidas, delta_color="inverse" if vencidas > 0 else "normal")
            col3.metric("Em Alerta (Próximas)", atencao)
            
            st.write("---")
            st.subheader("📊 Visão Estratégica da Frota")
            col_graf1, col_graf2 = st.columns(2)
            mapa_cores = {"🟢 Normal": "#28a745", "🟡 Atenção": "#ffc107", "🔴 Vencida": "#dc3545"}
            
            with col_graf1:
                fig_status = px.pie(df_frota, names="Status", title="Saúde da Frota", hole=0.4, color="Status", color_discrete_map=mapa_cores)
                st.plotly_chart(fig_status, use_container_width=True)
            with col_graf2:
                df_bar = df_frota.sort_values(by="Uso Restante")
                fig_bar = px.bar(df_bar, x="TAG", y="Uso Restante", title="Uso Restante (h ou km)", color="Status", color_discrete_map=mapa_cores, text="Uso Restante")
                st.plotly_chart(fig_bar, use_container_width=True)
                
            st.write("---")
            col_tab1, col_tab2 = st.columns([3, 1])
            with col_tab1: st.subheader("📋 Tabela Geral de Ativos")
            with col_tab2:
                buffer_frota = io.BytesIO()
                with pd.ExcelWriter(buffer_frota, engine='openpyxl') as writer:
                    df_frota.to_excel(writer, index=False, sheet_name='Status Frota')
                st.download_button(label="📥 Baixar Planilha (Excel)", data=buffer_frota.getvalue(), file_name=f'status_frota_{date.today()}.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                
            st.dataframe(df_frota_tela, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum equipamento cadastrado.")
            
        st.write("---")
        with st.expander("🔍 Ver Histórico de Manutenções Realizadas"):
            df_historico = pd.read_sql_query("SELECT tag_equipamento AS 'TAG', data_manutencao AS 'Data', valor_execucao AS 'Medidor na Parada', tipo_revisao AS 'Tipo' FROM historico_manutencoes ORDER BY id DESC", conn)
            if not df_historico.empty:
                st.dataframe(df_historico, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum registro encontrado.")

    # --- TELA 3: REGISTRAR MANUTENÇÃO (DAR BAIXA) ---
    elif menu == "Registrar Manutenção (Dar Baixa)":
        st.header("Dar Baixa em Revisão Realizada")
        
        cursor = conn.cursor()
        cursor.execute("SELECT tag, tipo_medidor FROM equipamentos ORDER BY tag")
        maquinas_no_banco = cursor.fetchall()
        
        if maquinas_no_banco:
            lista_tags = [m[0] for m in maquinas_no_banco]
            tag_selecionada = st.selectbox("Selecione a Máquina/Veículo", lista_tags)
            tipo_medidor_atual = next(m[1] for m in maquinas_no_banco if m[0] == tag_selecionada)
            unidade = "h" if tipo_medidor_atual == "Horímetro" else "km"
            
            cursor.execute("SELECT medidor_ultima_revisao, data_ultima_revisao FROM equipamentos WHERE tag = ?", (tag_selecionada,))
            dados_revisao = cursor.fetchone()
            ultima_rev_val = dados_revisao[0]
            
            query_ultimo = """
                SELECT COALESCE(MAX(l.valor_medidor), e.medidor_ultima_revisao)
                FROM equipamentos e
                LEFT JOIN leituras l ON e.tag = l.tag_equipamento
                WHERE e.tag = ?
            """
            cursor.execute(query_ultimo, (tag_selecionada,))
            medidor_atual_val = cursor.fetchone()[0]
            
            if tipo_medidor_atual == "Horímetro":
                proxima_meta = ultima_rev_val + 500
                tipo_rev_concluida = "1000h" if int(proxima_meta) % 1000 == 0 else "500h"
                aviso = f"**{tipo_rev_concluida}** em **{proxima_meta}h**"
            else:
                proxima_meta = ultima_rev_val + 10000
                tipo_rev_concluida = "10.000km/6meses"
                aviso = f"**10.000km** (Meta: {proxima_meta}km) ou **6 meses**"
            
            col_info1, col_info2 = st.columns(2)
            col_info1.warning(f"Revisão Esperada: {aviso}")
            col_info2.info(f"Uso Atual Registrado: **{medidor_atual_val}{unidade}**")
            
            st.write("---")
            medidor_fechamento = st.number_input(f"Valor Real da Execução ({unidade})", min_value=float(ultima_rev_val), value=float(medidor_atual_val), format="%.1f")
            data_fechamento = st.date_input("Data da Realização da Manutenção", date.today())
            
            if st.button("Confirmar Conclusão da Revisão"):
                novo_tipo_base = 1000 if tipo_rev_concluida == "1000h" else 500
                cursor.execute("UPDATE equipamentos SET medidor_ultima_revisao = ?, data_ultima_revisao = ?, tipo_ultima_revisao = ? WHERE tag = ?", (medidor_fechamento, data_fechamento, novo_tipo_base, tag_selecionada))
                cursor.execute("INSERT INTO leituras (tag_equipamento, data_leitura, valor_medidor) VALUES (?, ?, ?)", (tag_selecionada, data_fechamento, medidor_fechamento))
                cursor.execute("INSERT INTO historico_manutencoes (tag_equipamento, data_manutencao, valor_execucao, tipo_revisao) VALUES (?, ?, ?, ?)", (tag_selecionada, data_fechamento, medidor_fechamento, f"Revisão {tipo_rev_concluida}"))
                conn.commit()
                st.success("Revisão salva no histórico permanente e ciclos reiniciados!")
                st.rerun()
        else:
            st.warning("Nenhum equipamento disponível.")

    # --- TELA 4: CADASTRO BÁSICO ---
    elif menu == "Cadastrar Máquina":
        st.header("Cadastro de Equipamento e Veículos")
        
        nova_tag = st.text_input("TAG (Ex: RETRO-01 ou GOL-05)").strip().upper()
        novo_modelo = st.text_input("Modelo (Ex: CAT 416F2 ou VW Gol)")
        
        tipo_medicao = st.radio("Como o uso é medido?", ["Horímetro", "Hodômetro"])
        unidade = "Horas" if tipo_medicao == "Horímetro" else "Km"
        
        medidor_base = st.number_input(f"Valor na Última Revisão ({unidade})", min_value=0.0, step=1.0)
        data_revisao_base = st.date_input("Data da Última Revisão", date.today())
        
        if st.button("Salvar Equipamento/Veículo"):
            cursor = conn.cursor()
            if not nova_tag:
                st.error("A TAG não pode ficar em branco.")
            else:
                cursor.execute("SELECT tag FROM equipamentos WHERE tag = ?", (nova_tag,))
                if cursor.fetchone():
                    st.error(f"A TAG {nova_tag} já está cadastrada no sistema!")
                else:
                    cursor.execute("INSERT INTO equipamentos (tag, modelo, tipo_medidor, medidor_ultima_revisao, data_ultima_revisao, tipo_ultima_revisao) VALUES (?, ?, ?, ?, ?, ?)", 
                                   (nova_tag, novo_modelo, tipo_medicao, medidor_base, data_revisao_base, 500))
                    conn.commit()
                    st.success(f"Ativo {nova_tag} cadastrado com sucesso!")