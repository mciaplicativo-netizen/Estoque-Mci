import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
import plotly.express as px
from io import BytesIO

DB_PATH = "estoque_mci.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def importar_excel(file):
    df = pd.read_excel(file, sheet_name="Banco de Dados")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM produtos")
    for _, row in df.iterrows():
        cur.execute("""
            INSERT INTO produtos (descricao, unidade, tipo, local, est_seguranca)
            VALUES (?, ?, ?, ?, ?)
        """, (
            str(row["Descrição"]),
            str(row["Unidade"]),
            str(row["Tipo"]),
            str(row["Local"]),
            float(row["Est Segurança"]) if not pd.isna(row["Est Segurança"]) else None
        ))
    conn.commit()
    conn.close()

def estoque_por_local(local=None):
    conn = get_connection()
    query = """
    SELECT p.id, p.descricao, p.unidade, p.local,
           IFNULL(SUM(e.quantidade), 0) - IFNULL(SUM(s.quantidade), 0) AS saldo
    FROM produtos p
    LEFT JOIN entradas e ON e.produto_id = p.id
    LEFT JOIN saidas s ON s.produto_id = p.id
    """
    if local:
        query += f" WHERE p.local = '{local}'"
    query += " GROUP BY p.id, p.descricao, p.unidade, p.local ORDER BY p.local, p.descricao"
    df = pd.read_sql(query, conn)
    conn.close()
    df = df[df["saldo"] > 0]
    return df

def resumo_geral():
    conn = get_connection()
    query = """
    SELECT p.descricao, p.unidade,
           IFNULL(SUM(e.quantidade), 0) - IFNULL(SUM(s.quantidade), 0) AS saldo_total
    FROM produtos p
    LEFT JOIN entradas e ON e.produto_id = p.id
    LEFT JOIN saidas s ON s.produto_id = p.id
    GROUP BY p.descricao, p.unidade
    HAVING saldo_total > 0
    ORDER BY p.descricao
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def listar_produtos_por_local(local):
    conn = get_connection()
    query = "SELECT id, descricao, unidade FROM produtos WHERE local = ? ORDER BY descricao"
    df = pd.read_sql(query, conn, params=[local])
    conn.close()
    return df

def exportar_excel(df, sheet_name="Estoque"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

def lancar_entrada(produto_id, quantidade, fornecedor=None, observacao=""):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO entradas (produto_id, quantidade, fornecedor, observacao, data)
        VALUES (?, ?, ?, ?, ?)
    """, (produto_id, quantidade, fornecedor, observacao, date.today()))
    conn.commit()
    conn.close()

def lancar_saida(produto_id, quantidade, destino="", observacao=""):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO saidas (produto_id, quantidade, destino, observacao, data)
        VALUES (?, ?, ?, ?, ?)
    """, (produto_id, quantidade, destino, observacao, date.today()))
    conn.commit()
    conn.close()

def consultar_movimentacoes():
    conn = get_connection()
    entradas = pd.read_sql("""
        SELECT e.id, p.descricao, e.quantidade, e.data, e.observacao
        FROM entradas e
        JOIN produtos p ON e.produto_id = p.id
        ORDER BY e.data DESC, e.id DESC
        LIMIT 20
    """, conn)
    saidas = pd.read_sql("""
        SELECT s.id, p.descricao, s.quantidade, s.data, s.destino, s.observacao
        FROM saidas s
        JOIN produtos p ON s.produto_id = p.id
        ORDER BY s.data DESC, s.id DESC
        LIMIT 20
    """, conn)
    conn.close()
    return entradas, saidas

def produtos_mais_movimentados():
    conn = get_connection()
    query = """
    SELECT p.id, p.descricao,
           (IFNULL((SELECT SUM(e.quantidade) FROM entradas e WHERE e.produto_id = p.id), 0) +
            IFNULL((SELECT SUM(s.quantidade) FROM saidas s WHERE s.produto_id = p.id), 0)) AS total_mov
    FROM produtos p
    ORDER BY total_mov DESC
    LIMIT 10
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def historico_produto(produto_id):
    conn = get_connection()
    query = f"""
    SELECT data, 'Entrada' as tipo, quantidade
    FROM entradas WHERE produto_id = {produto_id}
    UNION ALL
    SELECT data, 'Saída' as tipo, -quantidade
    FROM saidas WHERE produto_id = {produto_id}
    ORDER BY data
    """
    df = pd.read_sql(query, conn)
    conn.close()

    if df.empty:
        return pd.DataFrame()

    df["saldo"] = df["quantidade"].cumsum()
    return df

# ----------------- Interface Streamlit -----------------
st.set_page_config(page_title="Gestão de Estoque MCI", layout="wide")
st.title("📦 Gestão de Estoque MCI")

menu = st.sidebar.radio("Menu", ["Estoque Geral", "Lançar Entrada", "Lançar Saída", "Relatórios", "Importar Dados do Excel"])

if menu == "Estoque Geral":
    st.subheader("📍 Estoque por Local")
    locais = pd.read_sql("SELECT DISTINCT local FROM produtos WHERE local IS NOT NULL", get_connection())["local"].tolist()
    local_sel = st.selectbox("Filtrar por Local", ["Todos"] + locais)
    if local_sel != "Todos":
        df = estoque_por_local(local_sel)
    else:
        df = estoque_por_local()
    df_local = df[["local", "descricao", "saldo", "unidade"]]
    st.dataframe(df_local)

    if not df_local.empty:
        excel_bytes = exportar_excel(df_local, sheet_name="Estoque por Local")
        st.download_button(
            label="📥 Exportar Estoque por Local",
            data=excel_bytes,
            file_name="estoque_por_local.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    st.subheader("📊 Resumo Consolidado Geral")
    df_resumo = resumo_geral()
    st.dataframe(df_resumo)

    if not df_resumo.empty:
        excel_bytes2 = exportar_excel(df_resumo, sheet_name="Resumo Geral")
        st.download_button(
            label="📥 Exportar Resumo Geral",
            data=excel_bytes2,
            file_name="resumo_geral.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

elif menu == "Lançar Entrada":
    st.subheader("➕ Nova Entrada")
    locais = pd.read_sql("SELECT DISTINCT local FROM produtos WHERE local IS NOT NULL", get_connection())["local"].tolist()
    local_sel = st.selectbox("Local", locais, index=0 if locais else None)
    if local_sel:
        df = listar_produtos_por_local(local_sel)
        produto = st.selectbox("Produto", df["descricao"], index=None)
        if produto:
            produto_id = df.loc[df["descricao"] == produto, "id"].values[0]
            quantidade = st.number_input("Quantidade", min_value=1.0, step=1.0)
            fornecedor = st.text_input("Fornecedor (opcional)")
            observacao = st.text_input("Observação")
            if st.button("Salvar Entrada"):
                lancar_entrada(produto_id, quantidade, fornecedor=fornecedor, observacao=observacao)
                st.success("Entrada lançada com sucesso!")

elif menu == "Lançar Saída":
    st.subheader("➖ Nova Saída")
    locais = pd.read_sql("SELECT DISTINCT local FROM produtos WHERE local IS NOT NULL", get_connection())["local"].tolist()
    local_sel = st.selectbox("Local", locais, index=0 if locais else None)
    if local_sel:
        df = listar_produtos_por_local(local_sel)
        produto = st.selectbox("Produto", df["descricao"], index=None)
        if produto:
            produto_id = df.loc[df["descricao"] == produto, "id"].values[0]
            quantidade = st.number_input("Quantidade", min_value=1.0, step=1.0)
            destino = st.text_input("Destino")
            observacao = st.text_input("Observação")
            if st.button("Salvar Saída"):
                lancar_saida(produto_id, quantidade, destino=destino, observacao=observacao)
                st.success("Saída lançada com sucesso!")

elif menu == "Relatórios":
    st.subheader("📑 Relatórios de Estoque")

    st.markdown("### 🔄 Movimentações Recentes")
    entradas, saidas = consultar_movimentacoes()
    st.write("**Últimas Entradas**")
    st.dataframe(entradas)
    st.write("**Últimas Saídas**")
    st.dataframe(saidas)

    st.markdown("### 📦 Produtos mais movimentados")
    mov = produtos_mais_movimentados()
    st.dataframe(mov)
    if not mov.empty:
        fig = px.bar(mov, x="descricao", y="total_mov", title="Top 10 Produtos Mais Movimentados")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 📈 Evolução de Estoque de um Produto")
    df_all = pd.read_sql("SELECT id, descricao FROM produtos ORDER BY descricao", get_connection())
    produto_sel = st.selectbox("Selecione o produto", df_all["descricao"], index=None)
    if produto_sel:
        produto_id = df_all.loc[df_all["descricao"] == produto_sel, "id"].values[0]
        hist = historico_produto(produto_id)
        if hist.empty:
            st.info("Ainda não há movimentações para este produto.")
        else:
            fig2 = px.line(hist, x="data", y="saldo", markers=True, title=f"Evolução do Estoque - {produto_sel}")
            st.plotly_chart(fig2, use_container_width=True)

elif menu == "Importar Dados do Excel":
    st.subheader("📤 Importar Produtos via Excel")
    file = st.file_uploader("Selecione o arquivo Excel (Banco de Dados.xlsx)", type=["xlsx"])
    if file:
        try:
            importar_excel(file)
            st.success("Produtos atualizados com sucesso!")
        except Exception as e:
            st.error(f"Erro ao importar: {e}")
