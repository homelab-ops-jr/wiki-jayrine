# 04 — Service discovery & labels Docker

> **Type** : Notion · **Sujet** : Reverse proxy · **Prérequis** : [Providers statiques vs dynamiques](./02-providers-static-dynamic.md)

## En une phrase

Traefik **observe en continu le socket Docker** pour découvrir automatiquement les containers, lire leurs labels, et créer routers/services correspondants. Comprendre ce mécanisme évite la moitié des "mon container ne s'affiche pas dans le dashboard".

## Le principe

```
┌─────────────────────┐         ┌─────────────────────┐
│ Traefik             │ ◄───────│ Docker daemon       │
│                     │  events │                     │
│ Lit /var/run/       │ ──────► │ containers up/down  │
│ docker.sock         │  poll   │ labels modifiés     │
└─────────┬───────────┘         └─────────────────────┘
          │
          │ pour chaque container avec traefik.enable=true:
          │   - parse labels traefik.http.routers.X.*
          │   - parse labels traefik.http.services.X.*
          │   - parse labels traefik.http.middlewares.X.*
          │
          ▼
   Routers/services/middlewares créés dynamiquement
```

C'est ce qui rend Traefik si naturel en environnement Docker : tu déposes un container avec les bons labels, **il apparaît instantanément**. Tu l'arrêtes, il disparaît.

## Configuration du provider Docker (statique)

Dans `traefik.yml` :

```yaml
providers:
  docker:
    endpoint: "unix:///var/run/docker.sock"
    exposedByDefault: false        # ← très important
    network: proxy-tier            # réseau par défaut pour les services
    watch: true                    # surveille les events Docker (true par défaut)
    swarmMode: false               # pas de Swarm
```

⚠️ **`exposedByDefault: false`** est **fortement recommandé**. Sans ça, tout container démarré sur la machine sera exposé via Traefik dès qu'il a un port. Sécurité catastrophique : un container temporaire de debug se retrouve accessible publiquement.

Avec `exposedByDefault: false`, il faut explicitement `traefik.enable=true` sur chaque container que tu veux exposer.

## Le socket Docker monté en read-only

Dans le compose de Traefik :
```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock:ro
```

🔒 Monter le socket Docker dans un container, **même en read-only**, lui donne effectivement le contrôle du daemon (et donc de la machine). En `:ro` Traefik ne peut pas créer/supprimer des containers, mais il peut lire des secrets, inspecter, observer. Garder Traefik à jour est important.

Alternative plus sécurisée : un **socket proxy** (ex. `tecnativa/docker-socket-proxy`) qui filtre les endpoints accessibles. Mention ici pour info, peu utilisé en homelab personnel.

## Anatomie d'un set de labels complet

Le minimum pour un service exposé en HTTPS avec cert Let's Encrypt :

```yaml
services:
  monapp:
    image: monapp:latest
    networks:
      - proxy-tier
    labels:
      # 1. Activation explicite (requise avec exposedByDefault=false)
      - "traefik.enable=true"

      # 2. Quel réseau Docker utiliser (utile si multi-network)
      - "traefik.docker.network=proxy-tier"

      # 3. Router
      - "traefik.http.routers.monapp.rule=Host(`monapp.example.com`)"
      - "traefik.http.routers.monapp.entrypoints=websecure"
      - "traefik.http.routers.monapp.tls=true"
      - "traefik.http.routers.monapp.tls.certresolver=myresolver"

      # 4. Service (port interne du container)
      - "traefik.http.services.monapp.loadbalancer.server.port=3000"
```

Décortiquons.

### `traefik.enable=true`

Active la prise en compte du container par Traefik. Sans ce label (et avec `exposedByDefault: false`), Traefik ignore complètement le container.

### `traefik.docker.network=proxy-tier`

Précise sur **quel réseau Docker** Traefik doit contacter le container. Indispensable si le container est sur plusieurs réseaux (cas fréquent : un app + une base de données + le réseau proxy).

Sans ce label, Traefik prend "un" des réseaux du container — souvent le mauvais (le réseau interne avec la DB), ce qui se traduit par "502 Bad Gateway" sans erreur claire.

### Le nommage `traefik.http.routers.MONAPP.X`

`MONAPP` est un **identifiant arbitraire**, mais il doit être unique entre tous les containers exposés. Convention : le nom du service Docker, ou un dérivé.

⚠️ Si deux containers ont le même nom de router, ils entrent en conflit — le dernier démarré gagne, l'autre disparaît du routage. Toujours unique.

💡 Tu peux utiliser des variables d'environnement pour générer le nom automatiquement, en YAML compose :
```yaml
labels:
  - "traefik.http.routers.${COMPOSE_PROJECT_NAME}.rule=Host(...)"
```

### `loadbalancer.server.port=3000`

Le port **interne au container** sur lequel l'application écoute. Pas le port mappé sur l'hôte.

⚠️ Confusion fréquente : si dans le compose tu as `ports: ["8080:3000"]`, Traefik utilise `3000`, pas `8080`. D'ailleurs, **pas besoin de `ports:` du tout** si Traefik est sur le même réseau que le container — le mapping de port externe devient inutile et indésirable (pourquoi exposer le port directement quand on a un reverse proxy ?).

## Le piège du multi-network

Cas typique : un service web avec une base PostgreSQL.

```yaml
services:
  monapp:
    networks:
      - proxy-tier        # avec Traefik
      - monapp-internal   # avec sa DB
    # ...

  postgres:
    networks:
      - monapp-internal   # isolé du proxy
    # ...

networks:
  proxy-tier:
    external: true
  monapp-internal:
    # interne, isolé
```

Sans `traefik.docker.network=proxy-tier`, Traefik peut essayer de joindre `monapp` via `monapp-internal` — qui n'est pas dans son scope. Résultat : pas de routage, ou 502.

🔑 **Règle** : dès qu'un container est sur **plusieurs réseaux** avec Traefik dans le set, ajouter `traefik.docker.network` explicitement.

## Ports découverts automatiquement (à éviter)

Si tu omets `loadbalancer.server.port`, Traefik essaie de deviner le port à partir des `EXPOSE` du Dockerfile. Ça marche parfois, ça échoue souvent, et c'est imprévisible :

- Une image qui expose plusieurs ports (8080 + 9090) → Traefik choisit lequel ?
- Une image qui n'expose rien → Traefik tente le 80
- Une image qui change d'expose entre versions → ton routage casse à la mise à jour

🔑 **Toujours déclarer explicitement** `loadbalancer.server.port`.

## Plusieurs routers/services sur le même container

Cas légitime : ton container expose deux interfaces (admin + API publique) sur deux ports différents. Tu peux déclarer plusieurs services :

```yaml
labels:
  - "traefik.enable=true"

  # API publique
  - "traefik.http.routers.api.rule=Host(`api.example.com`)"
  - "traefik.http.routers.api.service=api-svc"
  - "traefik.http.services.api-svc.loadbalancer.server.port=80"

  # Admin (port différent)
  - "traefik.http.routers.admin.rule=Host(`admin.example.com`)"
  - "traefik.http.routers.admin.service=admin-svc"
  - "traefik.http.routers.admin.middlewares=authelia@docker"
  - "traefik.http.services.admin-svc.loadbalancer.server.port=8081"
```

Notes :
- `traefik.http.routers.X.service=Y` désambiguïse quand router et service ont des noms différents.
- L'admin a un middleware d'auth en plus.

## Plusieurs replicas

Avec `docker compose up -d --scale monapp=3`, Traefik **load-balance automatiquement** entre les trois containers (round-robin par défaut). Aucune config supplémentaire.

Pour changer la stratégie :
```yaml
labels:
  - "traefik.http.services.monapp.loadbalancer.sticky.cookie=true"
```

## Labels les plus utilisés (cheatsheet)

| Label | Rôle |
|-------|------|
| `traefik.enable=true` | Active le container |
| `traefik.docker.network=NET` | Réseau à utiliser |
| `traefik.http.routers.X.rule=…` | Règle de routing |
| `traefik.http.routers.X.entrypoints=websecure` | Entrypoint(s) |
| `traefik.http.routers.X.tls=true` | TLS activé |
| `traefik.http.routers.X.tls.certresolver=myresolver` | Resolver ACME |
| `traefik.http.routers.X.middlewares=A@docker,B@file` | Chaîne de middlewares |
| `traefik.http.routers.X.priority=N` | Priorité explicite (défaut: spécificité de la rule) |
| `traefik.http.services.X.loadbalancer.server.port=N` | Port backend |
| `traefik.http.services.X.loadbalancer.healthcheck.path=/health` | Healthcheck |
| `traefik.http.services.X.loadbalancer.sticky.cookie=true` | Sticky sessions |

## À retenir

- Toujours `exposedByDefault: false` + `traefik.enable=true` explicite.
- Toujours `traefik.docker.network=` quand le container est multi-network.
- Toujours `loadbalancer.server.port=` explicite, pas de découverte automatique.
- Le port = port **interne** du container.
- Noms de routers uniques entre tous les containers (sinon conflit silencieux).
- Le socket Docker monté est puissant — garder Traefik à jour, considérer un socket proxy en environnement multi-tenant.

## Pour aller plus loin

- [Headers HTTP et X-Forwarded-*](./05-headers-x-forwarded.md)
- [Méthode : Diagnostiquer un router ou middleware](../methodes/traefik-debug-router-middleware.md)
- Documentation officielle : [Traefik Docker provider](https://doc.traefik.io/traefik/providers/docker/)
