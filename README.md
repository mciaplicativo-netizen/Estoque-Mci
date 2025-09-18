# 📦 Gestão de Estoque MCI

Aplicativo web simples para controle de estoque, desenvolvido em **Streamlit** e **SQLite**.

## 🚀 Funcionalidades
- Consultar estoque atual
- Lançar entradas e saídas
- Relatórios:
  - Últimas movimentações
  - Produtos mais movimentados
  - Estoque crítico
  - Gráficos interativos (evolução de estoque)

## 📂 Estrutura
- `app.py` → Código principal do aplicativo
- `estoque_mci.db` → Banco de dados SQLite
- `requirements.txt` → Dependências do projeto

## ▶️ Executar localmente
```bash
pip install -r requirements.txt
streamlit run app.py
```

## ☁️ Deploy no Streamlit Cloud
1. Suba este repositório no GitHub.
2. Acesse [Streamlit Cloud](https://share.streamlit.io/).
3. Clique em **"New app"** e conecte ao repositório.
4. Informe:
   - **Main file path** → `app.py`
5. Clique em **Deploy** 🚀

O app ficará disponível em um link como:
```
https://seu-usuario-estoque-mci.streamlit.app
```
