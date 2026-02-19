"""
Analyse des appels d'offres
"""
import streamlit as st
from pypdf import PdfReader
from datetime import datetime
import re
import database
from llm_manager import LLMManager


llm_manager = LLMManager()


def show_analyse_tab(user, projets_antecedents):
    """Affiche l'onglet d'analyse"""
    st.header("🔍 Lancer une préqualification")
    
    with st.form("analyse_form"):
        numero_projet = st.text_input("🔢 Numéro du projet")
        nom_projet = st.text_input("📋 Nom du projet")
        uploaded_file = st.file_uploader("📄 PDF Appel d'offre", type=['pdf'])
        submit = st.form_submit_button("🚀 Lancer l'analyse", use_container_width=False)
    
    if submit and uploaded_file:
        if not nom_projet:
            st.error("❌ Le nom du projet est obligatoire")
        else:
            with st.spinner("🤖 Analyse IA en cours..."):
                try:
                    reader = PdfReader(uploaded_file)
                    text = " ".join([page.extract_text() or "" for page in reader.pages])[:8000]
                    
                    if not text.strip():
                        st.error("❌ Le PDF semble vide ou le texte n'a pas pu être extrait")
                        st.stop()
                    
                    today = datetime.today()
                    today_str = today.strftime("%Y-%m-%d")
                    
                    projets_text = "\n".join([
                        f"- {p['nom_projet']} ({p['montant']}$, {p['duree_jours']} jours): {p['specifications']}"
                        for p in projets_antecedents
                    ]) if projets_antecedents else "Aucun projet antérieur fourni."
                    
                    prompt_with_context = f"""
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

🎯 OBJECTIF : Analyser cet appel d'offres PUBLIC (adressé à toutes les entreprises) pour déterminer si l'entreprise doit soumissionner.

⚠️ CONTEXTE IMPORTANT :
- Cet appel d'offres est PUBLIC et ouvert à toutes les entreprises qualifiées
- L'analyse doit déterminer si CETTE entreprise spécifique devrait soumissionner
- Comparer les exigences avec le profil et l'expérience de l'entreprise

📝 STYLE D'ÉCRITURE OBLIGATOIRE :
- Dans l'ANALYSE : Utiliser UNIQUEMENT la 2ème ou 3ème personne du singulier/pluriel
  ✅ "Vous possédez", "L'entreprise a", "Elle dispose", "Ils ont"
  ❌ JAMAIS "Je pense", "J'estime", "Nous pensons"
- Dans la RECOMMANDATION FINALE : Utiliser la 1ère personne
  ✅ "Je recommande GO", "Je suggère de ne pas soumissionner"
- Être concis, précis et professionnel
- Éviter les phrases trop longues
- Aller droit au but

⚠️ AVERTISSEMENT IA OBLIGATOIRE :
COMMENCER l'analyse par :
"⚠️ AVERTISSEMENT : Cette analyse est générée par un système d'intelligence artificielle. Bien que nous nous efforcions de fournir des informations précises basées sur le document fourni, des erreurs d'interprétation peuvent survenir. Il est impératif de vérifier personnellement toutes les informations critiques dans le document original avant de prendre une décision."

📅 ANALYSE DES DATES - TRÈS CRITIQUE :

1. **Date de visite des lieux** :
   - Identifier la date de visite dans le document
   - Calculer le délai entre AUJOURD'HUI ({today_str}) et la date de visite
   - Si délai < 5 jours ouvrables : 
     ⚠️ POINT FAIBLE MAJEUR : "La visite des lieux est prévue le [DATE], soit dans seulement X jours ouvrables. Ce délai très court peut compliquer l'organisation et la participation à la visite obligatoire."
   - Si délai ≥ 5 jours ouvrables :
     ✅ POINT FORT : "La visite des lieux est prévue le [DATE], soit dans X jours ouvrables, ce qui laisse un délai raisonnable pour s'organiser."

2. **Délai visite → clôture** :
   - Identifier la date de clôture/dépôt des soumissions
   - Calculer jours ouvrables entre visite et clôture
   - Si < 5 jours ouvrables :
     ⚠️ POINT FAIBLE : "Le délai entre la visite et la clôture est de seulement X jours ouvrables, ce qui est insuffisant pour préparer une soumission complète après la visite."
   - Si ≥ 5 jours ouvrables :
     ✅ POINT NEUTRE : Mentionner simplement le délai

🚫 INFORMATIONS NON DISPONIBLES - NE PAS INVENTER :
- NE PAS mentionner les assurances si non trouvées dans le document
- NE PAS mentionner le cautionnement si non trouvé dans le document  
- NE PAS inventer de montants, dates ou exigences
- SI une information n'est PAS dans le document : indiquer clairement "Information non disponible dans le document"
- Se limiter STRICTEMENT aux informations présentes dans le document fourni

🏗️ COMPARAISON AVEC PROJETS ANTÉRIEURS :
- Comparer le montant estimé avec les projets antérieurs
- Comparer la durée estimée avec les projets antérieurs
- Comparer le type de travaux avec les spécifications des projets antérieurs
- Si AUCUNE expérience similaire : 
  "L'entreprise n'a pas de projet similaire dans son historique. Elle devra démontrer sa capacité à réaliser ce type de travaux par d'autres moyens (références, sous-traitants, partenariats)."
- Si expérience similaire : 
  "L'entreprise a déjà réalisé des projets comparables, notamment [liste avec montants et durées], ce qui démontre sa capacité à réaliser ce type de travaux."

📊 STRUCTURE DE LA RÉPONSE :

1. **AVERTISSEMENT IA** (obligatoire en haut)

2. **CONTEXTE DE L'APPEL D'OFFRES**
   - "Cet appel d'offres public est ouvert à toutes les entreprises qualifiées."
   - Nature du projet en 1-2 phrases
   - Principal enjeu pour CETTE entreprise

3. **DATES CLÉS ET DÉLAIS** ⏰
   - Date du jour : {today_str}
   - Date visite : [DATE] → Délai : X jours ouvrables [✅/⚠️/❌]
   - Date clôture : [DATE]
   - Délai visite → clôture : X jours ouvrables [✅/⚠️/❌]
   - Date début travaux : [DATE si disponible]
   - Date fin travaux : [DATE si disponible]
   - Durée totale : X jours [si disponible]

4. **ADÉQUATION AVEC L'EXPÉRIENCE** 🏗️
   - Comparaison détaillée avec projets antérieurs
   - Points de correspondance ou différences majeures
   - Montants comparables ? Durées similaires ? Types de travaux ?

5. **POINTS FORTS** ✅ (maximum 5 points)
   - Chaque point avec référence précise : (Réf: Page X, Section Y)
   - Inclure les délais raisonnables si applicable

6. **POINTS FAIBLES** ⚠️ (maximum 5 points)
   - Chaque point avec référence précise ou [Information non disponible]
   - Inclure les délais courts si applicable
   - Inclure le manque d'expérience similaire si applicable

7. **CRITÈRES D'ADMISSIBILITÉ** 📋
   - UNIQUEMENT mentionner ce qui est TROUVÉ dans le document
   - Licence RBQ : [OUI/NON/NON SPÉCIFIÉ] - Référence : Page X
   - Si assurances TROUVÉES : [Montant/Type] - Référence : Page X
   - Si cautionnement TROUVÉ : [Montant/%] - Référence : Page X
   - Expérience minimale : [Description si trouvée] - Référence : Page X
   - NE PAS inventer ces informations si absentes

8. **ACTIONS PRIORITAIRES** 🎯 (maximum 5 actions concrètes)
   - 🔴 URGENT : [Action avec date limite si délai court]
   - 🟠 IMPORTANT : [Action nécessaire]
   - 🟡 À PRÉVOIR : [Action recommandée]

9. **RECOMMANDATION FINALE** 💭 (ici utiliser 1ère personne)
   - "Je recommande GO" / "Je recommande NO-GO" / "Je recommande PEUT-ÊTRE"
   - Justification en 2-3 paragraphes CONCIS
   - Mentionner les facteurs décisifs

10. **SCORE** : X/100
    - Justification du score en 1-2 phrases

═══════════════════════════════════════════════════════════════

⚠️ RAPPELS FINAUX :
- ✅ Appel d'offres PUBLIC pour toutes entreprises
- ✅ Comparer date visite avec AUJOURD'HUI ({today_str})
- ✅ Vérifier délai visite → clôture (min 5 jours ouvrables)
- ✅ 2ème/3ème personne dans l'analyse
- ✅ 1ère personne dans la recommandation
- ✅ Ne mentionner que les infos TROUVÉES dans le document
- ❌ NE PAS inventer assurances/cautionnement si absents
- ✅ Comparer avec projets antérieurs
- ✅ Être CONCIS et PRÉCIS

### Appel d'offre à analyser :
{text}
"""
                    
                    analysis_result = llm_manager.analyze(prompt_with_context, max_tokens=2500)
                    
                    if not analysis_result["success"]:
                        st.error(f"❌ {analysis_result['error']}")
                        st.stop()
                    
                    result = analysis_result["result"]
                    
                    st.markdown("### 📋 Résultat de l'analyse IA")
                    st.markdown("---")
                    st.markdown(result)
                    
                    rec = "INCONNU"
                    result_upper = result.upper()
                    if "JE RECOMMANDE GO" in result_upper and "NO-GO" not in result_upper and "NO GO" not in result_upper:
                        rec = "GO"
                    elif "NO-GO" in result_upper or "NO GO" in result_upper or "JE RECOMMANDE NO" in result_upper:
                        rec = "NO-GO"
                    elif "PEUT-ÊTRE" in result_upper or "MAYBE" in result_upper or "PEUT ÊTRE" in result_upper:
                        rec = "PEUT-ÊTRE"
                    
                    score = 0
                    score_match = re.search(r"(?:Score|SCORE)\s*[:\-]?\s*(\d+)", result, re.IGNORECASE)
                    if score_match:
                        score = int(score_match.group(1))
                    
                    soumission_data = {
                        "numero_projet": numero_projet,
                        "nom_projet": nom_projet,
                        "document": uploaded_file,
                        "analyse_json": {"raw_response": result},
                        "recommendation": rec,
                        "score": score,
                        "statut": "qualifie" if rec == "GO" else "non_qualifie"
                    }
                    
                    soumission = database.save_soumission(user['id'], soumission_data)
                    
                    if soumission:
                        st.success("✅ Analyse sauvegardée dans la base de données !")
                    else:
                        st.warning("⚠️ L'analyse a été effectuée mais n'a pas pu être sauvegardée")
                
                except Exception as e:
                    st.error(f"❌ Erreur lors de l'analyse : {str(e)}")
    elif submit:
        st.error("❌ Veuillez uploader un fichier PDF")
