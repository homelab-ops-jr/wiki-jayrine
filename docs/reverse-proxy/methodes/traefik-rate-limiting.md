# Méthode — Rate limiting avec Traefik

> **Type** : Méthode · **Outil** : Traefik v3 · **Difficulté** : ⭐ Débutant

## Quand l'utiliser

- Protéger une **API publique** contre l'abus ou le scraping
- Protéger une **page de login** contre le brute-force
- Limiter les **endpoints coûteux** (recherches, exports)
- Mettre une protection de base avant des solutions plus avancées (CrowdSec, fail2ban)

⚠️ Le rate limit Traefik est **simple et stateless** (par instance Traefik). Pour une protection plus fine (réputation IP, signatures d'attaque), passer à CrowdSec via plugin.

## Concept

Le middleware `rateLimit` de Traefik limite le **nombre de requêtes par source dans une fenêtre de temps**. Les paramètres :

| Paramètre | Rôle |
|-----------|------|
| `average` | Nombre de requêtes **par période** autorisées en régime établi |
| `period` | Durée de la période d'évaluation (défaut `1s`) |
| `burst` | Nombre de requêtes autorisées **en pic court** (token bucket) |
| `sourceCriterion` | Comment identifier une "source" (IP, header, etc.) |

Mécanisme **token bucket** :
- À chaque période, `average` nouveaux jetons sont disponibles
- Chaque requête consomme un jeton
- Un "réservoir" de `burst` jetons absorbe les pics
- Plus de jetons → réponse `429 Too Many Requests`

## Exemples concrets

### Protection de base — 100 req/sec en moyenne, burst 200

```yaml
# dynamic/middlewares.yml
http:
  middlewares:
    rate-limit-default:
      rateLimit:
        average: 100
        burst: 200
        period: 1s
```

Application sur un router :
```yaml
labels:
  - "traefik.http.routers.monapp.middlewares=rate-limit-default@file"
```

### Protection forte d'une page de login — 5 req/minute par IP

```yaml
http:
  middlewares:
    rate-limit-login:
      rateLimit:
        average: 5
        period: 1m
        burst: 10
```

Appliqué uniquement à la route `/login` via un router spécifique :
```yaml
labels:
  # Router login (auth-sensitive)
  - "traefik.http.routers.monapp-login.rule=Host(`monapp.example.com`) && PathPrefix(`/login`)"
  - "traefik.http.routers.monapp-login.entrypoints=websecure"
  - "traefik.http.routers.monapp-login.tls=true"
  - "traefik.http.routers.monapp-login.middlewares=rate-limit-login@file"
  - "traefik.http.routers.monapp-login.service=monapp"

  # Router général (rate limit plus souple)
  - "traefik.http.routers.monapp.rule=Host(`monapp.example.com`)"
  - "traefik.http.routers.monapp.entrypoints=websecure"
  - "traefik.http.routers.monapp.tls=true"
  - "traefik.http.routers.monapp.middlewares=rate-limit-default@file"

  - "traefik.http.services.monapp.loadbalancer.server.port=3000"
```

Le router `monapp-login` (avec PathPrefix) est plus spécifique → il prend les requêtes `/login/*`. Le router générique gère le reste.

### API publique — limite douce mais ferme

```yaml
http:
  middlewares:
    rate-limit-api:
      rateLimit:
        average: 60          # 60 req/minute = 1 req/sec en moyenne
        period: 1m
        burst: 30            # accepte un burst court
```

## Identification de la "source" — `sourceCriterion`

Par défaut, Traefik utilise l'**IP source** de la connexion. Mais derrière un autre proxy (Cloudflare, etc.), c'est l'IP du proxy amont, pas du client réel — tous les visiteurs comptent comme une seule source.

### Cas 1 — Traefik est en frontal direct
Pas de config particulière, l'IP source est la bonne :
```yaml
rateLimit:
  average: 100
  burst: 200
  # sourceCriterion implicite : ipStrategy par défaut
```

### Cas 2 — Cloudflare ou autre CDN devant Traefik
Tu dois pointer le rate limit sur le `X-Forwarded-For` que CF transmet :
```yaml
rateLimit:
  average: 100
  burst: 200
  sourceCriterion:
    ipStrategy:
      depth: 1   # prend la N-ième IP depuis la fin du X-Forwarded-For
```

Le `depth: 1` signifie "ignore les 1 dernières IPs du X-Forwarded-For" — donc tu sautes l'IP de Cloudflare et tu prends celle juste avant (le vrai client).

⚠️ Ne fonctionne que si Cloudflare est dans tes `forwardedHeaders.trustedIPs` (sinon Traefik écrase les X-Forwarded-* et il n'y a rien à parser).

### Cas 3 — Rate limit par utilisateur authentifié
Si tu veux limiter par utilisateur (et non par IP), utilise un header transmis par Authelia ou ton système d'auth :
```yaml
rateLimit:
  average: 100
  burst: 200
  sourceCriterion:
    requestHeaderName: "Remote-User"
```

Limite : si le header n'est pas présent (client non auth), tous les non-auth comptent comme une seule source. Combiner avec un fallback IP-based pour les routes publiques.

### Cas 4 — Rate limit global (toutes IPs confondues)
Si tu veux limiter la **charge totale** sur ton backend, peu importe la source :
```yaml
rateLimit:
  average: 1000
  burst: 2000
  sourceCriterion:
    requestHost: true   # toutes les requêtes pour le même Host comptent ensemble
```

## Application au niveau entrypoint (rate limit global)

Tu peux appliquer un middleware par défaut à tous les routers d'un entrypoint, sans avoir à le redéclarer partout. Dans `traefik.yml` :

```yaml
entryPoints:
  websecure:
    address: ":443"
    http:
      middlewares:
        - rate-limit-default@file
```

Tous les routers sur `websecure` héritent du rate limit, sauf override explicite. Pratique pour une protection de base globale.

## Réponse côté client : le 429

Quand le rate limit déclenche, Traefik répond :
```http
HTTP/1.1 429 Too Many Requests
Retry-After: 1
```

Le header `Retry-After` est un standard que les clients bien faits respectent. Les bots l'ignorent.

Pour personnaliser la réponse (page d'erreur custom), combiner avec un middleware `errors` :
```yaml
http:
  middlewares:
    rate-limit-with-page:
      chain:
        middlewares:
          - rate-limit-default
          - errors-page

    errors-page:
      errors:
        status:
          - "429"
        service: error-pages-svc
        query: "/429.html"
```

(Nécessite un container qui sert la page d'erreur.)

## Tester son rate limit

Outil simple : `hey` ou `wrk`. Exemple avec `hey` :

```bash
# Installer (Debian/Ubuntu)
sudo apt install hey

# 200 requêtes en série, voir combien sont rate limitées
hey -n 200 -c 1 https://monapp.example.com/

# Sortie attendue (extrait) :
Status code distribution:
  [200] 100 responses
  [429] 100 responses
```

Avec `curl` :
```bash
for i in $(seq 1 150); do
  curl -s -o /dev/null -w "%{http_code}\n" https://monapp.example.com/
done | sort | uniq -c
```

## Combiner rate limit avec auth

L'ordre des middlewares détermine ce qui est protégé en premier. Deux philosophies :

### A. Rate limit AVANT auth
```yaml
middlewares=rate-limit-default@file,authelia@docker
```
Le rate limit protège **Authelia elle-même** (limite les tentatives de login).

### B. Auth AVANT rate limit
```yaml
middlewares=authelia@docker,rate-limit-default@file
```
Le rate limit ne s'applique qu'aux utilisateurs authentifiés. Évite que des bots non-auth consomment ton quota.

Pour la plupart des cas : **A** (rate limit en premier) est plus défensif.

## Pièges fréquents

| Symptôme | Cause |
|----------|-------|
| Rate limit ne déclenche jamais | `sourceCriterion` mal configuré, ou Traefik voit toutes les requêtes comme venant d'une IP (ex. depth mal réglé) |
| Tous les clients limités très vite | Une seule IP visible (proxy en amont sans X-Forwarded-For trusted) |
| 429 sur des requêtes légitimes | `burst` trop bas ; augmenter pour absorber les pics |
| Les requêtes statiques (CSS/JS) consomment le quota | Sortir les statiques sur un router/middleware séparé |
| Différence entre `period: 1s, average: 100` et `period: 1m, average: 6000` | Pas équivalent côté burst — la première autorise une rafale par seconde, la seconde lisse sur la minute |
| Cluster Traefik multi-instances : limite par instance, pas globale | `rateLimit` Traefik n'est **pas distribué** — chaque instance compte indépendamment |

## Limites connues

- **Stateless par instance** : si tu as plusieurs Traefik en parallèle, chaque instance a son propre compteur. Pour du rate limit distribué, il faut un Redis externe (non supporté nativement dans la communauté edition).
- **Pas de réputation IP** : une IP qui a déjà fait du brute-force ailleurs n'est pas pré-bloquée. Pour ça → CrowdSec.
- **Pas de granularité par endpoint sans router séparé** : pour `rateLimit` différent sur `/login` vs `/`, il faut deux routers.

## À retenir

- `average` (taux établi) + `burst` (pic absorbable) + `period` (fenêtre) sont les trois leviers.
- `sourceCriterion.ipStrategy.depth` pour s'adapter à un CDN/proxy amont.
- Combinable au niveau **entrypoint** pour une protection globale par défaut.
- L'ordre vs auth dépend du modèle de menace — par défaut, rate limit en premier.
- Pour aller plus loin que le rate limit basique : **CrowdSec** via plugin Traefik.

## Voir aussi

- [Notion : Middlewares — concept et chaînage](../notions/03-middlewares.md)
- [Notion : Headers HTTP et X-Forwarded-*](../notions/05-headers-x-forwarded.md) — important pour le rate limit derrière un CDN
- Documentation : [Traefik RateLimit middleware](https://doc.traefik.io/traefik/middlewares/http/ratelimit/)
