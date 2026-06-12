# Méthode — Headers de sécurité avec Traefik

> **Type** : Méthode · **Outil** : Traefik v3 · **Difficulté** : ⭐ Débutant à ⭐⭐ pour CSP

## Quand l'utiliser

Renforcer la sécurité côté navigateur **sans modifier le backend** : forcer HTTPS persistant (HSTS), bloquer l'embarquement en iframe (clickjacking), restreindre les ressources externes (CSP), etc. C'est une couche défensive minimale à mettre sur **tout service web exposé**.

## Headers à connaître

| Header | Effet | Priorité |
|--------|-------|----------|
| `Strict-Transport-Security` (HSTS) | Le navigateur force HTTPS pour les visites suivantes | 🟢 Essentiel |
| `X-Content-Type-Options: nosniff` | Empêche le MIME sniffing | 🟢 Essentiel |
| `X-Frame-Options: DENY` (ou `SAMEORIGIN`) | Anti-clickjacking | 🟢 Essentiel |
| `Referrer-Policy` | Que transmettre dans `Referer` (fuite d'info) | 🟢 Essentiel |
| `Permissions-Policy` | Désactive APIs navigateur (caméra, mic, géoloc) | 🟡 Recommandé |
| `Content-Security-Policy` (CSP) | Restriction très fine des sources autorisées | 🟡 Recommandé (compliqué) |
| `X-XSS-Protection` | Anti-XSS legacy | 🔴 Obsolète |

## Procédure — un middleware réutilisable

Le plus propre : déclarer un seul middleware `secure-headers` en fileProvider, et l'appliquer à tous les routers.

### Étape 1 — Créer le middleware

`/data/services/traefik/dynamic/middlewares-security.yml` :

```yaml
http:
  middlewares:
    secure-headers:
      headers:
        # HSTS — Force HTTPS pendant 2 ans, applique aux sous-domaines, demande inclusion dans la preload list
        stsSeconds: 63072000
        stsIncludeSubdomains: true
        stsPreload: true

        # MIME sniffing protection
        contentTypeNosniff: true

        # Clickjacking protection
        frameDeny: true                 # ou customFrameOptionsValue: "SAMEORIGIN"

        # Referer policy
        referrerPolicy: "strict-origin-when-cross-origin"

        # Permissions Policy (anciennement Feature-Policy)
        customResponseHeaders:
          Permissions-Policy: "geolocation=(), microphone=(), camera=(), payment=()"

        # Empêcher l'app d'utiliser ces APIs (cosmétique, peut être adapté)
        browserXssFilter: false   # obsolète, mais le mettre à false évite que Traefik le force

        # Si Traefik est exposé en HTTPS et l'app aussi
        sslRedirect: true
        sslForceHost: true
```

### Étape 2 — L'appliquer aux routers

Sur chaque service à protéger :
```yaml
labels:
  - "traefik.http.routers.monapp.middlewares=secure-headers@file"
```

Ou si tu chaînes plusieurs middlewares :
```yaml
labels:
  - "traefik.http.routers.monapp.middlewares=secure-headers@file,rate-limit-default@file,authelia@docker"
```

### Étape 3 — Application globale via entrypoint (optionnel)

Pour appliquer `secure-headers` **à tous les routers** par défaut, dans `traefik.yml` :

```yaml
entryPoints:
  websecure:
    address: ":443"
    http:
      middlewares:
        - secure-headers@file
```

Tout router sur `websecure` hérite des secure-headers sans qu'on ait à le préciser. Toujours overridable au cas par cas.

### Étape 4 — Vérifier

Outil rapide en ligne de commande :
```bash
curl -sI https://monapp.example.com | grep -iE 'strict|x-frame|content-type|referrer|permissions'
```

Sortie attendue :
```
strict-transport-security: max-age=63072000; includeSubDomains; preload
x-content-type-options: nosniff
x-frame-options: DENY
referrer-policy: strict-origin-when-cross-origin
permissions-policy: geolocation=(), microphone=(), camera=(), payment=()
```

Outil web : [securityheaders.com](https://securityheaders.com) — score A+ atteignable avec la config ci-dessus.

## HSTS en profondeur

HSTS dit au navigateur : "pour les N prochaines secondes, considère ce domaine comme HTTPS-only". Une fois posé, **impossible de revenir en arrière côté visiteur** avant expiration.

```yaml
headers:
  stsSeconds: 63072000              # 2 ans
  stsIncludeSubdomains: true        # applique aux *.example.com
  stsPreload: true                  # demande d'inclusion dans la HSTS Preload List
```

⚠️ **Le piège** : si tu actives `stsIncludeSubdomains` et `stsPreload`, tu ne pourras plus servir **aucun** sous-domaine en HTTP sans casser pour les visiteurs qui ont déjà chargé HSTS. Pas de retour arrière facile.

🔒 **Recommandations** :
- En dev/test : `stsSeconds: 300` (5 min) pour pouvoir corriger sans bloquer
- En prod stabilisée : `stsSeconds: 31536000` (1 an) puis monter à 2 ans
- `stsPreload: true` uniquement quand tu es certain de toujours servir tout en HTTPS — c'est un engagement
- Pour entrer dans la HSTS Preload List : voir [hstspreload.org](https://hstspreload.org/) (séparé de Traefik)

## Content-Security-Policy (CSP)

CSP est le plus puissant et **le plus compliqué**. Il dicte au navigateur quelles ressources (scripts, images, styles, fonts) sont autorisées.

### Cas 1 — Tu maîtrises ton frontend
CSP stricte est faisable :
```yaml
customResponseHeaders:
  Content-Security-Policy: "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; script-src 'self'; font-src 'self' data:"
```

### Cas 2 — Tu utilises des CDN externes (Google Fonts, etc.)
Lister chaque domaine autorisé :
```yaml
customResponseHeaders:
  Content-Security-Policy: "default-src 'self'; style-src 'self' 'unsafe-inline' fonts.googleapis.com; font-src 'self' fonts.gstatic.com"
```

### Cas 3 — Application tierce (Nextcloud, Forgejo, Sonarr...)
**Ne pas imposer de CSP au niveau Traefik** — l'app gère sa propre CSP en interne. La forcer côté Traefik casse l'app.

🔑 **Règle** : CSP est sensible. Si tu n'as pas développé l'app, laisser le backend gérer. Pour tes propres apps (site perso, dashboard, wiki MkDocs), CSP au niveau Traefik est OK.

### Mode "Report-Only" pour expérimenter
Avant d'imposer, observer ce que ça casserait :
```yaml
customResponseHeaders:
  Content-Security-Policy-Report-Only: "default-src 'self'; report-uri /csp-report"
```

Le navigateur **ne bloque pas** mais reporte les violations. Une fois zéro violation : passer en `Content-Security-Policy` actif.

## Headers spécifiques à certains services

### Bypasser secure-headers pour un service qui en a besoin

Certains services (Plex, Jellyfin) servent du contenu embarqué qui ne supporte pas `X-Frame-Options: DENY`. Solutions :

**Option A** : ne pas appliquer le middleware sur ce router :
```yaml
labels:
  - "traefik.http.routers.plex.middlewares="  # vide = override
```

(Si tu as un middleware par défaut au niveau entrypoint, ça l'écrase.)

**Option B** : créer un middleware variante :
```yaml
http:
  middlewares:
    secure-headers-relaxed:
      headers:
        stsSeconds: 63072000
        contentTypeNosniff: true
        customFrameOptionsValue: "SAMEORIGIN"   # au lieu de DENY
        referrerPolicy: "strict-origin-when-cross-origin"
```

Et appliquer `secure-headers-relaxed@file` sur le router concerné.

### Nextcloud — headers spécifiques requis

Nextcloud génère ses propres headers de sécurité **et** s'attend à certaines configurations. Souvent il est plus simple de laisser Nextcloud gérer entièrement (pas de middleware secure-headers sur son router).

Exception : ajouter explicitement `Strict-Transport-Security` si tu veux un HSTS plus agressif que celui de Nextcloud.

## Modifier des headers de requête (entrants)

Le middleware `headers` peut aussi modifier les headers que Traefik envoie au backend (`customRequestHeaders`) :

```yaml
http:
  middlewares:
    inject-real-ip:
      headers:
        customRequestHeaders:
          X-Real-IP: ""    # supprime un header (= ne pas le transmettre)
        # Ajout
        # customRequestHeaders:
        #   X-Custom-Source: "traefik"
```

Usage rare en homelab mais utile pour des migrations ou debug.

## Cas pratique : config recommandée pour un service "standard"

Service personnel exposé publiquement (site, blog, wiki), HTTPS uniquement, sans iframe :

```yaml
http:
  middlewares:
    secure-headers:
      headers:
        stsSeconds: 31536000              # 1 an
        stsIncludeSubdomains: true
        stsPreload: false                 # à activer plus tard si entrée preload list
        contentTypeNosniff: true
        frameDeny: true
        referrerPolicy: "strict-origin-when-cross-origin"
        customResponseHeaders:
          Permissions-Policy: "geolocation=(), microphone=(), camera=()"
        # CSP minimaliste compatible avec MkDocs Material, sites statiques :
          Content-Security-Policy: "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; font-src 'self' data:"
```

## Pièges fréquents

| Symptôme | Cause |
|----------|-------|
| HSTS persiste après suppression du middleware | C'est le but — le navigateur a mémorisé. Solution : attendre l'expiration, ou en dev, `chrome://net-internals/#hsts` |
| CSP casse l'app (CSS/JS ne charge plus) | CSP trop restrictive ; passer en `Report-Only` pour identifier ce qu'il faut autoriser |
| Header pas appliqué malgré la config | Suffixe `@file` manquant, ou middleware en conflit avec celui de l'app (Nextcloud renvoie le sien) |
| Score securityheaders.com mauvais sur un sous-domaine | Le middleware n'est pas appliqué à ce router (entrypoint OK, router non) |
| HSTS bloque l'accès à un sous-domaine HTTP-only | `includeSubdomains` propagé : à éviter si tu as des services internes HTTP |
| `X-Frame-Options` empêche l'embarquement légitime | Passer en `SAMEORIGIN` au lieu de `DENY`, ou utiliser `frame-ancestors` en CSP |

## À retenir

- Un middleware **`secure-headers` en fileProvider** + application au niveau entrypoint = sécurité de base partout.
- **HSTS est un engagement** : `stsPreload` ne se prend pas à la légère.
- **CSP** : pour tes propres apps oui, pour les apps tierces (Nextcloud, etc.) laisser le backend gérer.
- Toujours vérifier avec `curl -sI` puis [securityheaders.com](https://securityheaders.com) après déploiement.
- **`Report-Only`** est ton meilleur ami pour tester CSP sans rien casser.

## Voir aussi

- [Notion : Middlewares — concept et chaînage](../notions/03-middlewares.md)
- [Notion : Headers HTTP et X-Forwarded-*](../notions/05-headers-x-forwarded.md)
- Documentation : [Traefik Headers middleware](https://doc.traefik.io/traefik/middlewares/http/headers/)
- Outil : [securityheaders.com](https://securityheaders.com)
- Référence : [MDN — Security headers](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers)
