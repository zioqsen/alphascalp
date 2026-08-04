# Terminer `beta_02`

La configuration non sensible a été préparée automatiquement :

- WebRequest activé avec l'adresse `https://alphascalp.onrender.com` ;
- Trading Algo global activé ;
- imports DLL interdits ;
- `AlphaScalpCopier.ex5` déjà installé ;
- preset de risque prudent déjà créé.

## Étapes manuelles restantes

1. Lancer `LANCER_BETA_02.cmd`.
2. Connecter ou créer directement dans MT5 un compte **démo** distinct.
3. Vérifier **Outils → Options → Expert Consultants** :
   - Trading algorithmique autorisé ;
   - WebRequest autorisé ;
   - `https://alphascalp.onrender.com` présent dans la liste.
4. Ouvrir un graphique et y déposer `AlphaScalpCopier` une seule fois.
5. Onglet **Données d'entrée** → **Charger**, puis sélectionner :

   ```text
   MQL5\Presets\AlphaScalpCopier_BETA02.set
   ```

6. Coller manuellement la clé bêta propre à ce testeur dans `CleApi`. Ne
   placer cette clé dans aucun fichier, message ou capture d'écran.
7. Vérifier impérativement `AutoriserCompteReel=false`, puis valider.
8. Dans l'onglet **Experts**, vérifier la version 1.12, le compte démo, la
   connexion serveur et l'absence d'erreur WebRequest.

Le preset utilise `RisqueParTrade=0.1`, `LotMaximum=0.01`, une seule position
et le numéro magique `770702`. Il ne contient aucun compte ni aucune clé.
