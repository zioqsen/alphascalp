# Terminer `beta_03`, `beta_04` et `beta_05`

Les trois terminaux portables sont installés séparément. Chacun contient le
copieur AlphaScalp 1.13 et un preset sans compte ni clé.

| Terminal | Lanceur | Preset | Numéro magique |
|---|---|---|---:|
| `beta_03` | `LANCER_BETA_03.cmd` | `AlphaScalpCopier_BETA03.set` | `770703` |
| `beta_04` | `LANCER_BETA_04.cmd` | `AlphaScalpCopier_BETA04.set` | `770704` |
| `beta_05` | `LANCER_BETA_05.cmd` | `AlphaScalpCopier_BETA05.set` | `770705` |

## Étapes manuelles pour chaque terminal

1. Lancer uniquement le lanceur correspondant.
2. Créer ou connecter directement dans MT5 un compte **démo distinct**.
3. Vérifier dans **Outils → Options → Expert Consultants** :
   - Trading algorithmique autorisé ;
   - imports DLL interdits ;
   - WebRequest autorisé ;
   - `https://alphascalp.onrender.com` présent dans la liste.
4. Ouvrir un graphique et déposer `AlphaScalpCopier` une seule fois.
5. Dans **Données d'entrée**, charger le preset correspondant.
6. Coller localement la clé bêta propre au testeur dans `CleApi`. Ne jamais
   placer cette clé dans un fichier de suivi, un message ou une capture.
7. Vérifier impérativement `AutoriserCompteReel=false`, puis valider.
8. Dans **Experts**, vérifier la version 1.13, le mode démo et l'absence
   d'erreur WebRequest.

Les réglages WebRequest ont été préremplis à partir de la section non sensible
`[Experts]` de `beta_02`. Leur présence dans l'interface doit rester vérifiée
au premier lancement : aucun terminal ni compte n'a été démarré pendant la
préparation.
