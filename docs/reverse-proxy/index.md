# Reverse proxy & routage

Le reverse proxy est le point d'entrée HTTP/HTTPS de la plupart des homelabs : il termine TLS, route les requêtes vers les bons backends, applique de l'authentification, du rate limiting, des headers de sécurité. Ce sujet entre dans le détail de **Traefik v3** (le reverse proxy le plus utilisé en environnement Docker) et des situations concrètes qu'on rencontre derrière lui.

Les fondamentaux ("qu'est-ce qu'un reverse proxy") sont supposés acquis — ce sujet vise une compréhension opérationnelle approfondie.

## Parcours suggéré

Si tu connais déjà Traefik en surface mais que tu veux comprendre ce qui se passe vraiment :

1. [Anatomie d'une requête dans Traefik](./notions/01-anatomie-requete-traefik.md) — la base de tout debug
2. [Providers statiques vs dynamiques](./notions/02-providers-static-dynamic.md) — où mettre quelle config
3. [Middlewares — concept et chaînage](./notions/03-middlewares.md)
4. [Service discovery & labels Docker](./notions/04-service-discovery-labels.md)
5. [Headers HTTP et X-Forwarded-*](./notions/05-headers-x-forwarded.md) — source classique de bugs

## Fiches notions

| Fiche | À comprendre avant de… |
|-------|------------------------|
| [01 — Anatomie d'une requête dans Traefik](./notions/01-anatomie-requete-traefik.md) | Debug un router qui ne match pas, lire les logs |
| [02 — Providers statiques vs dynamiques](./notions/02-providers-static-dynamic.md) | Décider où mettre chaque morceau de config |
| [03 — Middlewares — concept et chaînage](./notions/03-middlewares.md) | Configurer auth, rate limit, headers |
| [04 — Service discovery & labels Docker](./notions/04-service-discovery-labels.md) | Exposer un service via Docker labels |
| [05 — Headers HTTP et X-Forwarded-*](./notions/05-headers-x-forwarded.md) | Diagnostiquer une app qui ne voit pas la bonne IP client |

## Fiches méthodes

| Méthode | Cas d'usage |
|---------|-------------|
| [Forward auth avec Authelia](./methodes/traefik-forward-auth-authelia.md) | Protéger une app sans login natif (Sonarr, Radarr, dashboards…) |
| [Rate limiting](./methodes/traefik-rate-limiting.md) | Protéger une API publique ou un endpoint sensible |
| [Headers de sécurité (HSTS, CSP…)](./methodes/traefik-headers-securite.md) | Renforcer la sécurité côté navigateur sans toucher au backend |
| [Redirections (HTTP→HTTPS, www, paths)](./methodes/traefik-redirections.md) | Migrations d'URLs, canonicalisation |
| [Diagnostiquer un router ou middleware](./methodes/traefik-debug-router-middleware.md) | Le router est listé mais ne match pas, le middleware ne s'applique pas |
| [Sécuriser le dashboard Traefik](./methodes/traefik-dashboard-securise.md) | Accéder au dashboard sans l'exposer publiquement |

## À ajouter plus tard

- [ ] Reverse proxy vs load balancer vs API gateway vs ingress (notion vocabulaire)
- [ ] Sticky sessions et affinités (méthode)
- [ ] Healthchecks et load balancing entre replicas (méthode)
- [ ] Exposer un service externe (non-Docker) via fileProvider (méthode)
- [ ] Routing rules avancées : Headers(), Query(), expressions composées (notion approfondie)
- [ ] Plugins Traefik (notion + méthode pour CrowdSec bouncer)
- [ ] Observabilité : access logs, métriques Prometheus, tracing (méthode)
