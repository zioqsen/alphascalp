# AlphaScalp — Serveur de licence + relais de signaux (MVP bêta)

Brique 1 du moteur. Rôle : recevoir les trades du **bot maître**, les relayer aux
**followers** *uniquement si leur clé d'abonnement est active*, et gérer les clés
via une page admin. Tout en démo/gratuit pour la bêta — le toggle actif/inactif
simule l'état d'abonnement.

## Lancer

```bash
pip install -r requirements.txt

# Jetons (à changer ; sinon valeurs de dev par défaut)
export ALPHASCALP_MASTER_TOKEN="ton-jeton-maitre"
export ALPHASCALP_ADMIN_TOKEN="ton-jeton-admin"

python server.py
```

- Page admin : `http://127.0.0.1:8000/admin?token=<ADMIN_TOKEN>`
- Base SQLite créée automatiquement (`alphascalp.db`).

## Flux

```
   BOT MAÎTRE                SERVEUR                 FOLLOWER (chez le testeur)
  scalp_bot ──POST /api/signal──►  [signals]  ◄──GET /api/signals?since=N── bot follower
                                   [clients]──► clé active ? oui→signaux / non→403 pause
                                      ▲
                              page admin (toggle)
```

## Endpoints

| Méthode | Route | Auth | Usage |
|---|---|---|---|
| POST | `/api/signal` | header `X-Master-Token` | le maître publie un trade (`open`/`close`) |
| GET  | `/api/status` | header `X-Api-Key` | le follower vérifie son état + dernier id |
| GET  | `/api/signals?since=N` | header `X-Api-Key` | nouveaux signaux d'id > N (403 si inactif) |
| GET  | `/api/admin/clients` | `?token=` | liste des clés |
| POST | `/api/admin/clients?name=&plan=` | `?token=` | créer une clé |
| POST | `/api/admin/clients/{key}/toggle` | `?token=` | activer/désactiver |
| POST | `/api/admin/clients/{key}/delete` | `?token=` | supprimer |

## Tester au curl

```bash
M="ton-jeton-maitre" ; A="ton-jeton-admin" ; B=http://127.0.0.1:8000

# 1. créer une clé
curl -s -X POST "$B/api/admin/clients?name=Pote&plan=beta&token=$A"
#   → { "api_key": "as_xxx", ... }   ← note la clé

K="as_xxx"

# 2. le maître publie une ouverture
curl -s -X POST "$B/api/signal" -H "X-Master-Token: $M" -H "Content-Type: application/json" \
  -d '{"action":"open","ref_id":"T1","symbol":"XAUUSD","direction":"BUY","volume_ref":0.2,"price":4350,"sl":4344,"tp":4360,"regime":"TREND"}'

# 3. le follower (clé active) récupère
curl -s "$B/api/signals?since=0" -H "X-Api-Key: $K"

# 4. on désactive (simulate non-paiement)
curl -s -X POST "$B/api/admin/clients/$K/toggle?token=$A"

# 5. le follower est maintenant en pause (403)
curl -s "$B/api/signals?since=0" -H "X-Api-Key: $K"
```

## Idempotence & reconnexion (côté follower)

Le follower garde son **dernier id traité** (`since`) en local. À chaque poll il
demande `?since=<dernier_id>` → pas de doublon, pas de rejouage.
Sur un follower **neuf** : appeler d'abord `/api/status`, lire `latest_signal_id`,
et partir de là (sinon il rejouerait tout l'historique).

## La suite (pas encore inclus)

1. **Hook maître** dans `scalp_bot` : après chaque `order_send` réussi (ouverture
   et fermeture), un `POST /api/signal`. Volume envoyé en **ratio du capital**,
   pas en lot fixe, pour que chaque follower adapte à son compte.
2. **Bot follower** : poll `/api/signals`, applique les nouveaux signaux sur son
   MT5, avec **tolérance d'écart de prix max** (skip si le prix a trop bougé — clé
   pour ne pas diverger sur du scalp), et dédup via `since`.
3. **Stripe** : un webhook remplacera le toggle manuel → bascule `active` selon le
   paiement. Le reste du serveur ne bouge pas.

## ⚠️ Avant d'exposer en ligne

MVP de dev : auth par jetons simples, HTTP local. Avant toute mise en ligne :
HTTPS (reverse proxy), jetons forts en variables d'env, et durcissement de l'accès
admin. Ne pas exposer `/admin` publiquement sans ça.
