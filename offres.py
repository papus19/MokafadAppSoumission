"""
Interface utilisateur pour la génération d'offres
"""
import streamlit as st
from pypdf import PdfReader
from datetime import datetime
import json
import generateur_offres
import database


def show_offres_tab(user, projets_antecedents):
    """Affiche l'onglet de génération d'offres"""
    st.header("📝 Générateur d'Offres")
    
    # Récupérer les soumissions qualifiées
    try:
        database.apply_supabase_auth()
        soumissions = database.supabase.table('soumissions').select("*").eq(
            'entreprise_id', user['id']
        ).in_('recommendation', ['GO', 'PEUT-ÊTRE']).order('created_at', desc=True).execute()
        
        soumissions_list = soumissions.data if soumissions.data else []
    except Exception as e:
        st.error(f"❌ Erreur chargement : {str(e)}")
        soumissions_list = []
    
    if not soumissions_list:
        st.info("📭 Aucune soumission qualifiée. Analysez d'abord des appels d'offres.")
        return
    
    # Sélectionner une soumission
    st.subheader("1️⃣ Sélectionner un projet")
    
    soumission_selectionnee = st.selectbox(
        "Projet",
        options=soumissions_list,
        format_func=lambda x: f"{x.get('nom_projet')} - Score: {x.get('score', 0)}/100"
    )
    
    if not soumission_selectionnee:
        return
    
    # Initialiser l'état de session
    if 'offre_data' not in st.session_state:
        st.session_state.offre_data = {}
    
    # Tabs pour les différentes étapes
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📄 Extraction", 
        "🔧 Offre Technique", 
        "💰 Offre Financière",
        "✅ Validation",
        "📤 Envoi",
        "📊 Suivi Statut"
    ])
    
    # ─────────────────────────────────────────────────────────
    # TAB 1 : Extraction des exigences
    # ─────────────────────────────────────────────────────────
    with tab1:
        st.subheader("2️⃣ Extraire les exigences")
        
        uploaded_file = st.file_uploader(
            "📄 Charger l'appel d'offres complet (PDF)",
            type=['pdf'],
            key="offre_pdf"
        )
        
        if uploaded_file and st.button("🔍 Extraire les exigences"):
            with st.spinner("🤖 Extraction en cours..."):
                try:
                    reader = PdfReader(uploaded_file)
                    texte = " ".join([page.extract_text() or "" for page in reader.pages])
                    
                    exigences = generateur_offres.extraire_exigences_appel_offre(texte)
                    
                    if exigences:
                        st.session_state.offre_data['exigences'] = exigences
                        st.success("✅ Exigences extraites !")
                except Exception as e:
                    st.error(f"❌ Erreur : {str(e)}")
        
        if st.session_state.offre_data.get('exigences'):
            exigences = st.session_state.offre_data['exigences']
            
            st.success("✅ Exigences extraites avec succès")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Projet", exigences.get('numero_projet', 'N/A'))
            with col2:
                st.metric("Client", exigences.get('client', 'N/A'))
            with col3:
                st.metric("Durée", exigences.get('duree_projet', 'N/A'))
            
            with st.expander("📋 Voir le détail des exigences"):
                st.markdown(f"**Nom projet :** {exigences.get('nom_projet', 'N/A')}")
                st.markdown(f"**Date clôture :** {exigences.get('date_cloture', 'N/A')}")
                st.markdown(f"**Sommaire :** {exigences.get('sommaire', 'N/A')}")
                
                st.markdown("**Méthodologie requise :**")
                for item in exigences.get('methodologie_requise', []):
                    st.write(f"  • {item}")
                
                st.markdown("**Livrables attendus :**")
                for item in exigences.get('livrables', []):
                    st.write(f"  • {item}")
                
                st.markdown("**Exigences techniques :**")
                for item in exigences.get('exigences_techniques', []):
                    st.write(f"  • {item}")
    
    # ─────────────────────────────────────────────────────────
    # TAB 2 : Offre technique — édition complète de toutes les sections
    # ─────────────────────────────────────────────────────────
    with tab2:
        st.subheader("3️⃣ Générer l'offre technique")
        
        if not st.session_state.offre_data.get('exigences'):
            st.warning("⚠️ Extrayez d'abord les exigences (Onglet Extraction)")
        else:
            if st.button("🤖 Générer l'offre technique"):
                with st.spinner("🤖 Génération en cours..."):
                    try:
                        offre_tech = generateur_offres.generer_offre_technique(
                            st.session_state.offre_data['exigences'],
                            projets_antecedents,
                            user
                        )
                        
                        if offre_tech:
                            st.session_state.offre_data['offre_technique'] = offre_tech
                            st.success("✅ Offre technique générée !")
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erreur : {str(e)}")
            
            if st.session_state.offre_data.get('offre_technique'):
                offre_tech = st.session_state.offre_data['offre_technique']
                
                st.success("✅ Offre technique disponible — toutes les sections sont modifiables ci-dessous")
                st.markdown("---")

                # ── Section 1 : Titre ──────────────────────────────────
                st.markdown("### ✏️ Titre de l'offre")
                offre_tech['titre_offre'] = st.text_input(
                    "Titre",
                    value=offre_tech.get('titre_offre', ''),
                    key="edit_titre"
                )

                # ── Section 2 : Introduction ───────────────────────────
                st.markdown("### 1. Introduction")
                offre_tech['introduction'] = st.text_area(
                    "Introduction",
                    value=offre_tech.get('introduction', ''),
                    height=150,
                    key="edit_intro"
                )

                # ── Section 3 : Compréhension du projet ───────────────
                st.markdown("### 2. Compréhension du projet")
                offre_tech['comprehension_projet'] = st.text_area(
                    "Compréhension du projet",
                    value=offre_tech.get('comprehension_projet', ''),
                    height=150,
                    key="edit_comprehension"
                )

                # ── Section 4 : Approche méthodologique ───────────────
                st.markdown("### 3. Approche méthodologique")
                
                approche = offre_tech.setdefault('approche_methodologique', {})
                approche['description'] = st.text_area(
                    "Description de l'approche",
                    value=approche.get('description', ''),
                    height=120,
                    key="edit_approche_desc"
                )

                st.markdown("#### Phases du projet")
                phases = approche.setdefault('phases', [])
                phases_a_supprimer = []

                for i, phase in enumerate(phases):
                    with st.expander(f"Phase {i+1} : {phase.get('nom', 'Nouvelle phase')}", expanded=False):
                        phase['nom'] = st.text_input("Nom de la phase", value=phase.get('nom', ''), key=f"phase_nom_{i}")
                        phase['duree'] = st.text_input("Durée (ex: 10 jours)", value=phase.get('duree', ''), key=f"phase_duree_{i}")
                        phase['description'] = st.text_area("Description", value=phase.get('description', ''), height=100, key=f"phase_desc_{i}")
                        if st.button("🗑️ Supprimer cette phase", key=f"phase_del_{i}"):
                            phases_a_supprimer.append(i)

                for idx in sorted(phases_a_supprimer, reverse=True):
                    phases.pop(idx)

                if st.button("➕ Ajouter une phase"):
                    phases.append({"nom": "Nouvelle phase", "duree": "X jours", "description": ""})
                    st.rerun()

                # ── Section 5 : Équipe proposée ────────────────────────
                st.markdown("### 4. Équipe proposée")
                equipe = offre_tech.setdefault('equipe_proposee', [])
                membres_a_supprimer = []

                for i, membre in enumerate(equipe):
                    with st.expander(f"👤 {membre.get('nom', 'Nouveau membre')} — {membre.get('role', '')}", expanded=False):
                        col1, col2 = st.columns(2)
                        with col1:
                            membre['nom'] = st.text_input("Nom", value=membre.get('nom', ''), key=f"mb_nom_{i}")
                            membre['role'] = st.text_input("Rôle", value=membre.get('role', ''), key=f"mb_role_{i}")
                        with col2:
                            membre['experience'] = st.text_input("Expérience", value=membre.get('experience', ''), key=f"mb_exp_{i}")
                        
                        responsabilites_text = "\n".join(membre.get('responsabilites', []))
                        new_resp = st.text_area(
                            "Responsabilités (une par ligne)",
                            value=responsabilites_text,
                            height=80,
                            key=f"mb_resp_{i}"
                        )
                        membre['responsabilites'] = [r.strip() for r in new_resp.split('\n') if r.strip()]
                        
                        if st.button("🗑️ Supprimer ce membre", key=f"mb_del_{i}"):
                            membres_a_supprimer.append(i)

                for idx in sorted(membres_a_supprimer, reverse=True):
                    equipe.pop(idx)

                if st.button("➕ Ajouter un membre"):
                    equipe.append({"nom": "", "role": "", "experience": "", "responsabilites": []})
                    st.rerun()

                # ── Section 6 : Livrables ──────────────────────────────
                st.markdown("### 5. Livrables")
                livrables = offre_tech.setdefault('livrables', [])
                livrables_a_supprimer = []

                for i, livrable in enumerate(livrables):
                    with st.expander(f"📄 {livrable.get('nom', 'Nouveau livrable')}", expanded=False):
                        livrable['nom'] = st.text_input("Nom", value=livrable.get('nom', ''), key=f"lv_nom_{i}")
                        livrable['description'] = st.text_area("Description", value=livrable.get('description', ''), height=80, key=f"lv_desc_{i}")
                        livrable['format'] = st.text_input("Format (ex: PDF, Excel)", value=livrable.get('format', ''), key=f"lv_fmt_{i}")
                        if st.button("🗑️ Supprimer ce livrable", key=f"lv_del_{i}"):
                            livrables_a_supprimer.append(i)

                for idx in sorted(livrables_a_supprimer, reverse=True):
                    livrables.pop(idx)

                if st.button("➕ Ajouter un livrable"):
                    livrables.append({"nom": "", "description": "", "format": "PDF"})
                    st.rerun()

                # ── Section 7 : Garanties qualité ─────────────────────
                st.markdown("### 6. Garanties qualité")
                garanties_text = "\n".join(offre_tech.get('garanties_qualite', []))
                new_garanties = st.text_area(
                    "Garanties (une par ligne)",
                    value=garanties_text,
                    height=100,
                    key="edit_garanties"
                )
                offre_tech['garanties_qualite'] = [g.strip() for g in new_garanties.split('\n') if g.strip()]

                # ── Section 8 : Avantages concurrentiels ──────────────
                st.markdown("### 7. Avantages concurrentiels")
                avantages_text = "\n".join(offre_tech.get('avantages_concurrentiels', []))
                new_avantages = st.text_area(
                    "Avantages (un par ligne)",
                    value=avantages_text,
                    height=100,
                    key="edit_avantages"
                )
                offre_tech['avantages_concurrentiels'] = [a.strip() for a in new_avantages.split('\n') if a.strip()]

                # ── Section 9 : Références clients ────────────────────
                st.markdown("### 8. Références clients")
                offre_tech['references_clients'] = st.text_area(
                    "Références",
                    value=offre_tech.get('references_clients', ''),
                    height=80,
                    key="edit_refs"
                )

                st.markdown("---")
                if st.button("💾 Sauvegarder les modifications", type="primary"):
                    st.session_state.offre_data['offre_technique'] = offre_tech
                    st.success("✅ Modifications sauvegardées !")

                with st.expander("🔧 Données JSON brutes (débogage)"):
                    st.json(offre_tech)

    # ─────────────────────────────────────────────────────────
    # TAB 3 : Offre financière
    # ─────────────────────────────────────────────────────────
    with tab3:
        st.subheader("4️⃣ Générer l'offre financière")
        
        if not st.session_state.offre_data.get('offre_technique'):
            st.warning("⚠️ Générez d'abord l'offre technique (Onglet Offre Technique)")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                taux_horaire = st.number_input(
                    "💵 Taux horaire ($/h)",
                    min_value=50,
                    max_value=500,
                    value=125,
                    step=5,
                    key="taux_horaire_input"
                )
            
            with col2:
                if st.button("💰 Calculer l'offre financière"):
                    try:
                        offre_fin = generateur_offres.calculer_offre_financiere(
                            st.session_state.offre_data['offre_technique'],
                            taux_horaire
                        )
                        
                        if offre_fin:
                            st.session_state.offre_data['offre_financiere'] = offre_fin
                            st.success("✅ Offre financière calculée !")
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erreur : {str(e)}")
            
            if st.session_state.offre_data.get('offre_financiere'):
                offre_fin = st.session_state.offre_data['offre_financiere']
                
                st.success("✅ Offre financière disponible")
                
                st.markdown("### 📊 Détail des coûts")
                
                with st.expander("✏️ Modifier les postes budgétaires", expanded=False):
                    st.info("💡 Modifiez les quantités ou prix unitaires ci-dessous")
                    
                    for i, poste in enumerate(offre_fin.get('postes_budgetaires', [])):
                        st.markdown(f"#### Poste {i+1}: {poste['description']}")
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            nouvelle_quantite = st.number_input(
                                "Quantité (heures)",
                                min_value=0,
                                value=int(poste['quantite']),
                                step=1,
                                key=f"qte_{i}"
                            )
                            poste['quantite'] = nouvelle_quantite
                        
                        with col2:
                            nouveau_prix = st.number_input(
                                "Prix unitaire ($)",
                                min_value=0,
                                value=int(poste['prix_unitaire']),
                                step=5,
                                key=f"prix_{i}"
                            )
                            poste['prix_unitaire'] = nouveau_prix
                        
                        with col3:
                            poste['total'] = nouvelle_quantite * nouveau_prix
                            st.metric("Total", f"{poste['total']:,.2f} $")
                        
                        st.markdown("---")
                    
                    if st.button("💾 Recalculer les totaux", type="primary"):
                        offre_fin['total_heures'] = sum(p['quantite'] for p in offre_fin['postes_budgetaires'])
                        offre_fin['total_ht'] = sum(p['total'] for p in offre_fin['postes_budgetaires'])
                        offre_fin['taxes'] = offre_fin['total_ht'] * 0.14975
                        offre_fin['total_ttc'] = offre_fin['total_ht'] + offre_fin['taxes']
                        st.success("✅ Totaux recalculés !")
                        st.rerun()
                
                with st.expander("➕ Ajouter un poste budgétaire", expanded=False):
                    nouvelle_description = st.text_input("Description du poste")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        nouvelle_qte = st.number_input("Quantité (heures)", min_value=0, value=8, step=1)
                    with col2:
                        nouveau_px = st.number_input("Prix unitaire ($)", min_value=0, value=125, step=5)
                    
                    if st.button("➕ Ajouter ce poste"):
                        offre_fin['postes_budgetaires'].append({
                            "description": nouvelle_description,
                            "quantite": nouvelle_qte,
                            "unite": "heures",
                            "prix_unitaire": nouveau_px,
                            "total": nouvelle_qte * nouveau_px
                        })
                        
                        offre_fin['total_heures'] = sum(p['quantite'] for p in offre_fin['postes_budgetaires'])
                        offre_fin['total_ht'] = sum(p['total'] for p in offre_fin['postes_budgetaires'])
                        offre_fin['taxes'] = offre_fin['total_ht'] * 0.14975
                        offre_fin['total_ttc'] = offre_fin['total_ht'] + offre_fin['taxes']
                        
                        st.success("✅ Poste ajouté !")
                        st.rerun()
                
                st.markdown("### 📋 Récapitulatif")
                
                for poste in offre_fin.get('postes_budgetaires', []):
                    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                    with col1:
                        st.write(f"**{poste['description']}**")
                    with col2:
                        st.write(f"{poste['quantite']} {poste['unite']}")
                    with col3:
                        st.write(f"{poste['prix_unitaire']} $")
                    with col4:
                        st.write(f"**{poste['total']:,.2f} $**")
                
                st.markdown("---")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total heures", f"{offre_fin['total_heures']:.0f}h")
                with col2:
                    st.metric("Sous-total HT", f"{offre_fin['total_ht']:,.2f} $")
                with col3:
                    st.metric("Taxes", f"{offre_fin['taxes']:,.2f} $")
                with col4:
                    st.metric("TOTAL TTC", f"{offre_fin['total_ttc']:,.2f} $")
    
    # ─────────────────────────────────────────────────────────
    # TAB 4 : Validation — non-bloquante, affiche les problèmes sans empêcher la suite
    # ─────────────────────────────────────────────────────────
    with tab4:
        st.subheader("5️⃣ Valider la conformité")
        
        if not st.session_state.offre_data.get('offre_financiere'):
            st.warning("⚠️ Complétez d'abord l'offre financière (Onglet Offre Financière)")
        else:
            if st.button("✅ Valider l'offre"):
                try:
                    offre_complete = {
                        "exigences": st.session_state.offre_data.get('exigences'),
                        "offre_technique": st.session_state.offre_data.get('offre_technique'),
                        "offre_financiere": st.session_state.offre_data.get('offre_financiere'),
                        "date_creation": str(datetime.now())
                    }
                    
                    conformite = generateur_offres.valider_conformite_offre(
                        offre_complete,
                        st.session_state.offre_data['exigences']
                    )
                    
                    st.session_state.offre_data['conformite'] = conformite
                    st.session_state.offre_data['offre_complete'] = offre_complete
                    
                except Exception as e:
                    st.error(f"❌ Erreur lors de la validation : {str(e)}")
            
            # ── Affichage des résultats de conformité ─────────────────
            if st.session_state.offre_data.get('conformite'):
                conformite = st.session_state.offre_data['conformite']

                # Défensif : compatibilité avec ancienne et nouvelle version de valider_conformite_offre
                score = conformite.get('score_conformite', conformite.get('score', 0))
                if score is None:
                    score = 0

                # Score visuel avec couleur selon le niveau
                col_score, col_statut = st.columns([1, 3])
                with col_score:
                    couleur = "🟢" if score >= 80 else "🟡" if score >= 50 else "🔴"
                    st.metric("Score de conformité", f"{couleur} {score}%")
                with col_statut:
                    if score >= 80:
                        st.success("✅ Offre conforme — prête à soumettre")
                    elif score >= 50:
                        st.warning("⚠️ Offre partiellement conforme — vous pouvez continuer ou corriger les points signalés")
                    else:
                        st.error("🔴 Score faible — plusieurs points méritent attention, mais vous pouvez quand même continuer")

                # ── Points conformes ──────────────────────────────────
                if conformite.get('points_conformes'):
                    st.markdown("#### ✅ Points conformes")
                    for point in conformite['points_conformes']:
                        st.success(point)
                
                # ── Points à améliorer (non-bloquants) ────────────────
                if conformite.get('points_manquants'):
                    st.markdown("#### ⚠️ Points à vérifier / améliorer")
                    st.info(
                        "Ces points sont signalés à titre informatif. "
                        "Vous pouvez les corriger dans les onglets précédents "
                        "**ou continuer quand même** vers l'envoi."
                    )
                    for point in conformite['points_manquants']:
                        st.warning(point)
                
                # ── Recommandations ───────────────────────────────────
                if conformite.get('recommandations'):
                    st.markdown("### 💡 Recommandations")
                    for reco in conformite['recommandations']:
                        st.info(reco)
                
                st.markdown("---")
                st.markdown("### 📋 Choisir le statut et sauvegarder")
                
                # Le statut est toujours disponible, peu importe le score
                statut_validation = st.radio(
                    "Statut de l'offre",
                    options=["brouillon", "a_valider"],
                    format_func=lambda x: {
                        "brouillon": "📝 Brouillon — travail en cours",
                        "a_valider": "📋 À valider — prêt pour révision finale"
                    }[x],
                    key="statut_validation"
                )
                
                # CORRECTION PRINCIPALE : passage explicite des 4 arguments
                if st.button("💾 Sauvegarder avec ce statut", type="primary"):
                    try:
                        offre_sauvegardee = generateur_offres.sauvegarder_offre(
                            user['id'],
                            soumission_selectionnee['id'],
                            st.session_state.offre_data['offre_complete'],
                            statut_validation           # 4e argument positionnel — OK
                        )
                        
                        if offre_sauvegardee:
                            st.success(f"✅ Offre sauvegardée avec le statut « {statut_validation} » !")
                            st.session_state.offre_data['offre_id'] = offre_sauvegardee['id']
                        else:
                            st.warning("⚠️ Sauvegarde terminée mais aucune donnée retournée.")
                    except Exception as e:
                        st.error(f"❌ Erreur sauvegarde : {str(e)}")
    
    # ─────────────────────────────────────────────────────────
    # TAB 5 : Envoi
    # ─────────────────────────────────────────────────────────
    with tab5:
        st.subheader("6️⃣ Finaliser et envoyer")
        
        if not st.session_state.offre_data.get('offre_complete'):
            st.warning("⚠️ Validez d'abord l'offre (Onglet Validation)")
        else:
            st.markdown("### 📤 Préparation de l'envoi")
            
            statut_envoi = st.selectbox(
                "Statut après envoi",
                options=["validee", "envoyee"],
                format_func=lambda x: {
                    "validee": "✅ Validée — prête à envoyer",
                    "envoyee": "📤 Envoyée — transmise au client"
                }[x]
            )
            
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("💾 Sauvegarder l'offre", type="primary"):
                    try:
                        offre_sauvegardee = generateur_offres.sauvegarder_offre(
                            user['id'],
                            soumission_selectionnee['id'],
                            st.session_state.offre_data['offre_complete'],
                            statut_envoi
                        )
                        
                        if offre_sauvegardee:
                            st.success(f"✅ Offre sauvegardée avec le statut « {statut_envoi} » !")
                            st.session_state.offre_data['offre_id'] = offre_sauvegardee['id']
                    except Exception as e:
                        st.error(f"❌ Erreur : {str(e)}")
            
            with col2:
                if st.button("📄 Télécharger PDF"):
                    try:
                        contenu_pdf = generateur_offres.generer_pdf_offre(
                            st.session_state.offre_data['offre_complete'],
                            user
                        )
                        
                        st.download_button(
                            label="📥 Télécharger l'offre",
                            data=contenu_pdf,
                            file_name=f"offre_{soumission_selectionnee.get('nom_projet', 'projet').replace(' ', '_')}.txt",
                            mime="text/plain"
                        )
                    except Exception as e:
                        st.error(f"❌ Erreur : {str(e)}")
    
    # ─────────────────────────────────────────────────────────
    # TAB 6 : Suivi Statut
    # ─────────────────────────────────────────────────────────
    with tab6:
        st.subheader("📊 Suivi du statut de l'offre")
        
        if not st.session_state.offre_data.get('offre_id'):
            st.info("ℹ️ Sauvegardez d'abord votre offre pour accéder au suivi de statut")
        else:
            nom_projet = soumission_selectionnee.get('nom_projet', 'Projet sans nom')
            st.success(f"✅ Projet : **{nom_projet}**")
            
            st.markdown("### 🔄 Mise à jour du statut")
            
            statut_suivi = st.selectbox(
                "Nouveau statut",
                options=["en_attente", "acceptee", "refusee"],
                format_func=lambda x: {
                    "en_attente": "⏳ En attente de réponse du client",
                    "acceptee": "🎉 Acceptée par le client",
                    "refusee": "❌ Refusée par le client"
                }[x]
            )
            
            if statut_suivi == "acceptee":
                st.success("""
                🎉 **Félicitations !** 
                
                Si vous marquez cette offre comme "Acceptée", elle sera automatiquement accessible 
                dans la section **Gestion de Projet** pour démarrer la planification.
                """)
            
            if statut_suivi == "refusee":
                raison_refus = st.text_area("Raison du refus (optionnel)", height=100)
            
            if st.button("🔄 Mettre à jour le statut", type="primary"):
                try:
                    result = generateur_offres.mettre_a_jour_statut_offre(
                        st.session_state.offre_data['offre_id'],
                        statut_suivi
                    )
                    
                    if result:
                        st.success(f"✅ Statut mis à jour : {statut_suivi}")
                        
                        if statut_suivi == "acceptee":
                            st.balloons()
                            st.success("🚀 **Prochaine étape** : Rendez-vous dans l'onglet **Gestion de Projet** !")
                except Exception as e:
                    st.error(f"❌ Erreur : {str(e)}")
            
            st.markdown("---")
            st.markdown("### 📜 Historique")
            
            try:
                database.apply_supabase_auth()
                offre_actuelle = database.supabase.table('offres').select("*").eq(
                    'id', st.session_state.offre_data['offre_id']
                ).execute()
                
                if offre_actuelle.data:
                    offre = offre_actuelle.data[0]
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Statut actuel", offre['statut'].upper())
                    with col2:
                        st.metric("Dernière mise à jour", offre['updated_at'][:10])
            except Exception as e:
                st.error(f"Erreur chargement : {str(e)}")


# ─────────────────────────────────────────────────────────────────────
# show_mes_offres_tab : liste toutes les offres sauvegardees
# Appele depuis app_modular.py dans l'onglet "Mes Offres"
# ─────────────────────────────────────────────────────────────────────

STATUTS_CFG = {
    "brouillon":   {"label": "Brouillon",    "emoji": "📝"},
    "a_valider":   {"label": "A valider",    "emoji": "📋"},
    "validee":     {"label": "Validee",      "emoji": "✅"},
    "envoyee":     {"label": "Envoyee",      "emoji": "📤"},
    "en_attente":  {"label": "En attente",   "emoji": "⏳"},
    "acceptee":    {"label": "Acceptee",     "emoji": "🎉"},
    "refusee":     {"label": "Refusee",      "emoji": "❌"},
}


def _extraire_infos_offre(offre: dict) -> dict:
    contenu = offre.get('contenu', {})
    if isinstance(contenu, str):
        try:
            contenu = json.loads(contenu)
        except Exception:
            contenu = {}
    nom = (
        contenu.get('offre_technique', {}).get('titre_offre')
        or contenu.get('exigences', {}).get('nom_projet')
        or contenu.get('projet', {}).get('nom')
        or f"Offre {offre.get('id', '')[:8]}"
    )
    numero = (
        contenu.get('exigences', {}).get('numero_projet')
        or contenu.get('projet', {}).get('numero')
        or "—"
    )
    client = contenu.get('exigences', {}).get('client') or "—"
    total_ttc = contenu.get('offre_financiere', {}).get('total_ttc', 0)
    date_maj  = (offre.get('updated_at') or '')[:10]
    return {"nom": nom, "numero": numero, "client": client,
            "total_ttc": total_ttc, "date_maj": date_maj, "contenu": contenu}


def show_mes_offres_tab(user):
    """Liste toutes les offres sauvegardees avec gestion du statut et selection pour Gestion de Projet"""
    from datetime import datetime as _dt

    st.header("Mes Offres")

    # Charger toutes les offres
    try:
        database.apply_supabase_auth()
        result = database.supabase.table('offres').select("*").eq(
            'entreprise_id', user['id']
        ).order('updated_at', desc=True).execute()
        offres_list = result.data or []
    except Exception as e:
        st.error(f"Erreur chargement : {str(e)}")
        offres_list = []

    if not offres_list:
        st.info("Aucune offre sauvegardee. Allez dans **Generateur d'Offres** pour creer une offre.")
        return

    # Filtres
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        recherche = st.text_input("Rechercher par nom ou numero", placeholder="Ex: relocalisation, 226-623")
    with col_f2:
        filtre_statut = st.selectbox(
            "Filtrer par statut",
            options=["Tous"] + list(STATUTS_CFG.keys()),
            format_func=lambda x: "Tous les statuts" if x == "Tous"
                else f"{STATUTS_CFG[x]['emoji']} {STATUTS_CFG[x]['label']}"
        )

    st.markdown("---")

    nb = 0
    for offre in offres_list:
        statut = offre.get('statut', 'brouillon')
        if filtre_statut != "Tous" and statut != filtre_statut:
            continue

        infos = _extraire_infos_offre(offre)

        if recherche:
            terme = recherche.lower()
            if terme not in infos['nom'].lower() and terme not in infos['numero'].lower():
                continue

        nb += 1
        cfg = STATUTS_CFG.get(statut, {"label": statut, "emoji": "•"})

        col1, col2, col3 = st.columns([4, 2, 2])

        with col1:
            st.markdown(f"### {cfg['emoji']} {infos['nom']}")
            st.caption(f"No {infos['numero']}  ·  {infos['client']}  ·  Maj: {infos['date_maj']}")
            if infos['total_ttc'] > 0:
                st.caption(f"**{infos['total_ttc']:,.0f} $ TTC**")

        with col2:
            st.markdown(f"**Statut actuel**")
            st.markdown(f"{cfg['emoji']} {cfg['label'].upper()}")

            # Changer statut
            nouveau = st.selectbox(
                "Nouveau statut",
                options=list(STATUTS_CFG.keys()),
                index=list(STATUTS_CFG.keys()).index(statut) if statut in STATUTS_CFG else 0,
                key=f"sel_{offre['id']}",
                label_visibility="collapsed"
            )
            if nouveau != statut:
                if st.button("Appliquer", key=f"apply_{offre['id']}"):
                    try:
                        database.apply_supabase_auth()
                        database.supabase.table('offres').update({
                            "statut": nouveau,
                            "updated_at": _dt.now().isoformat()
                        }).eq('id', offre['id']).execute()
                        st.success("Statut mis a jour !")
                        st.rerun()
                    except Exception as e:
                        st.error(f"{str(e)}")

        with col3:
            # Voir le detail
            if st.button("Voir le detail", key=f"detail_{offre['id']}"):
                st.session_state['offre_detail_id'] = offre['id']
                st.session_state['offre_detail_data'] = offre

            # Bouton demarrer projet uniquement si acceptee
            if statut == 'acceptee':
                if st.button("Demarrer le projet", key=f"projet_{offre['id']}", type="primary"):
                    st.session_state['offre_pour_projet'] = {
                        'id': offre['id'],
                        'nom_projet': infos['nom'],
                        'projet_numero': infos['numero'],
                        'offre_data': infos['contenu'],
                    }
                    st.success(
                        f"Offre selectionnee : **{infos['nom']}**  \n"
                        "Allez dans l'onglet **Gestion de Projet** pour continuer."
                    )

        st.markdown("---")

    if nb == 0:
        st.warning("Aucune offre ne correspond aux filtres.")

    # Panneau detail
    if st.session_state.get('offre_detail_id'):
        offre_d = st.session_state.get('offre_detail_data', {})
        infos_d = _extraire_infos_offre(offre_d)
        contenu = infos_d['contenu']
        offre_tech = contenu.get('offre_technique', {})
        offre_fin  = contenu.get('offre_financiere', {})

        st.markdown("---")
        st.markdown(f"## Detail — {infos_d['nom']}")

        if st.button("Fermer le detail"):
            del st.session_state['offre_detail_id']
            del st.session_state['offre_detail_data']
            st.rerun()

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"**Client :** {infos_d['client']}")
            st.markdown(f"**Numero :** {infos_d['numero']}")
        with col_b:
            cfg_d = STATUTS_CFG.get(offre_d.get('statut', ''), {"emoji": "•", "label": ""})
            st.markdown(f"**Statut :** {cfg_d['emoji']} {cfg_d['label']}")
            st.markdown(f"**Derniere MAJ :** {infos_d['date_maj']}")

        tabs_d = st.tabs(["Offre Technique", "Offre Financiere", "Exigences"])

        with tabs_d[0]:
            if offre_tech:
                st.markdown(f"**{offre_tech.get('titre_offre', '')}**")
                st.write(offre_tech.get('introduction', ''))
                phases = offre_tech.get('approche_methodologique', {}).get('phases', [])
                if phases:
                    st.markdown("**Phases**")
                    for p in phases:
                        st.markdown(f"- **{p.get('nom','')}** ({p.get('duree','')}) : {p.get('description','')}")
                equipe = offre_tech.get('equipe_proposee', [])
                if equipe:
                    st.markdown("**Equipe**")
                    for m in equipe:
                        st.markdown(f"- {m.get('role','')} : **{m.get('nom','')}**")
            else:
                st.info("Aucune offre technique disponible.")

        with tabs_d[1]:
            if offre_fin and offre_fin.get('total_ttc', 0) > 0:
                for p in offre_fin.get('postes_budgetaires', []):
                    c1, c2, c3 = st.columns([3, 1, 1])
                    c1.write(p.get('description', ''))
                    c2.write(f"{p.get('quantite', 0)} h")
                    c3.write(f"{p.get('total', 0):,.0f} $")
                st.markdown("---")
                ca, cb, cc = st.columns(3)
                ca.metric("Sous-total HT", f"{offre_fin.get('total_ht', 0):,.0f} $")
                cb.metric("Taxes",         f"{offre_fin.get('taxes', 0):,.0f} $")
                cc.metric("TOTAL TTC",     f"{offre_fin.get('total_ttc', 0):,.0f} $")
            else:
                st.info("Aucune offre financiere disponible.")

        with tabs_d[2]:
            exigences = contenu.get('exigences', {})
            if exigences:
                st.markdown(f"**Projet :** {exigences.get('nom_projet', '—')}")
                st.markdown(f"**Client :** {exigences.get('client', '—')}")
                st.markdown(f"**Cloture :** {exigences.get('date_cloture', '—')}")
                st.markdown(f"**Duree :** {exigences.get('duree_projet', '—')}")
                st.markdown(f"**Sommaire :** {exigences.get('sommaire', '—')}")
            else:
                st.info("Aucune exigence disponible.")