import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import math
import requests

# Configuration de la page
st.set_page_config(page_title="Gestionnaire de Portefeuille PEA", layout="wide")

# Initialisation du portfolio dynamique (on stocke toutes les infos nécessaires)
if "portfolio" not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(columns=["ISIN", "Ticker", "Nom", "Quantité", "PRU", "Geo"])

# --- FONCTIONS UTILES ---
@st.cache_data(ttl=3600)
def get_current_price(ticker):
    try:
        if not ticker: return 0.0
        stock = yf.Ticker(ticker)
        return float(stock.fast_info['last_price'])
    except Exception:
        return 0.0

def search_isin_yahoo(isin):
    """Cherche le ticker et le nom via l'API publique de recherche Yahoo Finance."""
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={isin}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        quotes = data.get('quotes', [])
        if quotes:
            # On récupère le premier résultat pertinent
            return quotes[0].get('symbol', ''), quotes[0].get('shortname', 'Nom inconnu')
    except Exception:
        pass
    return "", ""

# --- BARRE LATÉRALE : IMPORT / EXPORT & AJOUT ---
st.sidebar.header("📥 Importer / Sauvegarder")

uploaded_file = st.sidebar.file_uploader("Importer un portefeuille (CSV)", type=["csv"])
if uploaded_file is not None:
    try:
        imported_df = pd.read_csv(uploaded_file)
        if all(col in imported_df.columns for col in ["ISIN", "Ticker", "Nom", "Quantité", "PRU", "Geo"]):
            st.session_state.portfolio = imported_df
            st.sidebar.success("Portefeuille importé avec succès !")
        else:
            st.sidebar.error("Format de CSV invalide.")
    except Exception:
        st.sidebar.error("Erreur lors de l'importation.")

if not st.session_state.portfolio.empty:
    csv_data = st.session_state.portfolio.to_csv(index=False).encode('utf-8')
    st.sidebar.download_button("💾 Télécharger le portefeuille (CSV)", data=csv_data, file_name='mon_portefeuille_pea.csv', mime='text/csv')

st.sidebar.divider()

# --- MOTEUR D'AJOUT UNIVERSEL ---
st.sidebar.header("➕ Ajouter une position")
st.sidebar.write("Entrez un ISIN pour rechercher ses informations sur les marchés :")

input_isin = st.sidebar.text_input("Code ISIN (ex: FR0013412020)").strip().upper()

# Gestion de l'état temporaire pour la recherche
if "temp_ticker" not in st.session_state: st.session_state.temp_ticker = ""
if "temp_nom" not in st.session_state: st.session_state.temp_nom = ""

if st.sidebar.button("🔍 Chercher l'ISIN"):
    if input_isin:
        ticker, nom = search_isin_yahoo(input_isin)
        if ticker:
            st.session_state.temp_ticker = ticker
            st.session_state.temp_nom = nom
            st.sidebar.success(f"Trouvé : {nom} ({ticker})")
        else:
            st.sidebar.warning("Introuvable automatiquement. Veuillez remplir manuellement le Ticker Yahoo.")
            st.session_state.temp_ticker = ""
            st.session_state.temp_nom = ""

# Formulaire d'ajout des paramètres
with st.sidebar.form("add_form"):
    final_ticker = st.text_input("Ticker (Yahoo Finance)", value=st.session_state.temp_ticker)
    final_nom = st.text_input("Nom de l'actif", value=st.session_state.temp_nom)
    final_geo = st.selectbox("Zone géographique", ["États-Unis", "Zone Euro", "Europe Globale", "Émergents", "Asie-Pacifique", "Japon", "Monde", "Inconnu"])
    
    qty_input = st.number_input("Nombre de parts", min_value=1, step=1)
    pru_input = st.number_input("Prix de Revient Unitaire (PRU) €", min_value=0.0, step=0.1, format="%.2f")
    
    submitted = st.form_submit_button("Ajouter / Mettre à jour au portefeuille")
    
    if submitted and input_isin and final_ticker:
        new_data = {
            "ISIN": input_isin, 
            "Ticker": final_ticker, 
            "Nom": final_nom, 
            "Quantité": qty_input, 
            "PRU": pru_input, 
            "Geo": final_geo
        }
        
        # Mise à jour si l'ISIN est déjà présent, sinon ajout d'une nouvelle ligne
        if input_isin in st.session_state.portfolio["ISIN"].values:
            idx = st.session_state.portfolio[st.session_state.portfolio["ISIN"] == input_isin].index
            for col in new_data.keys():
                st.session_state.portfolio.loc[idx, col] = new_data[col]
        else:
            st.session_state.portfolio = pd.concat([st.session_state.portfolio, pd.DataFrame([new_data])], ignore_index=True)
            
        st.success("Position enregistrée !")
        st.session_state.temp_ticker = ""
        st.session_state.temp_nom = ""

if st.sidebar.button("🗑️ Vider le portefeuille"):
    st.session_state.portfolio = pd.DataFrame(columns=["ISIN", "Ticker", "Nom", "Quantité", "PRU", "Geo"])
    st.sidebar.warning("Portefeuille vidé.")

# --- DASHBOARD PRINCIPAL ---
st.title("📊 Tableau de Bord PEA")

if not st.session_state.portfolio.empty:
    df = st.session_state.portfolio.copy()
    
    # Conversions pour éviter les bugs de types avec pandas
    df["Quantité"] = pd.to_numeric(df["Quantité"])
    df["PRU"] = pd.to_numeric(df["PRU"])
    df["Prix Actuel (€)"] = df["Ticker"].apply(get_current_price)
    
    df["Valeur Totale (€)"] = df["Quantité"] * df["Prix Actuel (€)"]
    df["Investissement (€)"] = df["Quantité"] * df["PRU"]
    df["Plus-Value (€)"] = df["Valeur Totale (€)"] - df["Investissement (€)"]
    df["Plus-Value (%)"] = ((df["Prix Actuel (€)"] / df["PRU"]) - 1) * 100
    df["Plus-Value (%)"] = df["Plus-Value (%)"].fillna(0)
    
    st.subheader("📁 Positions Actuelles")
    display_df = df[["ISIN", "Ticker", "Nom", "Geo", "Quantité", "PRU", "Prix Actuel (€)", "Valeur Totale (€)", "Plus-Value (€)", "Plus-Value (%)"]].copy()
    st.dataframe(display_df.style.format({
        "PRU": "{:.2f} €",
        "Prix Actuel (€)": "{:.2f} €",
        "Valeur Totale (€)": "{:.2f} €",
        "Plus-Value (€)": "{:+.2f} €",
        "Plus-Value (%)": "{:+.2f} %"
    }), use_container_width=True)
    
    col1, col2, col3 = st.columns(3)
    val_totale = df['Valeur Totale (€)'].sum()
    inv_total = df['Investissement (€)'].sum()
    pv_globale = df['Plus-Value (€)'].sum()
    pv_pct = ((val_totale / inv_total) - 1) * 100 if inv_total > 0 else 0

    col1.metric("Valorisation Totale", f"{val_totale:.2f} €")
    col2.metric("Total Investi", f"{inv_total:.2f} €")
    col3.metric("Plus-Value Globale", f"{pv_globale:+.2f} €", f"{pv_pct:.2f}%")

    # Répartition Géographique Dynamique
    st.divider()
    st.subheader("🌍 Répartition Géographique")
    
    geo_df = df.groupby("Geo")["Valeur Totale (€)"].sum().reset_index()
    if not geo_df.empty and geo_df["Valeur Totale (€)"].sum() > 0:
        fig = px.pie(geo_df, values="Valeur Totale (€)", names="Geo", hole=0.4, title="Exposition du Portefeuille")
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👈 Ajoutez des positions ou importez un portefeuille CSV via la barre latérale pour commencer.")

# --- SIMULATEUR D'ORDRE DYNAMIQUE ---
st.divider()
st.subheader("🛒 Projet d'Ordre (Tarif PEA Découverte Boursobank)")

if not st.session_state.portfolio.empty:
    list_isins = st.session_state.portfolio["ISIN"].tolist()
    sim_isin = st.selectbox("Sélectionnez un ISIN présent dans votre portefeuille :", list_isins)

    is_boursomarkets_str = st.radio("Ce produit est-il éligible Boursomarkets ?", ["Non (Tarif Découverte)", "Oui (0€ de courtage)"])
    is_boursomarkets = (is_boursomarkets_str == "Oui (0€ de courtage)")

    if sim_isin:
        # On va chercher le ticker directement dans le dataframe du portefeuille
        ticker = st.session_state.portfolio.loc[st.session_state.portfolio["ISIN"] == sim_isin, "Ticker"].values[0]
        current_price = get_current_price(ticker)
        
        if current_price > 0:
            min_amount = 200.0
            qty_needed = math.ceil(min_amount / current_price)
            order_cost = qty_needed * current_price
            
            if is_boursomarkets:
                fees = 0.0
            else:
                base_fee = 1.99 if order_cost <= 500.0 else order_cost * 0.006
                max_legal_pea_fee = order_cost * 0.005
                fees = min(base_fee, max_legal_pea_fee)
                
            total_cost = order_cost + fees
            
            st.write(f"**Prix unitaire estimé :** {current_price:.2f} €")
            
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Quantité minimale (>200€)", f"{qty_needed} parts")
            col_b.metric("Valeur de l'ordre", f"{order_cost:.2f} €")
            col_c.metric("Frais de courtage estimés*", f"{fees:.2f} €")
            
            st.info(f"👉 **Coût total de l'opération : {total_cost:.2f} €**")
            st.caption("*Frais plafonnés légalement à 0,5% maximum pour le PEA.*")
        else:
            st.error("Impossible de récupérer le prix actuel. Vérifiez que le Ticker est correct.")
else:
    st.write("Ajoutez d'abord une ligne dans votre portefeuille pour simuler un ordre.")
