"""
Gestion des projets antérieurs
"""
import streamlit as st
import database


def show_projets_tab(user):
    """Affiche l'onglet des projets antérieurs"""
    st.header("🏗️ Vos projets antérieurs")
    
    with st.expander("➕ Ajouter un projet"):
        with st.form("add_projet"):
            col1, col2 = st.columns(2)
            with col1:
                nom_p = st.text_input("Nom du projet *")
                montant_p = st.number_input("Montant ($)", min_value=0, value=0)
                duree_p = st.number_input("Durée (jours)", min_value=1, value=1)
            with col2:
                specs_p = st.text_area("Spécifications")
                doc_p = st.file_uploader("Document PDF (optionnel)", type=["pdf"])
            
            if st.form_submit_button("💾 Ajouter", use_container_width=False):
                if not nom_p:
                    st.error("❌ Le nom du projet est obligatoire")
                else:
                    if database.add_projet_antecedent({
                        "nom_projet": nom_p,
                        "montant": montant_p,
                        "duree_jours": duree_p,
                        "specifications": specs_p,
                        "document": doc_p
                    }):
                        st.rerun()
    
    try:
        database.apply_supabase_auth()
        projets = database.supabase.table('projets_antecedents').select("*").eq(
            'entreprise_id', user['id']
        ).order('created_at', desc=True).execute()
        
        if not projets.data or len(projets.data) == 0:
            st.info("📭 Aucun projet pour le moment")
        else:
            for projet in projets.data:
                with st.expander(f"🏗️ {projet.get('nom_projet', 'Sans nom')}"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.write(f"**Montant :** {projet.get('montant', 0):,.2f} $")
                        st.write(f"**Durée :** {projet.get('duree_jours', 0)} jours")
                    with col_b:
                        st.write(f"**Date :** {projet.get('created_at', '')[:10]}")
                        if projet.get('document_url'):
                            st.markdown(f"[📄 Voir document]({projet['document_url']})")
                    st.write(f"**Spécifications :** {projet.get('specifications', 'Aucune')}")
    except Exception as e:
        st.error(f"❌ Erreur lors du chargement des projets : {str(e)}")
