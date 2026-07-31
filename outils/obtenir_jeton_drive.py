# -*- coding: utf-8 -*-
"""
=============================================================
 AlphaScalp — obtenir le jeton Google Drive (à faire UNE fois)
=============================================================
 Ce script tourne sur TON PC, pas sur le serveur. Il te demande
 d'autoriser AlphaScalp dans ton navigateur, puis il affiche les
 4 valeurs à coller dans Render.

 Il ne stocke rien, n'envoie rien ailleurs, et n'accède qu'au
 fichier qu'il crée lui-même (périmètre `drive.file`) : il ne
 peut pas lire le reste de ton Drive, même s'il le voulait.

 UTILISATION
   1. Suis d'abord GUIDE_DRIVE.md (console Google, 15 min)
   2. python obtenir_jeton_drive.py
   3. Colle les 4 valeurs affichées dans Render

 Aucune dépendance : uniquement la bibliothèque standard.
=============================================================
"""

import http.server
import json
import socket
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# `drive.file` = l'application ne voit QUE les fichiers qu'elle a créés.
# C'est aussi ce qui permet de publier l'application sans passer par la
# procédure de vérification de Google — et donc d'avoir un jeton qui
# n'expire pas au bout de 7 jours.
PERIMETRE = "https://www.googleapis.com/auth/drive.file"
NOM_FICHIER = "alphascalp_clients.json"
PORT = 8765
REDIRECTION = f"http://localhost:{PORT}"

_code = {}


class _Recepteur(http.server.BaseHTTPRequestHandler):
    """Attrape le code d'autorisation renvoyé par Google dans l'URL."""

    def do_GET(self):                                   # noqa: N802
        params = urllib.parse.parse_qs(
            urllib.parse.urlparse(self.path).query)
        _code["code"] = (params.get("code") or [None])[0]
        _code["erreur"] = (params.get("error") or [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        ok = bool(_code["code"])
        self.wfile.write(
            ("<html><body style='font:16px system-ui;background:#080b10;"
             "color:#f0f4ff;padding:60px;text-align:center'>"
             + ("<h2 style='color:#22c55e'>C'est bon.</h2>"
                "<p>Tu peux fermer cet onglet et revenir à la console.</p>"
                if ok else
                "<h2 style='color:#ef4444'>Autorisation refusée.</h2>"
                "<p>Relance le script pour réessayer.</p>")
             + "</body></html>").encode("utf-8"))

    def log_message(self, *a):                          # silence
        return


def _poste(url: str, donnees: dict) -> dict:
    corps = urllib.parse.urlencode(donnees).encode()
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, data=corps), timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise SystemExit(f"\n  ÉCHEC ({e.code}) : {detail}\n")


def main() -> int:
    print(__doc__)

    cid = input("  Client ID     : ").strip()
    secret = input("  Client secret : ").strip()
    if not cid or not secret:
        print("\n  Les deux valeurs sont obligatoires. Voir GUIDE_DRIVE.md.")
        return 1

    # Le port doit être libre, sinon Google renvoie sur une page morte et
    # l'erreur serait incompréhensible.
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", PORT)) == 0:
            print(f"\n  Le port {PORT} est déjà utilisé. Ferme le programme "
                  f"qui l'occupe et relance.")
            return 1

    serveur = http.server.HTTPServer(("127.0.0.1", PORT), _Recepteur)
    threading.Thread(target=serveur.handle_request, daemon=True).start()

    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": cid,
        "redirect_uri": REDIRECTION,
        "response_type": "code",
        "scope": PERIMETRE,
        # offline + consent : sans ces deux-là, Google ne renvoie PAS de
        # jeton de rafraîchissement, et tout le montage ne sert à rien.
        "access_type": "offline",
        "prompt": "consent",
    })

    print("\n  Ton navigateur va s'ouvrir. Choisis ton compte Google et")
    print("  accepte. Si un avertissement « application non vérifiée »")
    print("  apparaît : Paramètres avancés → Continuer. C'est TON application.")
    print(f"\n  Si rien ne s'ouvre, colle ceci dans ton navigateur :\n\n  {url}\n")
    webbrowser.open(url)

    print("  En attente de ton autorisation...", flush=True)
    for _ in range(240):                       # 4 minutes de patience
        if _code:
            break
        threading.Event().wait(1)
    serveur.server_close()

    if _code.get("erreur") or not _code.get("code"):
        print(f"\n  Autorisation non obtenue ({_code.get('erreur') or 'délai dépassé'}).")
        return 1

    print("  Autorisation reçue. Échange du jeton...", flush=True)
    jetons = _poste("https://oauth2.googleapis.com/token", {
        "code": _code["code"],
        "client_id": cid,
        "client_secret": secret,
        "redirect_uri": REDIRECTION,
        "grant_type": "authorization_code",
    })

    refresh = jetons.get("refresh_token")
    acces = jetons.get("access_token")
    if not refresh:
        print("\n  Google n'a pas renvoyé de jeton de rafraîchissement.")
        print("  Cause habituelle : tu avais déjà autorisé cette application.")
        print("  Va sur https://myaccount.google.com/permissions , retire")
        print("  l'accès d'AlphaScalp, puis relance ce script.")
        return 1

    # Création du fichier qui servira de base. On le crée ICI plutôt que côté
    # serveur : ainsi le serveur n'a jamais besoin du droit de créer quoi que
    # ce soit, seulement de lire et écrire CE fichier-là.
    print("  Création du fichier dans ton Drive...", flush=True)
    corps = json.dumps({"name": NOM_FICHIER,
                        "mimeType": "application/json"}).encode()
    req = urllib.request.Request(
        "https://www.googleapis.com/drive/v3/files", data=corps,
        headers={"Authorization": f"Bearer {acces}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            fichier = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"\n  Création refusée ({e.code}) : "
                         f"{e.read().decode('utf-8', 'replace')}\n")

    print("\n" + "=" * 66)
    print("  À COLLER DANS RENDER — Environment → Add Environment Variable")
    print("=" * 66 + "\n")
    print(f"  GOOGLE_CLIENT_ID       {cid}")
    print(f"  GOOGLE_CLIENT_SECRET   {secret}")
    print(f"  GOOGLE_REFRESH_TOKEN   {refresh}")
    print(f"  GOOGLE_FILE_ID         {fichier['id']}")
    print("\n" + "=" * 66)
    print(f"\n  Le fichier « {NOM_FICHIER} » existe maintenant dans ton Drive.")
    print("  Ne le déplace pas dans la corbeille : le serveur écrit dedans.")
    print("  Le déplacer dans un dossier ne pose aucun problème.\n")
    print("  ⚠️  Ces 4 valeurs sont des SECRETS : elles donnent accès à ce")
    print("      fichier. Ne les mets ni dans le dépôt Git, ni dans Telegram.")
    print("      Cette fenêtre est le seul endroit où elles s'affichent —")
    print("      colle-les dans Render maintenant.\n")

    # On n'écrit RIEN sur le disque : un fichier de secrets oublié dans un
    # dossier est exactement le genre de chose qui finit dans une sauvegarde,
    # puis dans un dépôt public.
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  Interrompu.")
        sys.exit(1)
