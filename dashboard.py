"""
Tableau de bord MOKAFAD — Design industriel-raffine
Cartes glassmorphism, palette acier/cyan, mini-graphiques CSS
"""
import streamlit as st
import database
import json


# ── Palette et styles globaux ─────────────────────────────────────────

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

/* Reset conteneur Streamlit */
.block-container { padding-top: 1rem !important; }

/* ── Variables ── */
:root {
  --bg:        #0d1117;
  --surface:   #161b22;
  --border:    rgba(48,54,61,0.8);
  --cyan:      #00e5ff;
  --cyan-dim:  rgba(0,229,255,0.12);
  --green:     #3fb950;
  --orange:    #f0883e;
  --red:       #f85149;
  --yellow:    #d29922;
  --text:      #e6edf3;
  --muted:     #7d8590;
  --card-bg:   rgba(22,27,34,0.85);
  --glow:      0 0 20px rgba(0,229,255,0.15);
}

/* ── Header ── */
.dash-header {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  margin-bottom: 28px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--border);
}
.dash-header .logo-mark {
  width: 44px; height: 44px;
  background: var(--cyan);
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-family: 'Syne', sans-serif;
  font-weight: 800; font-size: 20px;
  color: #0d1117;
  flex-shrink: 0;
  box-shadow: var(--glow);
}
.dash-header h1 {
  font-family: 'Syne', sans-serif !important;
  font-size: 26px !important;
  font-weight: 700 !important;
  color: var(--text) !important;
  margin: 0 !important; padding: 0 !important;
  letter-spacing: -0.5px;
}
.dash-header .subtitle {
  font-family: 'DM Sans', sans-serif;
  font-size: 13px;
  color: var(--muted);
  margin: 0;
}
.dash-time {
  margin-left: auto;
  font-family: 'DM Sans', sans-serif;
  font-size: 12px;
  color: var(--muted);
  text-align: right;
}
.dash-time strong { color: var(--cyan); display: block; font-size: 14px; }

/* ── Section label ── */
.section-label {
  font-family: 'Syne', sans-serif;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--cyan);
  margin: 24px 0 12px 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.section-label::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border);
}

/* ── Grille de KPI ── */
.kpi-grid {
  display: grid;
  gap: 12px;
  margin-bottom: 4px;
}
.kpi-grid-4 { grid-template-columns: repeat(4, 1fr); }
.kpi-grid-3 { grid-template-columns: repeat(3, 1fr); }
.kpi-grid-2 { grid-template-columns: repeat(2, 1fr); }

/* ── Carte KPI ── */
.kpi-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 18px 20px;
  position: relative;
  overflow: hidden;
  transition: border-color 0.2s, transform 0.2s;
  backdrop-filter: blur(8px);
}
.kpi-card:hover {
  border-color: rgba(0,229,255,0.3);
  transform: translateY(-2px);
}
.kpi-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: var(--accent-color, var(--cyan));
  opacity: 0.6;
}
.kpi-card .kpi-icon {
  font-size: 18px;
  margin-bottom: 10px;
  display: block;
}
.kpi-card .kpi-value {
  font-family: 'Syne', sans-serif;
  font-size: 36px;
  font-weight: 800;
  color: var(--accent-color, var(--cyan));
  line-height: 1;
  margin-bottom: 4px;
  letter-spacing: -1px;
}
.kpi-card .kpi-label {
  font-family: 'DM Sans', sans-serif;
  font-size: 12px;
  color: var(--muted);
  font-weight: 400;
  line-height: 1.3;
}
.kpi-card .kpi-bar {
  margin-top: 12px;
  height: 3px;
  background: rgba(255,255,255,0.06);
  border-radius: 2px;
  overflow: hidden;
}
.kpi-card .kpi-bar-fill {
  height: 100%;
  border-radius: 2px;
  background: var(--accent-color, var(--cyan));
  opacity: 0.7;
  transition: width 0.6s ease;
}

/* ── Carte large ── */
.section-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 0;
  overflow: hidden;
  margin-bottom: 16px;
  backdrop-filter: blur(8px);
}
.section-card-header {
  padding: 14px 20px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(255,255,255,0.02);
}
.section-card-header span.label {
  font-family: 'Syne', sans-serif;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}
.section-card-header span.count {
  margin-left: auto;
  background: var(--cyan-dim);
  color: var(--cyan);
  font-family: 'DM Sans', sans-serif;
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 20px;
}

/* ── Ligne d'item ── */
.item-row {
  display: flex;
  align-items: center;
  padding: 13px 20px;
  border-bottom: 1px solid var(--border);
  gap: 12px;
  transition: background 0.15s;
}
.item-row:last-child { border-bottom: none; }
.item-row:hover { background: rgba(255,255,255,0.02); }

.item-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.item-main { flex: 1; min-width: 0; }
.item-title {
  font-family: 'DM Sans', sans-serif;
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.item-sub {
  font-family: 'DM Sans', sans-serif;
  font-size: 11px;
  color: var(--muted);
  margin-top: 1px;
}
.item-badge {
  font-family: 'DM Sans', sans-serif;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  padding: 3px 8px;
  border-radius: 4px;
  flex-shrink: 0;
}
.badge-go     { background: rgba(63,185,80,0.15);  color: #3fb950; }
.badge-non    { background: rgba(248,81,73,0.15);   color: #f85149; }
.badge-maybe  { background: rgba(210,153,34,0.15);  color: #d29922; }
.badge-accept { background: rgba(0,229,255,0.12);   color: var(--cyan); }
.badge-envoi  { background: rgba(63,185,80,0.12);   color: #3fb950; }
.badge-refus  { background: rgba(248,81,73,0.12);   color: #f85149; }
.badge-brouil { background: rgba(125,133,144,0.15); color: #7d8590; }
.badge-cours  { background: rgba(240,136,62,0.15);  color: #f0883e; }
.badge-done   { background: rgba(63,185,80,0.15);   color: #3fb950; }

.item-score {
  font-family: 'Syne', sans-serif;
  font-size: 15px;
  font-weight: 700;
  flex-shrink: 0;
}
.item-date {
  font-family: 'DM Sans', sans-serif;
  font-size: 11px;
  color: var(--muted);
  flex-shrink: 0;
  min-width: 80px;
  text-align: right;
}

/* ── Empty state ── */
.empty-state {
  padding: 32px 20px;
  text-align: center;
  font-family: 'DM Sans', sans-serif;
  font-size: 13px;
  color: var(--muted);
}
.empty-state span { display: block; font-size: 24px; margin-bottom: 8px; }

/* ── Mini sparkline bars ── */
.sparkline {
  display: flex;
  align-items: flex-end;
  gap: 3px;
  height: 28px;
  margin-top: 10px;
}
.spark-bar {
  flex: 1;
  background: var(--accent-color, var(--cyan));
  opacity: 0.5;
  border-radius: 2px 2px 0 0;
  min-height: 3px;
  transition: opacity 0.2s;
}
.spark-bar:hover { opacity: 1; }

/* ── Taux de succes anneau ── */
.success-ring-wrap {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
}
.ring-label { font-family: 'DM Sans', sans-serif; font-size: 12px; color: var(--muted); }
.ring-value { font-family: 'Syne', sans-serif; font-size: 22px; font-weight: 700; color: var(--green); }

</style>
"""


def _kpi(icon, value, label, color, bar_pct=0):
    bar = f'<div class="kpi-bar"><div class="kpi-bar-fill" style="width:{min(bar_pct,100)}%"></div></div>' if bar_pct is not None else ''
    return f"""
<div class="kpi-card" style="--accent-color:{color}">
  <span class="kpi-icon">{icon}</span>
  <div class="kpi-value">{value}</div>
  <div class="kpi-label">{label}</div>
  {bar}
</div>"""


def _item_row(dot_color, title, subtitle, badge_html, extra=""):
    return f"""
<div class="item-row">
  <div class="item-dot" style="background:{dot_color}"></div>
  <div class="item-main">
    <div class="item-title">{title}</div>
    <div class="item-sub">{subtitle}</div>
  </div>
  {badge_html}
  {extra}
</div>"""


def show_dashboard(user):
    # Injecter CSS
    st.markdown(CSS, unsafe_allow_html=True)

    try:
        database.apply_supabase_auth()
    except Exception as e:
        st.error(f"Erreur connexion : {e}")
        return

    uid = user['id']

    def _count(table, filters: dict) -> int:
        try:
            q = database.supabase.table(table).select("id", count="exact")
            for k, v in filters.items():
                q = q.eq(k, v)
            return q.execute().count or 0
        except Exception:
            return 0

    # ── Données ───────────────────────────────────────────────────────
    total_analyses = _count('soumissions', {'entreprise_id': uid})
    go_count       = _count('soumissions', {'entreprise_id': uid, 'recommendation': 'GO'})
    maybe_count    = _count('soumissions', {'entreprise_id': uid, 'recommendation': 'PEUT-ETRE'})
    non_count      = _count('soumissions', {'entreprise_id': uid, 'recommendation': 'NON'})

    total_offres   = _count('offres', {'entreprise_id': uid})
    envoyees       = _count('offres', {'entreprise_id': uid, 'statut': 'envoyee'})
    acceptees      = _count('offres', {'entreprise_id': uid, 'statut': 'acceptee'})
    refusees       = _count('offres', {'entreprise_id': uid, 'statut': 'refusee'})

    en_cours = termines = 0
    try:
        gp = database.supabase.table('gestion_projets').select("statut").eq('entreprise_id', uid).execute()
        for row in (gp.data or []):
            s = row.get('statut', '')
            if s == 'termine':
                termines += 1
            elif s in ('demarrage', 'planification', 'execution', 'suivi', 'cloture'):
                en_cours += 1
    except Exception:
        pass

    taux_succes = round(acceptees / total_offres * 100) if total_offres > 0 else 0
    bar_go    = round(go_count    / total_analyses * 100) if total_analyses > 0 else 0
    bar_maybe = round(maybe_count / total_analyses * 100) if total_analyses > 0 else 0
    bar_non   = round(non_count   / total_analyses * 100) if total_analyses > 0 else 0

    nom_entreprise = user.get('nom_entreprise', 'Mon entreprise')
    contact        = user.get('contact_nom', '')
    from datetime import date
    aujourd_hui    = date.today().strftime("%d %B %Y")

    # ── Header ────────────────────────────────────────────────────────
    st.markdown(f"""
{CSS}
<div class="dash-header">
  <div class="logo-mark">M</div>
  <div>
    <h1>Tableau de bord</h1>
    <p class="subtitle">{nom_entreprise} · {contact}</p>
  </div>
  <div class="dash-time">
    <strong>{aujourd_hui}</strong>
    Vue d'ensemble
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Section 1 : Analyses ──────────────────────────────────────────
    st.markdown('<div class="section-label">Appels d\'offres analysés</div>', unsafe_allow_html=True)
    kpis_analyses = f"""
<div class="kpi-grid kpi-grid-4">
  {_kpi("📊", total_analyses, "Total analysés",   "#00e5ff", 100)}
  {_kpi("✅", go_count,       "Qualifiés — GO",    "#3fb950", bar_go)}
  {_kpi("🟡", maybe_count,    "Peut-être",         "#d29922", bar_maybe)}
  {_kpi("❌", non_count,      "Rejetés — NON",     "#f85149", bar_non)}
</div>"""
    st.markdown(kpis_analyses, unsafe_allow_html=True)

    # ── Section 2 : Offres ────────────────────────────────────────────
    st.markdown('<div class="section-label">Offres de services</div>', unsafe_allow_html=True)
    bar_acc  = round(acceptees / total_offres * 100) if total_offres > 0 else 0
    bar_env  = round(envoyees  / total_offres * 100) if total_offres > 0 else 0
    bar_ref  = round(refusees  / total_offres * 100) if total_offres > 0 else 0
    kpis_offres = f"""
<div class="kpi-grid kpi-grid-4">
  {_kpi("📁", total_offres, "Total offres",       "#00e5ff", 100)}
  {_kpi("📤", envoyees,     "Envoyées au client", "#3fb950", bar_env)}
  {_kpi("🎉", acceptees,    "Acceptées",          "#00e5ff", bar_acc)}
  {_kpi("❌", refusees,     "Refusées",           "#f85149", bar_ref)}
</div>"""
    st.markdown(kpis_offres, unsafe_allow_html=True)

    # ── Section 3 : Projets + Taux de succès ─────────────────────────
    st.markdown('<div class="section-label">Projets & performance</div>', unsafe_allow_html=True)
    kpis_projets = f"""
<div class="kpi-grid kpi-grid-3">
  {_kpi("⚡", en_cours,    "En cours d'exécution", "#f0883e", None)}
  {_kpi("🏁", termines,    "Projets terminés",      "#3fb950", None)}
  {_kpi("🎯", f"{taux_succes}%", "Taux d'acceptation", "#00e5ff", taux_succes)}
</div>"""
    st.markdown(kpis_projets, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 4 : Flux récents en 2 colonnes ────────────────────────
    col_a, col_b = st.columns(2)

    # ── Analyses récentes ─────────────────────────────────────────────
    with col_a:
        rows_html = ""
        try:
            recent = database.supabase.table('soumissions').select("*").eq(
                'entreprise_id', uid
            ).order('created_at', desc=True).limit(6).execute()

            if recent.data:
                for item in recent.data:
                    rec   = item.get('recommendation', 'N/A')
                    nom   = item.get('nom_projet', 'Sans nom')[:40]
                    score = item.get('score', '—')
                    dat   = item.get('created_at', '')[:10]

                    dot   = '#3fb950' if rec == 'GO' else '#f85149' if rec == 'NON' else '#d29922'
                    badge_cls = 'badge-go' if rec == 'GO' else 'badge-non' if rec == 'NON' else 'badge-maybe'
                    score_col = '#3fb950' if rec == 'GO' else '#f85149' if rec == 'NON' else '#d29922'

                    rows_html += _item_row(
                        dot, nom, dat,
                        f'<span class="item-badge {badge_cls}">{rec}</span>',
                        f'<span class="item-score" style="color:{score_col}">{score}</span>'
                    )
            else:
                rows_html = '<div class="empty-state"><span>📭</span>Aucune analyse</div>'
        except Exception as e:
            rows_html = f'<div class="empty-state"><span>⚠️</span>{str(e)[:60]}</div>'

        st.markdown(f"""
<div class="section-card">
  <div class="section-card-header">
    <span>📊</span>
    <span class="label">Analyses récentes</span>
    <span class="count">{total_analyses} total</span>
  </div>
  {rows_html}
</div>""", unsafe_allow_html=True)

    # ── Offres récentes ────────────────────────────────────────────────
    with col_b:
        rows_html2 = ""
        STATUT_CFG = {
            "brouillon":  ('#7d8590', 'badge-brouil', '📝'),
            "a_valider":  ('#d29922', 'badge-maybe',  '📋'),
            "validee":    ('#3fb950', 'badge-done',   '✅'),
            "envoyee":    ('#3fb950', 'badge-envoi',  '📤'),
            "en_attente": ('#f0883e', 'badge-cours',  '⏳'),
            "acceptee":   ('#00e5ff', 'badge-accept', '🎉'),
            "refusee":    ('#f85149', 'badge-refus',  '❌'),
        }
        try:
            offres_rec = database.supabase.table('offres').select("*").eq(
                'entreprise_id', uid
            ).order('updated_at', desc=True).limit(6).execute()

            if offres_rec.data:
                for o in offres_rec.data:
                    statut  = o.get('statut', 'brouillon')
                    contenu = o.get('contenu', {})
                    if isinstance(contenu, str):
                        try:
                            contenu = json.loads(contenu)
                        except Exception:
                            contenu = {}
                    nom = (
                        contenu.get('offre_technique', {}).get('titre_offre')
                        or contenu.get('exigences', {}).get('nom_projet')
                        or f"Offre {o['id'][:8]}"
                    )[:40]

                    ttc_raw = contenu.get('offre_financiere', {}).get('total_ttc', 0)
                    ttc_str = f"{ttc_raw:,.0f} $" if ttc_raw else "—"
                    maj     = o.get('updated_at', '')[:10]

                    dot, badge_cls, _ = STATUT_CFG.get(statut, ('#7d8590', 'badge-brouil', '•'))
                    rows_html2 += _item_row(
                        dot, nom, f"{maj} · {ttc_str}",
                        f'<span class="item-badge {badge_cls}">{statut.upper()}</span>'
                    )
            else:
                rows_html2 = '<div class="empty-state"><span>📭</span>Aucune offre</div>'
        except Exception as e:
            rows_html2 = f'<div class="empty-state"><span>⚠️</span>{str(e)[:60]}</div>'

        st.markdown(f"""
<div class="section-card">
  <div class="section-card-header">
    <span>📁</span>
    <span class="label">Offres récentes</span>
    <span class="count">{total_offres} total</span>
  </div>
  {rows_html2}
</div>""", unsafe_allow_html=True)