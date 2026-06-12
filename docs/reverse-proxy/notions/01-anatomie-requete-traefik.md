# 01 — Anatomie d'une requête dans Traefik

> **Type** : Notion · **Sujet** : Reverse proxy · **Prérequis** : Aucun (mais avoir déjà manipulé Traefik aide)

## En une phrase

Une requête HTTP qui arrive sur Traefik traverse une **chaîne d'étapes ordonnées** — entrypoint → router → middleware(s) → service → backend — chacune avec un rôle précis. Maîtriser cette chaîne, c'est savoir où regarder quand quelque chose ne marche pas.

## Le flow complet

```
Client (navigateur, curl, etc.)
   │
   │  HTTP/HTTPS sur :80 ou :443
   ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. EntryPoint (ex: websecure sur :443)                      │
│    - Reçoit la connexion TCP                                │
│    - Termine TLS (cert servi via certresolver myresolver,    │
│      ou via fileProvider)                                   │
│    - Lit le SNI pour décider quel cert présenter            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Router                                                   │
│    - Évalue les règles (Host(`x`), PathPrefix(`/y`), …)     │
│    - Sélectionne le router dont la rule matche              │
│    - Priorise selon la spécificité ou le poids `priority`   │
│    - Vérifie tls (cert OK pour ce hostname)                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Middlewares (chaîne ordonnée)                            │
│    - Exécutés dans l'ordre déclaré                          │
│    - Peuvent : modifier la requête, l'arrêter, ajouter      │
│      des headers, rediriger, authentifier, rate-limiter...  │
│    - Si un middleware répond (auth refusée, rate limit hit),│
│      la requête s'arrête ici                                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Service                                                  │
│    - Représente la cible (un ou plusieurs backends)         │
│    - Configure le load balancing si plusieurs replicas      │
│    - Gère les healthchecks éventuels                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Backend (ton conteneur, ton serveur)                     │
│    - Reçoit la requête transformée                          │
│    - Voit Traefik comme client (sauf si X-Forwarded-*       │
│      configurés et lus côté backend)                        │
└─────────────────────────────────────────────────────────────┘
```

La réponse remonte le chemin inverse, et certains middlewares peuvent aussi modifier la réponse (ajout de headers de sécurité par exemple).

## Étape par étape — détails utiles pour debug

### 1. EntryPoints

Définis dans la config **statique** (`traefik.yml`). C'est le port + protocole d'écoute. Un homelab typique a :

```yaml
entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https
          permanent: true
  websecure:
    address: ":443"
```

- `web` (port 80) ne sert qu'à rediriger vers HTTPS
- `websecure` (port 443) reçoit tout le trafic réel

⚠️ Si ton router ne précise pas `entrypoints: [websecure]`, il écoute par défaut sur **tous** les entrypoints, ce qui peut créer des comportements surprenants (la même rule matche sur `web` qui redirige, puis re-match sur `websecure` après redirect).

### 2. Routers

Définis en **config dynamique** (labels Docker dans ton cas, ou fileProvider). C'est l'élément clé pour comprendre **où va une requête**.

Anatomie d'un router via labels :
```yaml
labels:
  - "traefik.http.routers.MYROUTER.rule=Host(`app.example.com`)"
  - "traefik.http.routers.MYROUTER.entrypoints=websecure"
  - "traefik.http.routers.MYROUTER.tls=true"
  - "traefik.http.routers.MYROUTER.tls.certresolver=myresolver"
  - "traefik.http.routers.MYROUTER.middlewares=auth@docker,headers@docker"
  - "traefik.http.routers.MYROUTER.service=MYSERVICE"  # optionnel si nommage cohérent
```

**Évaluation des rules** : Traefik essaie chaque router et garde celui qui matche. Si plusieurs matchent, le **plus spécifique gagne** (ou celui avec `priority` le plus haut). Plus la rule a de contraintes (Host + PathPrefix + Headers), plus elle est prioritaire.

💡 Quand deux routers se chevauchent (ex. l'un sur `Host('a.com')`, l'autre sur `Host('a.com') && PathPrefix('/api')`), le second prend les requêtes `/api/*` et le premier prend le reste.

### 3. Middlewares

Détaillé dans la [fiche dédiée](./03-middlewares.md). Important à comprendre ici :

- Les middlewares sont **ordonnés** dans le label `middlewares=`. L'ordre compte.
- Un middleware peut **court-circuiter** la chaîne : rate limit hit → 429, auth refusée → 401/302, etc. Le service ne reçoit jamais la requête.
- La syntaxe `xxx@docker`, `xxx@file` etc. indique d'où vient le middleware (provider). Indispensable quand tu as les deux.

### 4. Services

Le service "résout" vers un ou plusieurs backends. En Docker, c'est automatique : Traefik trouve l'IP du container et le port via les labels `loadbalancer.server.port`.

```yaml
labels:
  - "traefik.http.services.MYSERVICE.loadbalancer.server.port=8080"
```

Si tu as plusieurs replicas (`docker compose up -d --scale=3`), Traefik load-balance entre eux automatiquement (round-robin par défaut).

### 5. Le backend

C'est ton container. Quelques pièges fréquents à ce niveau :

- **Le port** : `loadbalancer.server.port` doit être le port **interne** du container (pas celui exposé sur l'hôte). Pas besoin de `ports:` dans le compose si le container est sur le même réseau que Traefik.
- **L'IP source** : depuis le backend, l'IP de la requête est celle de Traefik. Pour récupérer l'IP réelle du client, le backend doit lire `X-Forwarded-For` ([fiche dédiée](./05-headers-x-forwarded.md)).
- **Le Host** : par défaut Traefik préserve le header `Host` original — utile pour les apps qui en dépendent (Nextcloud, par exemple).

## Lire ce flow dans les logs Traefik

Avec les access logs activés :

```yaml
# traefik.yml
accessLog:
  filePath: /var/log/traefik/access.log
  format: json
log:
  level: INFO
```

Chaque requête produit une ligne JSON avec, entre autres :
```json
{
  "ClientHost": "203.0.113.42",        // IP réelle du client
  "RequestHost": "app.example.com",     // Header Host
  "RouterName": "MYROUTER@docker",      // Quel router a matché
  "ServiceName": "MYSERVICE@docker",    // Quel service a été utilisé
  "ServiceURL": "http://172.18.0.5:8080", // Backend retenu
  "DownstreamStatus": 200,              // Code de retour du backend
  "Duration": 14523000                  // ns
}
```

Si `RouterName` est absent → aucun router n'a matché (404). Si `ServiceURL` est manquant → service mal résolu. Si `DownstreamStatus` est anormal → c'est ton backend qui répond mal, pas Traefik.

## Pourquoi cette compréhension est cruciale

90 % des "Traefik ne marche pas" se résument à une étape mal comprise :

| Symptôme | Étape probable |
|----------|----------------|
| 404 sur tout | Aucun router ne matche (rule fausse, entrypoint manquant) |
| 404 sur une URL précise | Une rule plus spécifique d'un autre router intercepte |
| Erreur TLS | EntryPoint, certresolver, ou SNI |
| 401/403 inattendu | Middleware d'auth dans la chaîne |
| 429 (Too Many Requests) | Middleware rate limit |
| 502 Bad Gateway | Backend injoignable (mauvais port, container down, mauvais network) |
| 504 Gateway Timeout | Backend trop lent ou healthcheck mal configuré |
| Le bon cert ne se sert pas | Router OK mais SNI / `tls.domains` mal configurés |

## À retenir

- 5 étapes ordonnées : **entrypoint → router → middlewares → service → backend**.
- **Statique** (entrypoints, certresolvers) ≠ **dynamique** (routers, middlewares, services).
- Pour debug : remonter le flow, lire les access logs, consulter le dashboard.
- Le router le plus **spécifique** gagne en cas de conflit.
- Un middleware peut court-circuiter la chaîne — le backend ne saura même pas qu'une requête a été tentée.

## Pour aller plus loin

- [Providers statiques vs dynamiques](./02-providers-static-dynamic.md)
- [Middlewares — concept et chaînage](./03-middlewares.md)
- [Méthode : Diagnostiquer un router ou middleware](../methodes/traefik-debug-router-middleware.md)
- Documentation officielle : [Traefik routing concepts](https://doc.traefik.io/traefik/routing/overview/)
