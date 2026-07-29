# Déployer AlphaScalp en ligne (pas-à-pas)

Objectif : passer de « ça marche sur mon PC » à « une URL que j'envoie à un
béta-testeur ». On utilise **Render.com** (gratuit pour la bêta).

---

## Avant de commencer

1. Le code est sur GitHub : `github.com/zioqsen/alphascalp`. Si ce n'est pas
   encore poussé :
   ```bash
   cd "C:\PROJET AlphaScalp"
   git push -u origin main
   ```
2. Crée un compte gratuit sur **render.com** (connexion avec GitHub = plus simple).

---

## Déploiement (5 minutes)

1. Sur Render : **New +** → **Blueprint**.
2. Choisis ton dépôt **alphascalp**. Render détecte `render.yaml` et propose de
   créer le service tout seul.
3. Render génère automatiquement tes deux jetons secrets
   (`ALPHASCALP_MASTER_TOKEN` et `ALPHASCALP_ADMIN_TOKEN`) — **note-les** dans
   l'onglet *Environment* du service après création, tu en auras besoin :
   - le **MASTER** : à mettre dans le `.env` de ton bot maître
     (`RELAY_MASTER_TOKEN`) pour qu'il puisse poster ses signaux.
   - l'**ADMIN** : pour accéder à ta page d'admin.
4. Clique **Apply / Create**. Render installe, build, et démarre.
5. Au bout de ~2 min, tu obtiens une URL du type
   `https://alphascalp.onrender.com`.

C'est en ligne. Teste :
- `https://alphascalp.onrender.com/` → ta landing
- `https://alphascalp.onrender.com/rejoindre` → l'inscription
- `https://alphascalp.onrender.com/admin?token=<TON_ADMIN_TOKEN>` → ton admin

---

## Connecter ton bot maître au serveur en ligne

Dans le `.env` du scalp (`C:\scalping\.env`) :
```
RELAY_ENABLED=true
RELAY_SERVER_URL=https://alphascalp.onrender.com
RELAY_MASTER_TOKEN=<le MASTER token généré par Render>
```
Redémarre le scalp → ses ouvertures/fermetures arrivent sur le serveur en ligne,
et les followers actifs les reçoivent.

---

## Rafraîchir les chiffres de perf affichés

La landing et `/performance` affichent des chiffres **figés au dernier push**
(le serveur en ligne n'a pas accès aux données de tes bots, qui vivent sur ton
PC). Pour mettre à jour ce qui est affiché publiquement :

```bash
cd C:\bot
python alphascalp_showcase.py         # régénère index (stats) + performance.html
cd "C:\PROJET AlphaScalp"
git add "landing page/index.html" "landing page/performance.html"
git commit -m "maj chiffres perf"
git push
```
Render redéploie tout seul en ~1 min. **C'est volontairement manuel** : tu
maîtrises exactement quels chiffres sont publics et quand.

---

## Points d'attention (bêta)

- **Le plan gratuit s'endort** après 15 min sans visite : le premier accès
  suivant met ~30 s à réveiller le service. Normal pour une bêta. (Plan payant
  ~7 $/mois pour rester éveillé, plus tard.)
- **La base des inscriptions est sur un disque persistant** (`/data`) : les
  emails/clés béta survivent aux redéploiements. Ne change pas ce chemin.
- **Les jetons sont des secrets** : ne les mets jamais dans le code ni sur
  GitHub. Ils vivent uniquement dans l'onglet Environment de Render.
- **Le contrôle d'accès reste le tien** : chaque inscrit est créé INACTIF ;
  c'est toi qui l'actives depuis l'admin.

---

## Alternative : Railway

Même principe. `New Project` → `Deploy from GitHub repo` → sélectionne
alphascalp. Ajoute les variables d'environnement à la main
(`HOST=0.0.0.0`, `ALPHASCALP_MASTER_TOKEN`, `ALPHASCALP_ADMIN_TOKEN`,
`ALPHASCALP_DB=/data/alphascalp.db`) et un volume monté sur `/data`.
Railway fournit `$PORT` automatiquement, comme Render.
