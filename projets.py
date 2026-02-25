"""
Gestion des projets antérieurs
Fonctionnalités :
  - Upload multi-fichiers avec cases à cocher (sélectionner / désélectionner)
  - Import en lot : un projet créé par fichier sélectionné
  - Ajout manuel d'un projet avec ou sans document
  - Modification et suppression de chaque projet
"""
import streamlit as st
import database


# ── CSS zone de dépôt et cases à cocher ──────────────────────────────
_CSS = """
<style>
/* Zone de dépôt */
[data-testid='stFileUploader'] {
    border: 2px dashed #2E75B6 !important;
    border-radius: 12px !important;
    background: #D5E8F0 !important;
    padding: 20px !important;
    transition: border-color 0.2s, background 0.2s;
}
[data-testid='stFileUploader']:hover {
    border-color: #1E3A5F !important;
    background: #BDD7EE !important;
}
/* Lignes fichiers sélectionnés */
.fichier-row {
    display: flex; align-items: center; gap: 10px;
    padding: 6px 10px; border-radius: 8px;
    background: #F8FAFC; border: 1px solid #E2E8F0;
    margin-bottom: 6px;
}
.fichier-row:hover { background: #EFF6FF; }
.fichier-nom { font-size: 14px; color: #1E293B; flex: 1; }
.fichier-taille { font-size: 12px; color: #64748B; }
</style>
"""


# ════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════

def _taille_label(nb_bytes: int) -> str:
    kb = nb_bytes / 1024
    return f"{kb/1024:.1f} MB" if kb >= 1024 else f"{kb:.0f} KB"


def _upload_multi(key: str, label: str = "Glissez vos documents ici ou cliquez"):
    """
    Zone de dépôt multi-fichiers avec cases à cocher.
    Retourne la liste des fichiers cochés par l'utilisateur.
    """
    st.markdown(_CSS, unsafe_allow_html=True)

    fichiers = st.file_uploader(
        label=label,
        type=None,
        accept_multiple_files=True,
        key=key,
        help=(
            "Sélectionnez plusieurs fichiers d'un coup (Ctrl+clic ou Maj+clic dans le "
            "sélecteur) ou glissez un dossier entier — Tous types acceptés"
        ),
    )

    if not fichiers:
        st.caption("_Aucun fichier sélectionné_")
        return []

    # ── Cases à cocher par fichier ────────────────────────────────────
    st.markdown(f"**{len(fichiers)} fichier(s) déposé(s) — cochez ceux à importer :**")

    col_tout, col_rien = st.columns([1, 1])
    with col_tout:
        if st.button("☑️ Tout sélectionner", key=f"{key}_all"):
            for f in fichiers:
                st.session_state[f"{key}_chk_{f.name}"] = True
    with col_rien:
        if st.button("⬜ Tout désélectionner", key=f"{key}_none"):
            for f in fichiers:
                st.session_state[f"{key}_chk_{f.name}"] = False

    selectionnes = []
    for f in fichiers:
        chk_key = f"{key}_chk_{f.name}"
        if chk_key not in st.session_state:
            st.session_state[chk_key] = True   # coché par défaut

        coche = st.checkbox(
            f"**{f.name}** — {_taille_label(f.size)}",
            value=st.session_state[chk_key],
            key=chk_key,
        )
        if coche:
            selectionnes.append(f)

    if selectionnes:
        total = sum(f.size for f in selectionnes)
        st.success(f"✅ **{len(selectionnes)}/{len(fichiers)}** fichier(s) sélectionné(s) — {_taille_label(total)} au total")
    else:
        st.warning("⚠️ Aucun fichier coché")

    return selectionnes


def _upload_single(key: str):
    """Zone de dépôt mono-fichier avec feedback visuel (pour édition)."""
    st.markdown(_CSS, unsafe_allow_html=True)
    doc = st.file_uploader(
        label="Glissez votre document ici ou cliquez pour sélectionner",
        type=None,
        key=key,
        help="Tous types acceptés — Taille max : 10 MB",
    )
    if doc:
        st.success(f"✅ **{doc.name}** ({_taille_label(doc.size)})")
    else:
        st.caption("_Aucun document — champ optionnel_")
    return doc


def _supprimer_projet(projet_id: str) -> bool:
    try:
        database.apply_supabase_auth()
        database.supabase.table('projets_antecedents').delete().eq('id', projet_id).execute()
        st.success("✅ Projet supprimé")
        return True
    except Exception as e:
        st.error(f"❌ Erreur suppression : {str(e)}")
        return False


def _modifier_projet(projet_id: str, data: dict) -> bool:
    try:
        database.apply_supabase_auth()
        update = {
            "nom_projet":     data["nom_projet"],
            "montant":        data["montant"],
            "duree_jours":    data["duree_jours"],
            "specifications": data.get("specifications", ""),
        }
        if data.get("document"):
            try:
                from storage import upload_document_projet
                url = upload_document_projet(
                    database.supabase, data["document"], data.get("entreprise_id")
                )
                if url:
                    update["document_url"] = url
            except Exception as e:
                st.warning(f"⚠️ Document non mis à jour : {e}")

        result = database.supabase.table('projets_antecedents').update(update).eq(
            'id', projet_id
        ).execute()

        if result.data:
            st.success("✅ Projet modifié avec succès")
            return True
        st.error("❌ Erreur lors de la modification")
        return False
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return False


# ════════════════════════════════════════════════════════════════════
# ONGLET PRINCIPAL
# ════════════════════════════════════════════════════════════════════

def show_projets_tab(user):
    """Affiche l'onglet des projets antérieurs."""
    st.header("🏗️ Vos projets antérieurs")

    tab_import, tab_manuel = st.tabs([
        "📦 Import par fichiers",
        "✏️ Ajout manuel",
    ])

    # ════════════════════════════════════════════════════════════════
    # ONGLET A — Import multi-fichiers avec cases à cocher
    # ════════════════════════════════════════════════════════════════
    with tab_import:
        st.markdown(
            "Déposez plusieurs documents d'un coup. Cochez ceux à importer, "
            "remplissez les informations communes puis cliquez **Importer**."
        )

        fichiers_coches = _upload_multi("import_multi")

        if fichiers_coches:
            st.markdown("---")
            st.markdown("##### 📋 Informations communes à tous les fichiers importés")
            st.caption(
                "Ces valeurs seront appliquées à chaque fichier. "
                "Vous pourrez les modifier individuellement ensuite."
            )

            with st.form("form_import_lot"):
                col1, col2 = st.columns(2)
                with col1:
                    montant_lot = st.number_input(
                        "Montant par défaut ($)", min_value=0, value=0
                    )
                    duree_lot   = st.number_input(
                        "Durée par défaut (jours)", min_value=1, value=30
                    )
                with col2:
                    specs_lot = st.text_area(
                        "Spécifications communes", height=100,
                        placeholder="Laissez vide si différentes par projet"
                    )

                st.markdown(
                    f"**{len(fichiers_coches)} projet(s) seront créés** — "
                    "le nom de chaque projet sera le nom du fichier (sans extension)."
                )

                if st.form_submit_button(
                    f"📥 Importer {len(fichiers_coches)} projet(s)",
                    type="primary",
                    use_container_width=False
                ):
                    succes = 0
                    erreurs = 0
                    barre = st.progress(0, text="Import en cours…")

                    for i, f in enumerate(fichiers_coches):
                        # Nom du projet = nom fichier sans extension
                        nom_projet = f.name.rsplit(".", 1)[0] if "." in f.name else f.name

                        ok = database.add_projet_antecedent({
                            "nom_projet":     nom_projet,
                            "montant":        montant_lot,
                            "duree_jours":    duree_lot,
                            "specifications": specs_lot,
                            "document":       f,
                        })
                        if ok:
                            succes += 1
                        else:
                            erreurs += 1

                        barre.progress(
                            (i + 1) / len(fichiers_coches),
                            text=f"Import {i+1}/{len(fichiers_coches)} — {f.name}"
                        )

                    barre.empty()

                    if succes:
                        st.success(f"✅ {succes} projet(s) importé(s) avec succès !")
                    if erreurs:
                        st.error(f"❌ {erreurs} projet(s) n'ont pas pu être importés")

                    # Réinitialiser les cases à cocher
                    for f in fichiers_coches:
                        st.session_state.pop(f"import_multi_chk_{f.name}", None)
                    st.session_state.pop("import_multi", None)
                    st.rerun()

    # ════════════════════════════════════════════════════════════════
    # ONGLET B — Ajout manuel (un projet à la fois, tous les champs)
    # ════════════════════════════════════════════════════════════════
    with tab_manuel:
        st.markdown("##### 📂 Document du projet")
        doc_p = _upload_single("upload_doc_ajout")
        st.markdown("---")

        with st.form("form_ajout_projet"):
            col1, col2 = st.columns(2)
            with col1:
                nom_p     = st.text_input("Nom du projet *")
                montant_p = st.number_input("Montant ($)", min_value=0, value=0)
                duree_p   = st.number_input("Durée (jours)", min_value=1, value=1)
            with col2:
                specs_p = st.text_area("Spécifications", height=120)

            if st.form_submit_button("💾 Ajouter", use_container_width=False):
                if not nom_p:
                    st.error("❌ Le nom du projet est obligatoire")
                else:
                    if database.add_projet_antecedent({
                        "nom_projet":     nom_p,
                        "montant":        montant_p,
                        "duree_jours":    duree_p,
                        "specifications": specs_p,
                        "document":       doc_p,
                    }):
                        st.session_state.pop("upload_doc_ajout", None)
                        st.rerun()

    # ════════════════════════════════════════════════════════════════
    # LISTE DES PROJETS
    # ════════════════════════════════════════════════════════════════
    st.markdown("---")
    try:
        database.apply_supabase_auth()
        result  = database.supabase.table('projets_antecedents').select("*").eq(
            'entreprise_id', user['id']
        ).order('created_at', desc=True).execute()
        projets = result.data or []
    except Exception as e:
        st.error(f"❌ Erreur lors du chargement : {str(e)}")
        return

    if not projets:
        st.info("📭 Aucun projet pour le moment")
        return

    st.markdown(f"**{len(projets)} projet(s) enregistré(s)**")

    for projet in projets:
        pid = str(projet.get('id', ''))
        nom = projet.get('nom_projet', 'Sans nom')

        with st.expander(f"🏗️ {nom}"):
            edit_key = f"edit_mode_{pid}"
            if edit_key not in st.session_state:
                st.session_state[edit_key] = False

            # ── VUE LECTURE ───────────────────────────────────────────
            if not st.session_state[edit_key]:
                col_a, col_b = st.columns(2)
                with col_a:
                    st.write(f"**Montant :** {projet.get('montant', 0):,.2f} $")
                    st.write(f"**Durée :** {projet.get('duree_jours', 0)} jours")
                with col_b:
                    st.write(f"**Date :** {projet.get('created_at', '')[:10]}")
                    if projet.get('document_url'):
                        st.markdown(f"[📄 Voir document]({projet['document_url']})")
                st.write(f"**Spécifications :** {projet.get('specifications') or 'Aucune'}")

                c1, c2, _ = st.columns([1, 1, 4])
                with c1:
                    if st.button("✏️ Modifier", key=f"btn_edit_{pid}"):
                        st.session_state[edit_key] = True
                        st.rerun()
                with c2:
                    if st.button("🗑 Supprimer", key=f"btn_del_{pid}"):
                        st.session_state[f"confirm_del_{pid}"] = True
                        st.rerun()

                if st.session_state.get(f"confirm_del_{pid}"):
                    st.warning(f"⚠️ Confirmer la suppression de **{nom}** ?")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ Oui, supprimer", key=f"yes_del_{pid}"):
                            if _supprimer_projet(pid):
                                st.session_state.pop(f"confirm_del_{pid}", None)
                                st.rerun()
                    with c2:
                        if st.button("❌ Annuler", key=f"no_del_{pid}"):
                            st.session_state.pop(f"confirm_del_{pid}", None)
                            st.rerun()

            # ── VUE ÉDITION ───────────────────────────────────────────
            else:
                st.markdown("##### ✏️ Modifier le projet")
                st.markdown("📂 **Remplacer le document** _(optionnel)_")
                nouveau_doc = _upload_single(f"upload_edit_{pid}")
                if projet.get('document_url'):
                    st.caption(
                        f"Document actuel : "
                        f"[{projet['document_url'].split('/')[-1]}]({projet['document_url']})"
                    )

                with st.form(f"form_edit_{pid}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        nom_e     = st.text_input("Nom du projet *", value=projet.get('nom_projet', ''))
                        montant_e = st.number_input("Montant ($)", min_value=0, value=int(projet.get('montant') or 0))
                        duree_e   = st.number_input("Durée (jours)", min_value=1, value=int(projet.get('duree_jours') or 1))
                    with col2:
                        specs_e = st.text_area("Spécifications", value=projet.get('specifications', ''), height=120)

                    c1, c2 = st.columns(2)
                    with c1:
                        sauvegarder = st.form_submit_button("💾 Sauvegarder", use_container_width=True)
                    with c2:
                        annuler = st.form_submit_button("↩️ Annuler", use_container_width=True)

                    if annuler:
                        st.session_state[edit_key] = False
                        st.session_state.pop(f"upload_edit_{pid}", None)
                        st.rerun()

                    if sauvegarder:
                        if not nom_e:
                            st.error("❌ Le nom est obligatoire")
                        else:
                            if _modifier_projet(pid, {
                                "nom_projet":     nom_e,
                                "montant":        montant_e,
                                "duree_jours":    duree_e,
                                "specifications": specs_e,
                                "document":       nouveau_doc,
                                "entreprise_id":  user['id'],
                            }):
                                st.session_state[edit_key] = False
                                st.session_state.pop(f"upload_edit_{pid}", None)
                                st.rerun()