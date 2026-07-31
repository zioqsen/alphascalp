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

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
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
# [31/07] Groupe des bêta-testeurs. Facultatif : sans lui, tout part en
# privé comme avant.
# ⚠️ RÈGLE ABSOLUE : aucune donnée personnelle dans le groupe. Les
# inscriptions contiennent nom, email et âge — les y envoyer serait les
# transmettre aux autres testeurs, ce que la politique de
# confidentialité promet explicitement de ne pas faire.
TG_GROUPE_ID = os.environ.get("ALPHASCALP_TG_GROUPE_ID", "")
# Lien d'invitation au groupe (t.me/+...). Sans lui, un inscrit n'a
# aucun moyen de nous rejoindre : il obtient sa clé et se retrouve seul.
# On NE demande PAS de numéro de téléphone pour l'ajouter d'office :
# Telegram interdit à un bot d'ajouter quelqu'un à un groupe, et ce
# serait une donnée personnelle de plus pour un résultat nul.
TG_INVITATION = os.environ.get("ALPHASCALP_TG_INVITATION", "")


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


# Un seul envoi à la fois. Telegram limite à ~20 messages par minute vers une
# même conversation ; sans sérialisation, une rafale (plusieurs inscriptions
# d'affilée) part en parallèle et se fait limiter d'un bloc.
_VERROU_TG = threading.Lock()


def _notify_telegram(texte: str, vers_groupe: bool = False) -> None:
    """Envoi Telegram, non bloquant, qui RESPECTE la limitation de débit.

    [31/07] Avant, un 429 « Too Many Requests » était avalé comme n'importe
    quelle erreur et le message était PERDU — sans que personne ne le sache.
    Or Telegram renvoie dans sa réponse le délai exact à attendre
    (`retry_after`) : l'information nécessaire pour réessayer proprement était
    là, on ne la lisait pas.

    On ne réessaie que sur 429 et sur les erreurs de connexion. Sur un 429,
    Telegram a explicitement REFUSÉ de délivrer : réessayer ne peut pas
    produire de doublon. C'est ce qui rend la reprise sûre sans clé
    d'idempotence — Telegram n'en propose pas.
    """
    # Sans groupe configuré, une annonce retombe en privé plutôt que d'être
    # perdue : mieux vaut la lire au mauvais endroit que pas du tout.
    destination = (TG_GROUPE_ID or TG_CHAT_ID) if vers_groupe else TG_CHAT_ID
    if not TG_TOKEN or not destination:
        return

    def _post():
        data = urllib.parse.urlencode({
            "chat_id": destination, "text": texte, "parse_mode": "HTML",
            "disable_web_page_preview": "true"}).encode()
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        with _VERROU_TG:
            for essai in range(1, 5):
                try:
                    urllib.request.urlopen(
                        urllib.request.Request(url, data=data), timeout=15).read()
                    return
                except urllib.error.HTTPError as e:
                    if e.code == 429:
                        # Le corps contient parameters.retry_after (secondes).
                        attente = 5
                        try:
                            corps = json.loads(e.read().decode("utf-8", "replace"))
                            attente = int(corps.get("parameters", {})
                                          .get("retry_after", 5)) + 1
                        except Exception:
                            pass
                        print(f"NOTIFY_429 | limité, nouvel essai dans {attente}s "
                              f"(essai {essai}/4)", flush=True)
                        time.sleep(min(attente, 60))
                        continue
                    print(f"NOTIFY_KO | HTTP {e.code}", flush=True)
                    return                       # 400/401 : réessayer ne sert à rien
                except Exception as e:           # noqa: BLE001
                    if essai == 4:
                        print(f"NOTIFY_PERDU | {type(e).__name__}: {e}", flush=True)
                        return
                    time.sleep(2 * essai)
            print("NOTIFY_PERDU | toujours limité après 4 essais", flush=True)

    threading.Thread(target=_post, daemon=True).start()


def _notify_restauration(email: str) -> None:
    _notify_telegram(
        "\U0001F511 <b>Clé restaurée</b>\n<i>AlphaScalp</i>\n\n"
        f"\U0001F4E7 <code>{_echappe(email)}</code>\n"
        f"\U0001F553 {_heure_paris()}\n\n"
        "Cette adresse a demandé sa clé et sa ligne n'existait plus — base "
        "réinitialisée, ou adresse jamais inscrite.\n"
        "⏳ Clé recréée <b>inactive</b> : vérifie dans ton historique que tu "
        "connais bien cette personne avant d'activer.\n"
        "➡️ <a href=\"https://alphascalp.onrender.com/admin\">Ouvrir l'admin</a>")


def _alerte_base_vide() -> None:
    """[31/07] Prévient quand le serveur démarre sur une base VIDE.

    L'hébergement gratuit a un stockage éphémère : à chaque redémarrage, les
    clés ET leur statut actif/inactif disparaissent. Les copieurs des testeurs
    se mettent alors en 401 ou en pause, et personne n'est prévenu — encore
    une panne qui ne dit pas son nom. Ce message la rend visible : il faut
    réactiver les clés.
    """
    try:
        with db() as conn:
            n = conn.execute("SELECT COUNT(*) AS n FROM clients").fetchone()["n"]
    except Exception:
        return
    if n == 0:
        print("EMPTY_DB | demarrage sur une base vide", flush=True)
        _notify_telegram(
            "⚠️ <b>Base réinitialisée</b>\n<i>AlphaScalp</i>\n\n"
            f"\U0001F553 {_heure_paris()}\n\n"
            "Le serveur a redémarré sur une base <b>vide</b> : toutes les clés "
            "et leurs activations ont disparu (stockage éphémère de l'offre "
            "gratuite).\n\n"
            "Conséquence : les copieurs des testeurs reçoivent une erreur et "
            "s'arrêtent d'ouvrir. Ils se réveilleront seuls dès réactivation.\n"
            "Les testeurs peuvent retrouver leur clé eux-mêmes avec leur "
            "email — elle est identique à celle d'avant.")
        # Annonce dans le groupe : les testeurs voient leur copieur se mettre
        # en pause et méritent d'en connaître la raison sans avoir à demander.
        # Aucune donnée personnelle ici, uniquement l'information de service.
        _notify_telegram(
            "🔧 <b>Interruption technique</b>\n\n"
            "L'hébergement a redémarré et remis les accès à zéro. Vos copieurs "
            "vont se mettre en pause tout seuls — c'est le comportement prévu, "
            "rien n'est cassé de votre côté.\n\n"
            "Je réactive les accès dans la foulée, ils repartiront seuls : "
            "<b>rien à relancer</b>.\n\n"
            "Clé perdue au passage ? Vous la retrouvez avec votre email et "
            "votre date de naissance sur "
            "https://alphascalp.onrender.com/rejoindre",
            vers_groupe=True)


app = FastAPI(title="AlphaScalp Server", version="0.1.0")


# ─────────────────────────────────────────────────────────────
# SÉCURITÉ  [31/07]
# ─────────────────────────────────────────────────────────────
# Limitation de débit MAISON, volontairement simple : en mémoire, sans
# dépendance. Elle se remet à zéro au redémarrage — acceptable ici, l'objectif
# n'est pas d'arrêter une attaque distribuée mais d'empêcher qu'on essaie des
# milliers de jetons admin ou qu'on énumère des adresses depuis une machine.
# À l'échelle commerciale, ça se remplace par un vrai limiteur en frontal.
_COMPTEURS: dict = {}
_VERROU_DEBIT = threading.Lock()

# (fenêtre en secondes, nombre d'appels autorisés) par chemin surveillé
_LIMITES = {
    "/api/admin": (300, 20),        # jeton admin : forçage brutal
    "/api/retrouver": (300, 10),    # énumération d'adresses
    "/api/signup": (3600, 15),      # création en masse
    "/telecharger/": (3600, 40),
}


def _ip_de(request: Request) -> str:
    """IP réelle derrière le frontal de l'hébergeur.

    X-Forwarded-For est fourni par le proxy de Render ; on prend la PREMIÈRE
    entrée, seule non falsifiable par le client (les suivantes sont ajoutées
    en amont et peuvent être forgées).
    """
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "?"


def _debit_depasse(cle: str, fenetre: int, maximum: int) -> bool:
    maintenant = datetime.now(timezone.utc).timestamp()
    with _VERROU_DEBIT:
        appels = [t for t in _COMPTEURS.get(cle, []) if maintenant - t < fenetre]
        if len(appels) >= maximum:
            _COMPTEURS[cle] = appels
            return True
        appels.append(maintenant)
        _COMPTEURS[cle] = appels
        # purge opportuniste : sans elle, le dictionnaire grossirait sans fin
        if len(_COMPTEURS) > 5000:
            for k in [k for k, v in _COMPTEURS.items()
                      if not v or maintenant - v[-1] > 3600]:
                _COMPTEURS.pop(k, None)
    return False


@app.middleware("http")
async def garde_securite(request: Request, call_next):
    chemin = request.url.path
    for prefixe, (fenetre, maximum) in _LIMITES.items():
        if chemin.startswith(prefixe):
            if _debit_depasse(f"{_ip_de(request)}|{prefixe}", fenetre, maximum):
                print(f"RATE_LIMIT | {_ip_de(request)} | {chemin}", flush=True)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Trop de requêtes. Réessaie dans quelques minutes."})
            break

    reponse = await call_next(request)

    # En-têtes de sécurité. Aucun n'était présent.
    reponse.headers["X-Content-Type-Options"] = "nosniff"      # pas de devinette de type
    reponse.headers["X-Frame-Options"] = "DENY"                # pas d'iframe : anti-clickjacking
    reponse.headers["Referrer-Policy"] = "no-referrer"         # l'URL ne fuit pas vers l'extérieur
    reponse.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # HSTS : impose HTTPS pour les visites suivantes. Sans danger, l'hébergeur
    # ne sert qu'en HTTPS.
    reponse.headers["Strict-Transport-Security"] = "max-age=31536000"
    # CSP : les pages sont autonomes (styles et scripts en ligne, aucune
    # ressource tierce). On interdit donc tout ce qui vient d'ailleurs, ce qui
    # neutralise l'injection d'un script externe.
    if reponse.headers.get("content-type", "").startswith("text/html"):
        reponse.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'none'; "
            "object-src 'none'")
    return reponse


# ─────────────────────────────────────────────────────────────
# BASE DE DONNÉES
# ─────────────────────────────────────────────────────────────
@contextmanager
def db():
    # [31/07] Le stockage est ÉPHÉMÈRE : le fichier peut disparaître pendant
    # que le processus tourne, sans redémarrage. Sans ce contrôle, SQLite
    # recrée alors un fichier VIDE, sans les tables — et chaque requête échoue
    # sur « no such table » jusqu'au prochain redéploiement. Le serveur répond,
    # le site s'affiche, mais plus rien ne fonctionne. Encore une panne
    # silencieuse. On vérifie donc l'existence du fichier à chaque connexion :
    # un appel système négligeable pour ce trafic.
    manquant = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if manquant:
            print("EMPTY_DB | fichier de base disparu — recréation des tables",
                  flush=True)
            _creer_tables(conn)
            conn.commit()
        yield conn
        conn.commit()
    finally:
        conn.close()


def _creer_tables(conn):
    """Schéma + migrations. Extrait de init_db pour être rejouable :
    db() s'en sert quand le fichier a disparu en cours de route."""

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


def init_db():
    with db() as conn:
        _creer_tables(conn)

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


def cle_pour(email: str, date_naissance: str) -> str:
    """Clé DÉRIVÉE de l'email, et non tirée au hasard.

    [31/07] Motif : la base est éphémère. Avec des clés aléatoires, un
    redémarrage de l'hébergeur les faisait toutes disparaître — et comme la
    clé ne figure plus dans la notification Telegram (retirée à raison, une
    clé n'a rien à faire dans un fil de discussion), PERSONNE ne pouvait la
    restituer, ni le testeur ni nous.

    En la dérivant de l'email, la même adresse redonne toujours la même clé :
    le testeur la retrouve seul, et le fil Telegram — qui contient les emails
    — devient une sauvegarde complète.

    ⚠️ LA DATE DE NAISSANCE FAIT PARTIE DE LA GRAINE, et ce n'est pas un
    détail. Avec l'email seul, quiconque connaît l'adresse d'un testeur
    pourrait redemander sa clé et récupérer son flux de signaux — la
    récupération deviendrait une porte d'entrée. Il faut donc les DEUX
    éléments, dont un que seul l'intéressé connaît.

    Le secret est le jeton maître, qui vit dans les variables d'environnement
    et survit donc aux redémarrages.
    ⚠️ Le régénérer invaliderait toutes les clés existantes.
    """
    graine = f"{email.strip().lower()}|{(date_naissance or '').strip()}"
    empreinte = hmac.new(MASTER_TOKEN.encode("utf-8"),
                         graine.encode("utf-8"),
                         hashlib.sha256).digest()
    return "as_" + base64.urlsafe_b64encode(empreinte).decode("ascii")[:24]


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
        # Le lien d'invitation n'est pas un secret : c'est justement ce qu'on
        # distribue. Les pages le lisent ici plutôt que de l'écrire en dur.
        "invitation": TG_INVITATION,
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
        # [31/07] `latest` accompagne CHAQUE réponse pour que le follower
        # puisse détecter une remise à zéro du serveur.
        #
        # Le problème : la base est éphémère. Au redémarrage de l'hébergeur la
        # table repart vide et les identifiants recommencent à 1. Un follower
        # qui avait mémorisé « j'en suis au 42 » demande alors les signaux
        # > 42 et n'en recevra PLUS JAMAIS — sans erreur, sans 401, juste du
        # silence. La copie s'arrête définitivement sans que personne ne le
        # sache. Avec `latest`, le client voit que le serveur est reparti en
        # arrière et se recale tout seul.
        dernier = conn.execute(
            "SELECT COALESCE(MAX(id), 0) AS m FROM signals").fetchone()["m"]
    return {"active": True, "latest": dernier, "signals": [dict(r) for r in rows]}


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
<div style="margin:10px 0 16px">
  <button class="ghost" onclick="chercherGroupes()">Trouver le groupe Telegram</button>
  <button class="ghost" onclick="posterAccueil()">Poster le message d'accueil</button>
  <button class="ghost" onclick="amenager()">Aménager le groupe</button>
  <button class="ghost" onclick="lienInvitation()">Créer le lien d'invitation</button>
  <div id="zoneGroupes" class="muted" style="margin-top:8px;font-size:13px"></div>
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
  // ⚠️ AUCUN BACKSLASH ICI, ET AUCUN TRIPLE GUILLEMET.
  // Ce JavaScript vit dans une chaîne Python à triple guillemet NON BRUTE.
  // Conséquence : Python interprète les échappements AVANT que le navigateur
  // ne voie le code. Une apostrophe échappée écrite ici arrive au navigateur
  // en apostrophe nue, ce qui ferme la chaîne JS et casse TOUT le script —
  // la page reste alors bloquée sur « Chargement… », sans le moindre message
  // côté serveur. C'est exactement ce qui s'est produit le 31/07.
  // Les apostrophes passent donc en entités HTML (&#39;) et aucun fragment
  // ne mélange les deux types de guillemets.
  d.innerHTML =
    '<div style="max-width:400px;width:100%;background:rgba(255,255,255,.03);'
    + 'border:1px solid rgba(255,255,255,.08);border-radius:18px;padding:32px 28px">'
    + '<div style="font-weight:800;font-size:23px;text-align:center;letter-spacing:-.5px">'
    + 'Alpha<span style="color:#3b82f6">Scalp</span></div>'
    + '<div style="color:#6b7a99;text-align:center;font-size:13.5px;margin:4px 0 24px">'
    + 'Espace d&#39;administration</div>'
    + '<label style="font-size:13px;color:#6b7a99;display:block;margin-bottom:6px" '
    + 'for="voileT">Jeton d&#39;administration</label>'
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
    + 'line-height:1.6">Le jeton reste dans cet onglet, n&#39;appara&icirc;t '
    + 'jamais dans l&#39;adresse, et est oubli&eacute; &agrave; la fermeture '
    + 'du navigateur.</div></div>';
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
// [31/07] Recherche du groupe Telegram depuis l'admin : le serveur detient
// deja le jeton du bot, inutile de le faire transiter vers un terminal.
async function lienInvitation(){
  const z = document.getElementById('zoneGroupes');
  z.innerHTML = 'Creation…';
  try{
    const j = await api('/api/admin/invitation', 'POST');
    z.innerHTML = '<div>Lien cree :</div><div><code>' + esc(j.lien) + '</code></div>'
      + '<div class="muted" style="margin-top:8px;font-size:12px">'
      + 'A coller dans Render sous <code>ALPHASCALP_TG_INVITATION</code></div>';
  }catch(e){ z.innerHTML = '<span style="color:#ef4444">' + esc(e.message) + '</span>'; }
}
async function amenager(){
  const z = document.getElementById('zoneGroupes');
  if(!confirm('Creer les sujets, poser la description et epingler l accueil ?')) return;
  z.innerHTML = 'Amenagement…';
  try{
    const j = await api('/api/admin/amenager', 'POST');
    let h = '<div>description : ' + esc(String(j.description)) + '</div>';
    (j.sujets || []).forEach(s => {
      h += '<div>' + esc(s.nom) + ' : ' + esc(s.etat) + '</div>'; });
    h += '<div>accueil : ' + esc(String(j.accueil))
       + (j.epingle ? ' (epingle)' : ' (non epingle)') + '</div>';
    z.innerHTML = h;
  }catch(e){ z.innerHTML = '<span style="color:#ef4444">' + esc(e.message) + '</span>'; }
}
async function posterAccueil(){
  const z = document.getElementById('zoneGroupes');
  if(!confirm('Poster le message d\'accueil dans le groupe et l\'epingler ?')) return;
  z.innerHTML = 'Envoi…';
  try{
    const j = await api('/api/admin/accueil', 'POST');
    z.innerHTML = '<span style="color:#0ca30c">Message poste'
      + (j.epingle ? ' et epingle' : ' (epinglage refuse : le bot est-il admin ?)')
      + '.</span>';
  }catch(e){ z.innerHTML = '<span style="color:#ef4444">' + esc(e.message) + '</span>'; }
}
async function chercherGroupes(){
  const z = document.getElementById('zoneGroupes');
  z.innerHTML = 'Recherche…';
  try{
    const j = await api('/api/admin/groupes');
    const noms = Object.keys(j.groupes || {});
    if(!noms.length){
      z.innerHTML = '<span style="color:#fab219">Aucun groupe trouve.</span> '
        + esc(j.aide || ''); return;
    }
    z.innerHTML = noms.map(id =>
      '<div style="margin:6px 0">' + esc(j.groupes[id])
      + ' &rarr; <code>' + esc(id) + '</code></div>').join('')
      + '<div class="muted" style="margin-top:8px;font-size:12px">'
      + 'A coller dans Render : <code>ALPHASCALP_TG_GROUPE_ID</code></div>';
  }catch(e){ z.innerHTML = '<span style="color:#ef4444">' + esc(e.message) + '</span>'; }
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

_EMAIL_RE = _re.compile(r"^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$")
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
        key = cle_pour(email, body.date_naissance)   # dérivée, donc retrouvable
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
        # [31/07] La CLÉ n'est plus journalisée. C'était un filet quand elle
        # était aléatoire et introuvable autrement ; depuis qu'elle se dérive
        # de l'email + la date de naissance, la consigner ne sert plus à rien
        # et l'expose dans les journaux de l'hébergeur.
        print(f"SIGNUP | {now_iso()} | {email}", flush=True)
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
    <div class="hint" style="margin-top:16px;text-align:center">
      Déjà inscrit et clé perdue ?
      <a href="#" onclick="retrouver();return false">La retrouver avec mon email</a>
    </div>
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
// [31/07] Recuperation en libre-service. La cle etant derivee de l'email,
// la retrouver est un calcul : plus besoin de passer par Flo, et ca marche
// meme apres une reinitialisation de la base.
// Le lien du groupe est LU depuis /api/health plutot qu'ecrit en dur : s'il
// change (revocation, nouveau groupe), les pages suivent sans redeploiement.
async function afficherGroupe(){
  try{
    const j = await (await fetch('/api/health')).json();
    const z = document.getElementById('zoneGroupe');
    if(!j.invitation || !z) return;
    z.innerHTML = '<a href="' + j.invitation + '" target="_blank" '
      + 'style="display:block;background:#3b82f6;color:#fff;text-decoration:none;'
      + 'border-radius:10px;padding:13px;text-align:center;font-weight:600;'
      + 'margin:14px 0;min-height:46px">Rejoindre le groupe Telegram</a>'
      + '<p style="color:#6b7a99;font-size:12.5px;margin:0">'
      + 'C&#39;est la qu&#39;on annonce les activations et qu&#39;on repond aux '
      + 'questions.</p>';
  }catch(e){}
}
async function retrouver(){
  const email = (document.getElementById('email').value || '').trim();
  const msg = document.getElementById('msg');
  const ddn = document.getElementById('ddn').value;
  if(!/^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(email)){
    msg.innerHTML = '<span class=err>Saisis d'abord ton email ci-dessus.</span>'; return; }
  if(!ddn){
    msg.innerHTML = '<span class=err>Saisis aussi ta date de naissance — '
      + 'la meme qu&#39;a l&#39;inscription. Sans elle, n&#39;importe qui '
      + 'connaissant ton email pourrait recuperer ta cle.</span>'; return; }
  msg.textContent = 'Recherche…';
  try{
    const r = await fetch('/api/retrouver', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({email, date_naissance: ddn})});
    const j = await r.json();
    if(!r.ok) throw new Error(j.detail || 'Erreur');
    msg.innerHTML = '<span class="ok">Voici ta clé :</span>'
      + '<div class="key">' + j.api_key + '</div>'
      + '<p style="color:#6b7a99;font-size:13px">'
      + (j.active ? 'Elle est <b>active</b>.'
                  : 'Elle est <b>en attente d'activation</b>.')
      + ' Note-la — mais tu peux toujours la retrouver ici avec ton email.</p>';
  }catch(e){ msg.innerHTML = '<span class=err>' + e.message + '</span>'; }
}
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
      +'<div id="zoneGroupe"></div>'
      +'<ol class="steps"><li>Ta clé est <b>en attente d\\'activation</b> — on t\\'ouvre l\\'accès très vite (places limitées).</li>'
      +'<li>Tu recevras alors les instructions pour relier ton compte démo à la stratégie, en 1 clic chez le broker.</li>'
      +'<li>Ensuite tout est automatique : tu suis tes résultats, tu ne touches à rien.</li></ol>';
      afficherGroupe();
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


# ─────────────────────────────────────────────────────────────
# TÉLÉCHARGEMENT DU CLIENT DE COPIE  [31/07]
# ─────────────────────────────────────────────────────────────
# Un bêta-testeur ne va pas chercher un fichier sur GitHub. On sert l'EA
# depuis le site, avec les étapes d'installation SUR LA MÊME PAGE : ouvrir un
# second document pendant qu'on manipule MetaTrader fait perdre tout le monde.
#
# Pas de protection par clé : l'EA ne fait rien sans une clé ACTIVE, et le
# code source est de toute façon public. Verrouiller le téléchargement
# ajouterait une friction sans rien protéger.
_TELECHARGER = os.path.join(_HERE, "landing page", "telecharger.html")


@app.get("/telecharger", response_class=HTMLResponse)
def telecharger_page():
    """Page d'installation du copieur : téléchargements + étapes sur la MÊME
    page. Un testeur qui manipule MetaTrader ne doit pas avoir à jongler avec
    un second document ouvert ailleurs."""
    return _serve_file(_TELECHARGER, "<p>Page indisponible.</p>")


_CLIENT_DIR = os.path.join(_HERE, "client")
_FICHIERS_CLIENT = {
    "AlphaScalpCopier.ex5": "application/octet-stream",
    "AlphaScalpCopier.mq5": "text/plain; charset=utf-8",
}


class RetrouverIn(BaseModel):
    email: str
    date_naissance: Optional[str] = None


@app.post("/api/retrouver")
def retrouver_cle(body: RetrouverIn):
    """Retrouve sa clé à partir de son email — en libre-service.

    [31/07] Avant, une clé perdue était perdue : elle ne s'affichait qu'une
    fois à l'inscription, ne figurait plus dans la notification Telegram, et
    la base qui la contenait est effacée à chaque redémarrage de l'hébergeur.
    Ni le testeur ni nous ne pouvions la restituer.

    Maintenant qu'elle est DÉRIVÉE de l'email, la retrouver est un calcul, pas
    une lecture. Si la ligne a disparu avec la base, on la recrée — INACTIVE,
    parce qu'une réactivation automatique laisserait n'importe qui réactiver
    l'accès de quelqu'un d'autre en connaissant son adresse.
    """
    email = (body.email or "").strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Email invalide.")
    # La date de naissance est EXIGÉE : sans elle, connaître l'adresse d'un
    # testeur suffirait à récupérer sa clé, donc son flux de signaux. La
    # récupération deviendrait une porte d'entrée au lieu d'un dépannage.
    if _age_le(body.date_naissance or "") is None:
        raise HTTPException(
            status_code=400,
            detail="Date de naissance requise — la même qu'à l'inscription.")
    key = cle_pour(email, body.date_naissance)
    with db() as conn:
        row = conn.execute(
            "SELECT api_key, active, date_naissance FROM clients WHERE email = ?",
            (email,)).fetchone()
        if row:
            # ⚠️ La date DOIT être vérifiée ici aussi. Sans ce contrôle, le
            # garde-fou ne servait à rien : on renvoyait la clé de la ligne
            # trouvée par email, sans regarder la date fournie. Il ne
            # protégeait que le cas — rare — où la ligne a disparu.
            attendue = (row["date_naissance"] or "").strip()
            fournie = (body.date_naissance or "").strip()
            if attendue and fournie != attendue:
                raise HTTPException(
                    status_code=403,
                    detail="Date de naissance incorrecte.")
            return {"ok": True, "api_key": row["api_key"],
                    "active": bool(row["active"]), "restauree": False}
        # Ligne absente : soit la base a été réinitialisée, soit l'adresse
        # n'a jamais été inscrite. On ne peut pas distinguer les deux, et on
        # n'a pas à le faire : dans les deux cas la clé est inactive et c'est
        # Flo qui décide, avec son historique Telegram sous les yeux.
        conn.execute(
            "INSERT INTO clients (api_key, name, email, plan, active, created_at) "
            "VALUES (?,?,?,?,0,?)",
            (key, email.split("@")[0], email, "beta", now_iso()))
    print(f"RECOVER | {now_iso()} | {email}", flush=True)
    _notify_restauration(email)
    return {"ok": True, "api_key": key, "active": False, "restauree": True}


ACCUEIL_GROUPE = """👋 <b>Bienvenue dans la bêta AlphaScalp</b>

Ici on teste un copieur de trades sur <b>comptes de démonstration</b>.
Argent fictif, aucune coordonnée bancaire, aucun euro engagé.

<b>Pour démarrer</b>
1️⃣ S'inscrire → https://alphascalp.onrender.com/rejoindre
2️⃣ J'active ta clé et je te préviens
3️⃣ Télécharger et installer → https://alphascalp.onrender.com/telecharger

<b>Deux choses à savoir</b>
• Il te faut un <b>PC allumé</b> avec MetaTrader 5, ou un VPS. MetaTrader sur téléphone n'exécute pas ce type de programme — c'est une limite de MetaQuotes, pas un choix.
• Clé perdue ? Tu la retrouves seul avec ton email et ta date de naissance, sur la page d'inscription.

<b>Si ça coince</b>
Envoie une capture de l'onglet « Journal des experts » en bas de MetaTrader : tout y est écrit en clair.

<i>Le trading comporte un risque de perte. Rien n'est garanti, et on est ici pour mesurer, pas pour gagner.</i>"""


# ─────────────────────────────────────────────────────────────
# AMÉNAGEMENT DU GROUPE  [31/07]
# ─────────────────────────────────────────────────────────────
# Ce qu'un bot NE PEUT PAS faire, quelles que soient ses permissions :
#   • créer un groupe ou un canal  → réservé aux comptes utilisateurs
#   • activer le mode Forum (Sujets) → réglage manuel du propriétaire
# Ce qu'il peut faire, et qu'on automatise ici : la description, les sujets
# d'un forum déjà activé, le message d'accueil et son épinglage.

SUJETS_GROUPE = [
    ("📢 Annonces",        "Mises à jour du service. Lecture seule."),
    ("🆘 Support",         "Un souci d'installation ou d'exécution ? C'est ici."),
    ("📊 Retours",         "Ce que vous observez : trades copiés, écarts, ressenti."),
    ("💬 Discussion",      "Tout le reste."),
]

DESCRIPTION_GROUPE = (
    "Bêta privée d'AlphaScalp — copie de trades sur comptes de DÉMONSTRATION. "
    "Argent fictif, aucune coordonnée bancaire. "
    "Inscription : alphascalp.onrender.com/rejoindre"
)


def _tg_appel(methode: str, params: dict) -> dict:
    """Appel Telegram synchrone. Remonte l'erreur au lieu de l'avaler : ici on
    veut savoir précisément ce qui a échoué, contrairement aux notifications
    où une perte est tolérable."""
    data = urllib.parse.urlencode(params).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(
                f"https://api.telegram.org/bot{TG_TOKEN}/{methode}",
                data=data), timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        corps = e.read().decode("utf-8", "replace")
        try:
            return json.loads(corps)
        except Exception:
            return {"ok": False, "description": f"HTTP {e.code}: {corps[:120]}"}
    except Exception as e:                          # noqa: BLE001
        return {"ok": False, "description": str(e)[:120]}


@app.post("/api/admin/invitation")
def admin_invitation(token: Optional[str] = Query(None),
                     x_admin_token: Optional[str] = Header(None)):
    """Crée un lien d'invitation au groupe et le renvoie.

    Le lien est créé UNE FOIS puis collé dans les variables d'environnement :
    en générer un à chaque démarrage encombrerait le groupe de liens morts.
    """
    require_admin(token, x_admin_token)
    if not TG_TOKEN or not TG_GROUPE_ID:
        raise HTTPException(status_code=400,
                            detail="Jeton Telegram ou identifiant de groupe absent.")
    r = _tg_appel("createChatInviteLink",
                  {"chat_id": TG_GROUPE_ID, "name": "Bêta AlphaScalp"})
    if not r.get("ok"):
        raise HTTPException(status_code=502,
                            detail=f"Telegram : {r.get('description', '?')}")
    return {"ok": True, "lien": r["result"]["invite_link"],
            "a_coller": "ALPHASCALP_TG_INVITATION"}


@app.post("/api/admin/amenager")
def admin_amenager(token: Optional[str] = Query(None),
                   x_admin_token: Optional[str] = Header(None)):
    """Aménage le groupe : description, sujets, accueil épinglé.

    Idempotent en pratique : relancer ne casse rien. La description est
    réécrite à l'identique, et Telegram refuse un sujet dont le nom existe
    déjà — le refus est rapporté, pas traité comme une panne.
    """
    require_admin(token, x_admin_token)
    if not TG_TOKEN or not TG_GROUPE_ID:
        raise HTTPException(status_code=400,
                            detail="Jeton Telegram ou identifiant de groupe absent.")

    rapport = {"description": None, "sujets": [], "accueil": None, "epingle": False}

    r = _tg_appel("setChatDescription",
                  {"chat_id": TG_GROUPE_ID, "description": DESCRIPTION_GROUPE})
    rapport["description"] = "ok" if r.get("ok") else r.get("description", "?")

    for nom, _ in SUJETS_GROUPE:
        r = _tg_appel("createForumTopic", {"chat_id": TG_GROUPE_ID, "name": nom})
        if r.get("ok"):
            rapport["sujets"].append({"nom": nom, "etat": "créé"})
        else:
            # Cause n°1 : le mode Forum n'est pas activé sur le groupe. C'est
            # un réglage manuel, aucune permission de bot ne le remplace.
            rapport["sujets"].append({"nom": nom,
                                      "etat": r.get("description", "?")})

    r = _tg_appel("sendMessage", {
        "chat_id": TG_GROUPE_ID, "text": ACCUEIL_GROUPE,
        "parse_mode": "HTML", "disable_web_page_preview": "true"})
    if r.get("ok"):
        mid = r["result"]["message_id"]
        rapport["accueil"] = mid
        p = _tg_appel("pinChatMessage", {"chat_id": TG_GROUPE_ID,
                                         "message_id": mid,
                                         "disable_notification": "true"})
        rapport["epingle"] = bool(p.get("ok"))
    else:
        rapport["accueil"] = r.get("description", "?")

    return rapport


@app.post("/api/admin/accueil")
def admin_accueil(token: Optional[str] = Query(None),
                  x_admin_token: Optional[str] = Header(None)):
    """Poste le message d'accueil dans le groupe et l'épingle.

    Sert aussi de TEST du routage : si ce message arrive, l'identifiant de
    groupe est bon. C'est plus sûr que de le vérifier sur une notification
    réelle, qu'on ne contrôle pas.
    """
    require_admin(token, x_admin_token)
    if not TG_TOKEN:
        raise HTTPException(status_code=400, detail="Jeton Telegram absent.")
    if not TG_GROUPE_ID:
        raise HTTPException(status_code=400,
                            detail="ALPHASCALP_TG_GROUPE_ID non configuré.")
    try:
        envoi = urllib.parse.urlencode({
            "chat_id": TG_GROUPE_ID, "text": ACCUEIL_GROUPE,
            "parse_mode": "HTML", "disable_web_page_preview": "true"}).encode()
        with urllib.request.urlopen(urllib.request.Request(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                data=envoi), timeout=20) as r:
            rep = json.loads(r.read().decode("utf-8"))
        mid = rep.get("result", {}).get("message_id")
        epingle = False
        if mid:
            try:
                urllib.request.urlopen(urllib.request.Request(
                    f"https://api.telegram.org/bot{TG_TOKEN}/pinChatMessage",
                    data=urllib.parse.urlencode({
                        "chat_id": TG_GROUPE_ID, "message_id": mid,
                        "disable_notification": "true"}).encode()), timeout=20).read()
                epingle = True
            except Exception:
                pass          # épingler est un confort, l'envoi a réussi
        return {"ok": True, "message_id": mid, "epingle": epingle}
    except urllib.error.HTTPError as e:
        corps = e.read().decode("utf-8", "replace")[:200]
        raise HTTPException(status_code=502, detail=f"Telegram {e.code} : {corps}")
    except Exception as e:                          # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Envoi impossible : {e}")


@app.get("/api/admin/groupes")
def admin_groupes(token: Optional[str] = Query(None),
                  x_admin_token: Optional[str] = Header(None)):
    """Liste les groupes Telegram où le bot est présent.

    [31/07] Le serveur détient déjà le jeton du bot : il peut interroger
    Telegram lui-même. Ça évite de faire transiter un secret depuis Render
    vers un terminal — surtout depuis un téléphone, où le copier-coller entre
    deux applications est le meilleur moyen de laisser traîner un jeton dans
    un presse-papier.

    Le jeton du bot n'est JAMAIS renvoyé, seulement les identifiants de
    groupe. Ils ne sont pas secrets : sans le jeton, ils ne servent à rien.
    """
    require_admin(token, x_admin_token)
    if not TG_TOKEN:
        raise HTTPException(status_code=400,
                            detail="Aucun jeton Telegram configuré côté serveur.")
    try:
        with urllib.request.urlopen(
                f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates?limit=50",
                timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:                          # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Telegram injoignable : {e}")

    if not data.get("ok"):
        raise HTTPException(status_code=502,
                            detail=f"Telegram : {data.get('description', '?')}")

    groupes, prive = {}, None
    for maj in data.get("result", []):
        msg = (maj.get("message") or maj.get("channel_post")
               or maj.get("my_chat_member") or {})
        chat = msg.get("chat") or {}
        if chat.get("type") in ("group", "supergroup", "channel"):
            groupes[str(chat["id"])] = chat.get("title", "(sans titre)")
        elif chat.get("type") == "private":
            prive = str(chat["id"])
    return {"groupes": groupes, "prive": prive,
            "aide": ("Aucun groupe ? Le bot doit y avoir reçu un événement : "
                     "son ajout, sa promotion, ou une commande /start@sonnom. "
                     "Telegram ne conserve ces événements que 24 h.")}


@app.get("/api/stats")
def stats(x_master_token: Optional[str] = Header(None)):
    """État de la chaîne, pour le tableau de bord local.

    [31/07] Protégé par le jeton MAÎTRE (celui du relais), pas par le jeton
    admin : le tableau de bord tourne sur le PC, où ce jeton existe déjà dans
    le .env du scalp. Pas de nouveau secret à gérer.

    Ne renvoie AUCUNE clé ni email — uniquement des compteurs. Un tableau de
    bord n'a pas besoin de données nominatives pour dire si la chaîne vit.
    """
    require_master(x_master_token)
    maintenant = datetime.now(timezone.utc)
    with db() as conn:
        clients = conn.execute(
            "SELECT COUNT(*) n, COALESCE(SUM(active),0) a FROM clients").fetchone()
        sig = conn.execute(
            "SELECT COUNT(*) n, COALESCE(MAX(id),0) dernier, MAX(created_at) quand "
            "FROM signals").fetchone()
        vus = conn.execute(
            "SELECT last_seen FROM clients WHERE last_seen IS NOT NULL").fetchall()

    def _age_min(iso):
        try:
            d = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            return (maintenant - d).total_seconds() / 60.0
        except Exception:
            return None

    ages = [a for a in (_age_min(r["last_seen"]) for r in vus) if a is not None]
    return {
        "inscrits": clients["n"],
        "cles_actives": clients["a"],
        "followers_vus_1h": sum(1 for a in ages if a < 60),
        "follower_plus_recent_min": round(min(ages), 1) if ages else None,
        "signaux_total": sig["n"],
        "dernier_signal_id": sig["dernier"],
        "dernier_signal_age_min": round(_age_min(sig["quand"]), 1)
                                   if sig["quand"] and _age_min(sig["quand"]) is not None else None,
        "notif_telegram": bool(TG_TOKEN and TG_CHAT_ID),
    }


@app.get("/api/client/verifier")
def verifier_cle(x_api_key: Optional[str] = Header(None)):
    """Vérifie qu'une clé existe, pour déverrouiller la page de
    téléchargement. Renvoie 401 si elle est inconnue.

    On n'exige PAS que la clé soit active : le copieur est conçu pour attendre
    l'activation en veille, et l'installation prend une dizaine de minutes.
    Autant laisser le testeur préparer son poste pendant ce temps plutôt que
    de lui imposer un aller-retour.
    """
    c = get_client(x_api_key)
    return {"ok": True, "nom": c["name"], "active": bool(c["active"])}


@app.get("/telecharger/{nom}")
def telecharger_client(nom: str, x_api_key: Optional[str] = Header(None)):
    """Sert un fichier du client de copie, RÉSERVÉ AUX INSCRITS.

    [31/07] La clé est exigée ici, côté serveur, et pas seulement pour cacher
    un bouton dans la page : un verrou uniquement visuel se contourne en
    ouvrant l'adresse du fichier à la main. C'est pour ça que la page
    télécharge par requête authentifiée plutôt que par simple lien.

    ⚠️ À savoir : ceci contrôle l'ACCÈS AU SERVICE, pas la confidentialité du
    fichier — le dépôt GitHub est public et le .mq5 s'y trouve. Rendre le
    fichier réellement privé demanderait de sortir `client/` du dépôt public,
    ce qui est une autre décision.

    La liste blanche `_FICHIERS_CLIENT` empêche par ailleurs un `nom`
    malveillant (`../../server.py`, `../.env`) de faire sortir n'importe quel
    fichier : on ne nettoie pas le chemin, on n'accepte QUE des noms connus.
    Une liste blanche ne se contourne pas par une astuce d'encodage.
    """
    get_client(x_api_key)                    # 401 si clé absente ou inconnue
    if nom not in _FICHIERS_CLIENT:
        raise HTTPException(status_code=404, detail="Fichier inconnu")
    chemin = os.path.join(_CLIENT_DIR, nom)
    if not os.path.isfile(chemin):
        raise HTTPException(status_code=404, detail="Fichier indisponible")
    return FileResponse(chemin, media_type=_FICHIERS_CLIENT[nom], filename=nom)


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
# Doit venir APRÈS init_db : les tables doivent exister pour être comptées.
_alerte_base_vide()

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
