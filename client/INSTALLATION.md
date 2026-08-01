# AlphaScalp — installer le copieur sur ton MetaTrader 5

Compte **démo** uniquement pendant la bêta. L'EA refuse de démarrer sur un
compte réel, c'est volontaire.

**Il te faut un PC allumé** (ou un VPS). MetaTrader sur téléphone n'exécute
pas les Expert Advisors — c'est une limite de MetaQuotes, ni AlphaScalp ni
personne ne peut la contourner. Ton téléphone reste parfait pour *suivre* tes
résultats depuis l'appli MT5.

Compte 10 minutes la première fois.

---

## 1. Poser le fichier au bon endroit

Dans MetaTrader 5 : **Fichier → Ouvrir le dossier de données**. Une fenêtre
d'explorateur s'ouvre.

Va dans `MQL5` puis `Experts`, et copie **les deux fichiers** dedans :

- `AlphaScalpCopier.ex5` — le programme compilé, c'est lui qui tourne
- `AlphaScalpCopier.mq5` — le code source, pour que tu puisses le lire

> Tu n'as **rien à compiler** : le `.ex5` est fourni déjà prêt. Le `.mq5` est
> là par transparence — c'est un programme qui va passer des ordres sur ton
> compte, tu as le droit de voir ce qu'il fait. Si tu préfères le compiler
> toi-même, ouvre le `.mq5` dans MetaEditor (touche `F4` depuis MT5) et
> appuie sur `F7`.

Reviens dans MetaTrader et fais un clic droit sur **Expert Advisors** dans la
fenêtre « Navigateur » (à gauche) → **Actualiser**. `AlphaScalpCopier`
apparaît dans la liste.

> Si tu ne vois pas la fenêtre Navigateur : **Affichage → Navigateur**, ou
> `Ctrl+N`.

## 2. Autoriser MetaTrader à joindre le serveur

**C'est l'étape que tout le monde oublie, et sans elle rien ne marche.**

**Outils → Options → onglet Expert Advisors** :

1. coche **« Autoriser les WebRequest pour les URL listées »**
2. clique sur la ligne vide et saisis exactement :

```
https://alphascalp.onrender.com
```

3. valide avec **OK**

Sans ça, l'EA démarre mais ne reçoit jamais rien. Il te le dira dans son
journal, en toutes lettres.

## 3. Activer le trading automatique

Dans la barre d'outils, le bouton **« Algo Trading »** doit être **vert**.
S'il est rouge ou gris, clique dessus.

## 4. Lancer l'EA

Ouvre **n'importe quel graphique** (le symbole n'a aucune importance : l'EA
travaille sur tous les symboles reçus, pas sur celui du graphique).

Fais glisser `AlphaScalpCopier` depuis le Navigateur vers le graphique. Une
fenêtre de réglages s'ouvre.

Onglet **Paramètres d'entrée** :

| Réglage | À mettre |
|---|---|
| `CleApi` | **ta clé bêta**, celle qui commence par `as_` |
| `RisqueParTrade` | `1.0` pour commencer (1 % du capital par trade) |
| `SuffixeSymbole` | vide — sauf si ton broker ajoute un suffixe (voir plus bas) |
| `PositionsMaximum` | `3` |

Onglet **Commun** : coche **« Autoriser le trading automatique »**.

Valide avec **OK**. Un visage souriant apparaît en haut à droite du
graphique : l'EA tourne.

## 5. Vérifier que tout va bien

Onglet **« Experts »** en bas de MetaTrader — **pas** l'onglet « Journal »,
qui est juste à côté et ne contient aucun message de l'EA. Tu dois lire quelque
chose comme :

```
[AlphaScalp] === AlphaScalp Copier v1.00 ===
[AlphaScalp] Premier lancement — départ au signal n°42 (l'historique n'est pas rejoué).
[AlphaScalp] Compte 12345678 | capital 10000.00 EUR | risque 1.0% | max 3 positions | relève toutes les 10s
[AlphaScalp] Rappel : ce terminal doit rester ALLUMÉ pour que la copie fonctionne.
```

À partir de là, il n'y a plus rien à faire. Laisse tourner.

## 6. Et maintenant ? Il ne va rien se passer tout de suite

**C'est normal, et c'est le point le plus important de cette notice.**

La stratégie sort en moyenne **environ un trade par jour**, et il arrive
régulièrement qu'il n'y en ait **aucun pendant deux ou trois jours**. Le bot
ne trade que quand ses conditions sont réunies : rester à l'écart fait partie
de la stratégie, ce n'est pas une panne.

Ajoute que **les marchés sont fermés du vendredi soir au dimanche soir**. Si
tu installes le vendredi, tu peux très bien ne rien voir avant mardi.

**Ne désinstalle rien, ne relance rien.** Pour savoir si ça marche, ne regarde
pas les trades — regarde si ton copieur est vivant : recolle ta clé sur la
page d'installation du site, elle affiche *« Ton copieur tourne — vu il y a
1 min »*. C'est ça, la bonne réponse à « est-ce que ça fonctionne ? ».

---

## Si ça ne marche pas

**« Adresse NON AUTORISÉE dans MetaTrader »**
L'étape 2 n'a pas été faite, ou l'adresse a été saisie avec une faute. Elle
doit être exactement `https://alphascalp.onrender.com`, sans barre oblique
finale.

**« Clé encore INACTIVE côté AlphaScalp »**
Normal juste après l'inscription : ta clé doit être activée manuellement.
Laisse l'EA tourner, il se réveillera tout seul le moment venu. Rien à
relancer.

**« Symbole XAUUSD introuvable chez ton broker »**
Beaucoup de brokers renomment les symboles : `XAUUSD.r`, `XAUUSDm`,
`XAUUSD#`… Regarde dans ta fenêtre « Observation du marché » comment le tien
s'appelle, et renseigne la partie qui s'ajoute dans `SuffixeSymbole`
(par exemple `.r`) ou `PrefixeSymbole`.

**« au volume minimum … la perte serait de X alors que ton risque cible est Y »**
Ce n'est pas une erreur : l'EA refuse d'ouvrir parce que le plus petit
volume que ton broker accepte ferait risquer plus que voulu. Ça arrive sur
les indices avec un petit capital. Soit tu montes `RisqueParTrade`, soit tu
acceptes que ce symbole-là ne soit pas copié. **Ne monte pas le risque juste
pour faire passer un trade.**

**« COMPTE NON DÉMO détecté — démarrage REFUSÉ »**
Tu as attaché l'EA à un compte réel. La bêta se fait sur démo.

**Rien ne se passe, aucun message**
Vérifie le bouton « Algo Trading » (vert), et le visage souriant en haut à
droite du graphique. Un visage triste = trading automatique désactivé pour
cet EA (onglet Commun de ses réglages).

---

## Ce que l'EA fait, et ne fait pas

**Il fait :** relever les signaux, ouvrir et fermer *ses* positions, calculer
sa taille de position depuis ton capital à toi.

**Il ne fait pas :** toucher aux positions que tu as ouvertes à la main
(il ne gère que les siennes, reconnues par leur numéro magique), envoyer la
moindre donnée personnelle (seule ta clé circule), modifier tes réglages.

**La taille des positions n'est pas copiée telle quelle.** L'EA recalcule à
partir de TON capital et du % de risque que tu as choisi. Si AlphaScalp
risque 1 % du sien, tu risques 1 % du tien — quels que soient vos capitaux
respectifs.

**Si tu arrêtes l'EA**, les positions déjà ouvertes ne sont plus suivies mais
gardent leur SL et leur TP. Elles se fermeront dessus. Elles ne restent pas
sans filet.

**Terminal fermé = aucun trade reçu.** L'EA tourne dans *ton* MetaTrader : PC
éteint ou terminal fermé, personne ne relève les signaux à ta place. Les
trades émis pendant ce temps sont perdus pour toi.

C'est **volontaire** : au redémarrage, l'EA **refuse** les signaux vieux de
plus de `AgeMaxSignalSec` secondes (5 minutes par défaut) au lieu de les
rejouer. Le prix a bougé depuis, et le SL/TP avait été calculé pour un niveau
qui n'existe plus — copier en retard n'ouvrirait pas le même trade, mais un
autre, moins bon. Le journal te le dit en toutes lettres :

```
[AlphaScalp] Signal XAUUSD ignore : emis il y a 47 min, trop ancien
(limite 5 min). Ton terminal etait probablement eteint. Ce n est pas
une panne — le prix a bouge depuis, copier maintenant ouvrirait un
autre trade.
```
