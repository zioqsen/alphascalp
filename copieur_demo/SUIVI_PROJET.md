# Suivi partagé AlphaScalp — Codex / Claude

Ce fichier est la mémoire commune obligatoire du chantier. Codex et Claude
doivent le lire **en entier avant chaque intervention**, puis le mettre à jour
après toute modification. Il ne doit contenir aucun secret.

Dernière mise à jour : 05/08/2026 à 09:26 par Codex.

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

- Aucun travail déclaré.

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
- Les corrections du site et du serveur sont **fusionnées dans `main`** et
  **déployées** (`98c52e4`). La pull request `zioqsen/alphascalp#1` est donc
  close par la fusion. Vérifié sur Render : le script de `/rejoindre` se
  charge, le bouton est `type="button"` et appelle `inscrire()`, l'API refuse
  une inscription sans consentement (400, sans créer de ligne).
- `C:\bot` : la correction du générateur est reportée sur `master` (`64b52ce`)
  et le dépôt est désormais sauvegardé sur le remote GitHub privé
  `zioqsen/alphascalp-bot`.
- `*.bak` est désormais ignoré par Git. La copie compilée de l'EA 1.12 a été
  retirée du dépôt public tout en restant sur le disque.
- `landing page/performance.html` contenait des changements générés antérieurs
  qu'il faut préserver.
- Seul le bot scalping alimente actuellement automatiquement le relais.
- Le correctif local des annonces refuse désormais tout envoi sans cible
  `📢 Annonces` enregistrée. La cible est persistée avec les inscrits ; un
  administrateur peut relier le sujet existant avec `/lier_annonces` et les
  futurs sujets créés par l'aménagement sont enregistrés automatiquement.
- Ce correctif est commité et poussé sur `codex/cible-topic-annonces`
  (`a669235`), mais pas fusionné ni déployé. Le sujet existant n'est donc pas
  encore relié et l'annonce validée par Flo n'a pas été envoyée.

## Prochaines actions prioritaires

1. Créer manuellement la pull request du correctif des annonces, la relire puis
   la fusionner ; attendre le déploiement Render et vérifier `/api/health`.
2. Ouvrir temporairement `📢 Annonces`, y envoyer `/lier_annonces` avec un
   compte administrateur non anonyme, puis vérifier le booléen public
   `annonces_topic_configure` sans exposer d'identifiant.
3. Publier le texte déjà validé par Flo et ne déclarer l'envoi réussi qu'après
   une réponse HTTP 200 contenant `ok: true` et la destination `annonces`.
4. Confirmer avec le propriétaire que les comptes démo sont créés par
   AlphaScalp, puis remis au testeur en accès de consultation.
5. Finaliser `beta_02` manuellement et vérifier l'accès mobile en lecture seule.
6. Mettre en place une supervision distincte pour chaque terminal.
7. Tester progressivement la charge avec cinq terminaux, puis davantage après
   le passage de 16 à 32 Go de RAM.
8. Valider le parcours complet avec un compte de test avant tout déploiement.

## Journal partagé

### 2026-08-05 09:26 — Codex — publication du correctif Telegram

- Demande : commiter et pousser le correctif après validation explicite du
  propriétaire.
- Fichiers consultés : présent suivi, document détaillé de mise en place,
  différences Git, état de `C:\bot`, remote et authentification GitHub.
- Fichiers modifiés : présent suivi pour consigner la publication. Le commit
  métier contient également `server.py`. `landing page/performance.html` est
  resté hors index et hors commit.
- Décisions et hypothèses : conserver la branche dédiée existante et ne pas
  fusionner sans nouvelle validation ; la publication d'une branche ne
  déclenche pas le déploiement Render de production.
- Vérifications exécutées et résultats : analyse syntaxique Python valide ;
  JavaScript rendu valide avec `node --check -` ; `git diff --check` et
  `git diff --cached --check` valides ; index vérifié à exactement deux
  fichiers avant le commit ; accès Git distant vérifié puis push réussi.
- Points non vérifiés : déploiement Render, liaison réelle du sujet Telegram
  et publication de l'annonce. Aucun message réel n'a été envoyé. La création
  automatique de la pull request a été refusée par l'intégration GitHub avec
  un statut 403 ; aucune pull request n'a été prétendue créée.
- Prochaines actions : créer manuellement la pull request depuis la branche,
  la relire et la fusionner après validation, attendre Render, relier
  `📢 Annonces`, puis publier le texte validé par Flo avec contrôle strict de
  la réponse.
- Git/déploiement : commit `a669235` poussé sur
  `origin/codex/cible-topic-annonces`, suivi par `8cf7a8a`. Aucun déploiement,
  aucune fusion et aucune pull request créée.

### 2026-08-05 09:11 — Codex — ciblage fiable du sujet Telegram Annonces

- Demande : corriger l'envoi refusé par Telegram avec `TOPIC_CLOSED` lors de
  la publication depuis l'administration.
- Fichiers consultés : présent suivi, document détaillé de mise en place,
  `server.py`, états et différences Git de `C:\PROJET AlphaScalp` et `C:\bot`.
- Fichiers modifiés : `server.py` et le présent suivi. Le changement généré
  antérieur de `landing page/performance.html` a été préservé sans modification.
- Décisions et hypothèses : la cause vérifiée est l'absence de
  `message_thread_id` dans l'envoi, qui visait alors le sujet général fermé
  (« A lire »). Aucun repli vers le général n'est permis. Le sujet existant se
  lie par un message Telegram authentifié, envoyé dans le sujet par un
  administrateur vérifié avec `getChatMember`; son identifiant est stocké en
  SQLite et dans l'instantané Google Drive. L'envoi rouvre explicitement le
  bon sujet, publie dedans, puis le referme.
- Vérifications exécutées et résultats : analyse syntaxique Python valide ;
  JavaScript rendu extrait puis validé par `node --check -` ; `git diff
  --check` valide ; harnais isolé couvrant absence de cible (409), envoi
  nominal, erreur Telegram, échec de refermeture, liaison administrateur,
  refus d'un membre et message privé vide : tous valides ; aller-retour du
  nouveau format de persistance et compatibilité de l'ancien format : valides.
- Points non vérifiés : comportement avec le vrai groupe Telegram, permission
  effective du bot pour gérer les sujets, persistance Drive réelle et page
  Render après déploiement. Aucun message réel n'a été envoyé.
- Prochaines actions : commiter/pousser après autorisation, vérifier Render,
  relier le sujet existant puis publier l'annonce déjà validée par Flo.
- Git/déploiement : branche locale `codex/cible-topic-annonces`; aucun commit,
  push ou déploiement effectué.

### 2026-08-04 21:23 — Codex — création du remote privé de `C:\bot`

- Demande : créer le remote de `C:\bot`, après lecture obligatoire du suivi.
- Fichiers consultés : présent suivi, document détaillé de mise en place,
  `.gitignore`, état et historique Git de `C:\bot`.
- Fichiers modifiés : le présent suivi uniquement ; aucun fichier métier de
  `C:\bot` n'a été modifié.
- Décisions et hypothèses : dépôt GitHub privé nommé
  `zioqsen/alphascalp-bot` ; `master` reste la branche principale ; aucune pull
  request initiale car le nouveau dépôt ne possédait pas encore de branche de
  base distincte.
- Vérifications exécutées et résultats : 42 fichiers suivis ; aucun nom de
  fichier sensible suivi dans l'état actuel ou l'historique ; aucun motif fort
  de secret ou d'identifiant générique détecté dans l'état actuel ou les
  différences historiques ; `.gitignore` confirmé en liste blanche stricte ;
  `master` poussée au commit `64b52ce`.
- Points non vérifiés : protection de branche GitHub et éventuelles règles de
  validation continue ; aucun bot ni terminal MT5 n'a été redémarré.
- Prochaines actions : conserver le dépôt privé et publier les futurs
  changements par branche et pull request.
- Git/déploiement : remote `origin` ajouté vers le dépôt privé
  `https://github.com/zioqsen/alphascalp-bot` ; `master` suit désormais
  `origin/master`. Aucun déploiement applicatif.

### 2026-08-04 21:20 — Claude — fusion, nettoyage et vérification en ligne

- Demande : relire le présent suivi pour y repérer d'éventuelles erreurs, puis
  publier le correctif d'inscription.
- Fichiers consultés : `server.py` sur `main` et sur la branche, page déployée
  `/rejoindre`, historiques et branches des deux dépôts, `SUIVI_PROJET.md`.
- Fichiers modifiés : `.gitignore` (règle `*.bak`), présent suivi. Aucune
  modification de code : la branche a été fusionnée telle quelle.
- **Correction du journal du 19:55** — la cause y est attribuée à `l\'etat`,
  chaîne qui n'existe dans aucune version de `server.py`. Les chaînes réelles
  sont `Suivre l\'activation`, `Tu n\'as rien a installer` et
  `dans l\'application officielle MT5`, dans le bloc `submit()` de la page
  `/rejoindre`. Le mécanisme décrit était exact, les mots ne l'étaient pas ;
  ce fichier sert de mémoire au prochain agent, donc la nuance compte.
- Responsabilité : ces lignes n'ont pas été écrites par Claude, mais elles ont
  été **commitées et déployées** par lui dans `2ffc60c`. `server.py` était
  modifié dans l'arbre de travail par un chantier antérieur ; seuls le nombre
  de lignes et l'absence de secrets ont été contrôlés, pas le contenu non
  écrit par l'auteur du commit. Leçon : `git add <fichier>` engage tout le
  fichier, pas seulement ses propres modifications.
- Décisions : fusion en avance directe (aucun conflit possible) ; `*.bak`
  ignoré plutôt que le seul fichier supprimé, pour fermer la classe et non le
  cas ; report de la correction du générateur sur `master` dans `C:\bot`.
- Vérifications exécutées et résultats : équilibrage des délimiteurs du
  JavaScript **rendu** (pas du source) avant/après — cassé sur `2ffc60c`,
  correct sur la branche puis en ligne ; sur le site déployé, présence de
  `id="consentement"`, absence de `id="ddn"`, `function inscrire` définie,
  bouton `type="button"` ; `POST /api/signup` sans consentement refusé en 400
  sans création de ligne ; copieur 1.13 intact sur la branche (`OrderCalcMargin`,
  `#define COPIEUR_VERSION "1.13"`), `.mq5` et `.ex5` inchangés par la fusion.
- Points non vérifiés : inscription complète réelle de bout en bout (elle
  créerait une ligne dans la base publique) ; réponse manuelle du support par
  email ; rendu visuel de la case sur mobile.
- Prochaines actions : compte démo à fort levier pour mesurer la marge réelle
  et valider la plage 200–1 000 EUR ; `RisqueParTrade` à 2.5 sur les terminaux ;
  installer le copieur 1.13 sur `beta_02` et le terminal swing, restés en 1.12 ;
  décider si les adresses email doivent continuer d'être écrites en clair dans
  les journaux Render (`SIGNUP`, `RECOVER_REQUEST`) ; combler l'absence des
  quatre champs d'inscription dans le guide, et retirer du contrôle de
  cohérence la règle « adresse à autoriser », devenue caduque avec le parcours
  hébergé.
- Git/déploiement : `main` fusionnée puis complétée par `98c52e4`, poussée et
  **déployée sur Render** (41 s), vérifiée en ligne. `C:\bot` : `master` avancé
  à `64b52ce`, non poussable (aucun distant).

### 2026-08-04 21:04 — Codex — sauvegarde de tous les changements restants

- Demande : commiter et pousser tous les changements locaux restants.
- Fichiers consultés : états et différences Git de `C:\PROJET AlphaScalp` et
  `C:\bot`, page de performance générée et générateur correspondant.
- Fichiers modifiés : aucun contenu métier supplémentaire ; indexation de
  `landing page/performance.html`, de
  `client/AlphaScalpCopier.ex5.1.12.bak` et de
  `C:\bot\alphascalp_showcase.py`, puis mise à jour du présent suivi.
- Décisions et hypothèses : la demande explicite « tout » inclut la copie
  compilée `.bak` de 69 398 octets et les statistiques démo générées à 21:01.
- Vérifications exécutées et résultats : `git diff --check` valide dans les
  deux dépôts ; syntaxe Python du générateur valide ; contenus indexés relus
  avant commit.
- Points non vérifiés : déploiement Render, fusion de la pull request et
  exécution du binaire `.bak` ; aucun terminal MT5 n'a été redémarré.
- Prochaines actions : relire et fusionner la pull request ; configurer un
  remote pour `C:\bot` si son historique doit aussi être hébergé sur GitHub.
- Git/déploiement : commit AlphaScalp `6e8faa9` poussé sur
  `codex/corrige-formulaire-rejoindre` et ajouté à la pull request #1 ; commit
  local `C:\bot` `64b52ce` sur `codex/maj-generateur-inscription-beta`, non
  poussable car aucun remote n'est configuré. Aucun déploiement ni fusion.

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
