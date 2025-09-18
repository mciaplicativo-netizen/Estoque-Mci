import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
import plotly.express as px

DB_PATH = "estoque_mci.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

# ----------------- Funções -----------------
def consultar_estoque():
    conn = get_connection()
    query = """
    SELECT p.id, p.sku, p.descricao, p.tipo, p.unidade,
           IFNULL((SELECT SUM(quantidade) FROM entradas e WHERE e.produto_id = p.id), 0) -
           IFNULL((SELECT SUM(quantidade) FROM saidas s WHERE s.produto_id = p.id), 0) AS saldo,
           p.est_seguranca
    FROM produtos p
    ORDER BY p.descricao
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def lancar_entrada(produto_id, quantidade, fornecedor_id=None, observacao=""):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO entradas (produto_id, quantidade, fornecedor_id, observacao, data)
        VALUES (?, ?, ?, ?, ?)
    """, (produto_id, quantidade, fornecedor_id, observacao, date.today()))
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

menu = st.sidebar.radio("Menu", ["Consultar Estoque", "Lançar Entrada", "Lançar Saída", "Relatórios"])

if menu == "Consultar Estoque":
    st.subheader("📊 Estoque Atual")
    df = consultar_estoque()
    df["Alerta"] = df.apply(lambda x: "⚠️ Baixo estoque" if x["saldo"] < (x["est_seguranca"] or 0) else "", axis=1)
    st.dataframe(df)

elif menu == "Lançar Entrada":
    st.subheader("➕ Nova Entrada")
    df = consultar_estoque()
    produto = st.selectbox("Produto", df["descricao"] + " (SKU: " + df["sku"] + ")", index=None)
    if produto:
        produto_id = df.loc[df["descricao"] + " (SKU: " + df["sku"] + ")" == produto, "id"].values[0]
        quantidade = st.number_input("Quantidade", min_value=1.0, step=1.0)
        observacao = st.text_input("Observação")
        if st.button("Salvar Entrada"):
            lancar_entrada(produto_id, quantidade, observacao=observacao)
            st.success("Entrada lançada com sucesso!")

elif menu == "Lançar Saída":
    st.subheader("➖ Nova Saída")
    df = consultar_estoque()
    produto = st.selectbox("Produto", df["descricao"] + " (SKU: " + df["sku"] + ")", index=None)
    if produto:
        produto_id = df.loc[df["descricao"] + " (SKU: " + df["sku"] + ")" == produto, "id"].values[0]
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

    st.markdown("### ⚠️ Produtos em estoque crítico")
    df = consultar_estoque()
    criticos = df[df["saldo"] < (df["est_seguranca"].fillna(0))]
    st.dataframe(criticos)

    st.markdown("### 📈 Evolução de Estoque de um Produto")
    produto_sel = st.selectbox("Selecione o produto", df["descricao"] + " (SKU: " + df["sku"] + ")", index=None)
    if produto_sel:
        produto_id = df.loc[df["descricao"] + " (SKU: " + df["sku"] + ")" == produto_sel, "id"].values[0]
        hist = historico_produto(produto_id)
        if hist.empty:
            st.info("Ainda não há movimentações para este produto.")
        else:
            fig2 = px.line(hist, x="data", y="saldo", markers=True, title=f"Evolução do Estoque - {produto_sel}")
            st.plotly_chart(fig2, use_container_width=True)
