# 05 — Headers HTTP et X-Forwarded-*

> **Type** : Notion · **Sujet** : Reverse proxy · **Prérequis** : [Anatomie d'une requête](./01-anatomie-requete-traefik.md)

## En une phrase

Derrière un reverse proxy, le backend voit **toutes les requêtes comme venant du proxy**, pas du client réel. Les headers `X-Forwarded-*` sont le canal standard pour transmettre l'info originale (IP, protocole, hostname), à condition que le proxy les pose **et que le backend les lise**.

## Le problème

Sans reverse proxy :
```
Client (203.0.113.42) ──HTTPS──► App (192.168.1.10:443)
                                  └── voit l'IP source: 203.0.113.42 ✓
```

Avec reverse proxy :
```
Client (203.0.113.42) ──HTTPS──► Traefik ──HTTP──► App (172.18.0.5:3000)
                                                     └── voit: 172.18.0.5 (Traefik) ✗
                                                         + protocole HTTP au lieu de HTTPS ✗
                                                         + hostname interne au lieu du public ✗
```

Conséquences :
- **Logs faussés** : tous les visiteurs apparaissent comme venant du proxy.
- **Rate limiting cassé** : si l'app implémente du rate limit par IP, elle limite Traefik (donc tout le monde, ou personne).
- **Géolocalisation/blocage IP** ne fonctionne pas.
- **Liens absolus mal générés** : l'app pense être en HTTP et génère `http://app:3000/...` au lieu de `https://app.example.com/...`.
- **Redirections cassées** (Nextcloud, GitLab) : redirige vers `http://` ou vers son hostname interne.
- **CSRF tokens** liés au protocole peuvent échouer.

## Les headers de la solution

Standardisés (RFC 7239) ou de facto :

| Header | Contenu | Exemple |
|--------|---------|---------|
| `X-Forwarded-For` | IP(s) du client, en chaîne | `203.0.113.42, 10.0.0.1` |
| `X-Forwarded-Proto` | Protocole original | `https` |
| `X-Forwarded-Host` | Hostname original (du Host original) | `app.example.com` |
| `X-Forwarded-Port` | Port original | `443` |
| `X-Real-IP` | IP du client (non-standard mais courant) | `203.0.113.42` |
| `Forwarded` | Header RFC 7239 unifié (peu adopté) | `for=203.0.113.42;proto=https;host=app.example.com` |

Traefik **ajoute automatiquement** les `X-Forwarded-*` standards en transmettant les requêtes vers le backend. Tu n'as rien à configurer côté Traefik pour ça (modulo les `trustedIPs`, voir plus bas).

## Côté backend : lire ces headers

L'app derrière Traefik doit savoir qu'elle est derrière un proxy et lire les `X-Forwarded-*`. Quelques exemples typiques :

### Nginx (en tant que backend, pas en tant que proxy)
```nginx
set_real_ip_from 172.18.0.0/16;  # le subnet du réseau Docker
real_ip_header X-Forwarded-For;
real_ip_recursive on;
```

### Node.js / Express
```js
app.set('trust proxy', true);  // fait confiance à X-Forwarded-*
```

### Python (Flask + ProxyFix)
```python
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
```

### Nextcloud
```php
// config/config.php
'trusted_proxies' => ['172.18.0.0/16'],
'overwriteprotocol' => 'https',
'overwritehost' => 'cloud.example.com',
'overwrite.cli.url' => 'https://cloud.example.com',
```

### Forgejo / Gitea
```ini
# app.ini
[server]
ROOT_URL = https://git.example.com/
```

🔑 Le pattern : indiquer à l'app **quelle est son URL publique réelle** et **à qui faire confiance**. Sans ça, elle continue de croire qu'elle est sur `http://localhost:3000`.

## Le piège de la confiance — `trustedIPs`

Les headers `X-Forwarded-*` sont **envoyés par le client**. Si le client en envoie déjà (un proxy en amont, un attaquant malveillant), ils sont préservés et le backend les voit.

Attaque classique : un attaquant envoie `X-Forwarded-For: 127.0.0.1` pour se faire passer pour localhost et contourner un filtre. Si le backend croit aveuglément le header, c'est bypassé.

**Solution Traefik** : `forwardedHeaders.trustedIPs` indique à Traefik **les sources auxquelles il fait confiance** pour préserver les `X-Forwarded-*` reçus. Pour toutes les autres, Traefik **écrase** les headers avec l'IP/protocole réels.

Dans `traefik.yml` :
```yaml
entryPoints:
  websecure:
    address: ":443"
    forwardedHeaders:
      trustedIPs:
        - "172.18.0.0/16"   # ton réseau Docker
        - "10.0.0.0/8"
        # NE PAS mettre 0.0.0.0/0 — ça vide la protection
```

Si Traefik est **directement exposé à Internet** (pas de CDN/proxy en amont) : laisser `trustedIPs` vide ou minimal. Traefik écrasera tout `X-Forwarded-*` injecté par un attaquant.

Si tu as **Cloudflare en amont** : ajouter les ranges d'IP Cloudflare aux trustedIPs, pour que Traefik fasse confiance au `X-Forwarded-For` que CF transmet (sinon l'IP que le backend voit est celle de CF, pas du client final).

## Côté backend : à qui faire confiance ?

Symétriquement, l'app backend doit définir **quelles sources de `X-Forwarded-*` sont fiables**. Une app qui fait `trust proxy: true` aveuglément accepte les headers de **n'importe qui** — y compris d'un attaquant qui parviendrait à contacter le backend directement (port mal fermé).

Bonnes pratiques :
- Confiance limitée au subnet Docker (`172.x.0.0/16`) ou à l'IP de Traefik
- Le port du backend **n'est pas exposé** sur l'hôte (pas de `ports:` dans le compose) — seul Traefik peut le contacter
- Le backend est sur un réseau Docker isolé avec Traefik

## Headers de réponse à connaître

Traefik (via middleware `headers`) ou le backend peuvent ajouter des headers de **sécurité** côté navigateur. Les principaux :

| Header | Rôle |
|--------|------|
| `Strict-Transport-Security` (HSTS) | Force HTTPS pendant N secondes |
| `X-Content-Type-Options: nosniff` | Bloque le MIME sniffing |
| `X-Frame-Options: DENY` (ou `SAMEORIGIN`) | Empêche le clickjacking via iframe |
| `Content-Security-Policy` (CSP) | Restriction très fine des ressources autorisées |
| `Referrer-Policy` | Que transmettre dans `Referer` |
| `Permissions-Policy` | Désactiver des APIs navigateur (caméra, mic, etc.) |

Détail dans la [méthode dédiée](../methodes/traefik-headers-securite.md).

## Le header `Host` — particularité

Par défaut, Traefik **préserve** le header `Host` original quand il transmet au backend. C'est rarement un souci, mais peut surprendre :

- Backend voit `Host: app.example.com`, pas `Host: monapp:3000`
- Utile pour les apps qui s'attendent à voir leur hostname public

Si pour une raison X tu veux que le backend voie un autre Host (rare), tu peux le forcer via un middleware :
```yaml
labels:
  - "traefik.http.middlewares.host-rewrite.headers.customrequestheaders.Host=interne.local"
  - "traefik.http.routers.monapp.middlewares=host-rewrite@docker"
```

Cas légitime : un service qui gère plusieurs vhosts mais que tu exposes en externe sous un seul nom.

## WebSockets et Upgrade

Pour WebSockets, le client envoie :
```
Connection: Upgrade
Upgrade: websocket
```

Traefik propage automatiquement ces headers — **rien à configurer côté reverse proxy**. Le backend doit juste savoir les gérer.

⚠️ Certains middlewares peuvent casser les WebSockets s'ils modifient ces headers. Si tu as un WebSocket qui plante après ajout d'un middleware "headers", vérifier que tu ne réécris pas `Connection`.

## Diagnostic : qu'est-ce que voit mon backend ?

Outil rapide : un container `mendhak/http-https-echo` qui renvoie tous les headers reçus :

```yaml
services:
  echo:
    image: mendhak/http-https-echo:latest
    networks:
      - proxy-tier
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.echo.rule=Host(`echo.example.com`)"
      - "traefik.http.routers.echo.entrypoints=websecure"
      - "traefik.http.routers.echo.tls=true"
      - "traefik.http.routers.echo.tls.certresolver=myresolver"
      - "traefik.http.services.echo.loadbalancer.server.port=8080"
```

Tu visites `https://echo.example.com` et tu vois exactement ce que Traefik transmet : tous les headers, l'IP source perçue, le path. Inestimable pour diagnostiquer.

## Pièges fréquents

| Symptôme | Cause |
|----------|-------|
| Tous les visiteurs ont l'IP du proxy dans les logs | Backend ne lit pas `X-Forwarded-For` (ou n'a pas de `trust proxy`) |
| Liens générés en `http://` au lieu de `https://` | Backend ignore `X-Forwarded-Proto` (souvent : `overwriteprotocol` à configurer) |
| L'app redirige vers `localhost` ou hostname interne | Backend ignore `X-Forwarded-Host` ou a un `BASE_URL` mal configuré |
| Bypass de filtre IP par X-Forwarded-For injecté | `trustedIPs` pas restreint côté Traefik OU backend qui croit aveuglément |
| 502 Bad Gateway sporadique sur WebSocket | Middleware qui casse le header `Connection` |
| Cookies secure mal posés | Backend ne sait pas qu'il est en HTTPS → ne marque pas les cookies `Secure` |

## À retenir

- Traefik ajoute automatiquement `X-Forwarded-For`, `-Proto`, `-Host`, `-Port` — pas de config.
- Le backend doit être **configuré** pour lire et faire confiance à ces headers (`trust proxy`, `trusted_proxies`, etc.).
- `forwardedHeaders.trustedIPs` côté Traefik = qui peut **injecter** des `X-Forwarded-*` qu'on préserve.
- Si Traefik est directement exposé : `trustedIPs` vide ou minimal (défaut sûr).
- L'image `mendhak/http-https-echo` est ton ami pour diagnostiquer ce que voit un backend.

## Pour aller plus loin

- [Méthode : Headers de sécurité](../methodes/traefik-headers-securite.md)
- [Méthode : Diagnostiquer un router ou middleware](../methodes/traefik-debug-router-middleware.md)
- RFC 7239 — Forwarded HTTP Extension
- Doc Traefik : [forwardedHeaders](https://doc.traefik.io/traefik/routing/entrypoints/#forwarded-headers)
