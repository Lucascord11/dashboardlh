import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from matplotlib.patches import Patch
import streamlit.components.v1 as components

# Configurar layout wide
st.set_page_config(layout="wide")

# CSS customizado para as tabelas resumo gerais
st.markdown("""
    <style>
    .summary-table { 
        width: 100% !important; 
        table-layout: auto; 
        font-size: 12px;
    }
    .summary-table th, .summary-table td {
        text-align: center;
        padding: 4px;
    }
    .summary-table th:first-child, .summary-table td:first-child {
        width: 120px;
    }
    </style>
    """, unsafe_allow_html=True)

# CSS específico para a tabela "Resultado de medição"
st.markdown("""
    <style>
    .result-table {
        width: 100% !important;
        table-layout: auto;
        font-size: 10px;
    }
    .result-table td:first-child {
        white-space: nowrap;
    }
    .result-table td:nth-child(2) {
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# Função para aplicar estilo à linha "Total" e esconder o índice
def style_total(df, key_column):
    return df.style.hide(axis="index").apply(
        lambda row: ['background-color: #d3d3d3; font-weight: bold' if row[key_column] == "Total" else '' for _ in row],
        axis=1
    ).to_html(classes="summary-table")

# --- Definir estilo para os gráficos com fallback ---
available_styles = plt.style.available
if "ggplot" in available_styles:
    plt.style.use("ggplot")
else:
    plt.style.use("default")

# Definir cores para os gráficos
dark_blue = "#1f77b4"   # tom de azul escuro
light_blue = "#aec7e8"  # tom de azul claro

# Função para converter datas
def parse_date(date_str):
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except Exception:
            continue
    return pd.NaT

# --- Conexão com o Google Sheets ---
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]
creds = ServiceAccountCredentials.from_json_keyfile_name("credenciais.json", scope)
client = gspread.authorize(creds)

# --- Carregar dados da planilha ---
spreadsheet = client.open("LH Tarefas")
tarefas_sheet = spreadsheet.worksheet("Tarefas")
usuarios_sheet = spreadsheet.worksheet("IDs Usuários")

# Converter os dados para DataFrames
df_tarefas = pd.DataFrame(tarefas_sheet.get_all_records())
df_usuarios = pd.DataFrame(usuarios_sheet.get_all_records())

# Forçar a coluna "Tarefa" a ser string
if "Tarefa" in df_tarefas.columns:
    df_tarefas["Tarefa"] = df_tarefas["Tarefa"].apply(lambda x: str(x) if pd.notnull(x) else "")

# Ajuste das colunas de datas
if "Data de Criação" in df_tarefas.columns:
    df_tarefas["Data de Criação"] = df_tarefas["Data de Criação"].apply(parse_date)
if "Prazo" in df_tarefas.columns:
    df_tarefas["Prazo"] = df_tarefas["Prazo"].apply(parse_date)
if "Última Atualização" in df_tarefas.columns:
    df_tarefas["Última Atualização"] = df_tarefas["Última Atualização"].apply(parse_date)

# --- Sidebar: Filtros ---
st.sidebar.header("Filtros")
# Removemos a opção "Todos"
lista_funcionarios = sorted([nome.strip() for nome in df_usuarios["Nome"].dropna().tolist() if nome.strip() != ""])
funcionario_selecionado = st.sidebar.selectbox("Selecione o funcionário:", lista_funcionarios)
min_date = df_tarefas["Data de Criação"].min().date() if not df_tarefas["Data de Criação"].isnull().all() else date.today()
max_date = df_tarefas["Data de Criação"].max().date() if not df_tarefas["Data de Criação"].isnull().all() else date.today()
data_inicio = st.sidebar.date_input("Data Início", min_date)
data_fim = st.sidebar.date_input("Data Fim", max_date)

# Filtragem dos dados para gráficos
df_filtrado = df_tarefas[
    (df_tarefas["Atribuído"] == funcionario_selecionado) |
    ((df_tarefas["Status"].isin(["Desvio Comportamental", "Sugestão de Melhoria", "Não Conformidade"])) &
     (df_tarefas["Atribuidor"] == funcionario_selecionado))
].copy()
if "Data de Criação" in df_filtrado.columns:
    df_filtrado = df_filtrado[
        (df_filtrado["Data de Criação"].dt.date >= data_inicio) &
        (df_filtrado["Data de Criação"].dt.date <= data_fim)
    ]

# Para os dois primeiros gráficos, excluir tarefas autoatribuídas
df_graph = df_filtrado[df_filtrado["Atribuidor"] != df_filtrado["Atribuído"]].copy()

# --- Header Principal e Intervalo de Medição ---
st.markdown(f"<h4>Relatório de tarefas do funcionário {funcionario_selecionado}</h4>", unsafe_allow_html=True)
st.markdown(f"<p style='font-size:14px;'>Intervalo de medição: {data_inicio.strftime('%d/%m/%Y')} - {data_fim.strftime('%d/%m/%Y')}</p>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# --- Novo: Tabela Resultado de medição ---
# Total de Tarefas recebidas (do gráfico "Total de tarefas atribuídas ao [funcionário]")
df_total = df_filtrado.copy()
df_total = df_filtrado[df_filtrado["Atribuidor"] != df_filtrado["Atribuído"]]
status_list = ["Pendente", "Concluída", "Aprovado", "Aprovado com ressalvas", "Aguardando Aprovacao", "Para Aprovação"]
counts_total = df_total["Status"].value_counts().reindex(status_list).fillna(0)
total_recebidas = int(counts_total.sum())

# Total de Tarefas ordenadas (do gráfico "Tarefas atribuídas pelo [funcionário]")
df_atribuidas_calc = df_tarefas.copy()
if "Data de Criação" in df_atribuidas_calc.columns:
    df_atribuidas_calc = df_atribuidas_calc[
        (df_atribuidas_calc["Data de Criação"].dt.date >= data_inicio) &
        (df_atribuidas_calc["Data de Criação"].dt.date <= data_fim)
    ]
df_atribuidas_calc = df_atribuidas_calc[
    (df_atribuidas_calc["Atribuidor"] == funcionario_selecionado) &
    (~df_atribuidas_calc["Status"].isin(["Deletada", "Sugestão de Melhoria", "Desvio Comportamental", "Não Conformidade"]))
].copy()
atribuicoes_calc = df_atribuidas_calc.groupby("Atribuído").size().reset_index(name="Total")
total_ordenadas = int(atribuicoes_calc["Total"].sum())

# Tarefas realizadas fora do prazo (do gráfico "Dentro x Fora de prazo")
status_concluidos = ["Concluída", "Aprovado", "Aprovado com ressalvas", "Aguardando Aprovacao"]
hoje = datetime.now()
dentro_prazo_calc = 0
fora_prazo_calc = 0
for idx, row in df_graph.iterrows():
    prazo = row.get("Prazo")
    status = row.get("Status")
    ultima_atualizacao = row.get("Última Atualização")
    if pd.notnull(prazo):
        if status in status_concluidos and pd.notnull(ultima_atualizacao):
            if ultima_atualizacao.date() <= prazo.date():
                dentro_prazo_calc += 1
            else:
                fora_prazo_calc += 1
        elif status == "Pendente":
            if hoje.date() > prazo.date():
                fora_prazo_calc += 1
total1 = dentro_prazo_calc + fora_prazo_calc
perc_fora = (fora_prazo_calc / total1) * 100 if total1 > 0 else 0
tarefas_fora_prazo = f"{perc_fora:.0f}%"

# Tarefas concluídas com ressalvas (do gráfico "Aprovado x Aprovado com ressalvas")
df_aprovados_calc = df_graph[df_graph["Status"].isin(["Aprovado", "Aprovado com ressalvas"])]
contagem_aprovados_calc = df_aprovados_calc["Status"].value_counts()
aprov_val_calc = int(contagem_aprovados_calc.get("Aprovado", 0))
aprov_r_val_calc = int(contagem_aprovados_calc.get("Aprovado com ressalvas", 0))
total2_calc = aprov_val_calc + aprov_r_val_calc
perc_aprovado_com = (aprov_r_val_calc / total2_calc) * 100 if total2_calc > 0 else 0
tarefas_com_ressalvas = f"{perc_aprovado_com:.0f}%"

# Novos índices para os status de Atribuidor
df_atribuidas_specific = df_tarefas.copy()
if "Data de Criação" in df_atribuidas_specific.columns:
    df_atribuidas_specific = df_atribuidas_specific[
         (df_atribuidas_specific["Data de Criação"].dt.date >= data_inicio) &
         (df_atribuidas_specific["Data de Criação"].dt.date <= data_fim)
    ]
df_atribuidas_specific = df_atribuidas_specific[df_atribuidas_specific["Atribuidor"] == funcionario_selecionado]
total_sugestao = df_atribuidas_specific[df_atribuidas_specific["Status"]=="Sugestão de Melhoria"].shape[0]
total_desvio = df_atribuidas_specific[df_atribuidas_specific["Status"]=="Desvio Comportamental"].shape[0]
total_naoconformidade = df_atribuidas_specific[df_atribuidas_specific["Status"]=="Não Conformidade"].shape[0]

resultado_medicao = pd.DataFrame({
    "Métrica": [
        "Total de Tarefas recebidas",
        "Total de Tarefas ordenadas",
        "Tarefas realizadas fora do prazo",
        "Tarefas concluídas com ressalvas",
        "Sugestão de Melhoria",
        "Desvio Comportamental",
        "Não Conformidade"
    ],
    "Valor": [total_recebidas, total_ordenadas, tarefas_fora_prazo, tarefas_com_ressalvas,
              total_sugestao, total_desvio, total_naoconformidade]
})

# Verifica a condição para a bonificação
if (perc_fora > 5) or (perc_aprovado_com > 5):
    bonus_text = "Bonificação não autorizada"
    bg_color = "red"
else:
    bonus_text = "Bonificação autorizada"
    bg_color = "green"

# Converte a tabela para HTML e insere a última linha mesclada
html_table = resultado_medicao.to_html(index=False, header=False, classes="result-table")
extra_row = f'<tr><td colspan="2" style="background-color: {bg_color}; color: white; text-align: center;">{bonus_text}</td></tr>'
html_table = html_table.replace("</tbody>", extra_row + "</tbody>")

st.markdown("<h5 style='text-align: left;'>Resultado de medição</h5>", unsafe_allow_html=True)
st.markdown(html_table, unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# --- Seção: Tarefas (restante do dashboard) ---
st.markdown("<h5 style='text-align: left;'>Tarefas</h5>", unsafe_allow_html=True)

# --- Gráfico 1: Tarefas concluídas dentro do prazo vs fora do prazo ---
dentro_prazo = 0
fora_prazo = 0
for idx, row in df_graph.iterrows():
    prazo = row.get("Prazo")
    status = row.get("Status")
    ultima_atualizacao = row.get("Última Atualização")
    if pd.notnull(prazo):
        if status in status_concluidos and pd.notnull(ultima_atualizacao):
            if ultima_atualizacao.date() <= prazo.date():
                dentro_prazo += 1
            else:
                fora_prazo += 1
        elif status == "Pendente":
            if hoje.date() > prazo.date():
                fora_prazo += 1

fig1, ax1 = plt.subplots(figsize=(8,5))
fig1.patch.set_facecolor("white")
ax1.set_facecolor("white")
ax1.bar(["Dentro do Prazo", "Fora do Prazo"], [dentro_prazo, fora_prazo],
        width=0.6, color=[dark_blue, light_blue], edgecolor="none")
ax1.yaxis.set_major_locator(MaxNLocator(integer=True))
ax1.tick_params(axis="x", labelsize=14)
ax1.spines["top"].set_visible(False)
ax1.spines["right"].set_visible(False)
ax1.set_xlim(-0.5, 1.5)

# --- Gráfico 2: Tarefas "Aprovado" vs "Aprovado com ressalvas" ---
df_aprovados = df_graph[df_graph["Status"].isin(["Aprovado", "Aprovado com ressalvas"])]
contagem_aprovados = df_aprovados["Status"].value_counts()
aprov_val = int(contagem_aprovados.get("Aprovado", 0))
aprov_r_val = int(contagem_aprovados.get("Aprovado com ressalvas", 0))
contagem_aprovados = pd.Series({"Aprovado": aprov_val, "Aprovado com ressalvas": aprov_r_val})
fig2, ax2 = plt.subplots(figsize=(8,5))
fig2.patch.set_facecolor("white")
ax2.set_facecolor("white")
ax2.bar(contagem_aprovados.index, contagem_aprovados.values,
        width=0.6, color=[dark_blue, light_blue], edgecolor="none")
ax2.yaxis.set_major_locator(MaxNLocator(integer=True))
ax2.tick_params(axis="x", labelsize=14)
ax2.spines["top"].set_visible(False)
ax2.spines["right"].set_visible(False)
ax2.set_xlim(-0.5, 1.5)

# --- Tabelas Resumo para Gráficos 1 e 2 ---
total1 = dentro_prazo + fora_prazo
perc_dentro = (dentro_prazo / total1) * 100 if total1 > 0 else 0
perc_fora = (fora_prazo / total1) * 100 if total1 > 0 else 0
summary1 = pd.DataFrame({
    "Dentro do prazo": [int(dentro_prazo), f"{perc_dentro:.0f}%"],
    "Fora do prazo": [int(fora_prazo), f"{perc_fora:.0f}%"]
})
total2 = aprov_val + aprov_r_val
perc_aprovado = (aprov_val / total2) * 100 if total2 > 0 else 0
perc_aprovado_com = (aprov_r_val / total2) * 100 if total2 > 0 else 0
summary2 = pd.DataFrame({
    "Aprovado": [aprov_val, f"{perc_aprovado:.0f}%"],
    "Aprovado com ressalvas": [aprov_r_val, f"{perc_aprovado_com:.0f}%"]
})

col1, col2 = st.columns(2)
with col1:
    st.markdown("<h5 style='text-align: left;'>Dentro x Fora de prazo</h5>", unsafe_allow_html=True)
    st.pyplot(fig1)
    st.write("**Resumo:**")
    st.markdown(summary1.to_html(index=False, classes="summary-table"), unsafe_allow_html=True)
with col2:
    st.markdown("<h5 style='text-align: left;'>Aprovado x Aprovado com ressalvas</h5>", unsafe_allow_html=True)
    st.pyplot(fig2)
    st.write("**Resumo:**")
    st.markdown(summary2.to_html(index=False, classes="summary-table"), unsafe_allow_html=True)

# --- Espaço extra antes do gráfico "Total de tarefas" ---
st.markdown("<br><br>", unsafe_allow_html=True)

# --- Gráfico: Total de tarefas por status (excluindo 'Deletada' e autoatribuídas) ---
df_total = df_filtrado.copy()
df_total = df_filtrado[df_filtrado["Atribuidor"] != df_filtrado["Atribuído"]]
status_list = ["Pendente", "Concluída", "Aprovado", "Aprovado com ressalvas", "Aguardando Aprovacao", "Para Aprovação"]
counts_total = df_total["Status"].value_counts().reindex(status_list).fillna(0)
cmap = plt.get_cmap("tab10")
status_colors = {status: cmap(i) for i, status in enumerate(status_list)}
fig3, ax3 = plt.subplots(figsize=(12, 6))
fig3.patch.set_facecolor("white")
ax3.set_facecolor("white")
bars = ax3.bar(counts_total.index, counts_total.values, width=0.6,
               color=[status_colors[status] for status in counts_total.index], edgecolor="none")
ax3.yaxis.set_major_locator(MaxNLocator(integer=True))
ax3.set_xticklabels([])
ax3.spines["top"].set_visible(False)
ax3.spines["right"].set_visible(False)
plt.subplots_adjust(right=0.8)
legend_labels = {
    "Pendente": "PEND.",
    "Concluída": "CONC.",
    "Aprovado": "APR.",
    "Aprovado com ressalvas": "APR+R.",
    "Aguardando Aprovacao": "AGU.",
    "Para Aprovação": "PARA."
}
legend_handles = [Patch(facecolor=status_colors[status], label=legend_labels[status]) for status in status_list]
ax3.legend(handles=legend_handles, loc="upper left", bbox_to_anchor=(1.02, 1), fontsize=10, frameon=False)
st.markdown(f"<h5 style='text-align: left;'>Total de tarefas atribuídas ao {funcionario_selecionado}</h5>", unsafe_allow_html=True)
st.pyplot(fig3)

# --- Tabela Resumo para "Total de tarefas atribuídas ao [funcionário]" ---
summary_total = pd.DataFrame({
    "Status": status_list,
    "Tarefas": counts_total.values.astype(int)
})
total_sum = summary_total["Tarefas"].sum()
summary_total = pd.concat([summary_total, pd.DataFrame({"Status": ["Total"], "Tarefas": [total_sum]})], ignore_index=True)
st.markdown("<h6 style='text-align: left;'>Resumo:</h6>", unsafe_allow_html=True)
st.markdown(summary_total.to_html(index=False, classes="summary-table"), unsafe_allow_html=True)

# --- Espaço extra antes do header "Tarefas atribuídas pelo" ---
st.markdown("<br><br>", unsafe_allow_html=True)

# --- Nova Seção: Tarefas atribuídas pelo funcionário ---
st.markdown(f"<h5 style='text-align: left;'>Total de tarefas atribuídas pelo {funcionario_selecionado}</h5>", unsafe_allow_html=True)
df_atribuidas = df_tarefas.copy()
if "Data de Criação" in df_atribuidas.columns:
    df_atribuidas = df_atribuidas[
        (df_atribuidas["Data de Criação"].dt.date >= data_inicio) &
        (df_atribuidas["Data de Criação"].dt.date <= data_fim)
    ]
df_atribuidas = df_atribuidas[
    (df_atribuidas["Atribuidor"] == funcionario_selecionado) &
    (~df_atribuidas["Status"].isin(["Deletada", "Sugestão de Melhoria", "Desvio Comportamental", "Não Conformidade"]))
].copy()
atribuicoes = df_atribuidas.groupby("Atribuído").size().reset_index(name="Total")
atribuicoes = atribuicoes.sort_values("Total", ascending=False)
total_atrib = atribuicoes["Total"].sum()
atribuicoes = pd.concat([atribuicoes, pd.DataFrame({"Atribuído": ["Total"], "Total": [total_atrib]})], ignore_index=True)
atribuicoes_graph = atribuicoes[atribuicoes["Atribuído"] != "Total"]
fig5, ax5 = plt.subplots(figsize=(12,6))
fig5.patch.set_facecolor("white")
ax5.set_facecolor("white")
ax5.bar(atribuicoes_graph["Atribuído"], atribuicoes_graph["Total"], color=dark_blue, width=0.6)
ax5.set_xlabel("Funcionários (Atribuídos)")
ax5.set_ylabel("Número de tarefas")
ax5.yaxis.set_major_locator(MaxNLocator(integer=True))
st.pyplot(fig5)
summary_atrib = atribuicoes.rename(columns={"Atribuído": "Funcionário", "Total": "Tarefas"})
st.markdown("<h6 style='text-align: left;'>Resumo:</h6>", unsafe_allow_html=True)
st.markdown(summary_atrib.to_html(index=False, classes="summary-table"), unsafe_allow_html=True)

# --- Espaço extra antes do gráfico "Tempo de realização de tarefas" ---
st.markdown("<br><br>", unsafe_allow_html=True)

# --- Gráfico: Tempo de realização de tarefas (gráfico de linha) ---
st.markdown("<h5 style='text-align: left;'>Tempo de realização de tarefas</h5>", unsafe_allow_html=True)
concluded_statuses = ["Concluída", "Aprovado", "Aprovado com ressalvas", "Aguardando Aprovacao"]
df_concluidas = df_filtrado[df_filtrado["Status"].isin(concluded_statuses)].copy()
df_concluidas = df_concluidas.dropna(subset=["Data de Criação", "Última Atualização"])
df_concluidas["Tempo"] = (df_concluidas["Última Atualização"] - df_concluidas["Data de Criação"]).dt.total_seconds() / (3600*24)
df_concluidas = df_concluidas.sort_values("Data de Criação")
x = range(len(df_concluidas))
y = df_concluidas["Tempo"]
fig4, ax4 = plt.subplots(figsize=(12,6))
fig4.patch.set_facecolor("white")
ax4.set_facecolor("white")
ax4.plot(x, y, marker='o', linestyle='-', color=dark_blue)
avg_time = y.mean() if len(y) > 0 else 0
ax4.axhline(avg_time, color='red', linestyle='--', linewidth=1)
ax4.text(0.95, 0.95, f"Tempo médio: {avg_time:.1f} dias",
         transform=ax4.transAxes, color='red', fontsize=10, ha='right', va='top',
         bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
ax4.set_xlabel("Tarefas (ordem cronológica)")
ax4.set_ylabel("Tempo de realização (dias)")
ax4.yaxis.set_major_locator(MaxNLocator(integer=True))
st.pyplot(fig4)
st.markdown("<br><br>", unsafe_allow_html=True)

# --- Seções: Sugestões, Desvios e Não Conformidades ---
st.markdown(f"<h5>Sugestões de melhorias enviadas pelo {funcionario_selecionado}</h5>", unsafe_allow_html=True)
df_sugestoes = df_filtrado[df_filtrado["Status"] == "Sugestão de Melhoria"]
if not df_sugestoes.empty:
    df_sugestoes_display = df_sugestoes[["Data de Criação", "Tarefa"]].copy()
    df_sugestoes_display.rename(columns={"Data de Criação": "Data", "Tarefa": "Sugestão"}, inplace=True)
    df_sugestoes_display["Data"] = df_sugestoes_display["Data"].dt.strftime("%d/%m/%Y")
    st.markdown(df_sugestoes_display.to_html(index=False, classes="summary-table"), unsafe_allow_html=True)
else:
    st.markdown(f"<p style='font-size:14px;'>Nesse intervalo de datas o funcionário {funcionario_selecionado} não enviou nenhuma sugestão de melhoria.</p>", unsafe_allow_html=True)

st.markdown(f"<h5>Desvios comportamentais enviados pelo {funcionario_selecionado}</h5>", unsafe_allow_html=True)
df_desvio = df_filtrado[df_filtrado["Status"] == "Desvio Comportamental"]
if not df_desvio.empty:
    df_desvio_display = df_desvio[["Data de Criação", "Tarefa"]].copy()
    df_desvio_display.rename(columns={"Data de Criação": "Data", "Tarefa": "Desvio"}, inplace=True)
    df_desvio_display["Data"] = df_desvio_display["Data"].dt.strftime("%d/%m/%Y")
    st.markdown(df_desvio_display.to_html(index=False, classes="summary-table"), unsafe_allow_html=True)
else:
    st.markdown(f"<p style='font-size:14px;'>Nesse intervalo de datas o funcionário {funcionario_selecionado} não enviou nenhum desvio comportamental.</p>", unsafe_allow_html=True)

st.markdown(f"<h5>Não conformidades enviadas pelo {funcionario_selecionado}</h5>", unsafe_allow_html=True)
df_naoconformidade = df_filtrado[df_filtrado["Status"] == "Não Conformidade"]
if not df_naoconformidade.empty:
    df_naoconformidade_display = df_naoconformidade[["Data de Criação", "Tarefa"]].copy()
    df_naoconformidade_display.rename(columns={"Data de Criação": "Data", "Tarefa": "Não Conformidade"}, inplace=True)
    df_naoconformidade_display["Data"] = df_naoconformidade_display["Data"].dt.strftime("%d/%m/%Y")
    st.markdown(df_naoconformidade_display.to_html(index=False, classes="summary-table"), unsafe_allow_html=True)
else:
    st.markdown(f"<p style='font-size:14px;'>Nesse intervalo de datas o funcionário {funcionario_selecionado} não enviou nenhuma não conformidade.</p>", unsafe_allow_html=True)

# --- Exibição da Tabela de Dados Filtrados (ao final da página) ---
st.write("### Dados Filtrados")
# Aqui, mostramos todas as tarefas (todas as colunas) onde o funcionário aparece como Atribuidor ou Atribuído
df_dados = df_tarefas.copy()
if "Data de Criação" in df_dados.columns:
    df_dados = df_dados[
        (df_dados["Data de Criação"].dt.date >= data_inicio) &
        (df_dados["Data de Criação"].dt.date <= data_fim)
    ]
df_dados = df_dados[
    (df_dados["Atribuidor"] == funcionario_selecionado) | (df_dados["Atribuído"] == funcionario_selecionado)
]
st.dataframe(df_dados.reset_index(drop=True))
