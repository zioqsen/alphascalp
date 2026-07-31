# AlphaScalp — audit détaillé du site

**Date :** 31/07/2026
**Site :** https://alphascalp.onrender.com
**Objet :** identifier les axes d'amélioration **non couverts**. Ce document
décrit ce qui existe déjà et ce qui a été mesuré, pour qu'un second regard se
concentre sur ce qui manque plutôt que de redécouvrir l'existant.

---

## 0. Contexte indispensable pour juger

Sans ça, une partie des recommandations habituelles tomberait à côté.

- **Produit :** copieur de trades. Un serveur publie les signaux d'une
  stratégie algorithmique ; un Expert Advisor MetaTrader 5 installé chez
  l'utilisateur les reproduit sur **son** compte, à **sa** taille de position.
- **Phase : bêta fermée et gratuite, exclusivement sur comptes de
  démonstration.** Aucun paiement, aucune collecte bancaire, aucune pièce
  d'identité. L'EA **refuse de démarrer** sur un compte réel par défaut.
- **Audience :** une poignée de testeurs recrutés de la main à la main.
  Le trafic organique est actuellement nul.
- **Contrainte technique :** hébergement Render **plan gratuit**. Système de
  fichiers éphémère, mise en veille après 15 min d'inactivité, réveil à froid
  mesuré entre 10 et 50 s. Une bascule de la base vers un stockage durable est
  décidée mais pas encore faite.
- **Pile :** FastAPI + SQLite. Pages HTML statiques, **zéro dépendance
  front** — pas de framework, pas de CDN, pas de police externe, aucune image.
  C'est délibéré.
- **Contraintes non négociables :** aucune promesse de gain, aucun conseil en
  investissement, jamais de demande d'identifiants de courtier.

---

## 1. Design / image de marque

### En place
- Thème sombre cohérent sur les 6 pages, palette unifiée par variables CSS
  (`--bg #080b10`, `--blue #3b82f6`, `--green #22c55e`, `--amber #fab219`,
  `--red #ef4444`), typographie système (`system-ui`) — donc zéro requête de
  police et aucun décalage de rendu.
- Composants récurrents : cartes, bandeaux d'avertissement colorés par
  gravité, étapes numérotées, tableaux.
- Logo « Alpha**Scalp** » avec le second mot en bleu, repris sur chaque page.

### Constaté
- **Aucun `<img>`, aucun `<canvas>`, 2 `<svg>` en tout sur l'ensemble du
  site.** L'identité repose entièrement sur la typographie, la couleur et les
  emoji. Sobre et rapide, mais très peu différenciant : le site ressemble à
  n'importe quel produit SaaS sombre de 2024.
- **Pas de favicon** (404 sur `/favicon.ico`), donc onglet générique.
- **Le titre H1 de l'accueil mélange deux langues** : « Trade smarter.
  Automatiquement. » Le reste du site est en français, tutoiement.
- Les emoji portent une part importante du sens (⚠️ ✅ 🔑 ⏳ 💻). Rendu
  variable selon les plateformes.
- Aucune charte écrite : pas de fichier de référence pour les couleurs, les
  espacements ou le ton.

### Questions ouvertes pour un second regard
- Quelle identité visuelle minimale apporterait de la différenciation **sans**
  introduire d'images lourdes ni de dépendance externe (contrainte forte) ?
- Le ton tutoyant, direct et sans superlatif est un choix assumé. Est-il
  cohérent avec l'audience visée, ou dessert-il la crédibilité ?

---

## 2. Crédibilité et confiance

### En place
Le positionnement est délibérément l'inverse du marketing habituel du secteur.

- Une **page de performance publique** affichant les résultats réels d'un
  compte de démonstration, **pertes comprises**, avec la date de dernière
  mise à jour.
- Mention explicite « en validation » sur chaque stratégie encore non
  concluante, et « on préfère ne rien afficher plutôt qu'un chiffre
  trompeur ».
- Avertissement de risque sur toutes les pages.
- Mentions légales et politique de confidentialité complètes.
- **Le code source de l'EA est fourni** avec le binaire : « ce programme va
  passer des ordres sur ton compte, tu as le droit de voir ce qu'il fait ».
- Avertissement anti-arnaque répété : *AlphaScalp ne demandera jamais tes
  identifiants de courtier*.
- Aucun témoignage, aucun chiffre de rendement promis, aucun compteur de
  fausse urgence.

### Constaté
- **Aucune preuve vérifiable par un tiers.** Les chiffres sont auto-déclarés
  et régénérés par un script. Rien ne relie la page à un relevé de courtier,
  un compte MyFxBook/FXBlue, ou une signature quelconque.
- **Aucune identité derrière le projet** : ni page « à propos », ni personne,
  ni histoire, ni photo. Le seul contact est une adresse email
  (`zioqsen@gmail.com`). Pour un produit financier, l'anonymat total est
  ambivalent — il protège, mais il rassure mal.
- Les **tarifs sont affichés** (« indicatifs, confirmés au lancement ») alors
  que rien n'est vendable. Un visiteur peut y voir une incohérence.
- La page de performance affiche « 88 trades / 48,9 % de réussite » sans
  **facteur de profit, espérance, drawdown maximal, ni intervalle de
  confiance**. Un taux de réussite seul n'est pas interprétable, et un lecteur
  averti le sait.

### Questions ouvertes
- Quel niveau de vérification externe est atteignable **gratuitement** et
  proportionné à une bêta sur démo ?
- Faut-il masquer les tarifs tant que rien n'est vendable ?
- Un anonymat total est-il tenable, ou faut-il au minimum une page « qui est
  derrière ce projet et pourquoi » ?

---

## 3. Conversion visiteur → testeur / Telegram

### En place
- Parcours : accueil → `/rejoindre` (prénom, nom, email, date de naissance) →
  clé affichée immédiatement → `/telecharger` (déverrouillé par la clé) →
  installation.
- 5 appels à l'action vers `/rejoindre` sur l'accueil.
- Groupe Telegram avec sujets thématiques, lien d'invitation récupéré
  dynamiquement depuis `/api/health` (jamais codé en dur).
- Liaison de compte Telegram par lien profond `t.me/<bot>?start=<code>` : un
  testeur qui lie son compte est prévenu automatiquement à l'activation de sa
  clé, avec le mode d'emploi.
- Page de téléchargement affichant en libre-service l'état du copieur du
  testeur (« Ton copieur tourne — vu il y a 1 min »).

### Constaté — c'est ici que se trouvent les manques les plus nets
- **Le bouton principal de la barre de navigation pointe vers `#tarifs`**, pas
  vers l'inscription. Un visiteur froid est envoyé vers une grille de prix
  d'un produit gratuit et non disponible. C'est probablement la plus grosse
  fuite du parcours.
- **Aucun appel à l'action Telegram sur l'accueil.** Telegram n'y apparaît que
  deux fois, comme *puce de fonctionnalité* dans les offres payantes
  (« Alertes Telegram instantanées »). Il n'existe **aucun moyen de rejoindre
  la communauté sans d'abord s'inscrire et obtenir une clé**. Si l'objectif
  est de faire croître un canal Telegram, le chemin est actuellement fermé.
- **La page d'inscription ne contient aucun titre** — ni `<h1>`, ni `<h2>`,
  ni `<h3>`. Le formulaire arrive sans promesse ni rappel de ce qu'on obtient.
- **4 champs demandés** (prénom, nom, email, date de naissance) pour une
  inscription gratuite. Le nom de famille ne sert à rien de fonctionnel.
  La date de naissance, si (contrôle de majorité + récupération de clé) — mais
  ce n'est expliqué qu'après.
- Aucune preuve sociale nulle part : ni nombre d'inscrits, ni nombre de
  testeurs actifs, ni activité du groupe.
- Aucune capture d'écran, aucune démonstration visuelle du produit en
  fonctionnement.
- Aucun moyen de rester en contact sans s'inscrire (pas de simple email, pas
  de canal Telegram public en lecture seule).

### Questions ouvertes
- Un **canal Telegram public en lecture seule** (annonces, signaux différés,
  résultats) séparé du **groupe privé de bêta** serait-il le bon montage ?
- Quelle friction retirer du formulaire sans perdre la récupération de clé,
  qui dépend du couple email + date de naissance ?
- Le tunnel « inscription → clé → téléchargement → installation MT5 » compte
  une trentaine de minutes et exige un PC allumé. Où placer l'aveu de cette
  friction pour ne pas la découvrir trop tard, sans décourager d'emblée ?

---

## 4. SEO

### Constaté — le point le plus faible, mesuré page par page

| Page | `<title>` | `<meta description>` | OG | Twitter | canonical | schema.org | `<h1>` |
|---|---|---|---|---|---|---|---|
| index | 37 car | **ABSENTE** | 0 | 0 | non | non | 1 |
| performance | 34 car | 73 car | 0 | 0 | non | non | **0** |
| guide | 47 car | 149 car | 0 | 0 | non | non | **0** |
| telecharger | 33 car | 89 car | 0 | 0 | non | non | 1 |
| confidentialite | 28 car | 127 car | 0 | 0 | non | non | 1 |
| mentions-legales | 29 car | 91 car | 0 | 0 | non | non | 1 |
| /rejoindre | oui | oui | 0 | 0 | non | non | **0** |

Également :
- `robots.txt` → **404**
- `sitemap.xml` → **404**
- `favicon.ico` → **404**
- Aucune balise Open Graph ni Twitter Card : **tout partage sur Telegram,
  WhatsApp, X ou Discord affiche un aperçu vide.** Pour un produit dont
  l'acquisition passe par le bouche-à-oreille et la messagerie, c'est
  probablement le manque le plus coûteux de toute cette section.
- Aucune donnée structurée (`Organization`, `FAQPage`, `SoftwareApplication`)
  alors que l'accueil contient une vraie FAQ et le guide un vrai mode d'emploi.
- `lang="fr"` présent partout. Un seul `<h1>` par page quand il existe.
- Domaine en `onrender.com` : aucune autorité propre, et le sous-domaine
  appartient à l'hébergeur.

### Questions ouvertes
- Quelles requêtes viser réellement ? Le marché « copy trading » /
  « signaux forex » est saturé et dominé par des acteurs à gros budget.
  Le SEO est-il seulement le bon canal à ce stade, ou faut-il n'investir que
  dans les cartes de partage (OG) qui servent le bouche-à-oreille ?
- Un nom de domaine propre change-t-il quelque chose avant d'avoir du contenu ?

---

## 5. Performance

### Mesuré en production

| Page | Poids | Temps (serveur éveillé) |
|---|---|---|
| `/` | 27,7 Ko | 0,27 s |
| `/performance` | 14,8 Ko | 0,23 s |
| `/telecharger` | 20,9 Ko | 0,24 s |
| `/guide` | 23,2 Ko | 0,81 s |
| `/rejoindre` | 10,3 Ko | 0,63 s |
| **Total site** | **~102 Ko** | — |

### En place
- **Zéro image, zéro police externe, zéro CDN, zéro framework.** Tout le CSS
  et le JS sont en ligne dans la page. Une seule requête par page.
- Poids remarquablement bas. Aucun script bloquant significatif.

### Constaté
- **Aucun en-tête `Cache-Control`.** Chaque visite retélécharge tout, alors
  que ces pages changent rarement.
- **Aucune compression** (`Content-Encoding` absent). Du HTML à ~100 Ko se
  compresse typiquement d'un facteur 4 à 5 — c'est le gain le plus simple
  disponible.
- **Le réveil à froid domine tout le reste** : 10 à 50 s sur le plan gratuit
  après 15 min d'inactivité. Un premier visiteur peut attendre 30 s pour une
  page qui se sert en 0,25 s une fois réveillée. **Optimiser 100 Ko n'a aucun
  sens tant que ce point n'est pas traité.**
- CSS dupliqué d'une page à l'autre (chaque page réembarque sa palette et ses
  composants) — sans conséquence à cette échelle, mais coûteux en maintenance.

### Questions ouvertes
- Compression et cache : à activer côté application ou côté Cloudflare (qui
  sert déjà d'intermédiaire d'après l'en-tête `server: cloudflare`) ?
- Le réveil à froid vaut-il un plan payant, un pinger externe, ou une bascule
  vers un hébergement statique pour les pages publiques ?

---

## 6. Sécurité

### En place — mesuré sur la réponse réelle

| En-tête | Valeur |
|---|---|
| `strict-transport-security` | `max-age=31536000` |
| `content-security-policy` | `default-src 'self'; script-src 'self' 'unsafe-inline'; …` |
| `x-content-type-options` | `nosniff` |
| `x-frame-options` | `DENY` |
| `referrer-policy` | `no-referrer` |
| `permissions-policy` | `geolocation=(), microphone=(), camera=()` |

Également en place :
- Limitation de débit par route : signal 60/30, admin 300/20, récupération de
  clé 300/10, inscription 3600/15, téléchargement 3600/40.
- **Clés dérivées par HMAC** du couple email + date de naissance : une clé
  perdue se recalcule à l'identique, elle n'est jamais stockée en clair
  ailleurs, et l'email seul ne suffit pas à la retrouver.
- Verrouillage après 5 échecs de récupération par adresse et par heure — la
  limite par IP ne protégeait pas une adresse ciblée.
- Téléchargement de l'EA **authentifié côté serveur**, pas seulement masqué
  dans la page. Liste blanche stricte des noms de fichiers (aucun nettoyage de
  chemin : seuls des noms connus sont acceptés).
- Jeton d'administration transmis par **en-tête**, jamais en URL.
- Aucun secret dans le dépôt (public) ; variables sensibles en `sync: false`.
- La télémétrie du copieur remonte version, courtier, type de compte et
  dernière erreur — **jamais le solde, jamais les positions, jamais
  d'identifiants**.

### Constaté
- **`'unsafe-inline'` dans la CSP** pour scripts et styles. Inévitable en
  l'état puisque tout est en ligne dans les pages, mais ça affaiblit la
  protection contre l'injection.
- **Le dépôt GitHub est public et contient le code source de l'EA.** Le
  contrôle d'accès au téléchargement protège donc le *service*, pas la
  *confidentialité du fichier*. C'est assumé, mais à connaître.
- Aucune authentification à deux facteurs ni journal d'audit sur `/admin`
  (jeton unique).
- Aucun `Content-Security-Policy-Report-Only` ni remontée de violations.
- Pas de politique de divulgation (`security.txt`).
- La base est éphémère : une réinitialisation efface toutes les clés
  actives — c'est un problème de disponibilité, déjà identifié et en cours de
  traitement.

### Questions ouvertes
- Vaut-il la peine d'externaliser CSS et JS pour supprimer `'unsafe-inline'`,
  au prix d'une requête supplémentaire et du renoncement au « une page = un
  fichier » ?
- Quelles protections manquent pour une application qui manipulera un jour de
  l'argent réel, même si ce n'est pas le cas aujourd'hui ?

---

## 7. Responsive mobile

### En place
- `viewport` correct sur toutes les pages.
- Points de rupture à 768 px et 640 px ; tableaux placés dans des conteneurs
  à défilement horizontal (`overflow-x:auto`).
- `html, body { max-width:100%; overflow-x:hidden }` en garde.
- Zones tactiles des champs et boutons à `min-height: 48px` sur le parcours
  d'inscription et de téléchargement.
- **Vérifié à 375 px de large** sur `/guide` et `/telecharger` : aucun
  débordement horizontal, aucun élément plus large que la fenêtre.

### Constaté
- Vérification faite **au niveau du document**, pas visuellement page par
  page. L'accueil, la page de performance et les pages légales n'ont pas été
  contrôlées à cette largeur.
- Aucun test sur très petit écran (320 px) ni en orientation paysage.
- Le mode sombre est **imposé** (`color-scheme: dark`) : aucune adaptation à
  la préférence système claire.
- Aucun test d'accessibilité : contrastes non mesurés, navigation au clavier
  non vérifiée, focus non stylé, aucun attribut ARIA.
- Ironie utile à signaler : **le produit ne fonctionne pas sur mobile** (MT5
  mobile n'exécute pas d'Expert Advisor), or le site est surtout consulté sur
  mobile. Les pages doivent donc convaincre sur un écran depuis lequel on ne
  pourra pas passer à l'acte.

### Questions ouvertes
- Comment traiter cette dissociation « je lis sur mobile / j'installe sur
  PC » ? Un envoi de lien vers soi-même, un QR code, un rappel ?

---

## 8. UX spécifique au trading

### En place
- Page de performance publique avec, par stratégie : nombre de trades, taux
  de réussite, statut (`en validation`, `démarrage`), capital du compte démo,
  signaux détectés, trades pris, positions en cours, horodatage.
- Explication du **filtrage** : « 20 signaux détectés, 5 trades pris — filtres
  stricts ». Ça montre que ne pas trader est un choix, pas une panne.
- Le guide explique la cadence réelle (~1 trade/jour, avec des jours à zéro)
  et prévient que rien ne se passera tout de suite — la question la plus
  fréquente, désamorcée avant d'être posée.
- Le copieur **recalcule la taille de position** depuis le capital du testeur
  et son pourcentage de risque : les lots ne sont jamais copiés tels quels.
- Positions gérées par un numéro magique : le copieur ne touche jamais aux
  trades ouverts à la main.
- Refus explicite d'ouvrir si le volume minimum du courtier dépasse le risque
  cible, avec la consigne écrite de **ne pas monter le risque pour faire
  passer un trade**.

> **CORRECTION du 31/07 — une première version de cette section affirmait
> qu'il n'y avait ni courbe, ni métrique de risque, ni historique. C'était
> FAUX**, dû à une extraction automatique qui n'avait capté qu'un seul motif
> de balise. Vérification faite sur la page servie en production, la réalité
> est nettement meilleure que décrite. Section refaite ci-dessous.

### En place (vérifié sur la page en production)
Par stratégie (XAUUSD, EURUSD), **six métriques** :
nombre de trades · taux de réussite · **facteur de profit** (coloré selon un
seuil : rouge < 1, orange < 1,2, vert au-delà) · résultat cumulé · gain
moyen · perte moyenne.

- **Une courbe de capital par stratégie**, en SVG généré côté serveur :
  20 points, aire douce sous la courbe, lignes de repère cotées, marqueur sur
  le dernier point. Zéro dépendance, zéro JavaScript.
- **Un tableau des 8 derniers trades**, gagnants et perdants, avec date, sens,
  motif de sortie et résultat.
- Un mécanisme d'honnêteté codé en dur : tant que le facteur de profit est
  sous 1,2, la stratégie est étiquetée « en validation » et **ne peut pas**
  être présentée comme confirmée.
- Le bloc SwingBot n'affiche **volontairement ni taux de réussite ni facteur
  de profit** : l'échantillon est trop petit pour qu'ils aient un sens.

### Constaté — ce qui manque réellement
- **Le drawdown est promis et jamais affiché.** L'introduction annonce
  « nous montrons TOUT — gains, pertes, **drawdown** — en temps réel ».
  Aucun drawdown n'existe sur la page. Pour un projet dont tout le
  positionnement est l'honnêteté, une promesse non tenue dans la phrase
  d'accroche est l'endroit le plus coûteux possible.
- **Le tableau des trades est replié par défaut** (`<details>`). La preuve la
  plus forte de la page — chaque trade, perdant compris — est cachée derrière
  un clic. *Indice qu'elle passe inaperçue : un relecteur externe a conclu que
  la page ne contenait ni graphique ni historique.*
- **Aucun intervalle de confiance ni cadrage de la taille d'échantillon.**
  À 88 trades, l'incertitude sur l'espérance reste très large ; la page ne le
  dit pas. Un facteur de profit de 1,12 sur 88 trades n'est pas
  distinguable de 1,00.
- Ni série de pertes consécutives la plus longue, ni R moyen, ni exposition.
- Aucune répartition par instrument, par heure, par jour, par régime.
- Aucune comparaison à une référence.
- Aucun export des données.
- Aucune répartition par instrument, par heure, par jour, par régime de marché.
- Aucune comparaison à une référence (achat-conservation, indice).
- Le lecteur ne peut pas distinguer « stratégie prudente qui filtre » de
  « stratégie qui ne trouve rien » — les deux produisent peu de trades.
- Pas de flux public des signaux (même différé), qui serait pourtant la preuve
  la plus directe que le système vit.

### Questions ouvertes
- Quelles métriques ajouter **sans** donner l'illusion d'une précision que
  l'échantillon ne permet pas ? Le risque est de passer d'un défaut (trop peu
  d'information) à un autre (surinterprétation).
- Comment rendre visuelle une performance encore non concluante sans tomber
  dans la courbe flatteuse tronquée, qui est exactement le procédé que ce
  projet refuse ?
- Un flux de signaux différé de 24 h serait-il une preuve de vie utile, ou un
  cadeau fait aux copieurs non payants ?

---

## 9. Ce qu'on sait déjà devoir faire

À ne pas resuggérer — c'est identifié, planifié, ou en cours.

1. Base de données durable (le stockage actuel est éphémère) — décidé, en
   attente d'une configuration côté Google Drive.
2. Parcours complet jamais effectué de bout en bout par un humain — prévu.
3. Moitié « réception » de la chaîne de signal non encore vérifiée.
4. Compression et cache HTTP absents.
5. `robots.txt`, `sitemap.xml`, favicon, Open Graph absents.

---

## 10. Ce qu'on demande à un second regard

1. **Ce qui n'est dans aucune des 8 sections ci-dessus** — l'angle mort.
2. Parmi les manques listés, **lesquels comptent vraiment** pour une bêta
   gratuite à quelques testeurs, et lesquels sont du polissage prématuré ?
3. Les erreurs de **conception du parcours** que la liste ne capture pas :
   ordre des étapes, moment où l'on demande quoi, ce qu'on montre trop tôt ou
   trop tard.
4. Les risques **juridiques ou réglementaires** propres à un produit lié au
   trading diffusé en Europe, même gratuit et sur démo.
5. Ce qui, dans le ton et la présentation, **desservirait la confiance** sans
   qu'on s'en rende compte.
