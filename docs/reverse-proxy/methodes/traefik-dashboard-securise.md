# Méthode — Sécuriser le dashboard Traefik

> **Type** : Méthode · **Outil** : Traefik v3 · **Difficulté** : ⭐ Débutant

## Quand l'utiliser

Tu veux accéder au dashboard Traefik (vue d'ensemble routers/services/middlewares, indispensable pour le debug — cf. fiche dédiée) **sans l'exposer publiquement sans protection**. Le dashboard contient en effet une vue complète de ton infrastructure interne (noms d'hôtes, certs, middlewares de sécurité), donc une cible privilégiée.

🔒 **Le dashboard ne doit jamais être accessible publiquement sans auth.** L'option `api.insecure: true` ouvre l'API sur le port 8080 sans aucune authentification — interdite hors localhost/dev.

## Trois stratégies, par ordre de sécurité

| Stratégie | Sécurité | Praticité | Quand utiliser |
|-----------|----------|-----------|----------------|
| 1. Tailscale-only (pas exposé) | 🟢 Excellente | 🟢 Bonne | Setup homelab solo |
| 2. Authelia forward auth | 🟢 Bonne | 🟢 Excellente | Tu utilises déjà Authelia |
| 3. Basic auth | 🟡 Acceptable | 🟢 Excellente | Pas d'Authelia, besoin rapide |

## Stratégie 1 — Tailscale-only

Le dashboard n'est accessible que via le VPN Tailscale. Aucune exposition publique. C'est l'approche recommandée pour un homelab où Tailscale est déjà en place.

### Configuration

Dans `traefik.yml` (statique), activer l'API en mode normal (pas `insecure`) :

```yaml
api:
  dashboard: true
  insecure: false
```

Et déclarer un entrypoint **dédié** qui écoute sur l'IP Tailscale du serveur :

```yaml
entryPoints:
  websecure:
    address: ":443"
  # Entrypoint Tailscale-only pour le dashboard
  traefik-dashboard:
    address: "100.103.215.106:9443"
```

⚠️ L'IP `100.103.215.106` est ton IP Tailscale. Adapter. Bind sur l'IP Tailscale **uniquement** → l'interface publique n'a rien sur 9443.

Dans le `docker-compose.yml` de Traefik, ne **PAS** mapper le port publiquement :
```yaml
ports:
  - "80:80"
  - "443:443"
  # PAS de "9443:9443" — le bind sur l'IP Tailscale est dans network=host
  #     mais avec network bridge classique, c'est différent. Cf. note ci-dessous.
```

💡 **Note importante sur le binding** : avec un container Docker en mode `bridge` (le défaut), bind sur une IP de l'hôte demande de passer le container en `network_mode: host`, ou d'utiliser un autre mécanisme. Plus simple en pratique : exposer le dashboard sur un **router avec rule + IP whitelist** (voir stratégie 2 ou 3).

Approche pragmatique alternative — Tailscale + label IP whitelist :

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.dashboard.rule=Host(`traefik.example.com`)"
  - "traefik.http.routers.dashboard.entrypoints=websecure"
  - "traefik.http.routers.dashboard.tls=true"
  - "traefik.http.routers.dashboard.tls.certresolver=myresolver"
  - "traefik.http.routers.dashboard.service=api@internal"
  - "traefik.http.routers.dashboard.middlewares=tailscale-only@file"

# dynamic/middlewares.yml
http:
  middlewares:
    tailscale-only:
      ipAllowList:
        sourceRange:
          - "100.64.0.0/10"   # le range Tailscale (CGNAT)
```

Le router est techniquement public, mais le middleware `ipAllowList` rejette toute IP qui n'est pas Tailscale. Aucune authentification → la confiance est dans l'appartenance au VPN.

## Stratégie 2 — Authelia forward auth

Si tu as déjà Authelia en place, c'est la solution la plus naturelle.

### Configuration

`traefik.yml` :
```yaml
api:
  dashboard: true
  insecure: false
```

Dans `docker-compose.yml` de Traefik, le router pour le dashboard (sur Traefik lui-même via labels) :
```yaml
services:
  traefik:
    # ...
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.dashboard.rule=Host(`traefik.example.com`)"
      - "traefik.http.routers.dashboard.entrypoints=websecure"
      - "traefik.http.routers.dashboard.tls=true"
      - "traefik.http.routers.dashboard.tls.certresolver=myresolver"
      - "traefik.http.routers.dashboard.service=api@internal"
      - "traefik.http.routers.dashboard.middlewares=authelia@docker"
```

Le service spécial `api@internal` est l'API intégrée de Traefik qui sert le dashboard. C'est lui qu'il faut référencer (pas un service Docker).

Côté Authelia, ajouter une règle 2FA pour ce domaine :
```yaml
# Authelia configuration.yml
access_control:
  rules:
    - domain: "traefik.example.com"
      policy: two_factor
      subject: "user:pezd"
```

Cf. fiche [Forward auth avec Authelia](./traefik-forward-auth-authelia.md).

### Avantages
- Login + 2FA centralisés
- Si tu changes ton mot de passe Authelia, ça s'applique partout
- Logs d'accès centralisés

### Inconvénient
- Si Authelia est down, tu perds l'accès au dashboard → utile justement quand tu debug. Garder une voie de secours (Tailscale, basic auth fallback).

## Stratégie 3 — Basic auth

Pas d'Authelia ou besoin rapide. HTTP basic auth est limité mais simple.

### Étape 1 — Générer le hash du mot de passe

Avec `htpasswd` (paquet `apache2-utils` sur Debian/Ubuntu) :
```bash
htpasswd -nbB admin "monMotDePasseSolide"
```
- `-n` : output sur stdout
- `-b` : password sur la ligne de commande (pas interactif — éviter en prod, l'historique shell le garde)
- `-B` : bcrypt (recommandé)

Sortie :
```
admin:$2y$05$abcd1234...
```

⚠️ Mieux : sans `-b` pour ne pas mettre le mot de passe en clair dans l'historique :
```bash
htpasswd -nB admin
```

### Étape 2 — Déclarer le middleware

En labels sur Traefik (échapper les `$` en `$$`) :
```yaml
services:
  traefik:
    labels:
      # Middleware basic auth
      - "traefik.http.middlewares.dashboard-auth.basicauth.users=admin:$$2y$$05$$abcd1234..."

      # Router dashboard
      - "traefik.enable=true"
      - "traefik.http.routers.dashboard.rule=Host(`traefik.example.com`)"
      - "traefik.http.routers.dashboard.entrypoints=websecure"
      - "traefik.http.routers.dashboard.tls=true"
      - "traefik.http.routers.dashboard.tls.certresolver=myresolver"
      - "traefik.http.routers.dashboard.service=api@internal"
      - "traefik.http.routers.dashboard.middlewares=dashboard-auth"
```

⚠️ Pas de `@docker` ici parce que le middleware est sur le même container. Si tu déplaces le middleware en fileProvider, ajouter `@file`.

🔒 Ne **jamais** committer le hash bcrypt en clair dans un repo public. Utiliser SOPS pour le secret ou passer par fileProvider avec fichier chiffré.

### Étape 3 — Vérifier

```bash
curl -I https://traefik.example.com/dashboard/
# HTTP/2 401
# www-authenticate: Basic realm="..."

curl -I -u admin:monMotDePasseSolide https://traefik.example.com/dashboard/
# HTTP/2 200
```

### Inconvénients du basic auth
- Pas de 2FA
- Le mot de passe est transmis à chaque requête (mais via HTTPS, donc OK)
- Pas de logout (le navigateur garde les credentials jusqu'à fermeture)
- Pas de rotation facile (changer un mot de passe = redéployer Traefik)

## Combiner plusieurs protections

Pour une sécurité maximum, combiner :

```yaml
labels:
  - "traefik.http.routers.dashboard.middlewares=tailscale-only@file,authelia@docker"
```

= dans le VPN Tailscale **ET** authentifié par Authelia. Surtout utile pour un dashboard qui sort un peu — tu peux l'ouvrir publiquement avec confiance.

## Sécuriser l'API en plus du dashboard

`api@internal` expose à la fois le dashboard ET les endpoints JSON (`/api/http/routers`, etc.). Une fois protégé, l'API l'est aussi.

⚠️ Ne **JAMAIS** utiliser `api.insecure: true` en production :
```yaml
api:
  insecure: true   # ← OUVRE l'API sur :8080 SANS AUTH
```
C'est uniquement pour du dev local.

## Désactiver complètement le dashboard

Si tu n'en as pas besoin (rare) :
```yaml
api:
  dashboard: false
```

Tu perds l'outil de debug principal — déconseillé.

## Pièges fréquents

| Symptôme | Cause |
|----------|-------|
| 404 sur le dashboard | `service=api@internal` oublié dans le router |
| Page blanche | URL sans `/` final (`/dashboard` au lieu de `/dashboard/`) |
| Basic auth rejette le mot de passe correct | `$` non doublés dans le hash bcrypt |
| Authelia redirige en boucle pour le dashboard | Pas mettre le middleware sur Authelia elle-même (cf. fiche dédiée) |
| Le dashboard est accessible sans auth | Tu as `api.insecure: true` quelque part — chercher dans `traefik.yml` ET les flags CLI |
| 401 même avec les bons credentials Authelia | `traefik.example.com` pas dans `access_control` côté Authelia, ou règle qui bypasse |

## À retenir

- **Ne jamais** activer `api.insecure: true` en prod.
- Trois stratégies : Tailscale-only, Authelia, basic auth — combinables.
- `service=api@internal` est le service spécial pour le dashboard.
- Le dashboard est accessible sur `/dashboard/` (slash final obligatoire).
- En basic auth via label : doubler les `$` du hash bcrypt.

## Voir aussi

- [Méthode : Forward auth avec Authelia](./traefik-forward-auth-authelia.md)
- [Méthode : Diagnostiquer un router ou middleware](./traefik-debug-router-middleware.md)
- Documentation : [Traefik API & Dashboard](https://doc.traefik.io/traefik/operations/api/)
