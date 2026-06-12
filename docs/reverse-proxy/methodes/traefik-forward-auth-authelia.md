# Méthode — Forward auth avec Authelia dans Traefik

> **Type** : Méthode · **Outils** : Traefik v3, Authelia · **Difficulté** : ⭐⭐ Intermédiaire

## Quand l'utiliser

Tu veux protéger une application qui **n'a pas de système de login natif robuste** (ou aucun), avec une page de connexion unifiée + 2FA, sans modifier le code de l'app. Le middleware `forwardAuth` de Traefik délègue la décision à Authelia.

Cas d'usage typiques :
- Sonarr / Radarr / Prowlarr / qBittorrent — pas d'auth nativement
- Dashboards (Homepage, Glances) qu'on veut garder privés
- Outils admin internes

## Ce que ce n'est PAS

⚠️ **Authelia n'est pas un vrai SSO** pour les apps qui ne supportent pas le forward auth. Pour les apps qui ont leur propre login (Plex, Jellyfin, Overseerr, Nextcloud, Forgejo), tu **ne dois pas** mettre Authelia devant — sinon l'utilisateur a deux écrans de login successifs, et certains clients (apps mobiles, API) ne savent pas suivre la redirection Authelia.

Règle simple :
- App **avec login natif** → laisser l'app gérer (éventuellement OIDC vers Authelia si supporté)
- App **sans login ou login faible** → Authelia en forward auth

🔒 Spécifiquement, **ne pas mettre Authelia devant Plex, Jellyfin, Overseerr** : leurs clients mobiles/TV cassent.

## Prérequis

- Traefik v3 fonctionnel avec Let's Encrypt (cf. fiche [DNS challenge](../../certificats/methodes/traefik-letsencrypt-dns-challenge.md))
- Authelia déjà déployée sur `auth.example.com` (au-delà du scope de cette fiche — voir doc Authelia)
- Tes apps tournent dans Docker avec labels Traefik

## Architecture cible

```
Client ──► Traefik (websecure)
            │
            ▼
        Router monapp (Host: monapp.example.com)
            │
            ▼
        Middleware authelia@docker (forwardAuth vers Authelia)
            │
            ├──► Authelia répond 200 + headers identité ─► Service monapp
            └──► Authelia répond 302 vers login          ─► Client redirigé
```

## Procédure

### Étape 1 — Déclarer le middleware Authelia côté Traefik

Le plus propre : déclarer **une fois** le middleware `forwardAuth`, soit comme label sur le container Authelia lui-même (provider Docker), soit en fileProvider. Ici en labels Docker (cohérent avec un setup où Authelia est containerisée) :

Dans le `docker-compose.yml` d'Authelia :
```yaml
services:
  authelia:
    image: authelia/authelia:latest
    container_name: authelia
    networks:
      - proxy-tier
    volumes:
      - ./config:/config
    env_file:
      - secrets.sops.env
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=proxy-tier"

      # Le router public Authelia (page de login accessible)
      - "traefik.http.routers.authelia.rule=Host(`auth.example.com`)"
      - "traefik.http.routers.authelia.entrypoints=websecure"
      - "traefik.http.routers.authelia.tls=true"
      - "traefik.http.routers.authelia.tls.certresolver=myresolver"
      - "traefik.http.services.authelia.loadbalancer.server.port=9091"

      # Le middleware forwardAuth réutilisable par les autres services
      - "traefik.http.middlewares.authelia.forwardauth.address=http://authelia:9091/api/verify?rd=https%3A%2F%2Fauth.example.com%2F"
      - "traefik.http.middlewares.authelia.forwardauth.trustForwardHeader=true"
      - "traefik.http.middlewares.authelia.forwardauth.authResponseHeaders=Remote-User,Remote-Groups,Remote-Name,Remote-Email"
```

Décomposition du middleware :
- `address=http://authelia:9091/api/verify?rd=...` — l'endpoint Authelia que Traefik interroge pour chaque requête. `rd=` est l'URL de redirection en cas de non-auth (la page de login Authelia, URL-encodée).
- `trustForwardHeader=true` — Authelia fait confiance aux `X-Forwarded-*` que Traefik transmet (essentiel pour qu'Authelia connaisse l'URL originale).
- `authResponseHeaders=...` — quels headers de réponse Authelia (qui contiennent l'identité de l'utilisateur authentifié) doivent être transmis au backend.

### Étape 2 — Configurer Authelia pour autoriser le domaine

Côté Authelia, dans `configuration.yml`, la section `access_control` définit qui peut accéder à quoi :

```yaml
access_control:
  default_policy: deny
  rules:
    # Pour les services protégés derrière forwardAuth
    - domain: "monapp.example.com"
      policy: two_factor      # ou one_factor
      subject: "group:admins"

    - domain: "sonarr.example.com"
      policy: two_factor
      subject: "user:pezd"

    # Bypass pour les endpoints publics éventuels
    - domain: "*.example.com"
      resources:
        - "^/api/.*"
      policy: bypass
```

⚠️ **Ordre des règles** : Authelia évalue dans l'ordre. La première qui matche gagne. Mettre les bypass plus spécifiques **avant** les règles génériques. Cf. ton learning : la règle 2FA pour ShadowBroker doit passer **avant** le `*.example.com /api bypass`.

### Étape 3 — Appliquer le middleware sur le service à protéger

Sur le container que tu veux protéger (ex. Sonarr) :

```yaml
services:
  sonarr:
    image: linuxserver/sonarr:latest
    # ...
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=proxy-tier"
      - "traefik.http.routers.sonarr.rule=Host(`sonarr.example.com`)"
      - "traefik.http.routers.sonarr.entrypoints=websecure"
      - "traefik.http.routers.sonarr.tls=true"
      - "traefik.http.routers.sonarr.tls.certresolver=myresolver"
      - "traefik.http.routers.sonarr.middlewares=authelia@docker"   # ← ici
      - "traefik.http.services.sonarr.loadbalancer.server.port=8989"
```

C'est tout — pas besoin de modifier Sonarr.

### Étape 4 — Redémarrer (pas restart)

```bash
docker compose down && docker compose up -d
```

⚠️ `docker compose restart` ne suffit pas si tu as modifié des labels — il faut `down` + `up`.

### Étape 5 — Vérifier

Aller sur `https://sonarr.example.com` dans un navigateur **non authentifié** (mode privé) :
1. Redirection automatique vers `https://auth.example.com/`
2. Login + 2FA
3. Redirection retour vers Sonarr

Vérification via les logs :
```bash
docker compose logs authelia | tail -20
docker compose logs traefik | grep sonarr
```

## Cas particuliers

### App qui supporte l'identité forwardée (rare)

Certaines apps lisent les headers `Remote-User`, `Remote-Groups` etc. transmis par Authelia et créent automatiquement le compte. Si c'est ton cas, vérifier qu'Authelia est configurée pour les envoyer (label `authResponseHeaders=Remote-User,Remote-Groups,Remote-Name,Remote-Email`) et que l'app les lit. Cas connus : Grafana, Outline.

### Authelia pour /api (à éviter par défaut)

Beaucoup d'apps exposent une API via `/api/...` qui est consommée par des clients (mobile, autres services). Ces clients ne peuvent pas suivre la redirection vers une page de login.

**Solution** : bypass de `/api` au niveau Authelia.

```yaml
# configuration.yml d'Authelia
access_control:
  rules:
    - domain: "*.example.com"
      resources:
        - "^/api/.*"
      policy: bypass
    - domain: "monapp.example.com"
      policy: two_factor
```

Le `bypass` doit être **plus haut** dans les règles que la protection générale du domaine (cf. ordre d'évaluation).

### Plusieurs niveaux d'auth pour le même service

Tu veux que tout le monde puisse voir la racine mais que `/admin` soit protégé ? Définir deux routers sur le même container :

```yaml
labels:
  # Router public (pas de middleware auth)
  - "traefik.http.routers.monapp.rule=Host(`monapp.example.com`)"
  - "traefik.http.routers.monapp.entrypoints=websecure"
  - "traefik.http.routers.monapp.tls=true"
  - "traefik.http.routers.monapp.tls.certresolver=myresolver"

  # Router /admin (avec auth) — priorité plus haute car règle plus spécifique
  - "traefik.http.routers.monapp-admin.rule=Host(`monapp.example.com`) && PathPrefix(`/admin`)"
  - "traefik.http.routers.monapp-admin.entrypoints=websecure"
  - "traefik.http.routers.monapp-admin.tls=true"
  - "traefik.http.routers.monapp-admin.middlewares=authelia@docker"

  - "traefik.http.services.monapp.loadbalancer.server.port=3000"
```

Le router le plus spécifique (avec `PathPrefix`) gagne pour les requêtes sur `/admin/*`.

## Pièges fréquents

| Symptôme | Cause |
|----------|-------|
| Redirection en boucle Authelia ↔ App | `auth.example.com` lui-même est protégé par Authelia — il ne doit **pas** avoir le middleware sur son propre router |
| 401 sans redirection vers la page login | `rd=` mal URL-encodé dans l'address forwardAuth |
| L'app ne reçoit pas Remote-User | `authResponseHeaders` mal déclaré côté Traefik OU app ne lit pas ces headers |
| Connexion OK mais 401 ensuite sur sous-requêtes | Cookie Authelia mal scopé : vérifier `default_redirection_url` et le domaine de session dans Authelia (doit être `.example.com` pour couvrir tous les sous-domaines) |
| Authelia inaccessible depuis Traefik | Pas sur le même réseau, ou `address=http://authelia:9091/...` pointe vers un mauvais hostname |
| L'app mobile ne se connecte plus après ajout d'Authelia | C'est attendu — ne pas mettre Authelia devant des apps consommées par clients tiers (Plex, Jellyfin, etc.) |
| `Trust forward header` non actif → IP fausse | Ajouter `trustForwardHeader=true` dans le middleware |

## Bonnes pratiques

- **Une déclaration de middleware** centralisée (chez Authelia ou en fileProvider), pas dupliquée sur chaque service.
- **Bypass `/api` proactif** quand un service expose une API consommée par d'autres clients.
- **Liste explicite des services protégés** dans `access_control.rules` — éviter `default_policy: two_factor` qui force l'auth partout et casse les services non-compatibles.
- **2FA obligatoire** pour les services sensibles (ne pas se contenter de `one_factor`).
- **Session domain `.example.com`** pour partager la session entre sous-domaines.

## À retenir

- `forwardAuth` délègue la décision d'auth à Authelia, par requête.
- Authelia n'est **pas** un SSO complet : ne pas mettre devant Plex/Jellyfin/Overseerr.
- Déclarer le middleware une seule fois (sur Authelia ou en fileProvider) et le réutiliser par référence (`authelia@docker`).
- Ordre des `access_control.rules` critique — bypass spécifiques **avant** les protections générales.
- Bypass `/api` quasi-systématique pour les services qui exposent une API.

## Voir aussi

- [Notion : Middlewares — concept et chaînage](../notions/03-middlewares.md)
- [Méthode : Diagnostiquer un router ou middleware](./traefik-debug-router-middleware.md)
- Documentation : [Authelia + Traefik](https://www.authelia.com/integration/proxies/traefik/)
