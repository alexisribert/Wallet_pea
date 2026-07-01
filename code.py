import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import math

# Configuration de la page
st.set_page_config(page_title="Gestionnaire de Portefeuille PEA", layout="wide")

# --- BASE DE DONNÉES LOCALE ---
ASSET_DB = {
    "FR0011871136": {"ticker": "PE500.PA", "name": "Amundi PEA S&P 500", "geo": {"États-Unis": 100}},
    "LU1646361276": {"ticker": "CG1.PA", "name": "Amundi MSCI EMU", "geo": {"Zone Euro": 100}},
    "FR0013412020": {"ticker": "PAEEM.PA", "name": "Amundi PEA Émergent", "geo": {"Émergents": 100}},
    "FR0011871110": {"ticker": "PUST.PA", "name": "Amundi PEA Nasdaq-100", "geo": {"États-Unis": 100}},
    "FR0011869312": {"ticker": "PAEJ.PA", "name": "Amundi PEA Asie-Pacifique", "geo": {"Asie-Pacifique": 100}},
    "FR0013411980": {"ticker": "PJE.PA", "name": "Amundi PEA Japon", "geo": {"Japon": 100}},
}

# Initialisation des données de session
if "portfolio" not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(columns=["ISIN", "Quantité", "PRU"])

# --- FONCTIONS UTILES ---
@st.cache_data(ttl=3600)
def get_current_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        return float(stock.fast_info['last_price'])
    except Exception:
        return 0.0

# --- BARRE LATÉRALE : IMPORT / EXPORT & AJOUT ---
st.sidebar.header("📥 Importer / Sauvegarder")

# Fonctionnalité d'importation CSV
uploaded_file = st.sidebar.file_uploader("Importer un portefeuille (CSV)", type=["csv"])
if uploaded_file is not None:
    try:
        imported_df = pd.read_csv(uploaded_file)
        # Vérification basique des colonnes
        if all(col in imported_df.columns for col in ["ISIN", "Quantité", "PRU"]):
            st.session_state.portfolio = imported_df
            st.sidebar.success("Portefeuille importé avec succès !")
        else:
            st.sidebar.error("Le CSV doit contenir les colonnes: ISIN, Quantité, PRU")
    except Exception as e:
        st.sidebar.error("Erreur lors de l'importation.")

# Fonctionnalité de sauvegarde CSV
if not st.session_state.portfolio.empty:
    csv_data = st.session_state.portfolio.to_csv(index=False).encode('utf-8')
    st.sidebar.download_button(
        label="💾 Télécharger le portefeuille (CSV)",
        data=csv_data,
        file_name='mon_portefeuille_pea.csv',
        mime='text/csv',
    )

st.sidebar.divider()

st.sidebar.header("➕ Ajouter une position")
selected_isin = st.sidebar.selectbox("Sélectionner un ISIN", list(ASSET_DB.keys()))
qty_input = st.sidebar.number_input("Nombre de parts", min_value=1, step=1)
pru_input = st.sidebar.number_input("Prix de Revient Unitaire (PRU) €", min_value=0.0, step=0.1)

if st.sidebar.button("Ajouter / Mettre à jour"):
    new_data = {"ISIN": selected_isin, "Quantité": qty_input, "PRU": pru_input}
    if selected_isin in st.session_state.portfolio["ISIN"].values:
        idx = st.session_state.portfolio[st.session_state.portfolio["ISIN"] == selected_isin].index
        st.session_state.portfolio.loc[idx, ["Quantité", "PRU"]] = [qty_input, pru_input]
    else:
        st.session_state.portfolio = pd.concat([st.session_state.portfolio, pd.DataFrame([new_data])], ignore_index=True)
    st.sidebar.success("Position mise à jour !")

if st.sidebar.button("Vider le portefeuille"):
    st.session_state.portfolio = pd.DataFrame(columns=["ISIN", "Quantité", "PRU"])
    st.sidebar.warning("Portefeuille vidé.")

# --- DASHBOARD PRINCIPAL ---
st.title("📊 Tableau de Bord PEA")

if not st.session_state.portfolio.empty:
    df = st.session_state.portfolio.copy()
    
    # Sécurisation des types pour les calculs
    df["Quantité"] = pd.to_numeric(df["Quantité"])
    df["PRU"] = pd.to_numeric(df["PRU"])
    
    # Enrichissement
    df["Nom"] = df["ISIN"].apply(lambda x: ASSET_DB.get(x, {}).get("name", "Inconnu"))
    df["Ticker"] = df["ISIN"].apply(lambda x: ASSET_DB.get(x, {}).get("ticker", ""))
    df["Prix Actuel (€)"] = df["Ticker"].apply(lambda x: get_current_price(x) if x else 0.0)
    
    df["Valeur Totale (€)"] = df["Quantité"] * df["Prix Actuel (€)"]
    df["Investissement (€)"] = df["Quantité"] * df["PRU"]
    df["Plus-Value (€)"] = df["Valeur Totale (€)"] - df["Investissement (€)"]
    df["Plus-Value (%)"] = ((df["Prix Actuel (€)"] / df["PRU"]) - 1) * 100
    df["Plus-Value (%)"] = df["Plus-Value (%)"].fillna(0)
    
    # Affichage du tableau
    st.subheader("📁 Positions Actuelles")
    display_df = df[["ISIN", "Nom", "Quantité", "PRU", "Prix Actuel (€)", "Valeur Totale (€)", "Plus-Value (€)", "Plus-Value (%)"]].copy()
    st.dataframe(display_df.style.format({
        "PRU": "{:.2f} €",
        "Prix Actuel (€)": "{:.2f} €",
        "Valeur Totale (€)": "{:.2f} €",
        "Plus-Value (€)": "{:+.2f} €",
        "Plus-Value (%)": "{:+.2f} %"
    }), use_container_width=True)
    
    # Métriques globales
    col1, col2, col3 = st.columns(3)
    val_totale = df['Valeur Totale (€)'].sum()
    inv_total = df['Investissement (€)'].sum()
    pv_globale = df['Plus-Value (€)'].sum()
    pv_pct = ((val_totale / inv_total) - 1) * 100 if inv_total > 0 else 0

    col1.metric("Valorisation Totale", f"{val_totale:.2f} €")
    col2.metric("Total Investi", f"{inv_total:.2f} €")
    col3.metric("Plus-Value Globale", f"{pv_globale:+.2f} €", f"{pv_pct:.2f}%")

    # Répartition Géographique
    st.divider()
    st.subheader("🌍 Répartition Géographique")
    
    geo_data = {}
    for _, row in df.iterrows():
        isin = row["ISIN"]
        valeur = row["Valeur Totale (€)"]
        geo_dict = ASSET_DB.get(isin, {}).get("geo", {"Inconnu": 100})
        
        for region, weight in geo_dict.items():
            part_valeur = valeur * (weight / 100.0)
            if region in geo_data:
                geo_data[region] += part_valeur
            else:
                geo_data[region] = part_valeur
                
    geo_df = pd.DataFrame(list(geo_data.items()), columns=["Région", "Valeur Exposée (€)"])
    if not geo_df.empty and geo_df["Valeur Exposée (€)"].sum() > 0:
        fig = px.pie(geo_df, values="Valeur Exposée (€)", names="Région", hole=0.4, title="Exposition du Portefeuille")
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👈 Ajoutez des positions ou importez un portefeuille CSV via la barre latérale.")

# --- SIMULATEUR D'ORDRE (TARIF DÉCOUVERTE) ---
st.divider()
st.subheader("🛒 Projet d'Ordre (Tarif PEA Découverte)")

sim_isin = st.selectbox("ISIN à acheter :", list(ASSET_DB.keys()))

# Choix de l'éligibilité Boursomarkets
is_boursomarkets_str = st.radio(
    "Ce produit est-il éligible Boursomarkets ?", 
    ["Non (Tarif Découverte)", "Oui (0€ de courtage)"]
)
is_boursomarkets = (is_boursomarkets_str == "Oui (0€ de courtage)")

if sim_isin:
    ticker = ASSET_DB[sim_isin]["ticker"]
    current_price = get_current_price(ticker)
    
    if current_price > 0:
        # Seuil PEA Boursobank
        min_amount = 200.0
        qty_needed = math.ceil(min_amount / current_price)
        order_cost = qty_needed * current_price
        
        # Calcul des frais selon la grille Découverte
        if is_boursomarkets:
            fees = 0.0
        else:
            # Grille image : 1,99€ jusqu'à 500€, puis 0,60% au-delà
            if order_cost <= 500.0:
                base_fee = 1.99
            else:
                base_fee = order_cost * 0.006
                
            # RÈGLE LÉGALE PEA : Plafond strict à 0,5% du montant de l'ordre
            max_legal_pea_fee = order_cost * 0.005
            
            # Le courtier applique le tarif de sa grille dans la limite légale
            fees = min(base_fee, max_legal_pea_fee)
            
        total_cost = order_cost + fees
        
        st.write(f"**Prix unitaire estimé :** {current_price:.2f} €")
        
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Quantité minimale (>200€)", f"{qty_needed} parts")
        col_b.metric("Valeur de l'ordre", f"{order_cost:.2f} €")
        col_c.metric("Frais de courtage estimés*", f"{fees:.2f} €")
        
        st.info(f"👉 **Coût total de l'opération : {total_cost:.2f} €**")
        st.caption("*Les frais appliquent la grille 'Découverte' (1,99€ < 500€, 0,60% au-delà) tout en respectant le plafond légal maximum du PEA fixé à 0,5% par transaction.*")
    else:
        st.error("Impossible de récupérer le prix actuel. Marché fermé ou ticker invalide.")
