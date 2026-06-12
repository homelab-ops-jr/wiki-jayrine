# 02 — Providers : configuration statique vs dynamique

> **Type** : Notion · **Sujet** : Reverse proxy · **Prérequis** : [Anatomie d'une requête](./01-anatomie-requete-traefik.md)

## En une phrase

Traefik a **deux types de configuration** : la **statique** (lue uniquement au démarrage, définit l'infrastructure du proxy) et la **dynamique** (rechargée à chaud, définit le routage en temps réel). Confondre les deux est l'erreur n°1 quand on configure Traefik.

## La séparation

```
┌──────────────────────────────────────────────────────────────┐
│ Configuration STATIQUE                                       │
│ - Lue une seule fois au démarrage                            │
│ - Modification = redémarrage Traefik obligatoire             │
│ - Définit "comment Traefik fonctionne"                       │
│                                                              │
│ Source unique : traefik.yml (ou args CLI, ou env vars)       │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ Configuration DYNAMIQUE                                      │
│ - Rechargée automatiquement à chaque changement              │
│ - Modification = effet immédiat (sans restart)               │
│ - Définit "ce que Traefik fait des requêtes"                 │
│                                                              │
│ Sources multiples (les "providers") :                        │
│   - Docker (labels)                                          │
│   - File (fichiers YAML/TOML watched)                        │
│   - Kubernetes (CRDs ou Ingress)                             │
│   - Consul, etcd, Redis, etc.                                │
└──────────────────────────────────────────────────────────────┘
```

## Ce qui va dans la config statique

`traefik.yml` (typiquement monté en `:ro` dans le container) :

```yaml
# Entrypoints (les ports d'écoute)
entryPoints:
  web:
    address: ":80"
  websecure:
    address: ":443"

# Providers (les sources de config dynamique)
providers:
  docker:
    endpoint: "unix:///var/run/docker.sock"
    exposedByDefault: false
    network: proxy-tier
  file:
    directory: /etc/traefik/dynamic
    watch: true

# Certificats Let's Encrypt (ACME)
certificatesResolvers:
  myresolver:
    acme:
      email: admin@example.com
      storage: /letsencrypt/acme.json
      dnsChallenge:
        provider: ovh

# API et dashboard
api:
  dashboard: true

# Logs
log:
  level: INFO
accessLog:
  filePath: /var/log/traefik/access.log

# Plugins (CrowdSec bouncer, etc.)
experimental:
  plugins:
    bouncer:
      moduleName: github.com/maxlerebourg/crowdsec-bouncer-traefik-plugin
      version: v1.x.x
```

**Tout ce qui est ici nécessite un redémarrage** pour être pris en compte :
```bash
docker compose down && docker compose up -d
# ⚠️ docker restart ne suffit pas pour relire ce fichier !
```

## Ce qui va dans la config dynamique

Tout ce qui concerne le **routage** d'une requête :

- **Routers** (rules, entrypoint, tls, middlewares)
- **Services** (backend, port, healthcheck, load balancing)
- **Middlewares** (auth, rate limit, headers, redirects, etc.)
- **TLS** : certificats statiques (fileProvider), options TLS, stores

Trois façons typiques de fournir cette config :

### Via Docker (labels)

Le plus courant en homelab. Tu déclares ton routage directement sur le container :

```yaml
services:
  monapp:
    image: monapp:latest
    networks:
      - proxy-tier
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.monapp.rule=Host(`monapp.example.com`)"
      - "traefik.http.routers.monapp.entrypoints=websecure"
      - "traefik.http.routers.monapp.tls=true"
      - "traefik.http.routers.monapp.tls.certresolver=myresolver"
      - "traefik.http.services.monapp.loadbalancer.server.port=3000"
```

Traefik observe le socket Docker et détecte les containers en temps réel. Démarrer/arrêter un container = router activé/désactivé instantanément.

### Via fileProvider (YAML déclaratif)

Pour la config qui n'est pas liée à un container : middlewares réutilisables, certificats statiques, services pointant vers des backends externes (machines hors Docker), TLS options.

`dynamic/middlewares.yml` :
```yaml
http:
  middlewares:
    secure-headers:
      headers:
        stsSeconds: 63072000
        stsIncludeSubdomains: true
        contentTypeNosniff: true
        frameDeny: true

    rate-limit:
      rateLimit:
        average: 100
        burst: 200
```

Référencé depuis un router via :
```yaml
labels:
  - "traefik.http.routers.monapp.middlewares=secure-headers@file,rate-limit@file"
```

Le suffixe `@file` est crucial — sans lui, Traefik cherche un middleware nommé `secure-headers` sur le même provider que le router (Docker), ne le trouve pas, et la requête échoue.

### Combinaison des deux

Cas courant : tu déclares des middlewares **réutilisables** en fileProvider, puis tu les appliques à tes routers Docker. C'est la pratique recommandée pour les choses qui se répètent (headers de sécu, auth Authelia, rate limit). La fiche [Headers de sécurité](../methodes/traefik-headers-securite.md) illustre ça en détail.

## Quand utiliser fileProvider plutôt que Docker labels

| Préfère **labels Docker** quand… | Préfère **fileProvider** quand… |
|----------------------------------|----------------------------------|
| Router/service propre à **un container** | Middleware **réutilisé** par plusieurs routers |
| Le service vit dans Docker | Backend hors Docker (machine bare-metal, VM) |
| Config courte et lisible inline | Config longue (CSP, plusieurs règles complexes) |
| Pas de partage entre stacks | Tu veux versionner séparément cette config |

🔑 **Règle pragmatique** : un middleware utilisé par **plus d'un** service = fileProvider. Un middleware spécifique à un service = label Docker.

## Hot reload : ce qui fonctionne, ce qui ne fonctionne pas

| Type de changement | Reload sans restart ? |
|---------------------|----------------------|
| Ajout/suppression d'un container avec labels | ✅ Instantané |
| Modification d'un label sur un container | ✅ Instantané (le container doit être recréé via `docker compose up -d`, pas `restart`) |
| Modification d'un fichier YAML dans `providers.file.directory` | ✅ Instantané (`watch: true` requis) |
| Modification de `traefik.yml` | ❌ Restart obligatoire |
| Ajout d'un nouvel entrypoint | ❌ Restart obligatoire |
| Modification d'un certresolver | ❌ Restart obligatoire |
| Variables d'environnement (`.env`, `env_file`) | ❌ `docker compose down && up`, pas `restart` |

⚠️ Le piège classique : modifier une variable dans `.env` puis `docker restart traefik`. Le `.env` n'est lu qu'au `compose up`. Toujours :
```bash
docker compose down && docker compose up -d
```

## Précédence et conflits

Si un même middleware est défini dans deux providers (par exemple `auth` en Docker et en fileProvider), tu **dois** désambiguïser avec le suffixe :

- `auth@docker` → middleware Docker
- `auth@file` → middleware fileProvider

Sans suffixe, Traefik prend celui du **même provider** que le router qui le référence. Pour éviter les surprises, prendre l'habitude de toujours suffixer.

## Anti-patterns courants

❌ **Mettre des certs Let's Encrypt en fileProvider** — utiliser un certresolver dans la config statique.

❌ **Mettre tout en fileProvider "pour la centralisation"** — la force des labels Docker est la **co-localisation** : tu modifies le service et son routage au même endroit, dans le même commit. Tu perds cette force si tout est externalisé.

❌ **Mettre des middlewares ad-hoc inline dans les labels d'un container** quand ils pourraient être réutilisés — duplication = drift à terme.

❌ **Modifier `traefik.yml` à chaud en espérant un reload** — ça ne marche pas (sauf rares exceptions). Restart explicite à chaque fois.

## À retenir

- **Statique** = `traefik.yml`, lu au démarrage, modifs = restart.
- **Dynamique** = labels Docker + fileProvider, modifs = reload auto.
- Routers/services propres à un container → **labels**.
- Middlewares partagés → **fileProvider**.
- Toujours suffixer `@docker` ou `@file` pour éviter l'ambiguïté.
- `docker restart` ne relit ni `.env` ni `traefik.yml`. Utiliser `down && up`.

## Pour aller plus loin

- [Middlewares — concept et chaînage](./03-middlewares.md)
- [Service discovery & labels Docker](./04-service-discovery-labels.md)
- Documentation officielle : [Traefik static and dynamic configuration](https://doc.traefik.io/traefik/getting-started/configuration-overview/)
