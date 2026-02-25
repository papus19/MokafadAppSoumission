"""
Analyse des appels d'offres
Modification : upload multi-documents, tous types de fichiers
"""
import streamlit as st
from datetime import datetime
import re
import database
from llm_manager import LLMManager
from extracteur import (
    extraire_texte_multiple,
    feedback_fichiers,
    LABEL_UPLOAD,
    HELP_UPLOAD,
    TYPES_ACCEPTES,
)


llm_manager = LLMManager()

# ── CSS zone de dépôt visuelle (cohérent avec projets.py) ─────────────
_DROP_CSS = """
<style>
[data-testid='stFileUploader'] {
    border: 2px dashed #2E75B6 !important;
    border-radius: 12px !important;
    background: #D5E8F0 !important;
    padding: 24px !important;
    transition: border-color 0.2s, background 0.2s;
}
[data-testid='stFileUploader']:hover {
    border-color: #1E3A5F !important;
    background: #BDD7EE !important;
}
</style>
"""


def show_analyse_tab(user, projets_antecedents):
    """Affiche l'onglet d'analyse"""
    st.header("🔍 Lancer une préqualification")

    # ── CSS ───────────────────────────────────────────────────────────
    st.markdown(_DROP_CSS, unsafe_allow_html=True)

    # ── ÉTAPE 1 — Upload HORS formulaire (multi-docs, drag & drop) ───
    st.markdown("##### 📂 Documents de l'appel d'offres")
    uploaded_files = st.file_uploader(
        label=LABEL_UPLOAD,
        type=TYPES_ACCEPTES,
        accept_multiple_files=True,
        key="analyse_docs",
        help=HELP_UPLOAD,
    )
    feedback_fichiers(uploaded_files)

    st.markdown("---")

    # ── ÉTAPE 2 — Formulaire des métadonnées ─────────────────────────
    with st.form("analyse_form"):
        numero_projet = st.text_input("🔢 Numéro du projet")
        nom_projet    = st.text_input("📋 Nom du projet")
        submit        = st.form_submit_button("🚀 Lancer l'analyse", use_container_width=False)

    if submit:
        if not uploaded_files:
            st.error("❌ Veuillez déposer au moins un document")
            return
        if not nom_projet:
            st.error("❌ Le nom du projet est obligatoire")
            return

        with st.spinner("🤖 Extraction et analyse IA en cours…"):
            try:
                # ── Extraction texte multi-documents ─────────────────
                text = extraire_texte_multiple(uploaded_files)

                if not text.strip():
                    st.error("❌ Aucun texte n'a pu être extrait des documents fournis")
                    return

                today     = datetime.today()
                today_str = today.strftime("%Y-%m-%d")

                projets_text = "\n".join([
                    f"- {p['nom_projet']} ({p['montant']}$, {p['duree_jours']} jours): {p['specifications']}"
                    for p in projets_antecedents
                ]) if projets_antecedents else "Aucun projet antérieur fourni."

                prompt = f"""
Analysez cet appel d'offres PUBLIC (adressé à toutes les entreprises) pour déterminer si l'entreprise doit soumissionner.

Informations sur l'entreprise :
- Nom : {user.get('nom_entreprise', 'N/A')}
- Spécialités : {', '.join(user.get('specialites', [])) if user.get('specialites') else 'Non spécifiées'}
- NEQ : {user.get('numero_neq', 'N/A')}
- Licence RBQ : {user.get('licence_rbq', 'N/A')}
- Adresse : {user.get('adresse', '')}, {user.get('ville', '')}, {user.get('province', '')} {user.get('code_postal', '')}
- Contact : {user.get('contact_nom', '')}, {user.get('contact_telephone', '')}, {user.get('contact_email', '')}

Projets antérieurs pertinents :
{projets_text}

DATE DU JOUR : {today_str}

═══════════════════════════════════════════════════════════════
📋 INSTRUCTIONS CRITIQUES POUR L'ANALYSE - À RESPECTER ABSOLUMENT
═══════════════════════════════════════════════════════════════

🎯 OBJECTIF : Analyser cet appel d'offres PUBLIC pour déterminer si l'entreprise doit soumissionner.

⚠️ CONTEXTE IMPORTANT :
- Cet appel d'offres est PUBLIC et ouvert à toutes les entreprises qualifiées
- L'analyse doit déterminer si CETTE entreprise spécifique devrait soumissionner
- Comparer les exigences avec le profil et l'expérience de l'entreprise

📝 STYLE D'ÉCRITURE OBLIGATOIRE :
- Dans l'ANALYSE : Utiliser UNIQUEMENT la 2ème ou 3ème personne
  ✅ "Vous possédez", "L'entreprise a", "Elle dispose"
  ❌ JAMAIS "Je pense", "J'estime", "Nous pensons"
- Dans la RECOMMANDATION FINALE : Utiliser la 1ère personne
  ✅ "Je recommande GO", "Je suggère de ne pas soumissionner"

⚠️ AVERTISSEMENT IA OBLIGATOIRE :
COMMENCER l'analyse par :
"⚠️ AVERTISSEMENT : Cette analyse est générée par un système d'intelligence artificielle. Bien que nous nous efforcions de fournir des informations précises basées sur le document fourni, des erreurs d'interprétation peuvent survenir. Il est impératif de vérifier personnellement toutes les informations critiques dans le document original avant de prendre une décision."

📅 ANALYSE DES DATES - TRÈS CRITIQUE :

1. **Date de visite des lieux** :
   - Identifier la date de visite dans le document
   - Calculer le délai entre AUJOURD'HUI ({today_str}) et la date de visite
   - Si délai < 5 jours ouvrables : ⚠️ POINT FAIBLE MAJEUR
   - Si délai ≥ 5 jours ouvrables : ✅ POINT FORT

2. **Délai visite → clôture** :
   - Si < 5 jours ouvrables : ⚠️ POINT FAIBLE
   - Si ≥ 5 jours ouvrables : ✅ Mentionner simplement le délai

🚫 INFORMATIONS NON DISPONIBLES - NE PAS INVENTER :
- NE PAS mentionner les assurances si non trouvées dans le document
- NE PAS mentionner le cautionnement si non trouvé
- NE PAS inventer de montants, dates ou exigences
- Si une information n'est PAS dans le document : "Information non disponible dans le document"

🏗️ COMPARAISON AVEC PROJETS ANTÉRIEURS :
- Comparer le montant estimé, la durée et le type de travaux avec les projets antérieurs
- Si AUCUNE expérience similaire : le mentionner clairement
- Si expérience similaire : citer les projets comparables

📊 STRUCTURE DE LA RÉPONSE :

1. **AVERTISSEMENT IA** (obligatoire en haut)
2. **CONTEXTE DE L'APPEL D'OFFRES**
3. **DATES CLÉS ET DÉLAIS** ⏰ (date visite, clôture, travaux, durée)
4. **ADÉQUATION AVEC L'EXPÉRIENCE** 🏗️
5. **POINTS FORTS** ✅ (maximum 5)
6. **POINTS FAIBLES** ⚠️ (maximum 5)
7. **CRITÈRES D'ADMISSIBILITÉ** 📋 (UNIQUEMENT ce qui est TROUVÉ dans le document)
8. **ACTIONS PRIORITAIRES** 🎯 (maximum 5 actions concrètes)
9. **RECOMMANDATION FINALE** 💭 (1ère personne) — GO / NO-GO / PEUT-ÊTRE
10. **SCORE** : X/100

═══════════════════════════════════════════════════════════════

### Documents à analyser ({len(uploaded_files)} fichier(s)) :
{text}
"""

                analysis_result = llm_manager.analyze(prompt, max_tokens=2500)

                if not analysis_result["success"]:
                    st.error(f"❌ {analysis_result['error']}")
                    return

                result = analysis_result["result"]

                st.markdown("### 📋 Résultat de l'analyse IA")
                st.markdown("---")
                st.markdown(result)

                # ── Détection recommandation et score ────────────────
                rec          = "INCONNU"
                result_upper = result.upper()
                if "JE RECOMMANDE GO" in result_upper and "NO-GO" not in result_upper and "NO GO" not in result_upper:
                    rec = "GO"
                elif "NO-GO" in result_upper or "NO GO" in result_upper or "JE RECOMMANDE NO" in result_upper:
                    rec = "NO-GO"
                elif "PEUT-ÊTRE" in result_upper or "MAYBE" in result_upper or "PEUT ÊTRE" in result_upper:
                    rec = "PEUT-ÊTRE"

                score       = 0
                score_match = re.search(r"(?:Score|SCORE)\s*[:\-]?\s*(\d+)", result, re.IGNORECASE)
                if score_match:
                    score = int(score_match.group(1))

                # ── Sauvegarde — on passe le premier fichier comme document principal ──
                soumission_data = {
                    "numero_projet": numero_projet,
                    "nom_projet":    nom_projet,
                    "document":      uploaded_files[0] if len(uploaded_files) == 1 else None,
                    "analyse_json":  {"raw_response": result},
                    "recommendation": rec,
                    "score":         score,
                    "statut":        "qualifie" if rec == "GO" else "non_qualifie"
                }

                soumission = database.save_soumission(user['id'], soumission_data)

                if soumission:
                    st.success("✅ Analyse sauvegardée dans la base de données !")
                else:
                    st.warning("⚠️ L'analyse a été effectuée mais n'a pas pu être sauvegardée")

            except Exception as e:
                st.error(f"❌ Erreur lors de l'analyse : {str(e)}")