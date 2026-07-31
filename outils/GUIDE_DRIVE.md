# Mettre la base AlphaScalp sur ton Drive — ta partie

**Ce que ça règle.** Aujourd'hui la base vit sur le disque de Render, qui est
effacé à chaque redémarrage : les clés bêta disparaissent, typiquement le
week-end. Après ça, elles vivent dans un fichier de **ton** Drive et ne
s'effacent plus.

**Combien de temps.** Quinze minutes, dont dix à chercher les bons boutons.
La console Google est pénible, c'est la seule vraie difficulté.

**À faire une seule fois.** Ensuite tu n'y reviens jamais.

> Google réorganise sa console régulièrement. Si un libellé ne correspond
> plus exactement, cherche le mot-clé en gras — la logique, elle, ne change
> pas.

---

## 1. Créer un projet

Va sur **https://console.cloud.google.com/**

En haut à gauche, le sélecteur de projet → **Nouveau projet**.
Nomme-le `AlphaScalp`. Crée. Attends quelques secondes, puis **sélectionne-le**
dans le même menu — c'est l'oubli classique, tout le reste se ferait dans le
mauvais projet.

## 2. Activer l'API Drive

Menu ☰ → **API et services** → **Bibliothèque**.
Cherche **Google Drive API** → **Activer**.

## 3. Configurer l'écran de consentement

Menu ☰ → **API et services** → **Écran de consentement OAuth**.

- Type d'utilisateur : **Externe** → Créer
- Nom de l'application : `AlphaScalp`
- E-mail d'assistance : le tien
- Coordonnées du développeur : le tien
- Enregistrer et continuer

**Étape « Niveaux d'accès » — c'est celle qui compte.**
Clique **Ajouter ou supprimer des niveaux d'accès**, et coche uniquement :

```
.../auth/drive.file
```

> Ne prends **rien d'autre**. Ce périmètre-là ne donne accès qu'aux fichiers
> créés par l'application — jamais au reste de ton Drive. C'est ce qui rend
> l'opération sûre, **et** ce qui te dispense de la procédure de vérification
> de Google. Si tu coches un périmètre plus large, Google exige une
> vérification et le montage ne marchera pas.

Enregistre et continue jusqu'au bout.

## 4. Publier l'application

Toujours dans **Écran de consentement OAuth**, section **État de
publication** : clique **PUBLIER L'APPLICATION** → confirme.

> **Ne saute pas cette étape.** En mode « Test », Google fait expirer
> l'autorisation **au bout de 7 jours** : le serveur perdrait l'accès à la
> base un beau matin, sans erreur visible. Publiée, elle ne périme plus.
>
> Google ne demandera **aucune vérification** : tu n'utilises que
> `drive.file`, qui n'est pas un périmètre sensible.

## 5. Créer l'identifiant

Menu ☰ → **API et services** → **Identifiants**
→ **Créer des identifiants** → **ID client OAuth**

- Type d'application : **Application de bureau**
- Nom : `AlphaScalp local`
- Créer

Une fenêtre affiche **ID client** et **Code secret du client**.
**Laisse-la ouverte**, tu en as besoin tout de suite.

## 6. Lancer le script

Dans un terminal :

```bash
python "C:\PROJET AlphaScalp\outils\obtenir_jeton_drive.py"
```

Il te demande les deux valeurs de l'étape 5, ouvre ton navigateur, et tu
autorises.

> Un écran « Google n'a pas validé cette application » peut apparaître :
> **Paramètres avancés** → **Continuer vers AlphaScalp**. C'est ta propre
> application, tu t'autorises toi-même.

Le script affiche alors **4 valeurs**. Elles ne s'afficheront qu'une fois.

## 7. Coller dans Render

Tableau de bord Render → service `alphascalp` → **Environment**
→ **Add Environment Variable**, quatre fois :

| Nom | Valeur |
|---|---|
| `GOOGLE_CLIENT_ID` | affichée par le script |
| `GOOGLE_CLIENT_SECRET` | affichée par le script |
| `GOOGLE_REFRESH_TOKEN` | affichée par le script |
| `GOOGLE_FILE_ID` | affichée par le script |

Puis **Save Changes**. Render redéploie tout seul.

> ⚠️ Ces quatre valeurs sont des **secrets**. Ni dans le dépôt Git (il est
> public), ni dans Telegram, ni dans un fichier texte sur le Bureau.
>
> Je les ajouterai à `render.yaml` en `sync: false` — c'est-à-dire déclarées
> mais **sans leur valeur**, qui reste uniquement chez Render. C'est
> obligatoire : ce service est un Blueprint, et une variable ajoutée à la
> main mais absente de `render.yaml` est **supprimée** à la synchro suivante.
> C'est ce qui a fait disparaître deux variables le 30/07.

---

## Quand c'est fait

Préviens-moi : j'ajoute le code côté serveur (une centaine de lignes, sans
nouvelle dépendance). Tant que les variables ne sont pas là, le serveur
fonctionne exactement comme aujourd'hui — le montage Drive s'active tout
seul quand il les trouve, et reste inerte sinon.

## Si quelque chose cloche

**« Google n'a pas renvoyé de jeton de rafraîchissement »**
Tu avais déjà autorisé l'application. Va sur
https://myaccount.google.com/permissions , retire l'accès d'AlphaScalp,
relance le script.

**« Le port 8765 est déjà utilisé »**
Un autre programme l'occupe. Ferme-le, ou dis-le-moi et je change le port.

**Le navigateur ne s'ouvre pas**
Le script affiche l'adresse à coller à la main, juste avant d'attendre.

**Tu as fermé la fenêtre du script avant de copier les valeurs**
Relance-le : il refait le tour complet et crée un nouveau fichier. L'ancien
peut être supprimé de ton Drive.
