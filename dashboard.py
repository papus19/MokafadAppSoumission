"""
MOKAFAD - Solution Soumission IA
Application principale
"""
import streamlit as st
import config
import database
import ui_components
import auth
import profile
import dashboard
import analyse
import projets
import offres
import generateur_offres
import gestion_projets

# Configuration de la page
st.set_page_config(
    page_title="MOKAFAD - Solution Soumission IA",
    page_icon="⚡",
    layout="wide"
)

# Verification des cles
if not config.SUPABASE_URL or not config.SUPABASE_ANON_KEY:
    st.error("Variables manquantes dans .env")
    st.stop()

# Initialisation de la session
for key, default in [
    ('logged_in', False),
    ('user', None),
    ('profile_completed', False),
    ('access_token', None),
    ('show_login_tab', True),
    ('default_tab', 0),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# En-tete
ui_components.display_header()
# CSS global : onglets plus grands et lisibles
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap');
.stTabs [data-baseweb="tab-list"] {
  gap: 4px; background: #f1f5f9; padding: 6px;
  border-radius: 12px; border: 1px solid #e2e8f0;
}
.stTabs [data-baseweb="tab"] {
  font-family: 'DM Sans', sans-serif !important;
  font-size: 14px !important; font-weight: 500 !important;
  color: #475569 !important; padding: 10px 18px !important;
  border-radius: 8px !important; border: none !important;
  background: transparent !important; white-space: nowrap !important;
}
.stTabs [data-baseweb="tab"]:hover { background: #ffffff !important; color: #1e293b !important; }
.stTabs [aria-selected="true"] {
  background: #ffffff !important; color: #1e6fe8 !important;
  font-weight: 600 !important; box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
}
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }
.stTabs [data-baseweb="tab-border"]    { display: none !important; }
section[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #e2e8f0; }
.stApp { background: #f4f6f9; }
</style>
""", unsafe_allow_html=True)


# Auth Supabase
if st.session_state.logged_in and st.session_state.access_token:
    database.apply_supabase_auth()

# --- AUTHENTIFICATION ---
if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["Connexion", "Inscription"])
    with tab1:
        auth.show_login_page()
    with tab2:
        auth.show_signup_page()

# --- PROFIL A COMPLETER ---
elif not st.session_state.profile_completed:
    profile.show_profile_completion()

# --- APPLICATION PRINCIPALE ---
else:
    user = st.session_state.user

    # SIDEBAR
    with st.sidebar:
        ui_components.display_logo_sidebar(user)
        st.write(f"**{user.get('contact_nom', 'Utilisateur')}**")
        st.write(f"**{user.get('nom_entreprise', 'Entreprise')}**")
        st.write(f"{user.get('ville', '')}, {user.get('province', '')}")

        if st.button("Deconnexion", use_container_width=False):
            try:
                database.supabase.auth.sign_out()
            except Exception:
                pass
            st.session_state.clear()
            st.rerun()

    # Charger les projets anterieurs
    try:
        database.apply_supabase_auth()
        projets_response = database.supabase.table('projets_antecedents').select("*").eq(
            'entreprise_id', user['id']
        ).execute()
        projets_antecedents = projets_response.data if projets_response.data else []
    except Exception as e:
        st.warning(f"Erreur chargement projets : {str(e)}")
        projets_antecedents = []

    # ONGLETS PRINCIPAUX — Mes Offres ajoutee entre Generateur d'Offres et Gestion de Projet
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "Tableau de bord",
        "Nouvelle analyse",
        "Generateur d'Offres",
        "Mes Offres",           # NOUVEL ONGLET
        "Gestion de Projet",
        "Projets anterieurs",
        "Mon profil"
    ])

    with tab1:
        dashboard.show_dashboard(user)

    with tab2:
        analyse.show_analyse_tab(user, projets_antecedents)

    with tab3:
        try:
            offres.show_offres_tab(user, projets_antecedents)
        except Exception as e:
            st.error(f"Erreur generateur d offres : {str(e)}")
            import traceback
            st.code(traceback.format_exc())

    with tab4:
        try:
            offres.show_mes_offres_tab(user)
        except Exception as e:
            st.error(f"Erreur Mes Offres : {str(e)}")
            import traceback
            st.code(traceback.format_exc())

    with tab5:
        try:
            gestion_projets.show_gestion_projets_tab(user)
        except Exception as e:
            st.error(f"Erreur Gestion de Projet : {str(e)}")
            import traceback
            st.code(traceback.format_exc())

    with tab6:
        projets.show_projets_tab(user)

    with tab7:
        profile.show_profile_tab(user)
