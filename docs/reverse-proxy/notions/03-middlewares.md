# 03 — Middlewares : concept et chaînage

> **Type** : Notion · **Sujet** : Reverse proxy · **Prérequis** : [Anatomie d'une requête](./01-anatomie-requete-traefik.md), [Providers](./02-providers-static-dynamic.md)

## En une phrase

Un **middleware** dans Traefik est un composant qui s'insère entre le router et le service pour **inspecter, transformer, court-circuiter, ou enrichir** la requête (et parfois la réponse). C'est l'outil principal pour ajouter de la logique sans toucher au backend.

## Le principe

Quand un router matche une requête, Traefik peut appliquer une **chaîne de middlewares** dans l'ordre, avant de passer au service final :

```
Requête → Router matché
            │
            ▼
        ┌─────────────┐
        │ Middleware 1│  (peut transformer, refuser, rediriger…)
        └──────┬──────┘
               ▼
        ┌─────────────┐
        │ Middleware 2│
        └──────┬──────┘
               ▼
        ┌─────────────┐
        │ Middleware 3│
        └──────┬──────┘
               ▼
            Service → Backend
```

Chaque middleware peut :

- **Modifier la requête** avant transmission (ajouter un header, réécrire un chemin)
- **Modifier la réponse** au retour (ajouter HSTS, compresser)
- **Court-circuiter** la chaîne (refuser une auth, rate limit atteint, IP blacklistée)
- **Rediriger** (3xx vers HTTPS, www → apex)

## Les catégories de middlewares Traefik

Voici les plus utilisés (sur ~40 disponibles dans Traefik v3) :

### Sécurité & authentification
- **`forwardAuth`** — délègue l'auth à un service externe (Authelia, Authentik, OAuth2-proxy)
- **`basicAuth`** — auth HTTP basique (htpasswd-style)
- **`digestAuth`** — auth HTTP digest (plus rare)
- **`ipWhiteList`** / **`ipAllowList`** (v3) — filtrer par IP source

### Throttling & protection
- **`rateLimit`** — limiter le nombre de requêtes par source
- **`inFlightReq`** — limiter le nombre de requêtes simultanées
- **`circuitBreaker`** — court-circuite si le backend renvoie trop d'erreurs

### Transformation HTTP
- **`headers`** — ajouter/modifier des headers de requête ou réponse (HSTS, CSP, CORS…)
- **`redirectScheme`** — rediriger HTTP → HTTPS
- **`redirectRegex`** — redirection conditionnelle par expression régulière
- **`stripPrefix`** / **`addPrefix`** — manipuler le path
- **`replacePath`** / **`replacePathRegex`** — réécrire l'URL
- **`compress`** — gzip/Brotli pour les réponses

### Gestion d'erreurs
- **`errors`** — interception et page custom pour les erreurs 4xx/5xx
- **`retry`** — réessai automatique en cas d'erreur

### Routing avancé
- **`buffering`** — bufferiser les requêtes/réponses (utile pour les uploads)
- **`chain`** — regrouper plusieurs middlewares sous un nom unique

## Déclaration et application

### Via labels Docker (middleware spécifique à un service)

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.monapp.rule=Host(`monapp.example.com`)"
  # Déclaration du middleware "auth-basique" sur ce container
  - "traefik.http.middlewares.auth-basique.basicauth.users=admin:$$2y$$05$$..."
  # Application
  - "traefik.http.routers.monapp.middlewares=auth-basique"
```

⚠️ Les `$` dans les hash bcrypt doivent être **doublés** en label (échappement Docker).

### Via fileProvider (middleware réutilisable)

`dynamic/middlewares.yml` :
```yaml
http:
  middlewares:
    secure-headers:
      headers:
        stsSeconds: 63072000
        stsIncludeSubdomains: true
        stsPreload: true
        contentTypeNosniff: true
        frameDeny: true
        browserXssFilter: true
        referrerPolicy: "strict-origin-when-cross-origin"

    rate-limit-default:
      rateLimit:
        average: 100
        burst: 200
        period: 1s
```

Application sur un router :
```yaml
labels:
  - "traefik.http.routers.monapp.middlewares=secure-headers@file,rate-limit-default@file"
```

## Le chaînage : ordre = critique

Les middlewares s'appliquent **dans l'ordre déclaré**, séparés par des virgules. L'ordre change tout :

### Exemple 1 — Auth avant rate limit
```yaml
middlewares=authelia@docker,rate-limit@file
```
→ Les requêtes non authentifiées sont **rejetées avant** d'être comptées par le rate limit. Les bots sans auth ne consomment pas ton quota.

### Exemple 2 — Rate limit avant auth
```yaml
middlewares=rate-limit@file,authelia@docker
```
→ Le rate limit s'applique **avant** l'auth. Tu protèges Authelia elle-même contre un brute-force.

Les deux sont valides selon ce que tu protèges. Pour la plupart des cas, **rate limit en premier** est préférable : ça protège tout ce qui suit.

### Exemple 3 — Redirect avant tout
```yaml
middlewares=redirect-www-to-apex@file,authelia@docker
```
→ La redirection se fait **avant** de demander l'auth. Sinon tu authentifies sur `www.example.com` puis tu rediriges, perdant la session.

## Le pattern `chain` (groupement)

Quand tu réutilises la même séquence partout, créer une **chain** évite la duplication :

```yaml
# dynamic/middlewares.yml
http:
  middlewares:
    default-protected:
      chain:
        middlewares:
          - secure-headers
          - rate-limit-default
          - authelia
```

Puis sur le router :
```yaml
labels:
  - "traefik.http.routers.monapp.middlewares=default-protected@file"
```

C'est plus DRY et plus lisible. Quand tu veux changer l'ordre ou ajouter un middleware partout, tu modifies **un seul endroit**.

## Suffixes de provider : indispensables

Comme vu dans la fiche [Providers](./02-providers-static-dynamic.md) :

- `middleware-X@docker` → cherche `X` parmi les middlewares Docker
- `middleware-X@file` → cherche `X` parmi les middlewares fileProvider
- Sans suffixe → même provider que le router qui le référence

🔑 **Toujours suffixer** quand on utilise un middleware d'un provider différent. C'est la cause n°1 de "le middleware n'est pas appliqué".

## Comment debug un middleware qui ne s'applique pas

1. **Dashboard Traefik** (`https://traefik.example.com/dashboard/#/http/middlewares`) — vérifier que le middleware existe avec le bon nom et le bon provider.

2. **Vérifier le router** dans le dashboard → onglet "Middlewares" : la chaîne attendue doit être listée. Si elle ne l'est pas, le label `middlewares=` est mal écrit.

3. **Logs Traefik** en mode DEBUG temporaire :
   ```yaml
   log:
     level: DEBUG
   ```
   Tu verras `Adding middleware X to router Y` au démarrage. Pas de log = pas chargé.

4. **Suffixe manquant** : c'est la cause la plus fréquente. Tu déclares en fileProvider mais tu référence sans `@file`.

5. **Conflit de noms** : deux middlewares du même nom dans deux providers → toujours suffixer.

Voir aussi la [fiche méthode de debug](../methodes/traefik-debug-router-middleware.md) pour le workflow complet.

## Middlewares vs plugins

Traefik a en plus un système de **plugins** (chargés en config statique, dans `experimental.plugins`). Le plus connu en homelab est le **CrowdSec bouncer**. Techniquement ils s'utilisent comme des middlewares :

```yaml
labels:
  - "traefik.http.routers.monapp.middlewares=crowdsec-bouncer@file"
```

Mais ils sont déclarés à part dans la config statique. C'est essentiellement le même concept, juste un autre canal d'extension.

## À retenir

- Les middlewares **s'enchaînent dans l'ordre** déclaré — l'ordre change le comportement.
- Un middleware peut **court-circuiter** la chaîne (auth refusée → 401 immédiat, le backend ne reçoit rien).
- **Toujours suffixer** `@docker` ou `@file` pour éviter les surprises.
- Pour réutiliser une séquence : utiliser `chain`.
- Middleware spécifique à un service → labels Docker. Middleware partagé → fileProvider.

## Pour aller plus loin

- [Méthode : Forward auth avec Authelia](../methodes/traefik-forward-auth-authelia.md)
- [Méthode : Rate limiting](../methodes/traefik-rate-limiting.md)
- [Méthode : Headers de sécurité](../methodes/traefik-headers-securite.md)
- Catalogue officiel : [Traefik middlewares](https://doc.traefik.io/traefik/middlewares/overview/)
