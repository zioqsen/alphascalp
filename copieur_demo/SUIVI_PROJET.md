# Suivi partagé AlphaScalp — Codex / Claude

Ce fichier est la mémoire commune obligatoire du chantier. Codex et Claude
doivent le lire **en entier avant chaque intervention**, puis le mettre à jour
après toute modification. Il ne doit contenir aucun secret.

Dernière mise à jour : 04/08/2026 à 20:54 par Codex.

## Documents de référence

- État détaillé initial :
  `C:\PROJET AlphaScalp\copieur_demo\SUIVI_MISE_EN_PLACE_2026-08-04.md`
- Projet isolé du copieur : `C:\bot\copieur_demo`
- Terminaux locaux : `C:\PROJET AlphaScalp\copieur_demo\runtime`
- Site et serveur : `C:\PROJET AlphaScalp`
- Générateur de performance : `C:\bot\alphascalp_showcase.py`

## Règles de collaboration

Avant de travailler, chaque agent doit :

1. lire ce fichier et le document détaillé de référence ;
2. lancer `git status --short` dans `C:\PROJET AlphaScalp` et `C:\bot` ;
3. examiner les différences qui touchent son périmètre ;
4. vérifier la section « Travail en cours » ;
5. déclarer son intervention dans cette section avant de modifier un fichier.

Après son intervention, chaque agent doit :

1. vérifier les fichiers modifiés et exécuter les tests adaptés ;
2. ajouter une entrée au journal sans réécrire les entrées précédentes ;
3. mettre à jour l'état courant et les prochaines actions ;
4. retirer sa déclaration de la section « Travail en cours » ;
5. préciser explicitement si rien n'a été déployé, commité ou poussé.

Ne jamais :

- écraser ou restaurer une modification dont l'origine n'est pas comprise ;
- modifier le même fichier pendant qu'un autre agent le déclare en cours ;
- lire, afficher ou consigner un login, mot de passe, clé API, jeton, numéro de
  compte ou fichier de session ;
- utiliser un compte réel ou activer `AutoriserCompteReel` ;
- redémarrer un terminal MT5, déployer, commiter ou pousser sans autorisation.

## Format obligatoire d'une entrée de journal

```text
### AAAA-MM-JJ HH:MM — Agent — objet
- Demande :
- Fichiers consultés :
- Fichiers modifiés :
- Décisions et hypothèses :
- Vérifications exécutées et résultats :
- Points non vérifiés :
- Prochaines actions :
- Git/déploiement :
```

Les commandes doivent être indiquées lorsqu'elles permettent de reproduire un
recensement ou un test. Ne jamais inclure leur sortie si elle contient un
secret.

## Travail en cours

Aucune intervention déclarée.

Si une ligne apparaît ici, ne pas toucher aux fichiers concernés sans faire
valider le chevauchement par le propriétaire du projet.

## État courant synthétique

- Parcours pilote retenu : un terminal MT5 et un compte démo dédiés sont
  hébergés par AlphaScalp ; le testeur consulte sur MT5 mobile.
- Comptes démo uniquement ; accès de consultation remis au testeur ; aucun
  identifiant de compte existant demandé.
- Données d'inscription : prénom, nom, email et confirmation de majorité. La
  date de naissance et l'âge ne sont ni demandés ni conservés.
- Une demande de récupération utilise l'email comme identifiant, mais la clé
  n'est jamais affichée sur la seule connaissance de l'adresse : l'admin
  répond manuellement à cette même adresse après vérification.
- `beta_01` est configuré et a déjà été lancé.
- `beta_02` est installé et préconfiguré, mais sa finalisation MT5 reste
  manuelle.
- Les tutoriels et principaux messages du serveur ont été adaptés localement
  au parcours hébergé.
- Les corrections du site et du serveur sont publiées sur la branche
  `codex/corrige-formulaire-rejoindre` et proposées dans la pull request
  brouillon GitHub `zioqsen/alphascalp#1`. Elles ne sont pas encore fusionnées
  ni vérifiées sur Render.
- `landing page/performance.html` contenait des changements générés antérieurs
  qu'il faut préserver.
- Seul le bot scalping alimente actuellement automatiquement le relais.

## Prochaines actions prioritaires

1. Faire relire les différences actuelles par le prochain agent sans modifier.
2. Confirmer avec le propriétaire que les comptes démo sont créés par
   AlphaScalp, puis remis au testeur en accès de consultation.
3. Finaliser `beta_02` manuellement et vérifier l'accès mobile en lecture seule.
4. Mettre en place une supervision distincte pour chaque terminal.
5. Tester progressivement la charge avec cinq terminaux, puis davantage après
   le passage de 16 à 32 Go de RAM.
6. Valider le parcours complet avec un compte de test avant tout déploiement.

## Journal partagé

### 2026-08-04 20:54 — Codex — publication du correctif d'inscription

- Demande : publier les corrections validées depuis le téléphone.
- Fichiers consultés : état Git, différences indexées et contrôles de syntaxe
  dans `C:\PROJET AlphaScalp` et `C:\bot`.
- Fichiers modifiés : le présent suivi uniquement pour cette entrée ; le
  correctif publié correspond aux six fichiers du commit `06eb28b`.
- Décisions et hypothèses : branche dédiée et pull request brouillon pour
  permettre une relecture avant fusion ; les statistiques générées localement
  dans `landing page/performance.html` et la sauvegarde `.bak` de l'EA restent
  hors commit.
- Vérifications exécutées et résultats : `git diff --cached --check` valide ;
  analyse syntaxique Python de `server.py` et de
  `C:\bot\alphascalp_showcase.py` valide ; branche distante créée.
- Points non vérifiés : fusion de la pull request, redéploiement Render et
  parcours public après déploiement.
- Prochaines actions : relire puis fusionner la pull request, attendre le
  déploiement Render et effectuer une inscription de test autorisée.
- Git/déploiement : commit `06eb28b` poussé sur
  `codex/corrige-formulaire-rejoindre` ; pull request brouillon
  `https://github.com/zioqsen/alphascalp/pull/1`. Aucun déploiement ni fusion.
  Le dépôt `C:\bot` n'a pas de remote configuré : la modification locale de son
  générateur ne peut pas être poussée depuis ce dépôt.

### 2026-08-04 20:13 — Codex — suppression de la date de naissance

- Demande : appliquer la règle de minimisation CNIL déjà décidée, conserver
  l'email pour la récupération et utiliser une case de confirmation de
  majorité à la place de la date de naissance.
- Fichiers consultés : `server.py`, pages publiques, générateur de performance,
  politique de confidentialité et documentation CNIL sur la minimisation.
- Fichiers modifiés : `server.py`, `landing page/index.html`,
  `landing page/performance.html`, `landing page/confidentialite.html`,
  `C:\bot\alphascalp_showcase.py` et le présent suivi.
- Décisions : aucune date de naissance ni aucun âge collecté ; confirmation de
  majorité obligatoire côté page et API ; l'email identifie une demande de
  récupération, mais sa simple saisie ne révèle jamais la clé et ne crée pas
  une inscription inconnue.
- Migration : les anciennes dates restaurées depuis la sauvegarde sont mises à
  `NULL`, puis une nouvelle sauvegarde sans ces valeurs est planifiée.
- Vérifications : syntaxe Python et JavaScript valides ; aperçu navigateur sans
  champ date ; case visible ; validations fonctionnelles ; récupération locale
  sans clé dans la réponse ; adresse inconnue sans création de ligne ; purge
  d'une ancienne date testée ; `git diff --check` valide.
- Points non vérifiés : parcours réel après déploiement et réponse manuelle par
  email depuis le support public.
- Prochaines actions : publier le correctif, puis tester une inscription et une
  demande de récupération avec une adresse de test autorisée.
- Git/déploiement : aucun commit, push ou déploiement effectué ; `gh` reste
  absent du poste au moment de cette intervention.

### 2026-08-04 19:55 — Codex — formulaire `/rejoindre` inactif

- Demande : le bouton « Rejoindre la bêta » ne produisait aucun résultat et la
  case de confirmation attendue était absente.
- Fichiers consultés : `server.py`, `landing page/confidentialite.html`, page
  déployée `https://alphascalp.onrender.com/rejoindre` et historique Git.
- Fichiers modifiés : `server.py` et `landing page/confidentialite.html`.
- Cause vérifiée : le commit `2ffc60c` avait ajouté `l\'etat` dans une chaîne
  JavaScript elle-même contenue dans une chaîne Python. Python consommait
  l'échappement ; le navigateur recevait une apostrophe non échappée, levait
  `SyntaxError: Unexpected identifier 'etat'`, puis `submit is not defined` au
  clic. Le formulaire ne contenait par ailleurs aucune case à cocher.
- Correction : suppression des apostrophes cassantes au profit d'entités HTML,
  renommage de la fonction en `inscrire`, bouton explicitement `type=button`,
  ajout d'une case de confirmation obligatoire et validation correspondante
  côté API. La date de naissance est conservée car la récupération sécurisée
  de la clé en dépend actuellement.
- Vérifications : problème reproduit sur la page déployée sans envoyer de
  données ; JavaScript rendu validé syntaxiquement ; aperçu local chargé ;
  case visible et cochable ; clic à vide et clic sans consentement renvoient
  les messages attendus ; aucune erreur console locale ; syntaxe Python et
  `git diff --check` valides.
- Points non vérifiés : inscription réelle complète sur Render, car les
  changements ne sont pas encore déployés et créer une inscription de test
  modifierait la base publique.
- Prochaines actions : déployer après relecture, puis effectuer un essai avec
  une adresse de test autorisée. Décider séparément si la date de naissance
  doit être supprimée, ce qui impose de remplacer le mécanisme de récupération
  de clé.
- Git/déploiement : aucun commit, push ou déploiement effectué.

### 2026-08-04 — Codex — préparation des deux terminaux et nouveau parcours

- Demande : isoler le copieur, préparer deux installations MT5 portables et
  remplacer le tutoriel public par le parcours hébergé/mobile.
- Fichiers consultés : dépôts `C:\bot` et `C:\PROJET AlphaScalp`, configuration
  non sensible des terminaux et pages publiques.
- Fichiers modifiés : projet `copieur_demo`, lanceurs `beta_01`/`beta_02`, pages
  publiques, `server.py`, `C:\bot\alphascalp_showcase.py` et documents de suivi.
- Décisions et hypothèses : comptes démo uniquement ; terminal hébergé par
  AlphaScalp ; accès mobile de consultation pour le testeur ; aucun SLA 24/7.
- Vérifications : présence et empreinte du copieur, isolation de `runtime`, test
  visuel ordinateur/mobile, syntaxe Python et `git diff --check`.
- Points non vérifiés : accès investisseur sur MT5 mobile, stabilité longue
  durée avec cinq terminaux et parcours réel complet de `beta_02`.
- Prochaines actions : voir la liste prioritaire ci-dessus.
- Git/déploiement : aucun commit, push ou déploiement effectué.
