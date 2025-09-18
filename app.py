import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime, timedelta
from io import BytesIO

DB_PATH = "estoque_mci.db"

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

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

def saldo_produto_local(produto_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT IFNULL((SELECT SUM(quantidade) FROM entradas WHERE produto_id=?),0) - IFNULL((SELECT SUM(quantidade) FROM saidas WHERE produto_id=?),0)", (produto_id, produto_id))
    row = cur.fetchone()
    conn.close()
    return row[0] if row is not None else 0

def estoque_por_local(local=None):
    conn = get_connection()
    if local:
        query = """
        SELECT p.local, p.descricao, p.unidade,
               IFNULL((SELECT SUM(e.quantidade) FROM entradas e WHERE e.produto_id = p.id),0) -
               IFNULL((SELECT SUM(s.quantidade) FROM saidas s WHERE s.produto_id = p.id),0) AS saldo
        FROM produtos p
        WHERE p.local = ?
        ORDER BY p.local, p.descricao
        """
        df = pd.read_sql(query, conn, params=[local])
    else:
        query = """
        SELECT p.local, p.descricao, p.unidade,
               IFNULL((SELECT SUM(e.quantidade) FROM entradas e WHERE e.produto_id = p.id),0) -
               IFNULL((SELECT SUM(s.quantidade) FROM saidas s WHERE s.produto_id = p.id),0) AS saldo
        FROM produtos p
        ORDER BY p.local, p.descricao
        """
        df = pd.read_sql(query, conn)
    conn.close()
    df = df[df["saldo"] > 0]
    return df

def resumo_geral():
    conn = get_connection()
    query = """
    SELECT p.descricao, p.unidade,
           IFNULL((SELECT SUM(e.quantidade) FROM entradas e WHERE e.produto_id = p.id),0) -
           IFNULL((SELECT SUM(s.quantidade) FROM saidas s WHERE s.produto_id = p.id),0) AS saldo_total
    FROM produtos p
    GROUP BY p.descricao, p.unidade
    HAVING saldo_total > 0
    ORDER BY p.descricao
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def listar_produtos_por_local(local):
    conn = get_connection()
    df = pd.read_sql("SELECT id, descricao, unidade FROM produtos WHERE local = ? ORDER BY descricao", conn, params=[local])
    conn.close()
    return df

def listar_todos_produtos():
    conn = get_connection()
    df = pd.read_sql("SELECT id, descricao FROM produtos ORDER BY descricao", conn)
    conn.close()
    return df

def exportar_excel(df, sheet_name="Dados"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

def lancar_entrada(produto_id, quantidade, fornecedor=None, observacao=""):
    if quantidade <= 0:
        return False
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO entradas (produto_id, quantidade, fornecedor, observacao, data) VALUES (?, ?, ?, ?, ?)",
                (produto_id, quantidade, fornecedor, observacao, date.today()))
    conn.commit()
    conn.close()
    return True

def lancar_saida(produto_id, quantidade, destino="", observacao=""):
    if quantidade <= 0:
        return False, None
    saldo_atual = saldo_produto_local(produto_id)
    if quantidade > saldo_atual:
        return False, saldo_atual
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO saidas (produto_id, quantidade, destino, observacao, data) VALUES (?, ?, ?, ?, ?)",
                (produto_id, quantidade, destino, observacao, date.today()))
    conn.commit()
    conn.close()
    return True, saldo_atual - quantidade

def consultar_entradas_filtros(start_date=None, end_date=None, produto_id=None, local=None):
    conn = get_connection()
    params = []
    query = """
    SELECT e.id, e.data, p.descricao, p.local, e.quantidade, e.fornecedor, e.observacao
    FROM entradas e JOIN produtos p ON e.produto_id = p.id
    WHERE 1=1
    """
    if start_date is not None:
        query += " AND e.data >= ?"
        params.append(start_date)
    if end_date is not None:
        query += " AND e.data <= ?"
        params.append(end_date)
    if produto_id is not None:
        query += " AND e.produto_id = ?"
        params.append(produto_id)
    if local is not None and local != "Todos":
        query += " AND p.local = ?"
        params.append(local)
    query += " ORDER BY e.data DESC, e.id DESC"
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return df

def consultar_saidas_filtros(start_date=None, end_date=None, produto_id=None, local=None):
    conn = get_connection()
    params = []
    query = """
    SELECT s.id, s.data, p.descricao, p.local, s.quantidade, s.destino, s.observacao
    FROM saidas s JOIN produtos p ON s.produto_id = p.id
    WHERE 1=1
    """
    if start_date is not None:
        query += " AND s.data >= ?"
        params.append(start_date)
    if end_date is not None:
        query += " AND s.data <= ?"
        params.append(end_date)
    if produto_id is not None:
        query += " AND s.produto_id = ?"
        params.append(produto_id)
    if local is not None and local != "Todos":
        query += " AND p.local = ?"
        params.append(local)
    query += " ORDER BY s.data DESC, s.id DESC"
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return df

# ----------------- Interface -----------------
st.set_page_config(page_title="Gestão de Estoque MCI", layout="wide")
st.title("📦 Gestão de Estoque MCI")

menu = st.sidebar.radio("Menu", ["Estoque Geral", "Lançar Entrada", "Lançar Saída", "Controle de Lançamentos", "Relatórios", "Importar Dados do Excel"])

if menu == "Estoque Geral":
    st.subheader("📍 Estoque por Local (itens com saldo > 0)")
    locais = pd.read_sql("SELECT DISTINCT local FROM produtos WHERE local IS NOT NULL", get_connection())["local"].tolist()
    local_sel = st.selectbox("Filtrar por Local", ["Todos"] + locais)
    if local_sel != "Todos":
        df_local = estoque_por_local(local_sel)
    else:
        df_local = estoque_por_local()
    df_local = df_local[["local", "descricao", "saldo", "unidade"]]
    st.dataframe(df_local)

    if not df_local.empty:
        st.download_button("📥 Exportar Estoque por Local", data=exportar_excel(df_local, sheet_name="Estoque por Local"),
                           file_name="estoque_por_local.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.subheader("📊 Resumo Consolidado Geral (entradas - saídas)")
    df_resumo = resumo_geral()
    st.dataframe(df_resumo)
    if not df_resumo.empty:
        st.download_button("📥 Exportar Resumo Geral", data=exportar_excel(df_resumo, sheet_name="Resumo Geral"),
                           file_name="resumo_geral.xlsx", mime="application/vnd.openxmlformats-officedocument-spreadsheetml.sheet")

elif menu == "Lançar Entrada":
    st.subheader("➕ Nova Entrada")
    locais = pd.read_sql("SELECT DISTINCT local FROM produtos WHERE local IS NOT NULL", get_connection())["local"].tolist()
    local_sel = st.selectbox("Local", locais, index=0 if locais else None)
    if local_sel:
        df = listar_produtos_por_local(local_sel)
        produto = st.selectbox("Produto", df["descricao"], index=None)
        if produto:
            produto_id = int(df.loc[df["descricao"] == produto, "id"].values[0])
            quantidade = st.number_input("Quantidade", min_value=0.0, step=1.0, format="%.2f")
            fornecedor = st.text_input("Fornecedor (opcional)")
            observacao = st.text_input("Observação")
            if st.button("Salvar Entrada"):
                ok = lancar_entrada(produto_id, float(quantidade), fornecedor=fornecedor, observacao=observacao)
                if ok:
                    st.success("Entrada lançada com sucesso!")
                else:
                    st.error("Quantidade inválida!")

elif menu == "Lançar Saída":
    st.subheader("➖ Nova Saída")
    locais = pd.read_sql("SELECT DISTINCT local FROM produtos WHERE local IS NOT NULL", get_connection())["local"].tolist()
    local_sel = st.selectbox("Local", locais, index=0 if locais else None)
    if local_sel:
        df = listar_produtos_por_local(local_sel)
        produto = st.selectbox("Produto", df["descricao"], index=None)
        if produto:
            produto_id = int(df.loc[df["descricao"] == produto, "id"].values[0])
            saldo_atual = saldo_produto_local(produto_id)
            st.info(f"Saldo atual no local: {saldo_atual}")
            quantidade = st.number_input("Quantidade", min_value=0.0, step=1.0, format="%.2f")
            destino = st.text_input("Destino")
            observacao = st.text_input("Observação")
            if st.button("Salvar Saída"):
                ok, novo = lancar_saida(produto_id, float(quantidade), destino=destino, observacao=observacao)
                if ok:
                    st.success(f"Saída lançada com sucesso! Novo saldo: {novo}")
                else:
                    st.error(f"Quantidade inválida ou insuficiente! Saldo disponível: {saldo_atual}")

elif menu == "Controle de Lançamentos":
    st.subheader("📑 Controle de Lançamentos (Entradas / Saídas)")

    # filtros com mês atual como padrão
    today = date.today()
    first_day = today.replace(day=1)
    last_day = (first_day + pd.DateOffset(months=1) - pd.DateOffset(days=1)).date()

    col1, col2, col3, col4 = st.columns([1,1,1,1])
    with col1:
        start_date = st.date_input("Data inicial", value=first_day)
    with col2:
        end_date = st.date_input("Data final", value=last_day)
    produtos_all = listar_todos_produtos()
    prod_options = ["Todos"] + produtos_all["descricao"].tolist()
    with col3:
        prod_sel = st.selectbox("Produto", prod_options, index=0)
    locais = ["Todos"] + pd.read_sql("SELECT DISTINCT local FROM produtos WHERE local IS NOT NULL", get_connection())["local"].tolist()
    with col4:
        local_sel = st.selectbox("Local", locais, index=0)

    # map produto selection to id
    produto_id = None
    if prod_sel != "Todos":
        produto_id = int(produtos_all[produtos_all["descricao"] == prod_sel]["id"].values[0])

    # Entradas
    st.markdown("### ➕ Entradas")
    entradas_df = consultar_entradas_filtros(start_date, end_date, produto_id, local_sel)
    st.dataframe(entradas_df)
    if not entradas_df.empty:
        st.download_button("📥 Exportar Entradas (filtradas)", data=exportar_excel(entradas_df, sheet_name="Entradas"),
                           file_name="entradas_filtradas.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # Saídas
    st.markdown("### ➖ Saídas")
    saidas_df = consultar_saidas_filtros(start_date, end_date, produto_id, local_sel)
    st.dataframe(saidas_df)
    if not saidas_df.empty:
        st.download_button("📥 Exportar Saídas (filtradas)", data=exportar_excel(saidas_df, sheet_name="Saidas"),
                           file_name="saidas_filtradas.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

elif menu == "Relatórios":
    st.subheader("📑 Relatórios de Estoque")
    st.markdown("### 🔄 Movimentações Recentes")
    entradas, saidas = (pd.read_sql("SELECT e.id, p.descricao, e.quantidade, e.data, e.observacao FROM entradas e JOIN produtos p ON e.produto_id = p.id ORDER BY e.data DESC, e.id DESC", get_connection()),
                        pd.read_sql("SELECT s.id, p.descricao, s.quantidade, s.data, s.destino, s.observacao FROM saidas s JOIN produtos p ON s.produto_id = p.id ORDER BY s.data DESC, s.id DESC", get_connection()))
    st.write("**Últimas Entradas**")
    st.dataframe(entradas)
    st.write("**Últimas Saídas**")
    st.dataframe(saidas)
    st.markdown("### 📦 Produtos mais movimentados")
    mov = pd.read_sql("""
    SELECT p.id, p.descricao,
           (IFNULL((SELECT SUM(e.quantidade) FROM entradas e WHERE e.produto_id = p.id), 0) +
            IFNULL((SELECT SUM(s.quantidade) FROM saidas s WHERE s.produto_id = p.id), 0)) AS total_mov
    FROM produtos p
    ORDER BY total_mov DESC
    LIMIT 10
    """, get_connection())
    st.dataframe(mov)

    st.markdown("### 📈 Evolução de Estoque de um Produto")
    df_all = listar_todos_produtos()
    produto_sel = st.selectbox("Selecione o produto", df_all["descricao"], index=None)
    if produto_sel:
        produto_id = int(df_all.loc[df_all["descricao"] == produto_sel, "id"].values[0])
        hist = pd.read_sql(f"""
            SELECT data, tipo, quantidade FROM (
              SELECT data, 'Entrada' as tipo, quantidade FROM entradas WHERE produto_id = {produto_id}
              UNION ALL
              SELECT data, 'Saída' as tipo, -quantidade FROM saidas WHERE produto_id = {produto_id}
            ) ORDER BY data
        """, get_connection())
        if hist.empty:
            st.info("Ainda não há movimentações para este produto.")
        else:
            hist["saldo"] = hist["quantidade"].cumsum()
            st.line_chart(hist.set_index("data")["saldo"])

elif menu == "Importar Dados do Excel":
    st.subheader("📤 Importar Produtos via Excel")
    file = st.file_uploader("Selecione o arquivo Excel (Banco de Dados.xlsx)", type=["xlsx"])
    if file:
        try:
            importar_excel(file)
            st.success("Produtos atualizados com sucesso!")
        except Exception as e:
            st.error(f"Erro ao importar: {e}")
