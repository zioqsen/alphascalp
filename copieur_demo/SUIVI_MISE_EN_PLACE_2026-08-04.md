# Transmission à Claude — copie automatique hébergée (04/08/2026)

## Objet

Ce document transmet l'état exact du chantier « bêta-testeurs sur terminaux
MT5 hébergés ». Il ne contient volontairement aucun login, mot de passe, clé
d'API, numéro de compte ou jeton.

## Décision produit

Le parcours initial demandait à chaque testeur d'installer
`AlphaScalpCopier` sur son propre PC ou VPS. Pour la phase pilote, le parcours
retenu est désormais :

1. AlphaScalp crée et héberge un terminal MT5 portable dédié par testeur.
2. Le terminal utilise exclusivement un compte de démonstration.
3. AlphaScalp installe et supervise le copieur sur sa machine.
4. Le testeur n'installe aucun EA et n'a aucun PC/VPS à laisser allumé.
5. Le testeur suit le compte depuis MT5 mobile avec un accès de consultation,
   sans capacité à passer des ordres.
6. AlphaScalp ne demande jamais les identifiants d'un compte existant du
   testeur : le compte de démonstration est créé pour la bêta.

Motif : le service public MQL5 Signals interdit aux fournisseurs de publier
depuis un compte démo. Le projet conserve donc son copieur privé. Le VPS
officiel MT5 est payant après son essai ; pour deux premiers bêta-testeurs, les
terminaux sont hébergés sur le PC du projet.

## Périmètre de sécurité

- Comptes **démo uniquement**.
- `AutoriserCompteReel=false` doit rester obligatoire.
- Aucun secret ne doit être demandé ou copié dans un ticket, Telegram, email,
  dépôt Git ou document de suivi.
- Les données locales des terminaux sont sous `runtime/`, ignoré par Git.
- Le testeur reçoit de préférence un accès investisseur/lecture seule.
- La disponibilité est celle d'une bêta hébergée sur un PC, pas celle d'un VPS
  commercial avec SLA.

## Projet isolé et outils

Projet de préparation :

```text
C:\bot\copieur_demo
```

Il contient :

- `client/AlphaScalpCopier.mq5` — source EA v1.12 ;
- `client/AlphaScalpCopier.ex5` — binaire distribué ;
- `outils/preflight_beta.*` — précontrôle sans ordre ;
- `outils/bac_a_sable_copieur.py` — serveur local isolé ;
- `outils/lancer_bac_a_sable.cmd` — lanceur du bac à sable ;
- `GUIDE_MT5_PORTABLE.md` et `TEST_BETA_DEMO.md`.

Le bac à sable écoute uniquement sur `127.0.0.1:8765`, utilise la clé factice
`as_local_demo_only` et ne contacte pas la production.

## Terminaux MT5 installés

Emplacement demandé par le propriétaire :

```text
C:\PROJET AlphaScalp\copieur_demo\runtime\beta_01
C:\PROJET AlphaScalp\copieur_demo\runtime\beta_02
```

Installateur utilisé : installateur IC Markets EU déjà présent sur le poste,
lancé en mode officiel `/auto /path:"..."`.

Vérifié :

- les deux `terminal64.exe` existent et ont la même taille ;
- le source et le binaire du copieur sont copiés dans chaque
  `MQL5\Experts` ;
- le SHA-256 du binaire copié correspond à celui du projet isolé ;
- les lanceurs imposent `/portable` ;
- aucun dossier de données des trois MT5 personnels n'a été recopié ;
- `copieur_demo/runtime/` est ignoré par Git.

Lanceurs :

```text
C:\PROJET AlphaScalp\copieur_demo\LANCER_BETA_01.cmd
C:\PROJET AlphaScalp\copieur_demo\LANCER_BETA_02.cmd
```

## État de `beta_01`

Déclaré par le propriétaire et confirmé par le nombre de processus : terminal
lancé, compte et paramètres renseignés.

Constats non sensibles observés dans le profil :

- serveur du copieur : production AlphaScalp ;
- version du copieur : 1.12 ;
- une clé est présente, mais elle n'est ni reproduite ni copiée ;
- le terminal est portable et possède son propre dossier de données.

Point à décider avant ouverture à un testeur : les paramètres saisis dans
`beta_01` ne sont pas ceux du preset prudent préparé pour `beta_02`. Ne pas les
uniformiser aveuglément : confirmer le risque pilote voulu avant toute
modification.

## État de `beta_02`

Installé mais pas encore lancé au moment du dernier contrôle.

Automatisé :

- `AlphaScalpCopier.ex5` et `.mq5` installés ;
- Trading Algo global activé dans la section `[Experts]` ;
- imports DLL interdits ;
- WebRequest activé ;
- URL publique AlphaScalp reprise depuis l'autorisation de `beta_01` ;
- aucun bloc `[Common]`, login, mot de passe ou serveur de courtage copié ;
- preset `MQL5\Presets\AlphaScalpCopier_BETA02.set` créé avec :
  - `RisqueParTrade=0.1` ;
  - `LotMaximum=0.01` ;
  - `PositionsMaximum=1` ;
  - `AutoriserCompteReel=false` ;
  - `NumeroMagique=770702` ;
  - clé volontairement vide.

Reste manuel :

1. créer/connecter le compte démo directement dans MT5 ;
2. vérifier visuellement que l'URL WebRequest apparaît ;
3. attacher une seule instance du copieur ;
4. charger le preset ;
5. saisir localement la clé distincte ;
6. vérifier les messages de l'onglet Experts sans copier d'identifiant.

Guide local :
`C:\PROJET AlphaScalp\copieur_demo\CONFIGURATION_BETA_02.md`.

## Chaîne technique existante

```text
scalp_bot_v3.py
  → signal_relay.py (outbox et reprises)
  → https://alphascalp.onrender.com
  → AlphaScalpCopier.mq5
  → compte suiveur démo
```

Seul le bot scalping appelle actuellement le relais automatiquement. Ne pas
présenter les autres bots comme copiés.

Le point public `/api/health` a répondu `ok=true`. Le précontrôle local et
l'auto-test du bac à sable ont réussi sans publication extérieure et sans
ordre MT5.

## Changement du tutoriel public

Ancienne méthode, désormais fausse pour la phase pilote :

- le testeur télécharge l'EA ;
- il installe MT5 sur son PC ;
- il autorise WebRequest ;
- son PC doit rester allumé ;
- AlphaScalp n'a aucun accès au compte.

Nouvelle méthode à raconter :

- AlphaScalp prépare un compte démo et un terminal dédiés ;
- le testeur n'installe rien et n'envoie aucun identifiant existant ;
- le terminal hébergé reçoit les signaux ;
- le testeur consulte depuis MT5 mobile ;
- AlphaScalp gère techniquement ce compte démo dédié, sans argent réel ;
- la disponibilité est celle d'une bêta pilote, sans garantie 24/7.

Pages/sources à maintenir cohérentes :

- `landing page/telecharger.html` ;
- `landing page/guide.html` ;
- `landing page/index.html` ;
- `landing page/performance.html` ;
- `landing page/pourquoi.html` ;
- `landing page/confidentialite.html` ;
- `C:\bot\alphascalp_showcase.py`, source qui régénère la page performance ;
- messages d'activation, d'état, de veille et réponses d'assistance intégrés à
  `server.py`.

Le 04/08, les pages ci-dessus et les principaux messages destinés aux testeurs
ont été réécrits pour le parcours hébergé. Les routes historiques de
téléchargement et les captures d'installation restent dans le serveur pour les
besoins techniques/administratifs, mais la page publique ne propose plus ces
téléchargements.

## Travail encore nécessaire avant deux vrais testeurs

- terminer et vérifier `beta_02` dans l'interface MT5 ;
- formaliser la création des comptes démo par AlphaScalp et la remise de
  l'accès lecture seule au testeur, sans transmettre le mot de passe maître ;
- vérifier que l'accès investisseur fonctionne sur MT5 mobile ;
- mettre en place un watchdog distinct par terminal ;
- décider du démarrage automatique Windows après plusieurs tests réussis ;
- tester une ouverture et une fermeture locales sur chaque compte ;
- tester ensuite un vrai signal scalping de production, sans injection fictive
  sur le serveur partagé ;
- mesurer RAM/CPU avec cinq terminaux pendant plusieurs heures ;
- documenter l'arrêt propre et la fermeture manuelle d'une position démo si le
  terminal tombe ;
- faire relire les messages Telegram/emails après déploiement avec un compte de
  test, afin de vérifier le parcours complet sans exposer de secret.

## Vérifications effectuées après la mise à jour du tutoriel

- `telecharger.html` chargé en navigateur local : rendu contrôlé en largeur
  ordinateur puis en largeur mobile 390 × 844, sans débordement horizontal ;
- `guide.html` chargé en largeur mobile 390 × 844, sans débordement horizontal ;
- recherche des anciennes consignes « PC allumé », téléchargement du copieur,
  WebRequest et Trading Algo dans les pages publiques et les messages testeur ;
- syntaxe de `server.py` et de `C:\bot\alphascalp_showcase.py` validée avec
  `ast.parse` ;
- `git diff --check` passé dans `C:\PROJET AlphaScalp` et `C:\bot` ; seuls des
  avertissements de conversion LF/CRLF ont été émis.

Commandes reproductibles, sans lecture de secret :

```powershell
rg -n -i "PC allum|télécharge le copieur|installe le copieur|autorise WebRequest|Trading Algo" "landing page" server.py
git diff --check
```

État de livraison : les fichiers locaux sont modifiés, mais aucun commit, push
ou déploiement Render n'a été effectué pendant ce chantier.

## État Git à préserver

Avant ce chantier, `landing page/performance.html` était déjà modifié par le
générateur de performance. Ne pas écraser ni restaurer ces chiffres. Les
changements du parcours hébergé doivent être appliqués dans une zone distincte
et également dans `C:\bot\alphascalp_showcase.py`, sinon la prochaine
régénération réintroduira l'ancien texte.
