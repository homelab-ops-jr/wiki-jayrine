# Méthode — Traefik + Let's Encrypt avec DNS challenge (wildcard)

> **Type** : Méthode · **Outil** : Traefik v3, Let's Encrypt · **Difficulté** : ⭐⭐ Intermédiaire

## Quand l'utiliser

- Tu veux **un seul certificat** qui couvre tous tes sous-domaines (`*.example.com`)
- Tu héberges des services derrière Traefik qui n'exposent **pas le port 80** publiquement
- Tu as un fournisseur DNS dont l'API est supportée par `lego` (le moteur ACME de Traefik) : Cloudflare, OVH, Route53, Gandi, Hetzner, DigitalOcean… [liste complète](https://doc.traefik.io/traefik/https/acme/#providers)

⚠️ Sans wildcard, tu peux aussi faire du DNS challenge **par sous-domaine** ou du **HTTP challenge** (port 80 ouvert). Le wildcard est juste plus pratique quand tu as 5+ services.

## Prérequis

- Traefik v3 fonctionnel
- Un domaine dont tu maîtrises les DNS, hébergé chez un provider supporté
- Des **credentials API** chez ce provider (token avec permission de créer/supprimer des TXT)
- Un système de gestion de secrets (SOPS+age dans ton cas)

## Architecture cible

```
Traefik
  └── certresolver "myresolver" (config statique)
        ├── DNS challenge via provider X
        ├── Storage: /letsencrypt/acme.json
        └── Email: admin@example.com

Services (config dynamique, via labels Docker)
  ├── service A → router avec tls.certresolver=myresolver
  │                 et tls.domains pour pré-générer le wildcard
  └── service B, C, D… → utilisent le wildcard servi par Traefik
```

## Procédure (exemple avec OVH)

### Étape 1 — Obtenir les credentials API chez le provider DNS

Pour OVH (le cas typique en France), voir [api.ovh.com/createToken](https://api.ovh.com/createToken) et générer un token avec :
- `GET /domain/zone/example.com/*`
- `POST /domain/zone/example.com/record`
- `DELETE /domain/zone/example.com/record/*`
- `POST /domain/zone/example.com/refresh`

Tu obtiens :
- `OVH_APPLICATION_KEY`
- `OVH_APPLICATION_SECRET`
- `OVH_CONSUMER_KEY`
- `OVH_ENDPOINT` (`ovh-eu` pour la zone Europe)

Pour Cloudflare : créer un API Token avec permission `Zone:DNS:Edit` sur la zone concernée. Variable unique : `CF_DNS_API_TOKEN`.

🔒 Les credentials API valent pour **toute la zone DNS**. Crée un token avec la portée la plus restreinte possible.

### Étape 2 — Stocker les credentials en secret

Avec SOPS+age (workflow homelab habituel), dans `stacks/traefik/secrets.sops.env` :

```env
OVH_ENDPOINT=ovh-eu
OVH_APPLICATION_KEY=xxxxxxxxxxxxxxxx
OVH_APPLICATION_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OVH_CONSUMER_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Chiffrer avec sops avant commit :
```bash
sops --encrypt --in-place stacks/traefik/secrets.sops.env
```

### Étape 3 — Configurer le certresolver dans Traefik (config statique)

Dans `stacks/traefik/traefik.yml` :

```yaml
entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https
  websecure:
    address: ":443"

certificatesResolvers:
  myresolver:
    acme:
      email: admin@example.com
      storage: /letsencrypt/acme.json
      # ⚠️ EN DEBUG : décommenter pour utiliser staging (pas de rate limit)
      # caServer: https://acme-staging-v02.api.letsencrypt.org/directory
      dnsChallenge:
        provider: ovh
        delayBeforeCheck: 30
        resolvers:
          - "1.1.1.1:53"
          - "8.8.8.8:53"
```

Notes importantes :
- `myresolver` est le nom du resolver — c'est lui qu'on référencera dans les labels. Sur ton homelab c'est exactement `myresolver`, **pas `letsencrypt`** (piège classique).
- `delayBeforeCheck: 30` : attend 30s entre la création du TXT et la requête à Let's Encrypt, pour laisser le DNS se propager.
- `resolvers` : Traefik va vérifier que le TXT est bien propagé via ces resolvers AVANT d'appeler Let's Encrypt. Mettre des resolvers publics évite les soucis de cache du resolver local.

### Étape 4 — Compose Traefik avec les variables d'env et le volume acme.json

`stacks/traefik/docker-compose.yml` :

```yaml
services:
  traefik:
    image: traefik:v3.1
    container_name: traefik
    restart: unless-stopped
    env_file:
      - secrets.sops.env  # ← OVH_* y sont chargées
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./traefik.yml:/etc/traefik/traefik.yml:ro
      - ./dynamic:/etc/traefik/dynamic:ro
      - ./letsencrypt:/letsencrypt
    networks:
      - proxy-tier
    # … (labels Traefik pour son dashboard si applicable)

networks:
  proxy-tier:
    external: true
```

Préparer le fichier ACME :
```bash
mkdir -p ./letsencrypt
touch ./letsencrypt/acme.json
chmod 600 ./letsencrypt/acme.json
```

⚠️ **`chmod 600` obligatoire**. Traefik refuse de démarrer sinon, avec un message du type `the permissions on /letsencrypt/acme.json are too open`.

### Étape 5 — Configurer un service pour utiliser le wildcard

Sur **n'importe quel service** derrière Traefik, ajouter les labels :

```yaml
services:
  monservice:
    # ...
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.monservice.rule=Host(`accueil.example.com`)"
      - "traefik.http.routers.monservice.entrypoints=websecure"
      - "traefik.http.routers.monservice.tls=true"
      - "traefik.http.routers.monservice.tls.certresolver=myresolver"
      # ↓ uniquement sur UN service, pour déclencher la génération du wildcard ↓
      - "traefik.http.routers.monservice.tls.domains[0].main=example.com"
      - "traefik.http.routers.monservice.tls.domains[0].sans=*.example.com"
```

💡 Tu ne **dois** mettre les `tls.domains[0]` que sur **un seul** service (typiquement Traefik lui-même ou ton service principal). Une fois le wildcard généré, **tous** les autres routers qui demandent un cert pour `*.example.com` se serviront du même.

### Étape 6 — Démarrer et observer

```bash
docker compose up -d
docker compose logs -f traefik | grep -i 'acme\|certif\|error'
```

Ce qu'on espère voir :
```
acme: Registering account for admin@example.com
[example.com] acme: Obtaining bundled SAN certificate
[*.example.com] acme: use dns-01 solver
[*.example.com] acme: Preparing to solve DNS-01
[*.example.com] acme: Trying to solve DNS-01
[*.example.com] acme: Waiting for DNS record propagation. timeout: 1m0s
[*.example.com] acme: Validations succeeded; requesting certificates
[example.com] Server responded with a certificate.
```

Quelques minutes plus tard, `acme.json` est rempli et le cert est servi.

### Étape 7 — Vérifier

```bash
curl -vI https://accueil.example.com 2>&1 | grep -E 'subject:|issuer:|expire'
```

Doit afficher quelque chose comme :
```
*  subject: CN=example.com
*  start date: ...
*  expire date: ...
*  subjectAltName: host "accueil.example.com" matched cert's "*.example.com"
*  issuer: C=US; O=Let's Encrypt; CN=R3
```

`R3` = ça vient bien de la prod Let's Encrypt (en staging tu verrais `(STAGING) Pretend Pear X1` ou similaire).

## Bonnes pratiques

### Toujours commencer en staging

Avant la première mise en route, **active le `caServer` staging** :
```yaml
caServer: https://acme-staging-v02.api.letsencrypt.org/directory
```
Test → si OK, commenter cette ligne → **supprimer `acme.json`** (`rm letsencrypt/acme.json && touch letsencrypt/acme.json && chmod 600 letsencrypt/acme.json`) → redémarrer → vrai cert.

Si tu ne supprimes pas `acme.json` en passant de staging à prod, Traefik réutilise le compte et le cert staging (que les navigateurs ne reconnaissent pas).

### Sauvegarder acme.json

Le fichier contient ta clé de compte ACME et tes certs. Le perdre force une régénération complète à chaque redémarrage. Inclure dans tes backups.

### Pas d'ACME pour les services internes Tailscale-only

Si un service n'est pas accessible publiquement (ex. Dockge bound à 100.103.215.106), pas la peine de lui demander un cert Let's Encrypt — soit pas de TLS (Tailscale chiffre déjà), soit cert auto-signé / CA interne.

### Limiter la portée du wildcard

Si tu n'exposes que quelques services et que tu maîtrises bien tes domaines, **plusieurs certs par sous-domaine** (pas de wildcard) est plus restrictif et donc plus sûr en cas de compromission. Le wildcard, lui, **vaut pour tout** sous-domaine.

## Pièges fréquents

| Symptôme | Cause |
|----------|-------|
| `unable to get ACME account` | Mauvais email ou souci de réseau vers Let's Encrypt |
| Erreur `dns timeout` | `delayBeforeCheck` trop court ou TTL des records TXT trop élevé chez le provider |
| Cert généré mais navigateur dit "not secure" | Tu es en staging — cert non reconnu (`(STAGING)` dans l'issuer) |
| `acme: error: 429 :: urn:ietf:params:acme:error:rateLimited` | Tu as fait trop de demandes → revenir en staging pour debug |
| Cert généré pour le bon domaine mais Traefik ne le sert pas | Les `tls.domains[0]` ne sont pas sur le bon router, ou le wildcard manque le nom apex (`example.com` à ajouter à part en `main`) |
| `the permissions on /letsencrypt/acme.json are too open` | Manque `chmod 600` |
| `cannot retrieve credentials from environment` | Les variables `OVH_*` ne sont pas chargées — vérifier `env_file` dans le compose |
| `acme.json` reste vide indéfiniment | Vérifier les logs Traefik : provider DNS qui rejette les credentials, propagation qui n'arrive pas, etc. |

## Forcer le renouvellement

Traefik renouvelle **automatiquement** à 30 jours de l'expiration. Pour forcer :

```bash
# Méthode douce : pour un cert spécifique, éditer acme.json et supprimer son bloc.
# Plus simple en pratique : repartir d'un acme.json vide.
docker compose stop traefik
rm letsencrypt/acme.json
touch letsencrypt/acme.json && chmod 600 letsencrypt/acme.json
docker compose up -d traefik
```

⚠️ Une régénération from scratch consomme une "émission" du rate limit (5/semaine pour le même set de noms). À ne pas faire en boucle.

## Migration depuis staging vers prod

1. Commenter la ligne `caServer:` (ou la mettre sur l'URL prod, qui est le défaut)
2. **Supprimer le contenu** de `acme.json` (compte et cert staging à jeter)
3. Redémarrer Traefik
4. Vérifier l'issuer du nouveau cert (`R3` ou `R10`/`R11` selon la période)

## À retenir

- DNS challenge = **seul moyen** d'obtenir un wildcard.
- Le resolver s'appelle `myresolver` sur ton homelab (pas `letsencrypt`).
- `acme.json` en `chmod 600`, sauvegardé.
- **Toujours debug en staging** avant la prod.
- Les `tls.domains` pour le wildcard ne se mettent **que sur un seul** router.

## Voir aussi

- [Diagnostiquer un acme.json cassé](./traefik-debug-acme-json.md)
- [Servir un certificat statique (fileProvider)](./traefik-certificat-statique.md)
- [Notion : ACME & Let's Encrypt](../notions/05-acme-letsencrypt.md)
