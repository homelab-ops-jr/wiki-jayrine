# Méthode — Diagnostiquer un router ou middleware Traefik

> **Type** : Méthode · **Outil** : Traefik v3 · **Difficulté** : ⭐⭐ Intermédiaire

## Quand l'utiliser

- Un service est démarré mais n'apparaît pas dans le dashboard
- Le router existe mais ne matche pas (404)
- Le middleware n'a aucun effet apparent
- Mauvais cert servi sur un hostname
- 502 Bad Gateway sans indication claire

C'est **la** fiche à avoir sous la main quand Traefik ne fait pas ce qu'on attend.

## Outils de diagnostic

Quatre instruments à connaître, du plus rapide au plus profond :

1. **Dashboard Traefik** (UI) — vue d'ensemble routers/services/middlewares
2. **API Traefik** (HTTP JSON) — interrogeable en CLI
3. **Logs Traefik** (stdout + access.log)
4. **Tests externes** (`curl`, `openssl s_client`, container `mendhak/http-https-echo`)

## Workflow général

Pour tout problème, suivre cet ordre :

```
┌─ 1. Le container est-il bien démarré et observable ? ────────┐
│    docker compose ps                                         │
│    docker compose logs <service>                             │
└──────────────────┬───────────────────────────────────────────┘
                   ▼
┌─ 2. Le router/service apparaît-il dans le dashboard ? ───────┐
│    https://traefik.example.com/dashboard/                    │
│    → si non : label `traefik.enable=true` manquant,          │
│      provider Docker mal configuré, ou exposedByDefault=false│
└──────────────────┬───────────────────────────────────────────┘
                   ▼
┌─ 3. La règle (rule) matche-t-elle bien ma requête ? ─────────┐
│    curl -I https://hostname/...                              │
│    Lire les access logs                                      │
└──────────────────┬───────────────────────────────────────────┘
                   ▼
┌─ 4. Le middleware est-il dans la chaîne du router ? ─────────┐
│    Dashboard → router → onglet Middlewares                   │
│    → si manquant : suffixe `@docker`/`@file` oublié          │
└──────────────────┬───────────────────────────────────────────┘
                   ▼
┌─ 5. Le service joint-il bien le backend ? ───────────────────┐
│    Dashboard → service → Servers (URL et état)               │
│    → 502 : mauvais réseau, mauvais port, container down      │
└──────────────────────────────────────────────────────────────┘
```

## Outil 1 — Dashboard Traefik

Le dashboard montre **l'état réel** de Traefik tel qu'il l'a parsé. Si quelque chose y est absent, c'est que Traefik ne l'a pas chargé — vérifier l'orthographe des labels, l'activation, le provider.

URL typique : `https://traefik.example.com/dashboard/#/` (avec slash final, **important**).

Pages utiles :

- **HTTP → Routers** : liste de tous les routers avec leur status (`Enabled` / `Warning` / `Disabled`), rule, entrypoints, middlewares, service
- **HTTP → Middlewares** : liste de tous les middlewares avec leur provider (`@docker`, `@file`, etc.)
- **HTTP → Services** : avec backends résolus (`Servers`) et leur état

⚠️ Si tu vois un router avec un **`!` jaune** (warning), il y a un souci de configuration (souvent : middleware référencé inexistant). Survoler le warning pour voir le message.

## Outil 2 — API Traefik (sans dashboard)

L'API expose les mêmes infos que le dashboard, en JSON. Pratique en CLI ou pour scripter.

Si l'API est activée (`api.dashboard: true` ou `api.insecure: true`), endpoints utiles :

```bash
# Liste de tous les routers
curl -s https://traefik.example.com/api/http/routers | jq '.[].name'

# Détail d'un router spécifique
curl -s https://traefik.example.com/api/http/routers/monapp@docker | jq

# Liste des middlewares
curl -s https://traefik.example.com/api/http/middlewares | jq '.[] | {name, type: (.type // (.middleware // {} | keys[0]))}'

# Liste des services et leurs backends
curl -s https://traefik.example.com/api/http/services | jq '.[] | {name, serverStatus}'

# Provider snapshot (config dynamique complète vue par Traefik)
curl -s https://traefik.example.com/api/rawdata | jq
```

💡 `/api/rawdata` est **le dump complet** de tout ce que Traefik a chargé. Utile pour comparer "ce que j'ai configuré" vs "ce que Traefik a lu". Si un label manque dans la rawdata, c'est qu'il n'a pas été parsé (typo, mauvais format).

## Outil 3 — Logs Traefik

### Logs de démarrage

```bash
docker compose logs traefik 2>&1 | head -100
```

À chercher :
- `Provider connection error` → Docker socket inaccessible
- `Configuration file 'X' reloaded` → un fichier dynamique a été pris en compte
- `Skipping container` → un container a été ignoré (raison entre parenthèses)
- `Error while building configuration` → label mal formé

### Passer en DEBUG temporairement

Dans `traefik.yml` :
```yaml
log:
  level: DEBUG
```

Restart Traefik, observer les logs au démarrage et lors d'une requête test :
```bash
docker compose logs -f traefik | grep -iE 'router|middleware|service|provider'
```

Tu verras chaque router/middleware/service créé, avec son provider. Si ton router n'apparaît **nulle part** : il n'a pas été parsé du tout.

🔒 Remettre `level: INFO` après debug — DEBUG est verbeux et peut révéler des infos sensibles.

### Access logs (structuré)

Si activés :
```yaml
accessLog:
  filePath: /var/log/traefik/access.log
  format: json
```

Pour chaque requête, une ligne avec `RouterName`, `ServiceName`, `DownstreamStatus`, etc. Pour analyser :

```bash
# Voir les dernières requêtes
docker compose exec traefik tail -f /var/log/traefik/access.log | jq

# Combien de requêtes vers chaque router en 5 min ?
docker compose exec traefik tail -n 1000 /var/log/traefik/access.log \
  | jq -r '.RouterName' | sort | uniq -c | sort -rn

# Quelles requêtes ont eu 404 (= aucun router matché) ?
docker compose exec traefik tail -n 1000 /var/log/traefik/access.log \
  | jq 'select(.DownstreamStatus == 404) | {RequestHost, RequestPath, RouterName}'
```

C'est l'outil le plus puissant pour comprendre **pourquoi une requête a fini où elle a fini**.

## Outil 4 — Tests externes

### `curl -I` pour les headers de réponse
```bash
curl -I https://monapp.example.com
```
Si tu obtiens du HTML d'erreur Traefik (404 par exemple), c'est que **aucun router** n'a matché.

### `curl -v` pour le détail complet
```bash
curl -v https://monapp.example.com 2>&1 | grep -E '^< |^> |^\* '
```
Montre : version HTTP, headers requête/réponse, cert TLS, etc.

### `openssl s_client` pour les problèmes de cert
```bash
openssl s_client -connect monapp.example.com:443 -servername monapp.example.com </dev/null 2>&1 \
  | grep -E 'subject=|issuer=|Verify return'
```
Voir la fiche [Handshake TLS](../../certificats/notions/04-tls-handshake.md).

### Container echo pour ce que voit le backend
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
Tu visites `https://echo.example.com` et tu vois tous les headers que Traefik transmet. Indispensable pour valider que Authelia injecte bien `Remote-User`, que `X-Forwarded-For` arrive, etc.

## Scénarios fréquents

### Le router n'apparaît pas dans le dashboard

1. Container démarré ? `docker compose ps`
2. `traefik.enable=true` présent ? (obligatoire avec `exposedByDefault: false`)
3. Container sur le réseau de Traefik ? (`networks: proxy-tier`)
4. Provider Docker activé dans `traefik.yml` ?
5. Socket Docker accessible (`/var/run/docker.sock` monté en `:ro`) ?

### Le router apparaît mais ne match pas

Symptôme : `curl https://monapp.example.com` retourne 404 alors que le router existe.

Causes possibles :
- **Rule fausse** : `Host(monapp.example.com)` au lieu de `` Host(`monapp.example.com`) `` (backticks obligatoires en YAML/label, échappés selon le contexte)
- **Mauvais entrypoint** : router sur `web` mais tu testes sur `websecure`
- **Cert manquant** pour `tls.certresolver=myresolver` → router actif mais pas servi (vérifier `acme.json`)
- **Priorité** : un autre router avec rule plus spécifique intercepte

Vérifier dans le dashboard quel router a actuellement la priorité pour ton hostname.

### Le middleware n'a aucun effet

1. **Suffixe oublié** : `middlewares=secure-headers` au lieu de `middlewares=secure-headers@file` (cause n°1)
2. **Nom incorrect** : typo dans `secure-headers` vs `secure_headers`
3. **Provider non chargé** : fileProvider mal configuré (`directory:` faux, `watch: false`)
4. **Middleware non déclaré** : tu référence un middleware qui n'existe pas → warning dans le dashboard
5. **Ordre dans la chaîne** : un middleware précédent court-circuite (auth refuse → tes headers ne sont jamais ajoutés)

Vérifier dans le dashboard sur le router → onglet "Middlewares" : la chaîne doit être listée avec les bons noms et providers.

### 502 Bad Gateway

Le router matche, mais Traefik ne peut pas joindre le backend :

1. **Mauvais port** dans `loadbalancer.server.port` (port externe au lieu d'interne)
2. **Mauvais réseau** : container sur un réseau différent de Traefik, `traefik.docker.network` manquant
3. **Container down** ou en cours de démarrage (vérifier `docker compose ps` + healthcheck)
4. **App qui crash** : `docker compose logs <service>` pour voir si l'app derrière vit
5. **App qui n'écoute pas sur 0.0.0.0** : certaines apps écoutent par défaut sur 127.0.0.1, donc inaccessibles depuis Traefik

Tester depuis Traefik vers le backend :
```bash
docker compose exec traefik wget -O- --spider http://monapp:3000/health
```

### Mauvais cert servi (cert auto-signé "Traefik default")

Traefik a un cert auto-signé interne qu'il sert quand **rien d'autre ne matche** ou quand l'ACME a échoué.

1. Vérifier le hostname demandé matche un router avec `tls.certresolver=`
2. `acme.json` contient bien un cert pour ce hostname ? (`jq '.myresolver.Certificates[].domain' acme.json`)
3. Le cert est-il dans la validité ? (Let's Encrypt valide 90j)
4. Le wildcard couvre-t-il le sous-domaine ? (`*.example.com` ne couvre PAS `example.com`)

Voir [Debug acme.json](../../certificats/methodes/traefik-debug-acme-json.md).

### Le bon router matche mais la mauvaise app répond

Très souvent : deux containers ont le même nom de router, et le dernier démarré gagne.

```bash
# Lister tous les routers dans le dashboard et chercher les doublons
curl -s https://traefik.example.com/api/http/routers | jq -r '.[] | "\(.name)  →  \(.service)"'
```

Si tu vois deux entrées différentes avec le même nom (mais provider différent), c'est un conflit. Renommer un des deux.

## Checklist de pré-flight (à faire avant de paniquer)

- [ ] Container démarré, healthy si healthcheck défini
- [ ] `traefik.enable=true`
- [ ] Container sur le bon réseau, `traefik.docker.network=proxy-tier` si multi-network
- [ ] `loadbalancer.server.port` explicite et **interne**
- [ ] `entrypoints=websecure` précisé
- [ ] `tls=true` + `tls.certresolver=myresolver` pour HTTPS
- [ ] Suffixes `@docker`/`@file` sur tous les middlewares référencés
- [ ] Pas de typo dans le nom du router/service (les conflits sont silencieux)
- [ ] `docker compose down && up` après modification de `.env` ou de la config statique

## À retenir

- **Dashboard d'abord**, logs ensuite. 70% des problèmes se voient dans l'UI.
- `/api/rawdata` = état complet vu par Traefik, comparable avec ce que tu as configuré.
- Access logs en JSON + `jq` = analyse fine du routage.
- DEBUG log temporaire pour comprendre ce qui se charge / se charge pas.
- Container echo (`mendhak/http-https-echo`) pour voir ce qui arrive vraiment au backend.

## Voir aussi

- [Notion : Anatomie d'une requête](../notions/01-anatomie-requete-traefik.md)
- [Méthode : Sécuriser le dashboard Traefik](./traefik-dashboard-securise.md)
- [Méthode : Diagnostiquer un acme.json cassé](../../certificats/methodes/traefik-debug-acme-json.md)
- Documentation : [Traefik API](https://doc.traefik.io/traefik/operations/api/)
