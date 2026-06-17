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

## Cartes d'entraînement

### Faits & terminologie

??? question "Qu'est-ce qu'un middleware dans Traefik, en une phrase ?"
    Un composant qui s'insère entre le router et le service pour **inspecter, transformer, court-circuiter ou enrichir** une requête (et parfois la réponse), sans qu'on ait à modifier le backend.

??? question "Quel middleware permet de déléguer l'authentification à un service externe comme Authelia ?"
    `forwardAuth`.
    
    Il transmet la requête à l'URL de l'auth provider, qui répond 200 (laisse passer) ou 401/403 (bloque). C'est ce qui rend Authelia, Authentik et OAuth2-proxy compatibles avec Traefik.

??? question "Quel middleware filtre par IP source dans Traefik v3 ?"
    `ipAllowList`.
    
    En Traefik v2 il s'appelait `ipWhiteList` — le nom a changé en v3 par souci d'inclusivité du vocabulaire.

??? question "Quel middleware limite le nombre de requêtes par seconde par source ?"
    `rateLimit`.

??? question "Quel middleware limite le nombre de requêtes simultanées (en vol) ?"
    `inFlightReq`.
    
    Différent de `rateLimit` : `rateLimit` compte les requêtes sur une fenêtre de temps, `inFlightReq` compte celles qui sont en cours de traitement à l'instant T.

??? question "Quel middleware court-circuite la chaîne si le backend renvoie trop d'erreurs ?"
    `circuitBreaker`.
    
    Pattern classique pour protéger un backend en détresse — au lieu de continuer à le marteler, Traefik renvoie directement une erreur le temps qu'il récupère.

??? question "Quel middleware permet d'ajouter ou modifier des headers HTTP ?"
    `headers`.
    
    C'est celui qu'on utilise pour HSTS, CSP, CORS, X-Frame-Options et tous les headers de sécurité.

??? question "Quel middleware redirige HTTP vers HTTPS ?"
    `redirectScheme`.
    
    Variante pour des redirections plus complexes (regex) : `redirectRegex`.

??? question "Quel middleware permet de compresser les réponses en gzip ou Brotli ?"
    `compress`.

??? question "Quel middleware permet de réessayer automatiquement en cas d'erreur backend ?"
    `retry`.
    
    À manier avec précaution : retry sur une opération non-idempotente (POST par exemple) peut créer des doublons côté backend.

??? question "Quel middleware permet de regrouper plusieurs middlewares sous un nom unique réutilisable ?"
    `chain`.
    
    Pattern essentiel quand tu réutilises la même séquence de middlewares sur plusieurs routers.

??? question "Quel suffixe utilise-t-on pour référencer un middleware déclaré via labels Docker ?"
    `@docker`.
    
    Exemple : `middlewares=auth-basique@docker`.

??? question "Quel suffixe utilise-t-on pour référencer un middleware déclaré en fileProvider ?"
    `@file`.
    
    Exemple : `middlewares=secure-headers@file`.

??? question "Combien de middlewares natifs offre Traefik v3, à l'ordre de grandeur ?"
    Une quarantaine.

### Concepts

??? question "Quelles sont les 4 actions principales qu'un middleware peut effectuer sur la requête ?"
    1. **Modifier la requête** avant transmission au backend (ajouter un header, réécrire le path).
    2. **Modifier la réponse** au retour (ajouter HSTS, compresser).
    3. **Court-circuiter** la chaîne (auth refusée, rate limit atteint, IP blacklistée — le backend ne reçoit rien).
    4. **Rediriger** (3xx vers HTTPS, www vers apex, etc.).

??? question "Pourquoi l'ordre des middlewares dans une chaîne est-il critique ?"
    Parce que chaque middleware peut **court-circuiter** la chaîne. Tout ce qui vient après un middleware bloquant n'est jamais évalué.
    
    Exemple : `auth,rateLimit` rejette les requêtes non authentifiées **avant** qu'elles consomment du quota. `rateLimit,auth` fait l'inverse : le rate limit protège l'auth elle-même contre un brute-force.
    
    Les deux sont valides selon ce que tu veux protéger en priorité.

??? question "Auth avant rate limit, ou rate limit avant auth — quel est l'effet pratique de chaque ordre ?"
    **`auth,rateLimit`** : les requêtes non authentifiées sont rejetées d'abord, donc les bots sans auth ne consomment pas ton quota. Tu protèges le backend.
    
    **`rateLimit,auth`** : le rate limit s'applique avant l'auth, donc Authelia elle-même est protégée contre un brute-force. Tu protèges l'auth.
    
    Choix dépendant du contexte : pour un service standard, auth d'abord ; si tu veux blinder ton SSO, rate limit d'abord.

??? question "Pourquoi placer un redirect (HTTP→HTTPS, www→apex) avant l'authentification dans la chaîne ?"
    Sinon tu authentifies sur l'URL "incorrecte" (par exemple `www.example.com`) **puis** tu rediriges, ce qui fait perdre la session côté client (les cookies sont liés au domaine).
    
    Ordre correct : on canonicalise l'URL d'abord, on authentifie ensuite — la session est attachée à la bonne origine d'emblée.

??? question "Qu'est-ce qu'un middleware `chain`, et quand l'utiliser ?"
    Un middleware qui en regroupe plusieurs sous un nom unique. Tu déclares `default-protected` = `secure-headers + rate-limit + authelia`, puis tu n'as plus qu'à appliquer `default-protected@file` partout.
    
    Avantage : un seul endroit à modifier quand tu veux changer la séquence pour tous tes services. Pattern DRY indispensable au-delà de 3-4 services.

??? question "Quelle est la différence entre déclarer un middleware via labels Docker et en fileProvider ? Quand choisir l'un ou l'autre ?"
    **Labels Docker** : le middleware est défini *avec* le service qui l'utilise. Pratique pour des middlewares spécifiques à un seul container (un `basicAuth` propre à cette app).
    
    **fileProvider** (YAML statique) : le middleware est défini centralement et **réutilisable** par n'importe quel router. Indispensable pour `secure-headers`, `rate-limit-default`, `authelia` — tout ce qui est partagé.
    
    Règle simple : spécifique à un service → labels. Partagé entre plusieurs → fileProvider.

??? question "Quelle est la différence (et la similitude) entre middlewares natifs et plugins Traefik ?"
    **Similitude** : ils s'utilisent identiquement dans la chaîne (`middlewares=crowdsec-bouncer@file`).
    
    **Différence** : les middlewares natifs sont compilés dans Traefik, disponibles immédiatement. Les plugins sont chargés au démarrage depuis un dépôt (déclarés dans `experimental.plugins` de la config statique) — c'est ainsi qu'on intègre des extensions tierces comme le **CrowdSec bouncer**.

??? question "Que se passe-t-il si un middleware d'authentification refuse la requête ? Le backend reçoit-il quelque chose ?"
    **Non, rien.** Le middleware court-circuite la chaîne et renvoie directement 401 ou 403 au client. Tout ce qui est en aval (autres middlewares + service) n'est jamais évalué.
    
    C'est une propriété essentielle : ton backend est totalement isolé des requêtes non authentifiées, même au niveau réseau.

??? question "Pourquoi les `$` dans un hash bcrypt doivent-ils être doublés dans un label Docker ?"
    Parce que Docker Compose **interprète `$VAR` comme une substitution de variable d'environnement**. Si tu mets `$2y$05$...` brut, Compose voit `$2y`, `$05`, etc. comme des variables non définies et les remplace par des chaînes vides — ton hash devient inutilisable.
    
    `$$` est la séquence d'échappement qui produit un `$` littéral après interprétation.

### Diagnostic

??? question "Tu as déclaré un middleware via fileProvider mais il n'a aucun effet sur ton router Docker. Quelle est la cause la plus probable ?"
    Le **suffixe `@file` manquant** dans la référence côté router.
    
    Sans suffixe, Traefik cherche le middleware dans le même provider que le router (donc `@docker`) — il ne le trouve pas, et applique silencieusement *rien*. Cause n°1 de "le middleware ne s'applique pas".

??? question "Tu as un router et un middleware, mais le dashboard Traefik ne liste pas le middleware sur le router. Que vérifier ?"
    1. Le label `middlewares=` du router contient-il bien le nom attendu, avec le bon suffixe (`@docker` ou `@file`) ?
    2. Le middleware existe-t-il bien dans le dashboard sous l'onglet HTTP > Middlewares ?
    3. En dernier recours, passer Traefik en log DEBUG temporairement : tu verras `Adding middleware X to router Y` au démarrage si tout est OK.

??? question "Tu as deux middlewares du même nom dans deux providers différents. Comment éviter le conflit ?"
    **Toujours suffixer** la référence avec `@docker` ou `@file` selon le provider visé.
    
    Sans suffixe, Traefik prend celui du même provider que le router — comportement implicite, source de bugs subtils. Avec suffixe, l'intention est explicite et lisible.

??? question "Tu veux protéger Authelia elle-même contre un brute-force. Quelle architecture de chaîne mettre en place ?"
    Placer le **rate limit avant l'auth** : `middlewares=rate-limit@file,authelia@docker`.
    
    Comme ça, même les tentatives de login répétées sont jugulées avant d'atteindre Authelia. À combiner idéalement avec CrowdSec qui bannira les IPs récidivistes au niveau Traefik.

??? question "Tu veux que ton quota de rate limit ne soit pas consommé par des bots non authentifiés. Quelle architecture de chaîne ?"
    Placer l'**auth avant le rate limit** : `middlewares=authelia@docker,rate-limit@file`.
    
    Les requêtes non authentifiées sont rejetées d'abord, donc ne comptent jamais dans le quota. Le rate limit ne protège que les vrais utilisateurs.

??? question "Comment activer le log DEBUG temporairement pour vérifier que Traefik charge bien tes middlewares ?"
    Dans la config statique (`traefik.yml` ou flags) :
    
    ​```yaml
    log:
      level: DEBUG
    ​```
    
    Puis redémarrer Traefik et chercher dans les logs des lignes du type `Adding middleware X to router Y`. Penser à **repasser en INFO** ensuite — DEBUG est très bavard et pollue les logs.

??? question "Où vérifier dans l'UI Traefik qu'un middleware est bien attaché à un router ?"
    Dashboard Traefik → **HTTP > Routers** → cliquer sur le router concerné → onglet **Middlewares**.
    
    La chaîne complète y est listée dans l'ordre d'application. Si elle ne correspond pas à ce que tu attends, le label `middlewares=` côté config est mal écrit (typo, suffixe oublié, séparateur incorrect).
