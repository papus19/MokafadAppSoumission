"""
Module de génération d'offres complètes
Modification : upload multi-documents, tous types de fichiers
"""
import streamlit as st
from datetime import datetime
import json
import re
from llm_manager import LLMManager
from extracteur import (
    extraire_texte_multiple,
    feedback_fichiers,
    LABEL_UPLOAD,
    HELP_UPLOAD,
    TYPES_ACCEPTES,
)
import database


llm_manager = LLMManager()


def extraire_exigences_appel_offre(texte_combine: str) -> dict:
    """Extrait les exigences clés d'un ou plusieurs documents d'appel d'offres"""
    try:
        prompt = f"""
Analyse cet appel d'offres et extrais les exigences clés en format JSON strict.

DOCUMENT :
{texte_combine[:8000]}

Réponds UNIQUEMENT avec un objet JSON (sans markdown, sans ```json) :
{{
    "numero_projet": "string",
    "nom_projet": "string",
    "client": "string",
    "date_cloture": "YYYY-MM-DD",
    "duree_projet": "X jours/mois",
    "budget_estime": "montant si disponible",
    "sommaire": "description courte du projet",
    "methodologie_requise": ["point 1", "point 2"],
    "livrables": ["livrable 1", "livrable 2"],
    "exigences_techniques": ["exigence 1", "exigence 2"],
    "criteres_evaluation": ["critère 1", "critère 2"],
    "documents_requis": ["doc 1", "doc 2"]
}}
"""
        result = llm_manager.analyze(prompt, max_tokens=2000)

        if result["success"]:
            texte = result["result"].strip()
            texte = texte.replace("```json", "").replace("```", "").strip()
            return json.loads(texte)
        else:
            st.error(f"❌ Erreur extraction : {result['error']}")
            return None

    except Exception as e:
        st.error(f"❌ Erreur parsing : {str(e)}")
        return None


def generer_offre_technique(exigences, projets_antecedents, user):
    """Génère une offre technique basée sur les exigences et projets similaires"""
    try:
        projets_text = "\n".join([
            f"- {p['nom_projet']} ({p['montant']}$, {p['duree_jours']} jours): {p['specifications']}"
            for p in projets_antecedents
        ]) if projets_antecedents else "Aucun projet antérieur."

        prompt = f"""
Génère une offre technique professionnelle en format JSON.

ENTREPRISE :
- Nom : {user.get('nom_entreprise')}
- Spécialités : {', '.join(user.get('specialites', []))}
- Licence RBQ : {user.get('licence_rbq')}

PROJETS SIMILAIRES :
{projets_text}

EXIGENCES DU PROJET :
{json.dumps(exigences, indent=2, ensure_ascii=False)}

Réponds UNIQUEMENT avec un objet JSON (sans markdown) :
{{
    "titre_offre": "string",
    "introduction": "paragraphe de présentation",
    "comprehension_projet": "notre compréhension du projet",
    "approche_methodologique": {{
        "description": "notre approche",
        "phases": [
            {{"nom": "Phase 1", "description": "...", "duree": "X jours"}},
            {{"nom": "Phase 2", "description": "...", "duree": "X jours"}}
        ]
    }},
    "equipe_proposee": [
        {{"role": "Chef de projet", "nom": "{user.get('contact_nom', 'À définir')}", "experience": "...", "responsabilites": ["...", "..."]}},
        {{"role": "Autre", "nom": "À définir", "experience": "...", "responsabilites": ["...", "..."]}}
    ],
    "livrables": [
        {{"nom": "Livrable 1", "description": "...", "format": "PDF/Autre"}},
        {{"nom": "Livrable 2", "description": "...", "format": "PDF/Autre"}}
    ],
    "calendrier": [
        {{"etape": "Démarrage", "date_debut": "À définir", "date_fin": "À définir"}},
        {{"etape": "Phase 1", "date_debut": "À définir", "date_fin": "À définir"}}
    ],
    "garanties_qualite": ["garantie 1", "garantie 2"],
    "references_clients": "Disponibles sur demande",
    "avantages_concurrentiels": ["avantage 1", "avantage 2"]
}}
"""
        result = llm_manager.analyze(prompt, max_tokens=3000)

        if result["success"]:
            texte = result["result"].strip()
            texte = texte.replace("```json", "").replace("```", "").strip()
            return json.loads(texte)
        else:
            st.error(f"❌ Erreur génération : {result['error']}")
            return None

    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return None


def calculer_offre_financiere(offre_technique, taux_horaire_base):
    """Génère une offre financière basée sur l'offre technique"""
    try:
        offre_financiere = {
            "taux_horaire_base":  taux_horaire_base,
            "postes_budgetaires": [],
            "total_heures":       0,
            "total_ht":           0,
            "taxes":              0,
            "total_ttc":          0
        }

        for phase in offre_technique.get("approche_methodologique", {}).get("phases", []):
            duree_text  = phase.get("duree", "")
            jours_match = re.search(r'(\d+)\s*jours?', duree_text.lower())

            if jours_match:
                jours  = int(jours_match.group(1))
                heures = jours * 8
                cout   = heures * taux_horaire_base

                offre_financiere["postes_budgetaires"].append({
                    "description":   phase.get("nom", "Phase"),
                    "quantite":      heures,
                    "unite":         "heures",
                    "prix_unitaire": taux_horaire_base,
                    "total":         cout
                })
                offre_financiere["total_heures"] += heures
                offre_financiere["total_ht"]     += cout

        offre_financiere["taxes"]     = offre_financiere["total_ht"] * 0.14975
        offre_financiere["total_ttc"] = offre_financiere["total_ht"] + offre_financiere["taxes"]

        return offre_financiere

    except Exception as e:
        st.error(f"❌ Erreur calcul financier : {str(e)}")
        return None


def valider_conformite_offre(offre_complete, exigences):
    """
    Valide la conformité de l'offre avec les exigences.
    Retourne la liste des problèmes SANS bloquer la progression.
    """
    conformite = {
        "conforme":         True,
        "points_conformes": [],
        "points_manquants": [],
        "recommandations":  [],
        "score_conformite": 0
    }

    total_points   = 0
    points_obtenus = 0

    # Livrables (30 pts)
    total_points += 30
    livrables_requis = set(exigences.get("livrables", []))
    livrables_offre  = set([l.get("nom", "") for l in offre_complete.get("offre_technique", {}).get("livrables", [])])

    if livrables_requis and livrables_requis.issubset(livrables_offre):
        conformite["points_conformes"].append("✅ Tous les livrables requis sont inclus")
        points_obtenus += 30
    else:
        manquants = livrables_requis - livrables_offre
        if manquants:
            conformite["points_manquants"].append(
                f"⚠️ Livrables potentiellement manquants : {', '.join(manquants)} "
                f"(vérifiez que les noms correspondent)"
            )
        else:
            points_obtenus += 30
            conformite["points_conformes"].append("✅ Livrables présents")

    # Exigences techniques (25 pts)
    total_points += 25
    if exigences.get("exigences_techniques"):
        offre_tech_text          = json.dumps(offre_complete.get("offre_technique", {}), ensure_ascii=False).lower()
        exigences_non_adressees  = []
        for exigence in exigences.get("exigences_techniques", []):
            mots_cles = exigence.lower().split()[:3]
            if not any(mot in offre_tech_text for mot in mots_cles if len(mot) > 4):
                exigences_non_adressees.append(exigence)

        if not exigences_non_adressees:
            conformite["points_conformes"].append("✅ Exigences techniques adressées")
            points_obtenus += 25
        else:
            conformite["points_manquants"].append(
                f"⚠️ Exigences techniques à vérifier : {', '.join(exigences_non_adressees[:3])}"
            )
            points_obtenus += 10
    else:
        conformite["points_conformes"].append("✅ Aucune exigence technique spécifique requise")
        points_obtenus += 25

    # Équipe (20 pts)
    total_points += 20
    equipe = offre_complete.get("offre_technique", {}).get("equipe_proposee", [])
    if equipe and len(equipe) > 0:
        membres_incomplets = [m for m in equipe if not m.get("nom") or not m.get("role")]
        if membres_incomplets:
            conformite["points_manquants"].append(
                f"⚠️ {len(membres_incomplets)} membre(s) de l'équipe avec informations incomplètes"
            )
            points_obtenus += 10
        else:
            conformite["points_conformes"].append(f"✅ Équipe proposée : {len(equipe)} membre(s) défini(s)")
            points_obtenus += 20
    else:
        conformite["points_manquants"].append("⚠️ Aucun membre d'équipe défini dans l'offre technique")

    # Offre financière (25 pts)
    total_points += 25
    offre_fin = offre_complete.get("offre_financiere", {})
    total_ttc = offre_fin.get("total_ttc", 0)
    postes    = offre_fin.get("postes_budgetaires", [])

    if total_ttc > 0 and len(postes) > 0:
        conformite["points_conformes"].append(
            f"✅ Offre financière complète : {total_ttc:,.2f} $ TTC ({len(postes)} poste(s))"
        )
        points_obtenus += 25
    elif total_ttc > 0:
        conformite["points_manquants"].append("⚠️ Offre financière sans détail des postes budgétaires")
        points_obtenus += 15
    else:
        conformite["points_manquants"].append("⚠️ Offre financière incomplète ou montant nul")

    conformite["score_conformite"] = int((points_obtenus / total_points) * 100) if total_points > 0 else 0
    conformite["conforme"]         = conformite["score_conformite"] >= 50

    if conformite["points_manquants"]:
        conformite["recommandations"].append(
            "📋 Des points méritent attention (voir ci-dessus), mais vous pouvez soumettre quand même"
        )
    conformite["recommandations"].append("📋 Relisez attentivement l'offre avant envoi")
    conformite["recommandations"].append("📎 Vérifiez que tous les documents requis sont joints")

    return conformite


def sauvegarder_offre(entreprise_id, soumission_id, offre_complete, statut="brouillon"):
    """Sauvegarde l'offre dans la base de données."""
    try:
        database.apply_supabase_auth()

        existing = database.supabase.table('offres').select("id").eq(
            'soumission_id', soumission_id
        ).execute()

        data = {
            "entreprise_id": entreprise_id,
            "soumission_id": soumission_id,
            "statut":        statut,
            "contenu":       offre_complete,
            "updated_at":    datetime.now().isoformat()
        }

        if existing.data and len(existing.data) > 0:
            result = database.supabase.table('offres').update(data).eq(
                'id', existing.data[0]['id']
            ).execute()
        else:
            result = database.supabase.table('offres').insert(data).execute()

        return result.data[0] if result.data and len(result.data) > 0 else None

    except Exception as e:
        st.error(f"❌ Erreur sauvegarde : {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return None


def mettre_a_jour_statut_offre(offre_id, nouveau_statut):
    """Met à jour le statut d'une offre"""
    try:
        database.apply_supabase_auth()
        result = database.supabase.table('offres').update({
            "statut":     nouveau_statut,
            "updated_at": datetime.now().isoformat()
        }).eq('id', offre_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        st.error(f"❌ Erreur mise à jour : {str(e)}")
        return None


def generer_pdf_offre(offre_complete, user):
    """Génère un texte formaté de l'offre (export texte)"""
    offre_tech = offre_complete.get('offre_technique', {})
    offre_fin  = offre_complete.get('offre_financiere', {})

    contenu = f"""
═══════════════════════════════════════════════════════════════
                    OFFRE DE SERVICES PROFESSIONNELS
═══════════════════════════════════════════════════════════════

{offre_tech.get('titre_offre', 'Offre technique')}

───────────────────────────────────────────────────────────────
INFORMATIONS ENTREPRISE
───────────────────────────────────────────────────────────────

Entreprise : {user.get('nom_entreprise')}
Licence RBQ : {user.get('licence_rbq')}
Contact : {user.get('contact_nom')}
Email : {user.get('contact_email', user.get('email', ''))}
Téléphone : {user.get('contact_telephone', user.get('telephone', ''))}

───────────────────────────────────────────────────────────────
1. INTRODUCTION
───────────────────────────────────────────────────────────────

{offre_tech.get('introduction', '')}

───────────────────────────────────────────────────────────────
2. COMPRÉHENSION DU PROJET
───────────────────────────────────────────────────────────────

{offre_tech.get('comprehension_projet', '')}

───────────────────────────────────────────────────────────────
3. APPROCHE MÉTHODOLOGIQUE
───────────────────────────────────────────────────────────────

{offre_tech.get('approche_methodologique', {}).get('description', '')}

PHASES DU PROJET :
"""

    for i, phase in enumerate(offre_tech.get('approche_methodologique', {}).get('phases', []), 1):
        contenu += f"\n{i}. {phase.get('nom', '')} ({phase.get('duree', '')})\n   {phase.get('description', '')}\n"

    contenu += "\n───────────────────────────────────────────────────────────────\n4. ÉQUIPE PROPOSÉE\n───────────────────────────────────────────────────────────────\n"

    for membre in offre_tech.get('equipe_proposee', []):
        contenu += (
            f"\n- {membre.get('role', '')} : {membre.get('nom', '')}\n"
            f"  Expérience : {membre.get('experience', '')}\n"
            f"  Responsabilités : {', '.join(membre.get('responsabilites', []))}\n"
        )

    contenu += "\n───────────────────────────────────────────────────────────────\n5. LIVRABLES\n───────────────────────────────────────────────────────────────\n"

    for livrable in offre_tech.get('livrables', []):
        contenu += (
            f"\n- {livrable.get('nom', '')}\n"
            f"  Description : {livrable.get('description', '')}\n"
            f"  Format : {livrable.get('format', '')}\n"
        )

    contenu += f"""
───────────────────────────────────────────────────────────────
6. OFFRE FINANCIÈRE
───────────────────────────────────────────────────────────────

Taux horaire de base : {offre_fin.get('taux_horaire_base', 0)} $/h

POSTES BUDGÉTAIRES :
"""

    for poste in offre_fin.get('postes_budgetaires', []):
        contenu += (
            f"\n- {poste.get('description', '')}\n"
            f"  Quantité : {poste.get('quantite', 0)} {poste.get('unite', '')}\n"
            f"  Prix unitaire : {poste.get('prix_unitaire', 0)} $\n"
            f"  Total : {poste.get('total', 0):,.2f} $\n"
        )

    contenu += f"""
───────────────────────────────────────────────────────────────
SOMMAIRE FINANCIER
───────────────────────────────────────────────────────────────

Total heures       : {offre_fin.get('total_heures', 0):.0f} h
Sous-total HT      : {offre_fin.get('total_ht', 0):,.2f} $
Taxes (TPS+TVQ)    : {offre_fin.get('taxes', 0):,.2f} $
─────────────────────────────────────────
TOTAL TTC          : {offre_fin.get('total_ttc', 0):,.2f} $
─────────────────────────────────────────

Date : {datetime.now().strftime("%Y-%m-%d")}

Cordialement,
{user.get('nom_entreprise')}

═══════════════════════════════════════════════════════════════
"""

    return contenu