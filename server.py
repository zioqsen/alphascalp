#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AlphaScalp — Serveur de licence + relais de signaux (MVP bêta)
==============================================================

Rôle :
  1. Recevoir les signaux du BOT MAÎTRE (ouverture / fermeture de position)
  2. Les relayer aux FOLLOWERS *uniquement si leur clé d'abonnement est active*
  3. Gérer les clés (créer / activer / désactiver) via une petite page admin

Conçu pour la phase bêta : tout en démo, abonnement "gratuit" simulé par le
toggle manuel actif/inactif. Le jour du passage payant, on remplace ce toggle
par un webhook Stripe qui bascule le champ `active` — le reste ne bouge pas.

Lancer :
    pip install fastapi uvicorn
    python server.py
    # → http://127.0.0.1:8000/admin?token=<ADMIN_TOKEN>

Config par variables d'environnement (sinon valeurs par défaut de dev) :
    ALPHASCALP_MASTER_TOKEN   jeton du bot maître (POST /api/signal)
    ALPHASCALP_ADMIN_TOKEN    jeton de la page admin
    ALPHASCALP_DB             chemin de la base SQLite
"""

import json
import os
import secrets
import sqlite3
import threading
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
MASTER_TOKEN = os.environ.get("ALPHASCALP_MASTER_TOKEN", "master-dev-changeme")
ADMIN_TOKEN  = os.environ.get("ALPHASCALP_ADMIN_TOKEN",  "admin-dev-changeme")
DB_PATH      = os.environ.get("ALPHASCALP_DB",           "alphascalp.db")

# [30/07] Notification Telegram des inscriptions. À renseigner dans les
# variables d'environnement de l'hébergeur — JAMAIS en dur dans le code, ce
# dépôt est public. Absentes = fonctionnalité simplement inactive.
TG_TOKEN   = os.environ.get("ALPHASCALP_TG_TOKEN", "")
TG_CHAT_ID = os.environ.get("ALPHASCALP_TG_CHAT_ID", "")


def _heure_paris() -> str:
    """Horodatage lisible en heure de Paris. Le serveur tourne en UTC : sans
    conversion, la notification afficherait une heure décalée de 1 ou 2 h selon
    la saison — de quoi douter de sa fraîcheur pour rien."""
    maintenant = datetime.now(timezone.utc)
    try:
        from zoneinfo import ZoneInfo          # stdlib depuis Python 3.9
        maintenant = maintenant.astimezone(ZoneInfo("Europe/Paris"))
        suffixe = ""
    except Exception:                          # tzdata absent sur l'image
        suffixe = " UTC"
    return maintenant.strftime("%d/%m/%Y à %H:%M") + suffixe


def _echappe(s: str) -> str:
    """Telegram en parse_mode HTML : un email contenant < ou & casserait le
    message (erreur 400, notification perdue). On échappe."""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _notify_signup(email: str, rang: Optional[int] = None,
                   prenom: str = "", nom: str = "",
                   age: Optional[int] = None) -> None:
    """Prévient d'une inscription par Telegram. Non bloquant et silencieux en
    cas d'échec : une notification perdue ne doit JAMAIS faire échouer une
    inscription — c'est du confort, la base et le log restent la source.
    urllib plutôt que requests : aucune dépendance ajoutée au déploiement.

    [30/07] La clé d'API a été RETIRÉE du message. Une clé qui donne accès au
    service n'a rien à faire dans un fil de discussion : elle y reste
    indéfiniment, se retrouve dans les sauvegardes du téléphone et s'affiche
    sur l'écran de verrouillage. Elle est de toute façon consultable dans
    /admin, qui est l'endroit d'où on l'active.
    """
    if not TG_TOKEN or not TG_CHAT_ID:
        return

    def _post():
        try:
            # Telegram n'accepte QUE b/i/u/s/a/code/pre/blockquote/tg-spoiler.
            # Une balise hors liste (<sup>, <br>, <div>...) fait renvoyer une
            # erreur 400 et la notification est perdue en silence.
            rang_txt = "1er" if rang == 1 else f"{rang}e"
            identite = _echappe(f"{prenom} {nom}".strip()) or "—"
            lignes = [
                "\U0001F680 <b>Nouvelle inscription bêta</b>",
                "<i>AlphaScalp</i>",
                "",
                f"\U0001F464 <b>{identite}</b>"
                + (f"  ·  {age} ans" if age is not None else ""),
                f"\U0001F4E7 <code>{_echappe(email)}</code>",
                f"\U0001F553 {_heure_paris()}",
            ]
            if rang:
                lignes.append(f"\U0001F3F7 {rang_txt} inscrit à la bêta")
            lignes += [
                "",
                "⏳ Clé créée <b>inactive</b> — elle ne donne accès à rien "
                "tant que tu ne l'actives pas.",
                "➡️ <a href=\"https://alphascalp.onrender.com/admin\">"
                "Ouvrir l'admin</a>",
            ]
            texte = "\n".join(lignes)
            data = urllib.parse.urlencode({
                "chat_id": TG_CHAT_ID, "text": texte, "parse_mode": "HTML",
                "disable_web_page_preview": "true",
            }).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", data=data)
            urllib.request.urlopen(req, timeout=10).read()
        except Exception as e:                      # noqa: BLE001
            print(f"SIGNUP_NOTIFY_KO | {email} | {e}", flush=True)

    threading.Thread(target=_post, daemon=True).start()


app = FastAPI(title="AlphaScalp Server", version="0.1.0")


# ─────────────────────────────────────────────────────────────
# BASE DE DONNÉES
# ─────────────────────────────────────────────────────────────
@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS clients (
            api_key     TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            plan        TEXT NOT NULL DEFAULT 'beta',
            active      INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT NOT NULL,
            last_seen   TEXT
        );
        CREATE TABLE IF NOT EXISTS signals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            action      TEXT NOT NULL,           -- 'open' | 'close'
            ref_id      TEXT NOT NULL,           -- identifiant logique du trade (ticket maître)
            symbol      TEXT NOT NULL,
            direction   TEXT,                    -- 'BUY' | 'SELL' (sur open)
            volume_ref  REAL,                    -- volume du maître (le follower adaptera au sien)
            price       REAL,
            sl          REAL,
            tp          REAL,
            regime      TEXT,                    -- info contextuelle (TREND/RANGE...)
            created_at  TEXT NOT NULL
        );
        """)
        # [28/07] Migration sûre : colonne email pour l'inscription publique.
        # ALTER TABLE ADD COLUMN est idempotent si on avale l'erreur "duplicate".
        try:
            conn.execute("ALTER TABLE clients ADD COLUMN email TEXT")
        except sqlite3.OperationalError:
            pass  # colonne déjà présente
        # [30/07] Identité + date de naissance : un produit financier ne peut
        # pas être proposé à un mineur. La déclaration sur l'honneur reste
        # faible — elle n'empêche personne de mentir — mais c'est la première
        # barrière, celle que tout le monde applique à l'inscription. La
        # vérification sérieuse (pièce d'identité) est de toute façon faite par
        # le BROKER à l'ouverture du compte : c'est lui qui détient les fonds.
        for _colonne in ("prenom TEXT", "nom TEXT", "date_naissance TEXT"):
            try:
                conn.execute(f"ALTER TABLE clients ADD COLUMN {_colonne}")
            except sqlite3.OperationalError:
                pass  # colonne déjà présente


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─────────────────────────────────────────────────────────────
# MODÈLES
# ─────────────────────────────────────────────────────────────
class SignalIn(BaseModel):
    action: str                       # 'open' ou 'close'
    ref_id: str                       # ticket / id logique du trade maître
    symbol: str
    direction: Optional[str] = None
    volume_ref: Optional[float] = None
    price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    regime: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# AUTH HELPERS
# ─────────────────────────────────────────────────────────────
def require_master(x_master_token: Optional[str]):
    if not x_master_token or not secrets.compare_digest(x_master_token, MASTER_TOKEN):
        raise HTTPException(status_code=401, detail="Jeton maître invalide")


def admin_ok(token: Optional[str], entete: Optional[str] = None) -> bool:
    """Le jeton admin peut venir de l'en-tête X-Admin-Token (à privilégier) ou
    du paramètre d'URL ?token= (conservé pour compatibilité).

    [31/07] L'en-tête a été ajouté parce qu'un jeton dans l'URL se retrouve
    dans l'historique du navigateur, dans les favoris, dans le champ Referer
    et dans les journaux d'accès du serveur. Ce n'est pas un endroit pour un
    secret qui donne les pleins pouvoirs sur les clés clients.
    """
    fourni = entete or token
    return bool(fourni) and secrets.compare_digest(fourni, ADMIN_TOKEN)


def require_admin(token: Optional[str], entete: Optional[str] = None):
    if not admin_ok(token, entete):
        raise HTTPException(status_code=401, detail="Jeton admin invalide")


def get_client(api_key: Optional[str]) -> sqlite3.Row:
    if not api_key:
        raise HTTPException(status_code=401, detail="Clé API manquante")
    with db() as conn:
        row = conn.execute("SELECT * FROM clients WHERE api_key = ?", (api_key,)).fetchone()
        if row is None:
            raise HTTPException(status_code=401, detail="Clé API inconnue")
        conn.execute("UPDATE clients SET last_seen = ? WHERE api_key = ?", (now_iso(), api_key))
    return row


# ─────────────────────────────────────────────────────────────
# API — BOT MAÎTRE (publie les signaux)
# ─────────────────────────────────────────────────────────────
@app.post("/api/signal")
def publish_signal(sig: SignalIn, x_master_token: Optional[str] = Header(None)):
    require_master(x_master_token)
    if sig.action not in ("open", "close"):
        raise HTTPException(status_code=400, detail="action doit être 'open' ou 'close'")
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO signals
               (action, ref_id, symbol, direction, volume_ref, price, sl, tp, regime, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (sig.action, sig.ref_id, sig.symbol, sig.direction, sig.volume_ref,
             sig.price, sig.sl, sig.tp, sig.regime, now_iso()),
        )
        signal_id = cur.lastrowid
    return {"ok": True, "signal_id": signal_id}


# ─────────────────────────────────────────────────────────────
# API — FOLLOWERS (récupèrent les signaux SI clé active)
# ─────────────────────────────────────────────────────────────
@app.get("/api/status")
def status(x_api_key: Optional[str] = Header(None)):
    c = get_client(x_api_key)
    with db() as conn:
        latest = conn.execute("SELECT COALESCE(MAX(id),0) AS m FROM signals").fetchone()["m"]
    return {"active": bool(c["active"]), "name": c["name"], "plan": c["plan"], "latest_signal_id": latest}


@app.get("/api/health")
def health():
    """Point de contrôle PUBLIC — ne renvoie que des booléens.

    [30/07] Ajouté parce qu'on tournait en rond : impossible de savoir si les
    variables d'environnement étaient réellement arrivées jusqu'au processus.
    Sur un Blueprint Render, une variable ajoutée à la main dans le tableau de
    bord mais absente de render.yaml est SUPPRIMÉE à la synchro suivante — on
    croyait avoir configuré, le serveur ne voyait rien.

    Aucune valeur n'est exposée, seulement la présence : un point de contrôle
    ne doit jamais devenir une fuite.
    """
    return {
        "ok": True,
        "notify_telegram": bool(TG_TOKEN and TG_CHAT_ID),
        "tg_token_present": bool(TG_TOKEN),
        "tg_chat_id_present": bool(TG_CHAT_ID),
    }


@app.get("/api/signals")
def get_signals(
    since: int = Query(0, ge=0, description="Renvoie les signaux d'id > since"),
    x_api_key: Optional[str] = Header(None),
):
    """Le follower poll régulièrement avec son dernier id connu (curseur).
    - Clé active   → renvoie les nouveaux signaux (idempotence garantie par `since`).
    - Clé inactive → 403 + pause demandée (le follower arrête d'ouvrir).
    Sur un follower neuf : appeler d'abord /api/status pour récupérer
    `latest_signal_id` et partir de là (évite de rejouer tout l'historique).
    """
    c = get_client(x_api_key)
    if not c["active"]:
        raise HTTPException(status_code=403, detail="Abonnement inactif — pause des nouvelles entrées")
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM signals WHERE id > ? ORDER BY id ASC LIMIT 200", (since,)
        ).fetchall()
    return {"active": True, "signals": [dict(r) for r in rows]}


# ─────────────────────────────────────────────────────────────
# API — ADMIN (gestion des clés = simulation d'abonnement)
# ─────────────────────────────────────────────────────────────
@app.get("/api/admin/clients")
def admin_list(token: Optional[str] = Query(None),
               x_admin_token: Optional[str] = Header(None)):
    require_admin(token, x_admin_token)
    with db() as conn:
        rows = conn.execute("SELECT * FROM clients ORDER BY created_at DESC").fetchall()
    return {"clients": [dict(r) for r in rows]}


@app.post("/api/admin/clients")
def admin_create(name: str = Query(...), plan: str = Query("beta"),
                 token: Optional[str] = Query(None),
                 x_admin_token: Optional[str] = Header(None)):
    require_admin(token, x_admin_token)
    key = "as_" + secrets.token_urlsafe(18)
    with db() as conn:
        conn.execute(
            "INSERT INTO clients (api_key, name, plan, active, created_at) VALUES (?,?,?,1,?)",
            (key, name.strip(), plan.strip(), now_iso()),
        )
    return {"ok": True, "api_key": key, "name": name, "plan": plan, "active": True}


@app.post("/api/admin/clients/{api_key}/toggle")
def admin_toggle(api_key: str, token: Optional[str] = Query(None),
                 x_admin_token: Optional[str] = Header(None)):
    require_admin(token, x_admin_token)
    with db() as conn:
        row = conn.execute("SELECT active FROM clients WHERE api_key = ?", (api_key,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Clé inconnue")
        new_state = 0 if row["active"] else 1
        conn.execute("UPDATE clients SET active = ? WHERE api_key = ?", (new_state, api_key))
    return {"ok": True, "api_key": api_key, "active": bool(new_state)}


@app.post("/api/admin/clients/{api_key}/delete")
def admin_delete(api_key: str, token: Optional[str] = Query(None),
                 x_admin_token: Optional[str] = Header(None)):
    require_admin(token, x_admin_token)
    with db() as conn:
        conn.execute("DELETE FROM clients WHERE api_key = ?", (api_key,))
    return {"ok": True, "deleted": api_key}


# ─────────────────────────────────────────────────────────────
# PAGE ADMIN (HTML minimaliste, thème AlphaScalp)
# ─────────────────────────────────────────────────────────────
ADMIN_HTML = """<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AlphaScalp — Admin</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;background:#080b10;color:#f0f4ff;padding:32px;max-width:1000px;margin:0 auto}
h1{font-size:22px;font-weight:700;letter-spacing:-.02em;display:flex;align-items:center;gap:10px;margin-bottom:4px}
.dot{width:9px;height:9px;border-radius:50%;background:#3b82f6;box-shadow:0 0 10px #3b82f6}
.sub{color:#6b7a99;font-size:13px;margin-bottom:28px}
.bar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:24px}
input,button,select{font-family:inherit;font-size:14px;border-radius:8px;border:1px solid rgba(255,255,255,.1);background:#0e1420;color:#f0f4ff;padding:10px 14px}
input:focus,select:focus{outline:none;border-color:#3b82f6}
button{cursor:pointer;background:#3b82f6;color:#fff;border:none;font-weight:500;transition:opacity .15s}
button:hover{opacity:.88}
button.ghost{background:transparent;border:1px solid rgba(255,255,255,.12);color:#f0f4ff}
button.danger{background:transparent;border:1px solid rgba(239,68,68,.4);color:#f0a4a4}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:#6b7a99;text-transform:uppercase;letter-spacing:.06em;font-size:11px;padding:10px 12px;border-bottom:1px solid rgba(255,255,255,.08)}
td{padding:12px;border-bottom:1px solid rgba(255,255,255,.05);vertical-align:middle}
code{font-family:ui-monospace,monospace;font-size:12px;color:#85b7eb;word-break:break-all}
.pill{display:inline-flex;align-items:center;gap:6px;font-size:12px;padding:3px 10px;border-radius:20px;font-weight:600}
.pill.on{background:rgba(34,197,94,.12);color:#5dcaa5;border:1px solid rgba(34,197,94,.25)}
.pill.off{background:rgba(239,68,68,.1);color:#f0a4a4;border:1px solid rgba(239,68,68,.25)}
.acts{display:flex;gap:8px;justify-content:flex-end}
.muted{color:#6b7a99}
.empty{color:#6b7a99;padding:40px;text-align:center}
</style></head><body>
<h1><span class="dot"></span> AlphaScalp — Admin</h1>
<div class="sub">Gestion des accès bêta. Activer / désactiver une clé simule l'état d'abonnement du follower.</div>
<div class="bar">
  <input id="name" placeholder="Nom du bêta-testeur" style="flex:1;min-width:200px">
  <select id="plan"><option value="beta">beta</option><option value="starter">starter</option><option value="pro">pro</option><option value="vip">vip</option></select>
  <button onclick="createClient()">Créer une clé</button>
</div>
<table><thead><tr><th>Nom</th><th>Clé API</th><th>Plan</th><th>État</th><th>Vu</th><th></th></tr></thead>
<tbody id="rows"><tr><td colspan="6" class="empty">Chargement…</td></tr></tbody></table>
<script>
// [31/07] Le jeton ne transite plus par l'URL mais par un en-tete.
// Dans l'URL il finissait dans l'historique du navigateur, les favoris, le
// champ Referer et les journaux d'acces du serveur -- pour un secret qui
// donne les pleins pouvoirs sur les cles clients, c'etait de trop.
// Si l'URL en contient un (ancien lien encore en circulation), on le range
// et on NETTOIE la barre d'adresse.
let token = sessionStorage.getItem('as_admin') || '';
(function(){
  const dansUrl = new URLSearchParams(location.search).get('token');
  if(dansUrl){
    token = dansUrl;
    sessionStorage.setItem('as_admin', token);
    history.replaceState(null, '', location.pathname);   // le jeton quitte la barre d'adresse
  }
})();
async function api(path, method='GET'){
  const r = await fetch(path, {method, headers:{'X-Admin-Token': token}});
  if(r.status === 401){
    sessionStorage.removeItem('as_admin');
    token = '';
    demanderJeton('Jeton refusé ou session expirée.');
    throw new Error('non authentifié');
  }
  if(!r.ok){ const e = await r.json().catch(()=>({detail:r.status})); throw new Error(e.detail||r.status); }
  return r.json();
}

// Formulaire de connexion en surcouche. Pas de rechargement de page : le
// jeton vit dans sessionStorage et ne survivrait pas à une navigation.
function demanderJeton(message){
  if(document.getElementById('voile')) {
    if(message) document.getElementById('voileErr').textContent = message;
    return;
  }
  const d = document.createElement('div');
  d.id = 'voile';
  d.style.cssText = 'position:fixed;inset:0;background:#080b10;z-index:99;'
    + 'display:flex;align-items:center;justify-content:center;padding:20px';
  d.innerHTML =
    '<div style="max-width:400px;width:100%;background:rgba(255,255,255,.03);'
    + 'border:1px solid rgba(255,255,255,.08);border-radius:18px;padding:32px 28px">'
    + '<div style="font-weight:800;font-size:23px;text-align:center;letter-spacing:-.5px">'
    + 'Alpha<span style="color:#3b82f6">Scalp</span></div>'
    + '<div style="color:#6b7a99;text-align:center;font-size:13.5px;margin:4px 0 24px">'
    + "Espace d'administration</div>"
    + '<label style="font-size:13px;color:#6b7a99;display:block;margin-bottom:6px" '
    + 'for="voileT">Jeton d\'administration</label>'
    + '<input id="voileT" type="password" autocomplete="current-password" '
    + 'placeholder="&bull;&bull;&bull;&bull;&bull;&bull;&bull;" '
    + 'style="width:100%;background:#0e1420;border:1px solid rgba(255,255,255,.1);'
    + 'border-radius:10px;padding:13px 14px;color:#f0f4ff;font-size:15px;min-height:46px">'
    + '<button id="voileB" style="width:100%;background:#3b82f6;color:#fff;border:0;'
    + 'border-radius:10px;padding:14px;font-size:15px;font-weight:600;cursor:pointer;'
    + 'margin-top:16px;min-height:46px">Entrer</button>'
    + '<div id="voileErr" style="color:#ef4444;font-size:13.5px;margin-top:14px;'
    + 'min-height:18px"></div>'
    + '<div style="color:#6b7a99;font-size:11.5px;margin-top:18px;text-align:center;'
    + "line-height:1.6\">Le jeton reste dans cet onglet, n'apparaît jamais dans "
    + "l'adresse, et est oublié à la fermeture du navigateur.</div></div>";
  document.body.appendChild(d);
  if(message) document.getElementById('voileErr').textContent = message;

  async function entrer(){
    const t = document.getElementById('voileT').value.trim();
    const e = document.getElementById('voileErr');
    if(!t){ e.textContent = 'Saisis le jeton.'; return; }
    e.textContent = 'Vérification…';
    try{
      const r = await fetch('/api/admin/clients', {headers:{'X-Admin-Token': t}});
      if(r.status === 401){ e.textContent = 'Jeton refusé.'; return; }
      if(!r.ok){ e.textContent = 'Erreur ' + r.status; return; }
      token = t;
      sessionStorage.setItem('as_admin', t);
      d.remove();
      load();
    }catch(err){ e.textContent = 'Serveur injoignable.'; }
  }
  document.getElementById('voileB').onclick = entrer;
  document.getElementById('voileT').addEventListener('keydown', ev => {
    if(ev.key === 'Enter') entrer();
  });
  document.getElementById('voileT').focus();
}
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
async function load(){
  try{
    const {clients} = await api('/api/admin/clients');
    const t = document.getElementById('rows');
    if(!clients.length){ t.innerHTML='<tr><td colspan="6" class="empty">Aucune clé. Crée la première ci-dessus.</td></tr>'; return; }
    t.innerHTML = clients.map(c=>`<tr>
      <td>${esc(c.name)}</td>
      <td><code>${esc(c.api_key)}</code></td>
      <td class="muted">${esc(c.plan)}</td>
      <td><span class="pill ${c.active?'on':'off'}">${c.active?'● actif':'○ inactif'}</span></td>
      <td class="muted">${c.last_seen?esc(c.last_seen.replace('T',' ').replace('Z','')):'jamais'}</td>
      <td><div class="acts">
        <button class="ghost" onclick="toggle('${c.api_key}')">${c.active?'Désactiver':'Activer'}</button>
        <button class="danger" onclick="del('${c.api_key}')">Suppr.</button>
      </div></td></tr>`).join('');
  }catch(e){ document.getElementById('rows').innerHTML='<tr><td colspan="6" class="empty">Erreur : '+esc(''+e.message)+'</td></tr>'; }
}
async function createClient(){
  const name = document.getElementById('name').value.trim();
  const plan = document.getElementById('plan').value;
  if(!name){ alert('Indique un nom'); return; }
  try{ await api('/api/admin/clients?name='+encodeURIComponent(name)+'&plan='+plan,'POST'); document.getElementById('name').value=''; load(); }
  catch(e){ alert('Erreur : '+e.message); }
}
async function toggle(k){ try{ await api('/api/admin/clients/'+encodeURIComponent(k)+'/toggle','POST'); load(); }catch(e){ alert(e.message); } }
async function del(k){ if(!confirm('Supprimer cette clé ?')) return; try{ await api('/api/admin/clients/'+encodeURIComponent(k)+'/delete','POST'); load(); }catch(e){ alert(e.message); } }
// Démarrage : soit on a déjà un jeton dans cet onglet, soit on le demande.
if(token) load(); else demanderJeton();
</script></body></html>"""


@app.get("/admin", response_class=HTMLResponse)
def admin_page(token: Optional[str] = Query(None),
               x_admin_token: Optional[str] = Header(None)):
    """[31/07] Renvoie un FORMULAIRE au lieu d'un 401 quand aucun jeton n'est
    fourni. Avant, /admin sans ?token= répondait « Jeton admin invalide » —
    c'est ce qui faisait échouer le lien des notifications Telegram, où l'on
    ne peut évidemment pas mettre le jeton en clair.

    La page admin elle-même vérifie ensuite le jeton via l'en-tête à son
    premier appel d'API : servir le HTML sans jeton n'expose aucune donnée,
    le gabarit est vide et toutes les routes de données restent protégées.
    """
    # On sert TOUJOURS le gabarit. Le gater ici créerait une boucle : après
    # saisie, le jeton vit dans sessionStorage et n'accompagne pas une simple
    # navigation — le serveur redemanderait donc le formulaire indéfiniment.
    # C'est la page qui se garde elle-même, et toutes les routes de DONNÉES
    # restent protégées : servir ce HTML n'expose rien.
    _ = (token, x_admin_token)
    return HTMLResponse(ADMIN_HTML)


# ─────────────────────────────────────────────────────────────
# INSCRIPTION PUBLIQUE À LA BÊTA  [28/07]
# ─────────────────────────────────────────────────────────────
# Le visiteur donne son email → on lui crée une clé bêta et on lui affiche
# ses instructions de connexion. Volontairement simple (objectif : minimum
# d'effort pour l'utilisateur). Protections de base : email valide, pas de
# doublon, clé créée INACTIVE (active=0) → c'est TOI qui l'actives depuis
# l'admin (contrôle de qui entre en bêta, anti-spam, places limitées).
import re as _re

class SignupIn(BaseModel):
    email: str
    prenom: Optional[str] = None
    nom: Optional[str] = None
    date_naissance: Optional[str] = None      # AAAA-MM-JJ (champ HTML type=date)

_EMAIL_RE = _re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
AGE_MINIMUM = 18


def _age_le(date_naissance: str) -> Optional[int]:
    """Âge révolu, ou None si la date est illisible/incohérente.

    Le calcul retranche 1 an tant que l'anniversaire n'est pas passé : sans ça
    quelqu'un né le 31/12/2008 serait majeur dès janvier 2026.
    """
    try:
        d = datetime.strptime(date_naissance.strip(), "%Y-%m-%d").date()
    except Exception:
        return None
    auj = datetime.now(timezone.utc).date()
    if d > auj or d.year < 1900:
        return None                            # date future ou aberrante
    return auj.year - d.year - ((auj.month, auj.day) < (d.month, d.day))


@app.post("/api/signup")
def public_signup(body: SignupIn):
    email = (body.email or "").strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Email invalide.")

    # [30/07] Identité + majorité. Validé CÔTÉ SERVEUR : les contrôles du
    # formulaire (required, min/max sur le champ date) ne protègent de rien,
    # n'importe qui peut appeler /api/signup directement.
    prenom = (body.prenom or "").strip()
    nom = (body.nom or "").strip()
    if len(prenom) < 2 or len(nom) < 2:
        raise HTTPException(status_code=400, detail="Prénom et nom requis.")
    if len(prenom) > 60 or len(nom) > 60:
        raise HTTPException(status_code=400, detail="Prénom ou nom trop long.")

    age = _age_le(body.date_naissance or "")
    if age is None:
        raise HTTPException(status_code=400, detail="Date de naissance invalide.")
    if age < AGE_MINIMUM:
        # 403 et non 400 : la demande est bien formée, elle est REFUSÉE.
        raise HTTPException(
            status_code=403,
            detail=f"Inscription réservée aux personnes majeures ({AGE_MINIMUM} ans et plus).")

    with db() as conn:
        existing = conn.execute("SELECT api_key, active FROM clients WHERE email = ?", (email,)).fetchone()
        if existing:
            # Déjà inscrit → on renvoie sa clé (idempotent, pas de doublon).
            return {"ok": True, "already": True, "api_key": existing["api_key"],
                    "active": bool(existing["active"])}
        key = "as_" + secrets.token_urlsafe(18)
        conn.execute(
            "INSERT INTO clients (api_key, name, email, plan, active, created_at, "
            "prenom, nom, date_naissance) VALUES (?,?,?,?,0,?,?,?,?)",
            (key, f"{prenom} {nom}".strip(), email, "beta", now_iso(),
             prenom, nom, body.date_naissance.strip()),
        )
        # Rang de l'inscrit, calculé ICI tant que la connexion est ouverte :
        # la notification part dans un thread, après la fermeture du bloc.
        rang = conn.execute(
            "SELECT COUNT(*) AS n FROM clients WHERE plan = 'beta'").fetchone()["n"]
    # [FILET 28/07] Trace dans les LOGS en plus de la base. Sur l'hébergement
    # gratuit (Render free), le système de fichiers est ÉPHÉMÈRE : la base
    # SQLite est effacée à chaque redéploiement/veille. Sans ce log, les emails
    # des béta-testeurs seraient définitivement perdus. Les logs, eux, sont
    # conservés par la plateforme → inscriptions récupérables.
    try:
        print(f"SIGNUP | {now_iso()} | {email} | {key}", flush=True)
    except Exception:
        pass
    # [30/07] Second filet, DURABLE celui-là : chaque inscription part en
    # Telegram. Les logs Render du plan gratuit sont conservés peu de temps et
    # se consultent à la main — inutilisable pour ne pas rater un inscrit. Une
    # notification Telegram est instantanée, et le fil de discussion devient
    # l'archive : même si la base SQLite disparaît au prochain réveil de
    # l'instance, aucun béta-testeur n'est perdu.
    _notify_signup(email, rang=rang, prenom=prenom, nom=nom, age=age)
    return {"ok": True, "already": False, "api_key": key, "active": False}


REJOINDRE_HTML = """<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rejoindre la bêta — AlphaScalp</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box;margin:0}
body{background:#080b10;color:#f0f4ff;font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;
 min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.box{max-width:440px;width:100%;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);
 border-radius:18px;padding:34px 30px}
.logo{font-weight:800;font-size:24px;letter-spacing:-.5px;text-align:center;margin-bottom:6px}
.logo span{color:#3b82f6}
.sub{color:#6b7a99;text-align:center;font-size:14px;margin-bottom:24px}
label{font-size:13px;color:#6b7a99;display:block;margin-bottom:6px}
input{width:100%;background:#0e1420;border:1px solid rgba(255,255,255,.1);border-radius:10px;
 padding:13px 14px;color:#f0f4ff;font-size:15px}
input:focus{outline:none;border-color:#3b82f6}
button{width:100%;background:#3b82f6;color:#fff;border:0;border-radius:10px;padding:14px;
 font-size:15px;font-weight:600;cursor:pointer;margin-top:16px}
button:disabled{opacity:.5;cursor:not-allowed}
label:not(:first-child){margin-top:14px}
/* prenom + nom cote a cote, empiles sous 380px (petits telephones) */
.duo{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:380px){.duo{grid-template-columns:1fr}}
.hint{color:#6b7a99;font-size:12px;margin-top:6px}
/* le champ date natif s'affiche en clair sur fond sombre sans ca */
input[type=date]{color-scheme:dark;min-height:46px}
.msg{margin-top:18px;font-size:14px;line-height:1.6}
.key{background:#0e1420;border:1px solid rgba(59,130,246,.4);border-radius:10px;padding:12px;
 font-family:ui-monospace,Consolas,monospace;font-size:13px;word-break:break-all;margin:10px 0}
.ok{color:#22c55e}.err{color:#ef4444}
.steps{color:#6b7a99;font-size:13.5px;margin-top:14px}
.steps li{margin:6px 0}
.note{color:#6b7a99;font-size:11.5px;margin-top:20px;text-align:center;line-height:1.6}
a{color:#3b82f6}
</style></head><body>
<div class="box">
  <div class="logo">Alpha<span>Scalp</span></div>
  <div class="sub">Bêta gratuite · compte démo · sans engagement</div>
  <div id="form">
    <div class="duo">
      <div>
        <label for="prenom">Prénom</label>
        <input id="prenom" type="text" placeholder="Marie" autocomplete="given-name" maxlength="60">
      </div>
      <div>
        <label for="nom">Nom</label>
        <input id="nom" type="text" placeholder="Durand" autocomplete="family-name" maxlength="60">
      </div>
    </div>
    <label for="email">Email</label>
    <input id="email" type="email" placeholder="toi@exemple.com" autocomplete="email" inputmode="email">
    <label for="ddn">Date de naissance</label>
    <input id="ddn" type="date" autocomplete="bday" max="2999-12-31">
    <div class="hint">Le trading est réservé aux personnes majeures.</div>
    <button id="btn" onclick="submit()">Rejoindre la bêta</button>
    <div id="msg" class="msg"></div>
  </div>
  <div class="note">
    En t'inscrivant, tu acceptes que le trading comporte un risque de perte.
    AlphaScalp ne fournit pas de conseil en investissement. Aucun résultat garanti.
    <br><br>
    <!-- [30/07] La version precedente affirmait que les donnees "ne sont
         transmises a personne". C'etait FAUX : la notification d'inscription
         envoie prenom, nom, email et age a Telegram. Une phrase rassurante et
         inexacte dans une mention legale est pire que pas de mention. -->
    Tes données servent uniquement à gérer ton accès à la bêta. Elles ne sont
    ni vendues ni utilisées pour de la publicité.
    <a href="/confidentialite">Politique de confidentialité</a>
  </div>
</div>
<script>
// Borne le champ date a [aujourd'hui - 100 ans ; aujourd'hui - 18 ans] : le
// selecteur mobile n'affiche alors QUE des dates valides, ce qui evite un
// refus apres coup. Le serveur revalide de toute facon -- ces bornes sont un
// confort, pas une securite.
(function(){
  const d=new Date(), p=n=>String(n).padStart(2,'0');
  const iso=x=>x.getFullYear()+'-'+p(x.getMonth()+1)+'-'+p(x.getDate());
  const ddn=document.getElementById('ddn');
  ddn.max=iso(new Date(d.getFullYear()-18,d.getMonth(),d.getDate()));
  ddn.min=iso(new Date(d.getFullYear()-100,d.getMonth(),d.getDate()));
})();
async function submit(){
  const email=document.getElementById('email').value.trim();
  const prenom=document.getElementById('prenom').value.trim();
  const nom=document.getElementById('nom').value.trim();
  const ddn=document.getElementById('ddn').value;
  const btn=document.getElementById('btn'), msg=document.getElementById('msg');
  if(prenom.length<2||nom.length<2){ msg.innerHTML='<span class=err>Indique ton prénom et ton nom.</span>'; return; }
  if(!/^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(email)){ msg.innerHTML='<span class=err>Email invalide.</span>'; return; }
  if(!ddn){ msg.innerHTML='<span class=err>Indique ta date de naissance.</span>'; return; }
  const n=new Date(ddn), t=new Date();
  let age=t.getFullYear()-n.getFullYear();
  if(t.getMonth()<n.getMonth()||(t.getMonth()===n.getMonth()&&t.getDate()<n.getDate())) age--;
  if(age<18){ msg.innerHTML='<span class=err>Inscription réservée aux personnes majeures.</span>'; return; }
  btn.disabled=true; btn.textContent='…';
  try{
    const r=await fetch('/api/signup',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({email,prenom,nom,date_naissance:ddn})});
    const j=await r.json();
    if(!r.ok){ throw new Error(j.detail||'Erreur'); }
    document.getElementById('form').innerHTML =
      '<div class="msg"><span class="ok">✅ '+(j.already?'Tu es déjà inscrit !':'Inscription reçue !')+'</span>'
      +'<p style="margin-top:10px;color:#6b7a99">Voici ta clé bêta (garde-la) :</p>'
      +'<div class="key">'+j.api_key+'</div>'
      +'<ol class="steps"><li>Ta clé est <b>en attente d\\'activation</b> — on t\\'ouvre l\\'accès très vite (places limitées).</li>'
      +'<li>Tu recevras alors les instructions pour relier ton compte démo à la stratégie, en 1 clic chez le broker.</li>'
      +'<li>Ensuite tout est automatique : tu suis tes résultats, tu ne touches à rien.</li></ol>';
  }catch(e){ msg.innerHTML='<span class=err>'+e.message+'</span>'; btn.disabled=false; btn.textContent='Rejoindre la bêta'; }
}
document.getElementById('email').addEventListener('keydown',e=>{if(e.key==='Enter')submit();});
</script></body></html>"""


@app.get("/rejoindre", response_class=HTMLResponse)
def rejoindre_page():
    return HTMLResponse(REJOINDRE_HTML)


# ── Servir la landing + la page de performance depuis le serveur ──────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_LANDING = os.path.join(_HERE, "landing page", "index.html")
_PERF = os.path.join(_HERE, "landing page", "performance.html")


def _serve_file(path, fallback):
    try:
        with open(path, encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except Exception:
        return HTMLResponse(fallback)


@app.get("/", response_class=HTMLResponse)
def root():
    return _serve_file(_LANDING,
        '<h1>AlphaScalp</h1><p>Landing introuvable. <a href="/rejoindre">Rejoindre la bêta</a> · '
        '<a href="/admin?token=…">Admin</a></p>')


@app.get("/performance", response_class=HTMLResponse)
def performance_page():
    return _serve_file(_PERF, "<p>Page de performance non encore générée "
                              "(lance alphascalp_showcase.py).</p>")


_GUIDE = os.path.join(_HERE, "landing page", "guide.html")


@app.get("/guide", response_class=HTMLResponse)
def guide_page():
    """Guide utilisateur : comment la copie fonctionne + création de compte."""
    return _serve_file(_GUIDE, "<p>Guide indisponible.</p>")


_CONFID = os.path.join(_HERE, "landing page", "confidentialite.html")


_MENTIONS = os.path.join(_HERE, "landing page", "mentions-legales.html")


@app.get("/mentions-legales", response_class=HTMLResponse)
def mentions_page():
    """Mentions légales (LCEN art. 6 III). En tant que personne physique
    éditant à titre NON professionnel, l'adresse postale n'a pas à être
    publiée dès lors que l'identité est connue de l'hébergeur — ce qui est le
    cas via le compte Render. À revoir au passage en commercial."""
    return _serve_file(_MENTIONS, "<p>Page indisponible.</p>")


@app.get("/confidentialite", response_class=HTMLResponse)
def confidentialite_page():
    """Politique de confidentialité. [30/07] Ajoutée parce que le formulaire
    collecte désormais nom, prénom et date de naissance — des données
    personnelles au sens du RGPD, ce que l'email seul était déjà d'ailleurs."""
    return _serve_file(_CONFID, "<p>Page indisponible.</p>")


# ─────────────────────────────────────────────────────────────
init_db()

if __name__ == "__main__":
    import sys as _sys, uvicorn
    # [FIX 28/07] stdout en UTF-8 : la console Windows (cp1252) plantait sur
    # les caractères non-ASCII des messages de démarrage (crash au boot).
    try:
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    # [DEPLOIEMENT 28/07] En LOCAL : 127.0.0.1:8000. En HÉBERGÉ (Render,
    # Railway...) : la plateforme fournit le port via $PORT et exige d'écouter
    # sur 0.0.0.0. On lit donc l'environnement — aucune config à changer selon
    # l'endroit où ça tourne.
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    local = host == "127.0.0.1"
    base = f"http://{host}:{port}" if local else f"(port {port}, accès via l'URL publique de l'hébergeur)"
    print("AlphaScalp - serveur demarre")
    print(f"  Landing     : {base}/")
    print(f"  Inscription : {base}/rejoindre")
    print(f"  Performance : {base}/performance")
    print(f"  Admin       : {base}/admin?token=" + ("***" if not local else ADMIN_TOKEN))
    uvicorn.run(app, host=host, port=port)
