# Méthode — Redirections avec Traefik

> **Type** : Méthode · **Outil** : Traefik v3 · **Difficulté** : ⭐ Débutant

## Quand l'utiliser

- Forcer HTTP → HTTPS sur **tout** le proxy
- Rediriger `www.example.com` → `example.com` (ou l'inverse)
- Migrer une URL après refactor (`/old/path` → `/new/path`)
- Rediriger un domaine entier vers un autre

## Types de redirection — choisir le bon code HTTP

| Code | Nom | Méthode HTTP préservée ? | Permanent ? | Quand l'utiliser |
|------|-----|--------------------------|-------------|------------------|
| **301** | Moved Permanently | Non (GET) | ✅ Caché | Migration définitive d'URL |
| **302** | Found | Non (GET) | ❌ Non caché | Redirection temporaire |
| **307** | Temporary Redirect | ✅ Oui | ❌ | Comme 302 mais préserve POST/PUT |
| **308** | Permanent Redirect | ✅ Oui | ✅ | Comme 301 mais préserve POST/PUT |

🔑 **En 2026, préférer 308 sur 301** : 308 préserve la méthode HTTP, ce qui évite les surprises sur les formulaires/API. 301 reste OK pour les redirections de pages statiques (GET-only).

⚠️ **301/308 sont mis en cache par les navigateurs**, parfois pour des durées longues. Une 301 mal posée peut "coller" plusieurs jours chez tes visiteurs. En cas de doute, commencer par 302/307, puis passer en 301/308 quand stabilisé.

## Cas 1 — HTTP → HTTPS au niveau entrypoint

**LE** cas le plus fréquent. Configuration dans `traefik.yml` (statique) :

```yaml
entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https
          permanent: true   # 301
  websecure:
    address: ":443"
```

Effet : **toute** requête arrivant sur le port 80 est redirigée vers le port 443 (HTTPS), avec un 301. Tu n'as plus à gérer la redirection par service.

💡 Pour 308 au lieu de 301, c'est `permanent: true` qui contrôle (true = 301/308 selon le mode, false = 302/307). Traefik utilise 301 par défaut pour `redirections.entryPoint`. Pour forcer un 308, passer par un middleware (voir cas 2).

## Cas 2 — HTTP → HTTPS via middleware (granulaire)

Si tu veux la redirection **par router** plutôt que globale :

```yaml
# dynamic/middlewares.yml
http:
  middlewares:
    redirect-https:
      redirectScheme:
        scheme: https
        permanent: true
```

Application :
```yaml
labels:
  # Router HTTP qui redirige
  - "traefik.http.routers.monapp-http.rule=Host(`monapp.example.com`)"
  - "traefik.http.routers.monapp-http.entrypoints=web"
  - "traefik.http.routers.monapp-http.middlewares=redirect-https@file"

  # Router HTTPS qui sert vraiment
  - "traefik.http.routers.monapp.rule=Host(`monapp.example.com`)"
  - "traefik.http.routers.monapp.entrypoints=websecure"
  - "traefik.http.routers.monapp.tls=true"
  - "traefik.http.routers.monapp.tls.certresolver=myresolver"

  - "traefik.http.services.monapp.loadbalancer.server.port=3000"
```

Quasiment toujours redondant avec le cas 1 — préférer la redirection au niveau entrypoint.

## Cas 3 — www → apex (ou l'inverse)

Tu sers `example.com` et tu veux que `www.example.com` redirige dessus :

```yaml
http:
  middlewares:
    redirect-www-to-apex:
      redirectRegex:
        regex: "^https?://www\\.example\\.com/(.*)"
        replacement: "https://example.com/${1}"
        permanent: true
```

Application sur un router dédié au `www` :
```yaml
labels:
  - "traefik.http.routers.www-redirect.rule=Host(`www.example.com`)"
  - "traefik.http.routers.www-redirect.entrypoints=websecure"
  - "traefik.http.routers.www-redirect.tls=true"
  - "traefik.http.routers.www-redirect.tls.certresolver=myresolver"
  - "traefik.http.routers.www-redirect.middlewares=redirect-www-to-apex@file"
  - "traefik.http.routers.www-redirect.service=noop@internal"
```

⚠️ Notes :
- Le `service=noop@internal` est nécessaire : un router doit pointer vers un service, mais ici on n'en sert pas — la redirection arrête le flow avant. `noop@internal` est un service vide intégré.
- Il faut **un certificat couvrant `www.example.com`**. Si ton wildcard `*.example.com` ne couvre pas, ajouter `www` dans les SAN.

Pour l'inverse (apex → www) :
```yaml
http:
  middlewares:
    redirect-apex-to-www:
      redirectRegex:
        regex: "^https?://example\\.com/(.*)"
        replacement: "https://www.example.com/${1}"
        permanent: true
```

## Cas 4 — Redirection de path

Migration d'URL après un refactor :

```yaml
http:
  middlewares:
    redirect-old-path:
      redirectRegex:
        regex: "^(https?://[^/]+)/old/(.*)"
        replacement: "${1}/new/${2}"
        permanent: true
```

Application :
```yaml
labels:
  - "traefik.http.routers.monapp.middlewares=redirect-old-path@file"
```

⚠️ Si tu veux que **seul** le chemin `/old/*` redirige (et que le reste continue normalement), il faut le mettre en router spécifique :

```yaml
labels:
  # Router pour l'ancien chemin uniquement
  - "traefik.http.routers.monapp-old.rule=Host(`monapp.example.com`) && PathPrefix(`/old`)"
  - "traefik.http.routers.monapp-old.middlewares=redirect-old-path@file"
  - "traefik.http.routers.monapp-old.service=noop@internal"

  # Router général
  - "traefik.http.routers.monapp.rule=Host(`monapp.example.com`)"
  - "traefik.http.services.monapp.loadbalancer.server.port=3000"
```

Le router avec `PathPrefix` est plus spécifique → il gagne pour `/old/*`.

## Cas 5 — Redirection de domaine entier

Tu as racheté un nouveau domaine, tu veux que `old-domain.com` redirige vers `new-domain.com` :

```yaml
http:
  middlewares:
    redirect-old-domain:
      redirectRegex:
        regex: "^https?://(?:www\\.)?old-domain\\.com/(.*)"
        replacement: "https://new-domain.com/${1}"
        permanent: true
```

Router :
```yaml
labels:
  - "traefik.http.routers.olddomain-redirect.rule=Host(`old-domain.com`) || Host(`www.old-domain.com`)"
  - "traefik.http.routers.olddomain-redirect.entrypoints=websecure"
  - "traefik.http.routers.olddomain-redirect.tls=true"
  - "traefik.http.routers.olddomain-redirect.tls.certresolver=myresolver"
  - "traefik.http.routers.olddomain-redirect.middlewares=redirect-old-domain@file"
  - "traefik.http.routers.olddomain-redirect.service=noop@internal"
```

Tu auras besoin que ton certresolver émette un cert pour `old-domain.com` (ne sera pas couvert par ton wildcard `*.new-domain.com`).

## Cas 6 — Redirection conditionnelle (par header, query, etc.)

Traefik ne supporte pas nativement les redirections **conditionnelles complexes** (par exemple selon le User-Agent). Pour ça, deux options :

1. **Plusieurs routers avec des rules différentes** (si la condition peut s'exprimer en rule)
2. **Délégation au backend** (le backend reçoit la requête et redirige lui-même)

Exemple de routing par header :
```yaml
labels:
  # Si le client envoie un header particulier
  - "traefik.http.routers.monapp-mobile.rule=Host(`monapp.example.com`) && Headers(`X-Client-Type`, `mobile`)"
  - "traefik.http.routers.monapp-mobile.middlewares=redirect-to-m@file"

  - "traefik.http.routers.monapp.rule=Host(`monapp.example.com`)"
```

## Préserver le query string

`redirectRegex` préserve naturellement le query string si le pattern le capture :

```yaml
regex: "^(https?://[^/]+)/old/(.*)"
replacement: "${1}/new/${2}"
```

Visite : `https://example.com/old/page?key=value`
Redirection : `https://example.com/new/page?key=value` ✓

Si le query est dans une partie non-capturée, il est perdu — vérifier en testant avec un URL qui en contient.

## Tester une redirection

```bash
# Suivre les redirections et voir la chaîne complète
curl -ILv https://example.com 2>&1 | grep -E '< HTTP|< Location|^>'

# Voir uniquement les headers de réponse de la première redirection (pas de suivi)
curl -I http://example.com

# Sortie attendue pour HTTP → HTTPS :
# HTTP/1.1 301 Moved Permanently
# Location: https://example.com/
```

Pour tester sans cache navigateur, utiliser le mode privé ou `curl` (qui n'a pas de cache HSTS).

## Pièges fréquents

| Symptôme | Cause |
|----------|-------|
| Loop de redirection (301 → 301 → 301…) | Deux règles qui se renvoient l'une à l'autre. Vérifier dans le dashboard quels routers matchent |
| La redirection ne déclenche pas | Router HTTPS prend la priorité ou règle pas matchée. Vérifier le router actif dans access logs |
| Query string perdu | Pattern `redirectRegex` qui ne capture pas le path complet |
| Redirection en HTTP au lieu de HTTPS | `scheme: https` oublié dans le `redirectScheme` |
| Cache navigateur garde une mauvaise redirection | 301/308 sont caché agressivement → tester en mode privé, en dev utiliser 302 |
| Le router redirect est ignoré | Cert manquant pour le hostname source (cas du redirect domain) |
| `Bad gateway` au lieu de redirection | Router sans middleware redirect, ou `service=noop@internal` oublié |

## À retenir

- HTTP → HTTPS : configurer **au niveau entrypoint** dans `traefik.yml`, c'est plus propre que par service.
- Pour www↔apex ou changement de domaine : middleware `redirectRegex` + router avec `service=noop@internal`.
- **301/308 sont permanents et cachés** : commencer par 302/307 si tu n'es pas sûr.
- **308 préserve la méthode HTTP** (POST, PUT) — préféré à 301 en 2026.
- Toujours tester avec `curl -I` avant de penser que ça marche.

## Voir aussi

- [Notion : Middlewares — concept et chaînage](../notions/03-middlewares.md)
- [Notion : Anatomie d'une requête](../notions/01-anatomie-requete-traefik.md)
- Documentation : [Traefik RedirectRegex](https://doc.traefik.io/traefik/middlewares/http/redirectregex/), [RedirectScheme](https://doc.traefik.io/traefik/middlewares/http/redirectscheme/)
