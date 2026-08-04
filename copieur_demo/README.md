# Terminaux MT5 portables — bêta démo

Deux installations neuves de MetaTrader 5 IC Markets EU sont prêtes :

- `runtime\beta_01`
- `runtime\beta_02`

Elles n'utilisent aucun fichier de données provenant des trois terminaux
personnels existants. Le dossier `runtime` est ignoré par Git parce qu'un
terminal peut y mémoriser localement des informations de connexion.

## Premier lancement

Lancer les terminaux uniquement avec :

- `LANCER_BETA_01.cmd`
- `LANCER_BETA_02.cmd`

Ces lanceurs imposent le mode `/portable`. Ne lancer pas directement un
`terminal64.exe`, sinon l'isolation des données ne serait plus garantie.

La configuration non sensible de `beta_02` est déjà automatisée. Suivre
`CONFIGURATION_BETA_02.md` pour les deux saisies qui doivent rester manuelles :
le compte démo et sa clé bêta distincte.

Au premier lancement de chaque terminal :

1. créer ou connecter un compte **démo** distinct directement dans MT5 ;
2. ne placer aucun identifiant dans ce dossier ou dans un message ;
3. utiliser **Fichier → Ouvrir le dossier des données** et vérifier que le
   chemin se termine bien par `runtime\beta_01` ou `runtime\beta_02` ;
4. autoriser les WebRequest vers `http://127.0.0.1:8765` pour le premier test ;
5. activer Trading Algo ;
6. actualiser les Expert Advisors : `AlphaScalpCopier` est déjà copié dans
   `MQL5\Experts`.

## Paramètres du test local

| Paramètre | beta_01 | beta_02 |
|---|---:|---:|
| `AdresseServeur` | `http://127.0.0.1:8765` | `http://127.0.0.1:8765` |
| `CleApi` | `as_local_demo_only` | `as_local_demo_only` |
| `RisqueParTrade` | `0.1` | `0.1` |
| `LotMaximum` | `0.01` | `0.01` |
| `PositionsMaximum` | `1` | `1` |
| `AutoriserCompteReel` | `false` | `false` |
| `NumeroMagique` | `770701` | `770702` |

Le bac à sable reste dans le projet isolé et se lance avec :

```text
C:\bot\copieur_demo\outils\lancer_bac_a_sable.cmd
```

Ne passer à `https://alphascalp.onrender.com` qu'après réussite de l'ouverture
et de la fermeture locales. Chaque testeur recevra alors une clé bêta distincte.
