"""
MOKAFAD - Module Gestion de Projet
Modifications :
  B — Hiérarchie Jalon → Livrable → Activité → Tâche avec liaisons obligatoires
  C — Génération IA d'un plan complet depuis la soumission (Claude Sonnet)
      + Suggestions contextuelles légères (Gemini/Groq via LLMManager)
"""

import streamlit as st
import anthropic
import config
import database
from datetime import datetime, date, timedelta
import json
from typing import List, Optional
import uuid


# ── Helpers ────────────────────────────────────────────────────────────

def _uid() -> str:
    return str(uuid.uuid4())[:8]


def creer_projet_vide(offre_id: str, offre_data: dict, entreprise_id: str) -> dict:
    return {
        "projet_id":       f"proj_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "offre_id":        offre_id,
        "entreprise_id":   entreprise_id,
        "offre_reference": offre_data.get('projet', {}).get('numero', ''),
        "nom_projet": (
            offre_data.get('offre_technique', {}).get('titre_offre')
            or offre_data.get('projet', {}).get('nom', '')
        ),
        "client":         offre_data.get('projet', {}).get('client', 'N/A'),
        "statut":         "demarrage",
        "date_creation":  datetime.now().isoformat(),
        "demarrage": {
            "parties_prenantes": [], "hypotheses": [], "risques": [],
            "plan_communication": [], "inclusions": [], "exclusions": [],
        },
        "planification": {
            "date_debut":      offre_data.get('dates', {}).get('travaux_debut', ''),
            "date_fin":        offre_data.get('dates', {}).get('travaux_fin', ''),
            "jalons":          [],
            "livrables":       [],
            "activites":       [],
            "taches":          [],
            "chemin_critique": [],
        },
        "suivi": {
            "jalons": [], "livrables": [], "activites": [], "taches": [],
            "reunions": [], "alertes": [],
        },
        "cloture":    {"elements_fermes": []},
        "postmortem": {"points_forts": [], "ameliorations": [], "conclusion": "", "complete": False},
        "budget":     {"planifie": 0, "reel": 0, "variance": 0},
        "duree":      {
            "planifiee_jours": offre_data.get('dates', {}).get('jours_ouvres', 0),
            "reelle_jours": 0
        },
        "ressources_projet": {
            "humaines":          [],
            "materielles":       [],
            "informationnelles": []
        },
    }


# ══════════════════════════════════════════════════════════════════════
# MODIFICATION B — Modèle de données avec liaisons parent obligatoires
# ══════════════════════════════════════════════════════════════════════

def _element_vide(type_el: str, nom: str = "", parent_id: str = None) -> dict:
    """
    Crée un élément vide.
    Hiérarchie stricte :
        jalon  → (racine)
        livrable → jalon_id    (obligatoire)
        activite → livrable_id (obligatoire)
        tache    → activite_id (obligatoire)
    """
    base = {
        "id":                    _uid(),
        "type":                  type_el,
        "nom":                   nom or f"Nouveau {type_el}",
        "description":           "",
        "date_debut":            None,
        "date_fin":              None,
        "duree_jours":           1,
        "statut":                "A faire",
        "priorite":              "Normale",
        "responsable_id":        None,
        "ressources_humaines":   [],
        "ressources_materielles":[],
        "ressources_info":       [],
        "dependances":           [],
        "avancement_pct":        0,
        "notes":                 "",
    }
    if type_el == "livrable":
        base["jalon_id"]    = parent_id
    elif type_el == "activite":
        base["livrable_id"] = parent_id
    elif type_el == "tache":
        base["activite_id"] = parent_id
    return base


def _calcul_avancement(plan: dict):
    """
    Remonte l'avancement bottom-up : tâches → activités → livrables → jalons.
    Appelé avant tout affichage de progression.
    """
    for act in plan.get("activites", []):
        taches = [t for t in plan.get("taches", []) if t.get("activite_id") == act["id"]]
        if taches:
            act["avancement_pct"] = int(
                sum(t.get("avancement_pct", 0) for t in taches) / len(taches)
            )

    for liv in plan.get("livrables", []):
        acts = [a for a in plan.get("activites", []) if a.get("livrable_id") == liv["id"]]
        if acts:
            liv["avancement_pct"] = int(
                sum(a.get("avancement_pct", 0) for a in acts) / len(acts)
            )

    for jal in plan.get("jalons", []):
        livs = [l for l in plan.get("livrables", []) if l.get("jalon_id") == jal["id"]]
        if livs:
            jal["avancement_pct"] = int(
                sum(l.get("avancement_pct", 0) for l in livs) / len(livs)
            )


def _migrer_orphelins(plan: dict):
    """
    Migration des projets existants : associe les éléments sans parent
    au premier parent disponible du niveau supérieur.
    Affiche un avertissement si des orphelins ont été détectés.
    """
    orphelins = False

    # Livrables sans jalon_id → premier jalon
    premier_jalon = plan["jalons"][0]["id"] if plan.get("jalons") else None
    for l in plan.get("livrables", []):
        if not l.get("jalon_id"):
            l["jalon_id"] = premier_jalon
            orphelins = True

    # Activités sans livrable_id → premier livrable
    premier_livrable = plan["livrables"][0]["id"] if plan.get("livrables") else None
    for a in plan.get("activites", []):
        if not a.get("livrable_id"):
            a["livrable_id"] = premier_livrable
            orphelins = True

    # Tâches sans activite_id → première activité
    premiere_activite = plan["activites"][0]["id"] if plan.get("activites") else None
    for t in plan.get("taches", []):
        if not t.get("activite_id"):
            t["activite_id"] = premiere_activite
            orphelins = True

    if orphelins:
        st.warning(
            "⚠️ Ce projet a été migré : des éléments sans liaison parent ont été "
            "automatiquement rattachés. Vérifiez la planification."
        )


# ══════════════════════════════════════════════════════════════════════
# MODIFICATION C — Génération IA d'un plan de projet complet
# ══════════════════════════════════════════════════════════════════════

def generer_plan_projet_ia(offre_data: dict, user: dict, dates: dict) -> Optional[dict]:
    """
    Appelle Claude Sonnet pour générer un plan de projet complet :
    jalons → livrables → activités → tâches, avec risques et parties prenantes.
    Retourne un dict ou None en cas d'échec.
    """
    try:
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

        nom_projet   = (
            offre_data.get('offre_technique', {}).get('titre_offre')
            or offre_data.get('projet', {}).get('nom', 'Projet')
        )
        specialites  = ", ".join(user.get('specialites', []))
        date_debut   = dates.get('debut', '')
        date_fin     = dates.get('fin', '')
        contenu_offre = json.dumps(offre_data, ensure_ascii=False)[:3000]

        prompt = f"""Tu es un expert en gestion de projet de construction au Québec.
Génère un plan de projet complet et réaliste pour :
- Entreprise : {user.get('nom_entreprise', '')}
- Spécialité : {specialites}
- Projet : {nom_projet}
- Dates : {date_debut} → {date_fin}
- Contenu de l'offre : {contenu_offre}

Réponds UNIQUEMENT en JSON valide, sans texte avant ni après, avec cette structure :
{{
  "jalons": [
    {{
      "id": "j1",
      "nom": "Nom du jalon",
      "date_fin": "YYYY-MM-DD",
      "livrables": [
        {{
          "id": "l1",
          "nom": "Nom du livrable",
          "activites": [
            {{
              "id": "a1",
              "nom": "Nom de l'activité",
              "duree_jours": 3,
              "taches": [
                {{
                  "id": "t1",
                  "nom": "Nom de la tâche",
                  "duree_jours": 1,
                  "responsable": "Rôle suggéré"
                }}
              ]
            }}
          ]
        }}
      ]
    }}
  ],
  "risques": [
    {{"description": "...", "impact": "Moyen", "probabilite": "Moyenne", "mitigation": "..."}}
  ],
  "parties_prenantes": [
    {{"nom": "...", "role": "...", "influence": "Elevee", "interet": "Eleve"}}
  ],
  "inclusions": ["..."],
  "exclusions": ["..."]
}}"""

        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        text = msg.content[0].text
        idx  = text.find('{')
        if idx >= 0:
            return json.loads(text[idx: text.rfind('}') + 1])
        return None

    except Exception as e:
        st.warning(f"⚠️ Génération IA non disponible : {e}")
        return None


def _aplatir_plan_ia(plan_ia: dict, plan: dict):
    """
    Convertit la structure imbriquée retournée par l'IA (jalons avec livrables
    imbriqués) en 4 listes plates avec liaisons parent (jalon_id, livrable_id,
    activite_id) dans le dictionnaire planification du projet.
    """
    for jal_ia in plan_ia.get("jalons", []):
        j = _element_vide("jalon", jal_ia.get("nom", "Jalon"))
        j["date_fin"] = jal_ia.get("date_fin")
        plan["jalons"].append(j)

        for liv_ia in jal_ia.get("livrables", []):
            l = _element_vide("livrable", liv_ia.get("nom", "Livrable"), parent_id=j["id"])
            plan["livrables"].append(l)

            for act_ia in liv_ia.get("activites", []):
                a = _element_vide("activite", act_ia.get("nom", "Activité"), parent_id=l["id"])
                a["duree_jours"] = act_ia.get("duree_jours", 1)
                plan["activites"].append(a)

                for tac_ia in act_ia.get("taches", []):
                    t = _element_vide("tache", tac_ia.get("nom", "Tâche"), parent_id=a["id"])
                    t["duree_jours"] = tac_ia.get("duree_jours", 1)
                    t["notes"]       = tac_ia.get("responsable", "")
                    plan["taches"].append(t)


def _suggestion_ia_legere(contexte: str, demande: str) -> str:
    """
    Suggestions légères via LLMManager (Gemini/Groq) pour ne pas consommer
    le budget Claude sur des appels mineurs.
    Retourne le texte de la suggestion ou une chaîne vide en cas d'échec.
    """
    try:
        from llm_manager import LLMManager
        mgr    = LLMManager()
        prompt = f"Contexte projet : {contexte}\n\n{demande}\n\nRéponds en français, de façon concise (5 lignes max)."
        result = mgr.analyze(prompt, max_tokens=300)
        return result.get("result", "") if result.get("success") else ""
    except Exception:
        return ""


# ── Analyse démarrage (conservée pour compatibilité) ──────────────────

def analyser_offre_pour_demarrage(offre_data: dict, user: dict) -> dict:
    """Conservée pour compatibilité. Utilisée si generer_plan_projet_ia échoue."""
    try:
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        nom    = (
            offre_data.get('offre_technique', {}).get('titre_offre')
            or offre_data.get('projet', {}).get('nom', '')
        )
        prompt = f"""Analyse cette offre et suggère des éléments de démarrage.
Projet: {nom}  Entreprise: {user.get('nom_entreprise', '')}
Spécialités: {', '.join(user.get('specialites', []))}

JSON uniquement:
{{
  "parties_prenantes": [{{"nom":"Client","role":"Commanditaire","influence":"Elevee","interet":"Eleve"}}],
  "risques": [{{"description":"Retard","impact":"Moyen","probabilite":"Moyenne","mitigation":"Suivi hebdo"}}],
  "inclusions": ["Installation selon plans"], "exclusions": ["Travaux civils"]
}}"""
        msg  = client.messages.create(
            model="claude-sonnet-4-20250514", max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        text = msg.content[0].text
        idx  = text.find('{')
        return json.loads(text[idx: text.rfind('}') + 1]) if idx >= 0 else {}
    except Exception as e:
        st.warning(f"Suggestions IA non disponibles : {e}")
        return {}


# ── Sauvegarde ────────────────────────────────────────────────────────

def _sauvegarder(projet: dict, user: dict):
    try:
        database.apply_supabase_auth()
        data = {
            'entreprise_id': user['id'],
            'projet_id':     projet['projet_id'],
            'nom_projet':    projet['nom_projet'],
            'statut':        projet['statut'],
            'data':          json.dumps(projet)
        }
        ex = database.supabase.table('gestion_projets').select("id").eq(
            'projet_id', projet['projet_id']
        ).execute()
        if ex.data:
            database.supabase.table('gestion_projets').update(data).eq(
                'projet_id', projet['projet_id']
            ).execute()
        else:
            database.supabase.table('gestion_projets').insert(data).execute()
        st.success("✅ Projet sauvegardé")
    except Exception as e:
        sl  = st.session_state.setdefault('projets_locaux', [])
        idx = next((i for i, p in enumerate(sl) if p['projet_id'] == projet['projet_id']), None)
        if idx is not None:
            sl[idx] = projet
        else:
            sl.append(projet)
        st.warning(f"⚠️ Sauvegarde locale (hors ligne) : {e}")


# ── Gantt ──────────────────────────────────────────────────────────────

def _afficher_gantt(elements: list, date_debut_projet: str):
    elems_dates = []
    ref = date.today()
    if date_debut_projet:
        try:
            ref = date.fromisoformat(date_debut_projet[:10])
        except Exception:
            pass

    for el in elements:
        dd = el.get('date_debut')
        df = el.get('date_fin')
        if dd and df:
            try:
                d0 = date.fromisoformat(dd[:10])
                d1 = date.fromisoformat(df[:10])
                elems_dates.append((el['nom'], el['type'], d0, d1, el.get('avancement_pct', 0)))
            except Exception:
                pass

    if not elems_dates:
        st.info("Définissez des dates de début et de fin pour afficher le Gantt.")
        return

    d_min      = min(e[2] for e in elems_dates)
    d_max      = max(e[3] for e in elems_dates)
    total_days = max((d_max - d_min).days + 1, 1)

    COULEURS = {
        "jalon":    "#3B82F6",
        "livrable": "#10B981",
        "activite": "#F59E0B",
        "tache":    "#8B5CF6",
    }
    ICONES = {"jalon": "J", "livrable": "L", "activite": "A", "tache": "T"}

    html = """
<style>
.gantt-wrap{font-family:sans-serif;font-size:12px;overflow-x:auto}
.gantt-row{display:flex;align-items:center;margin:3px 0}
.gantt-label{width:180px;min-width:180px;padding-right:8px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.gantt-track{flex:1;height:22px;background:#f0f0f0;border-radius:4px;position:relative}
.gantt-bar{position:absolute;height:100%;border-radius:4px;display:flex;align-items:center;padding:0 4px;color:#fff;font-size:10px;font-weight:600;overflow:hidden;box-sizing:border-box}
.gantt-progress{position:absolute;height:100%;border-radius:4px;background:rgba(0,0,0,0.25);pointer-events:none}
.gantt-header{display:flex;align-items:center;margin-bottom:4px;font-weight:600;color:#555}
.gantt-badge{display:inline-block;width:14px;height:14px;border-radius:3px;margin-right:4px;vertical-align:middle}
</style>
<div class="gantt-wrap">
<div class="gantt-header">
  <div style="width:180px">Élément</div>
  <div style="flex:1">Calendrier</div>
</div>"""

    for (nom, typ, d0, d1, avp) in elems_dates:
        left_pct    = (d0 - d_min).days / total_days * 100
        width_pct   = max((d1 - d0).days + 1, 1) / total_days * 100
        couleur     = COULEURS.get(typ, "#6B7280")
        icone       = ICONES.get(typ, "?")
        html += f"""
<div class="gantt-row">
  <div class="gantt-label" title="{nom}">
    <span class="gantt-badge" style="background:{couleur}">{icone}</span>{nom}
  </div>
  <div class="gantt-track">
    <div class="gantt-bar" style="left:{left_pct:.1f}%;width:{width_pct:.1f}%;background:{couleur}">
      {avp}%
      <div class="gantt-progress" style="width:{avp}%;"></div>
    </div>
  </div>
</div>"""

    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

    cols = st.columns(4)
    for i, (k, c) in enumerate(COULEURS.items()):
        cols[i].markdown(
            f'<span style="display:inline-block;width:12px;height:12px;background:{c};'
            f'border-radius:2px;margin-right:4px"></span>{k.capitalize()}',
            unsafe_allow_html=True
        )


# ══════════════════════════════════════════════════════════════════════
# MODIFICATION B — Formulaire d'édition d'un élément (inchangé)
# ══════════════════════════════════════════════════════════════════════

def _form_element(el: dict, key_prefix: str, ressources_projet: dict, tous_elements: list):
    STATUTS   = ["A faire", "En cours", "Termine", "Bloque"]
    PRIORITES = ["Basse", "Normale", "Haute", "Critique"]

    el['nom']         = st.text_input("Nom", el.get('nom', ''),          key=f"{key_prefix}_nom")
    el['description'] = st.text_area("Description", el.get('description', ''), height=70, key=f"{key_prefix}_desc")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        dd    = el.get('date_debut')
        dd_v  = date.fromisoformat(dd[:10]) if dd else None
        nd    = st.date_input("Début", value=dd_v, key=f"{key_prefix}_dd")
        el['date_debut'] = nd.isoformat() if nd else None
    with c2:
        df    = el.get('date_fin')
        df_v  = date.fromisoformat(df[:10]) if df else None
        nf    = st.date_input("Fin", value=df_v, key=f"{key_prefix}_df")
        el['date_fin'] = nf.isoformat() if nf else None
    with c3:
        s_idx = STATUTS.index(el.get('statut', 'A faire')) if el.get('statut') in STATUTS else 0
        el['statut'] = st.selectbox("Statut", STATUTS, index=s_idx, key=f"{key_prefix}_statut")
    with c4:
        p_idx = PRIORITES.index(el.get('priorite', 'Normale')) if el.get('priorite') in PRIORITES else 1
        el['priorite'] = st.selectbox("Priorité", PRIORITES, index=p_idx, key=f"{key_prefix}_prio")

    rh = ressources_projet.get('humaines', [])
    if rh:
        rh_labels  = [f"{r['nom']} ({r.get('role', '')})" for r in rh]
        rh_ids     = [r['id'] for r in rh]
        rh_selects = [rid for rid in el.get('ressources_humaines', []) if rid in rh_ids]
        rh_new     = st.multiselect("Ressources humaines", rh_labels,
                                    default=[rh_labels[rh_ids.index(rid)] for rid in rh_selects],
                                    key=f"{key_prefix}_rh")
        el['ressources_humaines'] = [rh_ids[rh_labels.index(l)] for l in rh_new]

    rm = ressources_projet.get('materielles', [])
    if rm:
        rm_labels  = [r['nom'] for r in rm]
        rm_ids     = [r['id'] for r in rm]
        rm_selects = [rid for rid in el.get('ressources_materielles', []) if rid in rm_ids]
        rm_new     = st.multiselect("Ressources matérielles", rm_labels,
                                    default=[rm_labels[rm_ids.index(rid)] for rid in rm_selects],
                                    key=f"{key_prefix}_rm")
        el['ressources_materielles'] = [rm_ids[rm_labels.index(l)] for l in rm_new]

    autres = [e for e in tous_elements if e['id'] != el['id']]
    if autres:
        dep_labels = [f"{e['nom']} [{e['type']}]" for e in autres]
        dep_ids    = [e['id'] for e in autres]
        dep_cur    = [did for did in el.get('dependances', []) if did in dep_ids]
        dep_new    = st.multiselect("Dépendances (prédécesseurs)", dep_labels,
                                    default=[dep_labels[dep_ids.index(d)] for d in dep_cur],
                                    key=f"{key_prefix}_dep")
        el['dependances'] = [dep_ids[dep_labels.index(l)] for l in dep_new]

    el['avancement_pct'] = st.slider("Avancement %", 0, 100, el.get('avancement_pct', 0), key=f"{key_prefix}_av")
    el['notes']          = st.text_area("Notes", el.get('notes', ''), height=60, key=f"{key_prefix}_notes")

    # ── Suggestion IA légère ──────────────────────────────────────────
    if st.button("🤖 Suggestion IA", key=f"{key_prefix}_ia_suggest"):
        with st.spinner("Analyse en cours..."):
            contexte = f"Projet — Élément : {el.get('nom','')} ({el.get('type','')})"
            demande  = "Propose 3 sous-tâches concrètes ou points d'attention pour cet élément."
            suggestion = _suggestion_ia_legere(contexte, demande)
        if suggestion:
            st.info(f"💡 {suggestion}")
        else:
            st.warning("Suggestion IA non disponible pour le moment.")


# ── Tableau récapitulatif ─────────────────────────────────────────────

def _tableau_elements(elements: list, ressources_projet: dict, label: str):
    if not elements:
        st.info(f"Aucun {label} défini.")
        return

    rh_map = {r['id']: r['nom'] for r in ressources_projet.get('humaines', [])}
    rows   = []
    for el in elements:
        resp_noms = ", ".join(rh_map.get(rid, rid) for rid in el.get('ressources_humaines', []))
        rows.append({
            "Nom":        el.get('nom', ''),
            "Statut":     el.get('statut', ''),
            "Priorité":   el.get('priorite', ''),
            "Début":      (el.get('date_debut') or '')[:10],
            "Fin":        (el.get('date_fin') or '')[:10],
            "Avancement": f"{el.get('avancement_pct', 0)}%",
            "Responsables": resp_noms,
        })
    import pandas as pd
    st.dataframe(pd.DataFrame(rows), use_container_width=True)


# ── Gestion des ressources du projet ─────────────────────────────────

def _section_ressources(projet: dict, user: dict):
    st.subheader("Ressources du projet")
    rp = projet.setdefault('ressources_projet', {
        'humaines': [], 'materielles': [], 'informationnelles': []
    })

    if not rp['humaines'] and user.get('equipe'):
        for m in user.get('equipe', []):
            rp['humaines'].append({
                'id': _uid(), 'nom': m.get('nom', ''), 'role': m.get('poste', ''),
                'taux_horaire': 75
            })

    tab_rh, tab_rm, tab_ri = st.tabs(["Humaines", "Matérielles", "Informationnelles"])

    with tab_rh:
        for i, r in enumerate(rp['humaines']):
            with st.expander(r.get('nom', 'Ressource'), expanded=False):
                c1, c2, c3 = st.columns(3)
                r['nom']          = c1.text_input("Nom",        r.get('nom', ''),   key=f"rh_n_{i}")
                r['role']         = c2.text_input("Rôle",       r.get('role', ''),  key=f"rh_r_{i}")
                r['taux_horaire'] = c3.number_input("Taux $/h", value=r.get('taux_horaire', 75), step=5, key=f"rh_t_{i}")
                if st.button("Supprimer", key=f"rh_del_{i}"):
                    rp['humaines'].pop(i); st.rerun()
        if st.button("➕ Ajouter ressource humaine"):
            rp['humaines'].append({'id': _uid(), 'nom': '', 'role': '', 'taux_horaire': 75}); st.rerun()

    with tab_rm:
        for i, r in enumerate(rp['materielles']):
            with st.expander(r.get('nom', 'Matériel'), expanded=False):
                c1, c2, c3, c4 = st.columns(4)
                r['nom']           = c1.text_input("Nom",            r.get('nom', ''),         key=f"rm_n_{i}")
                r['quantite']      = c2.number_input("Qté",          value=r.get('quantite', 1), step=1, key=f"rm_q_{i}")
                r['unite']         = c3.text_input("Unité",          r.get('unite', 'u'),       key=f"rm_u_{i}")
                r['cout_unitaire'] = c4.number_input("Coût unitaire $", value=r.get('cout_unitaire', 0.0), step=10.0, key=f"rm_c_{i}")
                if st.button("Supprimer", key=f"rm_del_{i}"):
                    rp['materielles'].pop(i); st.rerun()
        if st.button("➕ Ajouter ressource matérielle"):
            rp['materielles'].append({'id': _uid(), 'nom': '', 'quantite': 1, 'unite': 'u', 'cout_unitaire': 0.0}); st.rerun()

    with tab_ri:
        for i, r in enumerate(rp['informationnelles']):
            with st.expander(r.get('nom', 'Document'), expanded=False):
                c1, c2 = st.columns(2)
                r['nom']         = c1.text_input("Nom",                r.get('nom', ''),         key=f"ri_n_{i}")
                r['type']        = c2.text_input("Type (plan, spec…)", r.get('type', ''),        key=f"ri_t_{i}")
                r['description'] = st.text_area("Description",         r.get('description', ''), height=60, key=f"ri_d_{i}")
                if st.button("Supprimer", key=f"ri_del_{i}"):
                    rp['informationnelles'].pop(i); st.rerun()
        if st.button("➕ Ajouter ressource informationnelle"):
            rp['informationnelles'].append({'id': _uid(), 'nom': '', 'type': '', 'description': ''}); st.rerun()


# ══════════════════════════════════════════════════════════════════════
# MODIFICATION B — Phase planification avec vue arborescente hiérarchique
# ══════════════════════════════════════════════════════════════════════

def _show_arborescence(plan: dict, rp: dict):
    """
    Vue arborescente imbriquée : Jalon → Livrable → Activité → Tâche.
    Les enfants ne peuvent être créés que depuis leur parent.
    L'avancement est calculé bottom-up automatiquement.
    """
    _calcul_avancement(plan)

    if not plan.get("jalons"):
        st.info("Aucun jalon défini. Cliquez sur '➕ Ajouter un jalon' pour commencer.")

    for j_idx, jalon in enumerate(plan.get("jalons", [])):
        jalon.setdefault("type", "jalon")
        avj    = jalon.get("avancement_pct", 0)
        livs_j = [l for l in plan.get("livrables", []) if l.get("jalon_id") == jalon["id"]]

        with st.expander(
            f"🔵 JALON {j_idx+1} : {jalon.get('nom','Sans nom')}  "
            f"| {jalon.get('statut','A faire')}  | ▶ {avj}%  "
            f"| {len(livs_j)} livrable(s)",
            expanded=True
        ):
            # ── Édition du jalon ──────────────────────────────────────
            _form_element(jalon, f"jal_{j_idx}", rp, plan.get("jalons", []))
            col_del, col_add = st.columns([1, 2])
            with col_del:
                if st.button("🗑 Supprimer ce jalon", key=f"del_jal_{j_idx}"):
                    plan["jalons"].pop(j_idx); st.rerun()

            st.markdown("---")

            # ── Livrables de ce jalon ─────────────────────────────────
            for l_idx, liv in enumerate(livs_j):
                liv.setdefault("type", "livrable")
                avl    = liv.get("avancement_pct", 0)
                acts_l = [a for a in plan.get("activites", []) if a.get("livrable_id") == liv["id"]]

                with st.expander(
                    f"　🟢 LIVRABLE : {liv.get('nom','Sans nom')}  "
                    f"| {liv.get('statut','A faire')}  | ▶ {avl}%  "
                    f"| {len(acts_l)} activité(s)",
                    expanded=False
                ):
                    tous_pour_liv = (
                        [dict(e, type='jalon')    for e in plan.get('jalons', [])] +
                        [dict(e, type='livrable') for e in plan.get('livrables', [])]
                    )
                    _form_element(liv, f"liv_{j_idx}_{l_idx}", rp, tous_pour_liv)
                    if st.button("🗑 Supprimer ce livrable", key=f"del_liv_{j_idx}_{l_idx}"):
                        plan["livrables"].remove(liv); st.rerun()

                    st.markdown("---")

                    # ── Activités de ce livrable ──────────────────────
                    for a_idx, act in enumerate(acts_l):
                        act.setdefault("type", "activite")
                        ava    = act.get("avancement_pct", 0)
                        tacs_a = [t for t in plan.get("taches", []) if t.get("activite_id") == act["id"]]

                        with st.expander(
                            f"　　🟡 ACTIVITÉ : {act.get('nom','Sans nom')}  "
                            f"| {act.get('statut','A faire')}  | ▶ {ava}%  "
                            f"| {len(tacs_a)} tâche(s)",
                            expanded=False
                        ):
                            tous_pour_act = (
                                [dict(e, type='livrable') for e in plan.get('livrables', [])] +
                                [dict(e, type='activite') for e in plan.get('activites', [])]
                            )
                            _form_element(act, f"act_{j_idx}_{l_idx}_{a_idx}", rp, tous_pour_act)
                            if st.button("🗑 Supprimer cette activité", key=f"del_act_{j_idx}_{l_idx}_{a_idx}"):
                                plan["activites"].remove(act); st.rerun()

                            st.markdown("---")

                            # ── Tâches de cette activité ──────────────
                            for t_idx, tache in enumerate(tacs_a):
                                tache.setdefault("type", "tache")
                                with st.expander(
                                    f"　　　🟣 TÂCHE : {tache.get('nom','Sans nom')}  "
                                    f"| {tache.get('statut','A faire')}  "
                                    f"| ▶ {tache.get('avancement_pct',0)}%",
                                    expanded=False
                                ):
                                    tous_pour_tache = [dict(e, type='tache') for e in plan.get('taches', [])]
                                    _form_element(tache, f"tache_{j_idx}_{l_idx}_{a_idx}_{t_idx}", rp, tous_pour_tache)
                                    if st.button("🗑 Supprimer cette tâche", key=f"del_tache_{j_idx}_{l_idx}_{a_idx}_{t_idx}"):
                                        plan["taches"].remove(tache); st.rerun()

                            # ── Bouton ajouter tâche ──────────────────
                            if st.button(f"➕ Ajouter une tâche", key=f"add_tache_{act['id']}"):
                                plan["taches"].append(_element_vide("tache", parent_id=act["id"]))
                                st.rerun()

                    # ── Bouton ajouter activité ───────────────────────
                    if st.button(f"➕ Ajouter une activité", key=f"add_act_{liv['id']}"):
                        plan["activites"].append(_element_vide("activite", parent_id=liv["id"]))
                        st.rerun()

            # ── Bouton ajouter livrable ───────────────────────────────
            if st.button(f"➕ Ajouter un livrable", key=f"add_liv_{jalon['id']}"):
                plan["livrables"].append(_element_vide("livrable", parent_id=jalon["id"]))
                st.rerun()

    # ── Bouton ajouter jalon (niveau racine) ──────────────────────────
    st.markdown("---")
    if st.button("➕ Ajouter un jalon", type="primary"):
        plan["jalons"].append(_element_vide("jalon"))
        st.rerun()


def _show_planification(projet: dict, user: dict):
    st.header("Planification")

    plan = projet['planification']
    rp   = projet.get('ressources_projet', {'humaines': [], 'materielles': [], 'informationnelles': []})

    # Migration automatique des orphelins (projets existants)
    _migrer_orphelins(plan)

    # Recalcul avancement
    _calcul_avancement(plan)

    tous = (
        [dict(e, type='jalon')    for e in plan.get('jalons', [])] +
        [dict(e, type='livrable') for e in plan.get('livrables', [])] +
        [dict(e, type='activite') for e in plan.get('activites', [])] +
        [dict(e, type='tache')    for e in plan.get('taches', [])]
    )

    vue = st.radio("Vue", ["Arborescence (hiérarchique)", "Tableau récapitulatif", "Gantt"], horizontal=True)

    if vue == "Tableau récapitulatif":
        for label, key in [("Jalons", "jalons"), ("Livrables", "livrables"),
                           ("Activités", "activites"), ("Tâches", "taches")]:
            st.markdown(f"**{label}**")
            _tableau_elements(plan.get(key, []), rp, label)
        return

    if vue == "Gantt":
        _afficher_gantt(tous, plan.get('date_debut', ''))
        return

    # Vue arborescente hiérarchique (défaut)
    _show_arborescence(plan, rp)


# ── Phase suivi ───────────────────────────────────────────────────────

def _show_suivi(projet: dict):
    st.header("Exécution et Suivi")

    plan  = projet['planification']
    suivi = projet['suivi']
    rp    = projet.get('ressources_projet', {'humaines': [], 'materielles': [], 'informationnelles': []})

    for key in ['jalons', 'livrables', 'activites', 'taches']:
        if not suivi.get(key) and plan.get(key):
            suivi[key] = [
                {**el, 'avancement_pct': el.get('avancement_pct', 0), 'notes_suivi': ''}
                for el in plan[key]
            ]

    vue_s = st.radio("Vue suivi", ["Tableau", "Détail"], horizontal=True)
    tous_suivi = (
        [dict(e, type='jalon')    for e in suivi.get('jalons', [])] +
        [dict(e, type='livrable') for e in suivi.get('livrables', [])] +
        [dict(e, type='activite') for e in suivi.get('activites', [])] +
        [dict(e, type='tache')    for e in suivi.get('taches', [])]
    )

    if vue_s == "Tableau":
        _tableau_elements(tous_suivi, rp, "éléments de suivi")
        if st.checkbox("Afficher le Gantt de suivi"):
            _afficher_gantt(tous_suivi, plan.get('date_debut', ''))
    else:
        for label, key in [("Jalons", "jalons"), ("Livrables", "livrables"),
                           ("Activités", "activites"), ("Tâches", "taches")]:
            st.subheader(label)
            for i, el in enumerate(suivi.get(key, [])):
                with st.expander(f"{el.get('nom', '')} — {el.get('avancement_pct', 0)}%", expanded=False):
                    el['avancement_pct'] = st.slider("Avancement %", 0, 100,
                        el.get('avancement_pct', 0), key=f"sv_{key}_{i}")
                    STATUTS_S = ["A faire", "En cours", "Termine", "Bloque"]
                    s_idx = STATUTS_S.index(el.get('statut', 'A faire')) if el.get('statut') in STATUTS_S else 0
                    el['statut']      = st.selectbox("Statut", STATUTS_S, index=s_idx, key=f"sv_st_{key}_{i}")
                    el['notes_suivi'] = st.text_area("Notes de suivi", el.get('notes_suivi', ''),
                        height=60, key=f"sv_notes_{key}_{i}")
                    if el['avancement_pct'] == 100 and el.get('statut') == 'Termine':
                        if st.button("Fermer cet élément", key=f"sv_close_{key}_{i}"):
                            projet['cloture'].setdefault('elements_fermes', []).append({
                                "type": key[:-1], "nom": el['nom'],
                                "date_fermeture": datetime.now().isoformat()
                            })
                            st.rerun()

    st.markdown("---")
    st.subheader("Réunions de suivi")
    reunions = suivi.setdefault('reunions', [])
    for i, r in enumerate(reunions):
        with st.expander(f"Réunion — {r.get('date', 'N/A')} — {r.get('titre', '')}", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                rd    = r.get('date')
                rd_v  = date.fromisoformat(rd[:10]) if rd else None
                nr    = st.date_input("Date", value=rd_v, key=f"reu_d_{i}")
                r['date']  = nr.isoformat() if nr else None
                r['titre'] = st.text_input("Titre", r.get('titre', ''), key=f"reu_t_{i}")
            with c2:
                r['participants'] = st.text_input("Participants", r.get('participants', ''), key=f"reu_p_{i}")
                r['lieu']         = st.text_input("Lieu / lien visio", r.get('lieu', ''),   key=f"reu_l_{i}")
            r['ordre_du_jour'] = st.text_area("Ordre du jour",      r.get('ordre_du_jour', ''), height=80, key=f"reu_odj_{i}")
            r['decisions']     = st.text_area("Décisions / actions", r.get('decisions', ''),   height=80, key=f"reu_dec_{i}")
            if st.button("Supprimer", key=f"reu_del_{i}"):
                reunions.pop(i); st.rerun()

    if st.button("➕ Ajouter une réunion"):
        reunions.append({
            'id': _uid(), 'date': date.today().isoformat(), 'titre': '',
            'participants': '', 'lieu': '', 'ordre_du_jour': '', 'decisions': ''
        }); st.rerun()


# ── Phase démarrage ───────────────────────────────────────────────────

def _show_demarrage(projet: dict, user: dict):
    st.header("Phase de Démarrage")
    dem = projet['demarrage']

    st.subheader("Parties prenantes")
    for i, pp in enumerate(dem.get('parties_prenantes', [])):
        with st.expander(pp.get('nom', 'Partie prenante'), expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                pp['nom']  = st.text_input("Nom",  pp.get('nom', ''),  key=f"pp_n_{i}")
                pp['role'] = st.text_input("Rôle", pp.get('role', ''), key=f"pp_r_{i}")
            with c2:
                inf_opts = ["Faible", "Moyenne", "Elevee"]
                inf_val  = pp.get('influence', 'Moyenne') if pp.get('influence') in inf_opts else 'Moyenne'
                pp['influence'] = st.selectbox("Influence", inf_opts, index=inf_opts.index(inf_val), key=f"pp_i_{i}")
                int_opts = ["Faible", "Moyen", "Eleve"]
                int_val  = pp.get('interet', 'Moyen') if pp.get('interet') in int_opts else 'Moyen'
                pp['interet'] = st.selectbox("Intérêt", int_opts, index=int_opts.index(int_val), key=f"pp_in_{i}")
            if st.button("Supprimer", key=f"pp_del_{i}"):
                dem['parties_prenantes'].pop(i); st.rerun()
    if st.button("➕ Ajouter partie prenante"):
        dem.setdefault('parties_prenantes', []).append(
            {'nom': 'Nouveau', 'role': '', 'influence': 'Moyenne', 'interet': 'Moyen'}
        ); st.rerun()

    st.markdown("---")
    st.subheader("Registre des risques")
    for i, r in enumerate(dem.get('risques', [])):
        with st.expander(r.get('description', 'Risque')[:50], expanded=False):
            r['description'] = st.text_area("Description", r.get('description', ''), height=60, key=f"rq_d_{i}")
            c1, c2 = st.columns(2)
            with c1:
                imp_opts = ["Faible", "Moyen", "Eleve"]
                imp_val  = r.get('impact', 'Moyen') if r.get('impact') in imp_opts else 'Moyen'
                r['impact'] = st.select_slider("Impact", imp_opts, value=imp_val, key=f"rq_i_{i}")
            with c2:
                prob_opts = ["Faible", "Moyenne", "Elevee"]
                prob_val  = r.get('probabilite', 'Moyenne') if r.get('probabilite') in prob_opts else 'Moyenne'
                r['probabilite'] = st.select_slider("Probabilité", prob_opts, value=prob_val, key=f"rq_p_{i}")
            r['mitigation'] = st.text_input("Mitigation", r.get('mitigation', ''), key=f"rq_m_{i}")
            if st.button("Supprimer", key=f"rq_del_{i}"):
                dem['risques'].pop(i); st.rerun()
    if st.button("➕ Ajouter risque"):
        dem.setdefault('risques', []).append(
            {'description': '', 'impact': 'Moyen', 'probabilite': 'Moyenne', 'mitigation': ''}
        ); st.rerun()

    st.markdown("---")
    st.subheader("Inclusions / Exclusions")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Inclusions**")
        for i, inc in enumerate(dem.get('inclusions', [])):
            cols = st.columns([5, 1])
            dem['inclusions'][i] = cols[0].text_input("", inc, key=f"inc_{i}", label_visibility="collapsed")
            if cols[1].button("✕", key=f"del_inc_{i}"):
                dem['inclusions'].pop(i); st.rerun()
        if st.button("➕ Inclusion"):
            dem.setdefault('inclusions', []).append(""); st.rerun()
    with c2:
        st.markdown("**Exclusions**")
        for i, exc in enumerate(dem.get('exclusions', [])):
            cols = st.columns([5, 1])
            dem['exclusions'][i] = cols[0].text_input("", exc, key=f"exc_{i}", label_visibility="collapsed")
            if cols[1].button("✕", key=f"del_exc_{i}"):
                dem['exclusions'].pop(i); st.rerun()
        if st.button("➕ Exclusion"):
            dem.setdefault('exclusions', []).append(""); st.rerun()


# ── Clôture / Post-mortem ─────────────────────────────────────────────

def _show_cloture(projet: dict):
    st.header("Phase de Clôture")
    elements = projet['cloture'].get('elements_fermes', [])
    if not elements:
        st.info("Aucun élément fermé pour le moment.")
        return
    for e in elements:
        st.write(f"**{e['type'].upper()}** : {e['nom']} — {(e.get('date_fermeture') or '')[:10]}")


def _show_postmortem(projet: dict):
    st.header("Post-mortem")
    if projet['statut'] != 'termine':
        st.warning("Disponible une fois le projet marqué comme terminé.")
        return
    pm = projet['postmortem']
    pf = st.text_area("Points forts", "\n".join(pm.get('points_forts', [])), height=120)
    pm['points_forts'] = [l.strip() for l in pf.split('\n') if l.strip()]
    am = st.text_area("À améliorer", "\n".join(pm.get('ameliorations', [])), height=120)
    pm['ameliorations'] = [l.strip() for l in am.split('\n') if l.strip()]
    pm['conclusion'] = st.text_area("Conclusion", pm.get('conclusion', ''), height=150)


# ── Création nouveau projet ───────────────────────────────────────────

def _extraire_info_offre(offre: dict) -> dict:
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
        or f"Offre {str(offre.get('id', ''))[:8]}"
    )
    numero = (
        contenu.get('exigences', {}).get('numero_projet')
        or contenu.get('projet', {}).get('numero')
        or ''
    )
    return {"nom": nom, "numero": numero, "contenu": contenu}


def _creer_nouveau_projet_ui(user: dict) -> Optional[dict]:
    st.subheader("Créer un nouveau projet")

    if st.session_state.get('offre_pour_projet'):
        pre = st.session_state['offre_pour_projet']
        st.success(f"Offre sélectionnée : **{pre['nom_projet']}** — {pre['projet_numero']}")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🚀 Créer le projet avec cette offre", type="primary"):
                p = creer_projet_vide(pre['id'], pre['offre_data'], user['id'])
                if not p['nom_projet']:
                    p['nom_projet'] = pre['nom_projet']
                if not p['offre_reference']:
                    p['offre_reference'] = pre['projet_numero']

                # Ressources humaines depuis profil
                if user.get('equipe'):
                    p['ressources_projet']['humaines'] = [
                        {'id': _uid(), 'nom': m.get('nom', ''), 'role': m.get('poste', ''), 'taux_horaire': 75}
                        for m in user['equipe']
                    ]

                # ── MODIFICATION C — Génération plan complet par IA ──
                with st.spinner("🤖 L'IA génère votre plan de projet complet…"):
                    plan_ia = generer_plan_projet_ia(
                        offre_data=pre['offre_data'],
                        user=user,
                        dates={
                            'debut': p['planification']['date_debut'],
                            'fin':   p['planification']['date_fin'],
                        }
                    )

                if plan_ia:
                    _aplatir_plan_ia(plan_ia, p['planification'])
                    p['demarrage']['risques']            = plan_ia.get('risques', [])
                    p['demarrage']['parties_prenantes']  = plan_ia.get('parties_prenantes', [])
                    p['demarrage']['inclusions']         = plan_ia.get('inclusions', [])
                    p['demarrage']['exclusions']         = plan_ia.get('exclusions', [])
                    st.success(
                        "✅ Plan de projet généré par l'IA — "
                        "vérifiez et ajustez avant de sauvegarder."
                    )
                else:
                    # Fallback : démarrage seul
                    with st.spinner("Analyse IA du démarrage…"):
                        sug = analyser_offre_pour_demarrage(pre['offre_data'], user)
                        if sug:
                            p['demarrage'].update(sug)

                del st.session_state['offre_pour_projet']
                st.session_state['projet_actif'] = p
                st.rerun()
        with c2:
            if st.button("Choisir une autre offre"):
                del st.session_state['offre_pour_projet']; st.rerun()
        return st.session_state.get('projet_actif')

    # Chercher les offres acceptées
    offres_acc = []
    for table, filtre_k, filtre_v, nom_k, num_k, data_k in [
        ('offres',      'statut',         'acceptee', None,          None,            None),
        ('soumissions', 'recommendation', 'GO',       'nom_projet',  'projet_numero', 'analyse_json'),
        ('analyses',    'recommendation', 'OUI',      'nom_projet',  'projet_numero', 'analyse_json'),
    ]:
        try:
            rows = database.supabase.table(table).select("*").eq(
                'entreprise_id', user['id']
            ).eq(filtre_k, filtre_v).execute().data or []
            for row in rows:
                if table == 'offres':
                    info = _extraire_info_offre(row)
                    offres_acc.append({'id': row['id'], 'source': table,
                                       'nom_projet': info['nom'], 'projet_numero': info['numero'],
                                       'offre_data': info['contenu']})
                else:
                    raw = row.get(data_k, '{}')
                    try:
                        od = json.loads(raw) if isinstance(raw, str) else raw
                    except Exception:
                        od = {}
                    offres_acc.append({'id': row['id'], 'source': table,
                                       'nom_projet': row.get(nom_k, 'N/A'),
                                       'projet_numero': row.get(num_k, ''),
                                       'offre_data': od})
        except Exception:
            pass

    vus, offres_u = set(), []
    for o in offres_acc:
        if o['id'] not in vus:
            vus.add(o['id']); offres_u.append(o)

    if not offres_u:
        st.warning(
            "Aucune offre acceptée. Allez dans **Mes Offres**, "
            "marquez une offre comme **Acceptée** puis cliquez **Démarrer le projet**."
        )
        return None

    labels    = [f"{o['nom_projet']} — {o['projet_numero']}" for o in offres_u]
    label_sel = st.selectbox("Choisir une offre", labels)

    if st.button("🚀 Créer le projet", type="primary"):
        o = offres_u[labels.index(label_sel)]
        p = creer_projet_vide(o['id'], o['offre_data'], user['id'])
        if not p['nom_projet']:
            p['nom_projet'] = o['nom_projet']
        if not p['offre_reference']:
            p['offre_reference'] = o['projet_numero']
        if user.get('equipe'):
            p['ressources_projet']['humaines'] = [
                {'id': _uid(), 'nom': m.get('nom', ''), 'role': m.get('poste', ''), 'taux_horaire': 75}
                for m in user['equipe']
            ]

        # ── MODIFICATION C — Génération plan complet par IA ──────────
        with st.spinner("🤖 L'IA génère votre plan de projet complet…"):
            plan_ia = generer_plan_projet_ia(
                offre_data=o['offre_data'],
                user=user,
                dates={
                    'debut': p['planification']['date_debut'],
                    'fin':   p['planification']['date_fin'],
                }
            )

        if plan_ia:
            _aplatir_plan_ia(plan_ia, p['planification'])
            p['demarrage']['risques']           = plan_ia.get('risques', [])
            p['demarrage']['parties_prenantes'] = plan_ia.get('parties_prenantes', [])
            p['demarrage']['inclusions']        = plan_ia.get('inclusions', [])
            p['demarrage']['exclusions']        = plan_ia.get('exclusions', [])
            st.success("✅ Plan généré par l'IA — vérifiez et ajustez avant de sauvegarder.")
        else:
            with st.spinner("Analyse IA du démarrage…"):
                sug = analyser_offre_pour_demarrage(o['offre_data'], user)
                if sug:
                    p['demarrage'].update(sug)

        st.session_state['projet_actif'] = p
        st.rerun()

    return st.session_state.get('projet_actif')


# ── Onglet principal ──────────────────────────────────────────────────

def show_gestion_projets_tab(user: dict):
    st.title("Gestion de Projet")

    try:
        database.apply_supabase_auth()
        resp   = database.supabase.table('gestion_projets').select("*").eq(
            'entreprise_id', user['id']
        ).order('date_creation', desc=True).execute()
        projets = [json.loads(p['data']) for p in resp.data] if resp.data else []
    except Exception as e:
        st.warning(f"Mode hors ligne : {e}")
        projets = st.session_state.get('projets_locaux', [])

    col1, col2 = st.columns([3, 1])
    projet_actif = None

    with col1:
        if projets:
            opts = [
                f"{p['nom_projet']} ({p.get('offre_reference','')}) — {p['statut'].upper()}"
                for p in projets
            ]
            opts.insert(0, "Créer un nouveau projet")
            sel = st.selectbox("Projet", opts)
            if sel == "Créer un nouveau projet":
                projet_actif = _creer_nouveau_projet_ui(user)
            else:
                projet_actif = projets[opts.index(sel) - 1]
        else:
            projet_actif = _creer_nouveau_projet_ui(user)

    with col2:
        if projet_actif:
            STATUTS_PROJ = ["demarrage", "planification", "execution", "suivi", "cloture", "termine"]
            s_idx        = STATUTS_PROJ.index(projet_actif['statut']) if projet_actif['statut'] in STATUTS_PROJ else 0
            nouveau_statut = st.selectbox("Statut projet", STATUTS_PROJ, index=s_idx)
            if nouveau_statut != projet_actif['statut']:
                projet_actif['statut'] = nouveau_statut

    if not projet_actif:
        st.info("Créez un nouveau projet pour commencer.")
        return

    st.markdown("---")

    tabs = st.tabs(["Démarrage", "Ressources", "Planification", "Suivi", "Clôture", "Post-mortem"])

    with tabs[0]:
        _show_demarrage(projet_actif, user)
    with tabs[1]:
        _section_ressources(projet_actif, user)
    with tabs[2]:
        _show_planification(projet_actif, user)
    with tabs[3]:
        _show_suivi(projet_actif)
    with tabs[4]:
        _show_cloture(projet_actif)
    with tabs[5]:
        _show_postmortem(projet_actif)

    st.markdown("---")
    if st.button("💾 Sauvegarder le projet", type="primary"):
        _sauvegarder(projet_actif, user)
