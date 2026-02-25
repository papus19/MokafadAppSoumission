"""
MOKAFAD - Solution Soumission IA
Application principale
Modification : Tableau de bord, Projets antérieurs et Profil dans la sidebar
              Onglets principaux : Analyse, Générateur, Mes Offres, Gestion de Projet
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

# ── Configuration de la page ──────────────────────────────────────────
st.set_page_config(
    page_title="MOKAFAD - Solution Soumission IA",
    page_icon="⚡",
    layout="wide"
)

# ── Vérification des clés ─────────────────────────────────────────────
if not config.SUPABASE_URL or not config.SUPABASE_ANON_KEY:
    st.error("Variables manquantes dans .env")
    st.stop()

# ── Initialisation de la session ──────────────────────────────────────
for key, default in [
    ('logged_in',         False),
    ('user',              None),
    ('profile_completed', False),
    ('access_token',      None),
    ('show_login_tab',    True),
    ('default_tab',       0),
    ('sidebar_section',   'dashboard'),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── En-tête ───────────────────────────────────────────────────────────
ui_components.display_header()

# ── CSS global ────────────────────────────────────────────────────────
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

# ── Auth Supabase ─────────────────────────────────────────────────────
if st.session_state.logged_in and st.session_state.access_token:
    database.apply_supabase_auth()


# ════════════════════════════════════════════════════════════════════
# FONCTION ONGLETS PRINCIPAUX — définie avant utilisation
# ════════════════════════════════════════════════════════════════════

def _render_main_tabs(user, projets_antecedents):
    """Onglets du flux de travail principal."""
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔍 Nouvelle analyse",
        "📝 Générateur d'Offres",
        "📁 Mes Offres",
        "📋 Gestion de Projet",
    ])

    with tab1:
        analyse.show_analyse_tab(user, projets_antecedents)

    with tab2:
        try:
            offres.show_offres_tab(user, projets_antecedents)
        except Exception as e:
            st.error(f"Erreur générateur d'offres : {str(e)}")
            import traceback
            st.code(traceback.format_exc())

    with tab3:
        try:
            offres.show_mes_offres_tab(user)
        except Exception as e:
            st.error(f"Erreur Mes Offres : {str(e)}")
            import traceback
            st.code(traceback.format_exc())

    with tab4:
        try:
            gestion_projets.show_gestion_projets_tab(user)
        except Exception as e:
            st.error(f"Erreur Gestion de Projet : {str(e)}")
            import traceback
            st.code(traceback.format_exc())


# ════════════════════════════════════════════════════════════════════
# AUTHENTIFICATION
# ════════════════════════════════════════════════════════════════════

if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["Connexion", "Inscription"])
    with tab1:
        auth.show_login_page()
    with tab2:
        auth.show_signup_page()

# ════════════════════════════════════════════════════════════════════
# PROFIL À COMPLÉTER
# ════════════════════════════════════════════════════════════════════

elif not st.session_state.profile_completed:
    profile.show_profile_completion()

# ════════════════════════════════════════════════════════════════════
# APPLICATION PRINCIPALE
# ════════════════════════════════════════════════════════════════════

else:
    user = st.session_state.user

    # Charger les projets antérieurs
    try:
        database.apply_supabase_auth()
        projets_response    = database.supabase.table('projets_antecedents').select("*").eq(
            'entreprise_id', user['id']
        ).execute()
        projets_antecedents = projets_response.data if projets_response.data else []
    except Exception as e:
        st.warning(f"Erreur chargement projets : {str(e)}")
        projets_antecedents = []

    # ── SIDEBAR ───────────────────────────────────────────────────────
    with st.sidebar:
        ui_components.display_logo_sidebar(user)
        st.write(f"**{user.get('contact_nom', 'Utilisateur')}**")
        st.write(f"**{user.get('nom_entreprise', 'Entreprise')}**")
        st.write(f"{user.get('ville', '')}, {user.get('province', '')}")

        st.markdown("---")
        st.markdown("##### Navigation")

        if st.button("📊 Tableau de bord", key="nav_dashboard", use_container_width=True):
            st.session_state.sidebar_section = "dashboard"
            st.rerun()

        nb_projets  = len(projets_antecedents)
        label_proj  = f"🏗️ Projets antérieurs ({nb_projets})" if nb_projets else "🏗️ Projets antérieurs"
        if st.button(label_proj, key="nav_projets", use_container_width=True):
            st.session_state.sidebar_section = "projets"
            st.rerun()

        if st.button("👤 Mon profil", key="nav_profil", use_container_width=True):
            st.session_state.sidebar_section = "profil"
            st.rerun()

        if st.button("🛠️ Espace de travail", key="nav_travail", use_container_width=True):
            st.session_state.sidebar_section = "travail"
            st.rerun()

        st.markdown("---")

        # Indicateur section active
        labels = {
            "dashboard": "📊 Tableau de bord",
            "projets":   "🏗️ Projets antérieurs",
            "profil":    "👤 Mon profil",
            "travail":   "🛠️ Espace de travail",
        }
        active = st.session_state.get("sidebar_section", "dashboard")
        st.caption(f"Vue active : **{labels.get(active, active)}**")

        st.markdown("---")
        if st.button("🚪 Déconnexion", use_container_width=True):
            try:
                database.supabase.auth.sign_out()
            except Exception:
                pass
            st.session_state.clear()
            st.rerun()

    # ── CONTENU PRINCIPAL ─────────────────────────────────────────────
    active = st.session_state.get("sidebar_section", "dashboard")

    if active == "dashboard":
        dashboard.show_dashboard(user)

    elif active == "projets":
        projets.show_projets_tab(user)

    elif active == "profil":
        profile.show_profile_tab(user)

    else:
        # "travail" ou toute autre valeur → onglets principaux
        _render_main_tabs(user, projets_antecedents)