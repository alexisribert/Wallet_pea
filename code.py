import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import math
import requests

# Configuration de la page
st.set_page_config(page_title="Gestionnaire de Portefeuille PEA", layout="wide")

# Initialisation des variables de session
if "portfolio" not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(columns=["ISIN", "Ticker", "Nom", "Quantité", "PRU", "Geo"])

if "sim_ticker" not in st.session_state: st.session_state.sim_ticker = ""
if "sim_nom" not in st.session_state: st.session_state.sim_nom = ""
if "sim_geo" not in st.session_state: st.session_state.sim_geo = "Inconnu (à définir)"

# Liste des zones gérées
GEO_ZONES = ["États-Unis", "Zone Euro / Europe", "Émergents", "Asie-Pacifique", "Japon", "Monde", "Inconnu (à définir)"]

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
            return quotes[0].get('symbol', ''), quotes[0].get('shortname', 'Nom inconnu')
    except Exception:
        pass
    return "", ""

def guess_geo_from_name(name):
    """Déduit la zone géographique en fonction des mots-clés dans le nom de l'ETF."""
    name_lower = name.lower()
    if any(kw in name_lower for kw in ["s&p", "sp500", "nasdaq", " us ", "usa", "msci usa", "russell"]):
        return "États-Unis"
    elif any(kw in name_lower for kw in ["emu", "euro", "europe", "stoxx", "cac", "dax"]):
        return "Zone Euro / Europe"
    elif any(kw in name_lower for kw in ["emerging", "emergent", "em "]):
        return "Émergents"
    elif any(kw in name_lower for kw in ["asia", "asie", "pacific", "pacifique"]):
        return "Asie-Pacifique"
    elif any(kw in name_lower for kw in ["japan", "japon", "topix", "nikkei"]):
        return "Japon"
    elif any(kw in name_lower for kw in ["world", "monde", "acwi"]):
        return "Monde"
    else:
        return "Inconnu (à définir)"

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
    st.sidebar.download_button("💾 Télécharger (CSV)", data=csv_data, file_name='mon_portefeuille_pea.csv', mime='text/csv')

st.sidebar.divider()

# --- MOTEUR D'AJOUT UNIVERSEL ---
st.sidebar.header("➕ Ajouter une position")
st.sidebar.write("Entrez un ISIN pour auto-compléter ses données :")

input_isin = st.sidebar.text_input("Code ISIN (ex: FR0013412020)").strip().upper()

# Variables temporaires pour le formulaire d'ajout
if "add_ticker" not in st.session_state: st.session_state.add_ticker = ""
if "add_nom" not in st.session_state: st.session_state.add_nom = ""
if "add_geo" not in st.session_state: st.session_state.add_geo = "Inconnu (à définir)"

if st.sidebar.button("🔍 Chercher l'ISIN"):
    if input_isin:
        ticker, nom = search_isin_yahoo(input_isin)
        if ticker:
            st.session_state.add_ticker = ticker
            st.session_state.add_nom = nom
            st.session_state.add_geo = guess_geo_from_name(nom)
            st.sidebar.success(f"Trouvé : {nom} ({ticker})")
        else:
            st.sidebar.warning("Introuvable automatiquement. Remplissez manuellement.")
            st.session_state.add_ticker = ""
            st.session_state.add_nom = ""
            st.session_state.add_geo = "Inconnu (à définir)"

with st.sidebar.form("add_form"):
    final_ticker = st.text_input("Ticker (Yahoo Finance)", value=st.session_state.add_ticker)
    final_nom = st.text_input("Nom de l'actif", value=st.session_state.add_nom)
    
    default_geo_index = GEO_ZONES.index(st.session_state.add_geo) if st.session_state.add_geo in GEO_ZONES else 6
    final_geo = st.selectbox("Zone géographique", GEO_ZONES, index=default_geo_index)
    
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
        
        if input_isin in st.session_state.portfolio["ISIN"].values:
            idx = st.session_state.portfolio[st.session_state.portfolio["ISIN"] == input_isin].index
            for col in new_data.keys():
                st.session_state.portfolio.loc[idx, col] = new_data[col]
        else:
            st.session_state.portfolio = pd.concat([st.session_state.portfolio, pd.DataFrame([new_data])], ignore_index=True)
            
        st.success("Position enregistrée !")

if st.sidebar.button("🗑️ Vider le portefeuille"):
    st.session_state.portfolio = pd.DataFrame(columns=["ISIN", "Ticker", "Nom", "Quantité", "PRU", "Geo"])
    st.sidebar.warning("Portefeuille vidé.")

# --- DASHBOARD PRINCIPAL ---
st.title("📊 Tableau de Bord PEA")

if not st.session_state.portfolio.empty:
    df = st.session_state.portfolio.copy()
    
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

    st.divider()
    st.subheader("🌍 Répartition Géographique")
    
    geo_df = df.groupby("Geo")["Valeur Totale (€)"].sum().reset_index()
    if not geo_df.empty and geo_df["Valeur Totale (€)"].sum() > 0:
        fig = px.pie(geo_df, values="Valeur Totale (€)", names="Geo", hole=0.4, title="Exposition du Portefeuille")
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👈 Ajoutez des positions ou importez un portefeuille CSV via la barre latérale pour commencer.")

# --- SIMULATEUR D'ORDRE UNIVERSEL ---
st.divider()
st.subheader("🛒 Projet d'Ordre & Impact Géographique")
st.write("Saisissez n'importe quel ISIN pour simuler un ordre et visualiser son impact sur la répartition de votre portefeuille.")

col_s1, col_s2 = st.columns([2, 1])
with col_s1:
    sim_input_isin = st.text_input("Code ISIN à simuler (ex: FR0013412020) :").strip().upper()
with col_s2:
    st.write("")
    st.write("")
    if st.button("Chercher l'actif"):
        if sim_input_isin:
            ticker_sim, nom_sim = search_isin_yahoo(sim_input_isin)
            if ticker_sim:
                st.session_state.sim_ticker = ticker_sim
                st.session_state.sim_nom = nom_sim
                st.session_state.sim_geo = guess_geo_from_name(nom_sim)
            else:
                st.error("ISIN introuvable sur Yahoo Finance.")
                st.session_state.sim_ticker = ""

# Si un actif a été trouvé et stocké dans la session, on affiche la suite
if st.session_state.sim_ticker:
    st.success(f"Actif trouvé : **{st.session_state.sim_nom}** (Ticker: {st.session_state.sim_ticker})")
    
    current_price = get_current_price(st.session_state.sim_ticker)
    
    if current_price > 0:
        # Options de simulation
        col_opt1, col_opt2 = st.columns(2)
        with col_opt1:
            is_boursomarkets_str = st.radio("Frais de courtage :", ["Tarif Découverte Classique", "Éligible Boursomarkets (0€)"], horizontal=True)
            is_boursomarkets = (is_boursomarkets_str == "Éligible Boursomarkets (0€)")
        with col_opt2:
            default_sim_geo_idx = GEO_ZONES.index(st.session_state.sim_geo) if st.session_state.sim_geo in GEO_ZONES else 6
            sim_geo_selected = st.selectbox("Zone géo. de l'actif (modifiable) :", GEO_ZONES, index=default_sim_geo_idx)

        # Calculs de l'ordre
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
        
        st.write(f"**Prix unitaire actuel :** {current_price:.2f} €")
        
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Quantité minimale (>200€)", f"{qty_needed} parts")
        col_b.metric("Valeur de l'ordre", f"{order_cost:.2f} €")
        col_c.metric("Frais de courtage estimés*", f"{fees:.2f} €")
        
        st.info(f"👉 **Coût total de l'opération : {total_cost:.2f} €**")
        
        # --- PONDÉRATION GÉOGRAPHIQUE SIMULÉE ---
        st.markdown("### ⚖️ Comparatif de pondération (Avant / Après)")
        
        if not st.session_state.portfolio.empty:
            # Récupération des valorisations actuelles
            curr_df = st.session_state.portfolio.copy()
            curr_df["Valeur Totale (€)"] = pd.to_numeric(curr_df["Quantité"]) * curr_df["Ticker"].apply(get_current_price)
            current_geo = curr_df.groupby("Geo")["Valeur Totale (€)"].sum().reset_index()
            
            # Création du dataframe simulé avec le nouvel ordre
            new_row = pd.DataFrame([{"Geo": sim_geo_selected, "Valeur Totale (€)": order_cost}])
            sim_df = pd.concat([curr_df, new_row], ignore_index=True)
            simulated_geo = sim_df.groupby("Geo")["Valeur Totale (€)"].sum().reset_index()

            # Affichage des deux graphiques côte à côte
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                fig1 = px.pie(current_geo, values="Valeur Totale (€)", names="Geo", hole=0.4, title="Répartition Actuelle")
                fig1.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig1, use_container_width=True)
                
            with col_chart2:
                fig2 = px.pie(simulated_geo, values="Valeur Totale (€)", names="Geo", hole=0.4, title="Répartition Simulée (Post-Achat)")
                fig2.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig2, use_container_width=True)
        else:
            st.warning("Votre portefeuille est actuellement vide. Ajoutez d'abord vos positions existantes pour comparer la répartition avant et après cet ordre.")
    else:
        st.error("Prix indisponible actuellement.")
