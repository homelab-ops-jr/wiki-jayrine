# Méthode — Let's Encrypt avec HTTP challenge dans Traefik

> **Type** : Méthode · **Outil** : Traefik v3 + ACME · **Difficulté** : ⭐ Débutant

## Quand l'utiliser

- Pas d'accès à l'API DNS du registrar (ou pas envie de le configurer)
- Pas besoin de wildcards
- Le port 80 est ouvert sur Internet pour ton serveur
- Setup simple, peu de domaines

Pour les wildcards ou les comptes avec accès DNS API, préférer le **DNS challenge** ([Traefik + Let's Encrypt DNS challenge](./traefik-letsencrypt-dns-challenge.md)). Voir aussi [ACME & Let's Encrypt](../notions/05-acme-letsencrypt.md) pour le fond du protocole.

## Comparaison rapide HTTP vs DNS challenge

| Critère | HTTP challenge | DNS challenge |
|---------|----------------|---------------|
| Port 80 ouvert nécessaire | ✅ Oui | ❌ Non |
| Accès API DNS nécessaire | ❌ Non | ✅ Oui |
| Wildcards possibles | ❌ Non | ✅ Oui |
| Setup initial | Très simple | Plus complexe (clés API) |
| Marche derrière NAT/firewall strict ? | Non | Oui |
| Émission de cert pour LAN/RFC1918 ? | ❌ Non (LE veut joindre depuis Internet) | ✅ Oui |

🔑 Règle simple : **HTTP challenge si exposé Internet + port 80 ouvert + pas de wildcard**. DNS sinon.

## Principe du HTTP challenge

```
1. Traefik demande un cert à Let's Encrypt pour example.com
2. LE répond : "place un token X à l'URL http://example.com/.well-known/acme-challenge/X"
3. Traefik publie le token via son entrypoint 80
4. LE vient sur http://example.com/.well-known/acme-challenge/X, lit le token
5. Si correspondance, LE émet le cert
6. Traefik stocke le cert (dans acme.json) et le sert en HTTPS
```

Le challenge est **par hostname** : pas de wildcard possible.

## Prérequis

- Traefik v3 fonctionnel
- Port 80 ouvert depuis Internet vers Traefik (vraiment ouvert, pas redirigé ailleurs)
- DNS public qui pointe vers ton serveur pour chaque hostname à certifier
- Une adresse email pour le compte ACME

## Configuration

### Étape 1 — Déclarer le certresolver

Dans `traefik.yml` (config statique) :

```yaml
certificatesResolvers:
  letsencrypt:
    acme:
      email: admin@example.com
      storage: /letsencrypt/acme.json
      httpChallenge:
        entryPoint: web   # l'entrypoint qui écoute sur :80
      # Optionnel : utiliser le staging LE le temps des tests
      # caServer: https://acme-staging-v02.api.letsencrypt.org/directory
```

⚠️ Pendant les tests, **toujours commencer par le staging** :
```yaml
caServer: https://acme-staging-v02.api.letsencrypt.org/directory
```

Les certs staging sont émis par une CA non reconnue (donc warnings navigateur), mais ne consomment pas de [rate limit](https://letsencrypt.org/docs/rate-limits/). Une fois la config validée, retirer la ligne pour passer en prod.

### Étape 2 — Configurer les entrypoints

```yaml
entryPoints:
  web:
    address: ":80"
  websecure:
    address: ":443"
```

L'entrypoint `web` (port 80) **doit exister et être atteignable depuis Internet** — c'est sur lui que LE vient lire le challenge. Pas de truc bizarre type "redirige tout en HTTPS" qui empêcherait LE de récupérer son token.

### Étape 3 — Permettre la redirection HTTPS proprement

Cas piégeux. Tu veux à la fois :
- Que `http://example.com/.well-known/acme-challenge/X` réponde le token (pour le challenge)
- Que `http://example.com/page-classique` redirige vers `https://example.com/page-classique`

Traefik gère ça automatiquement quand le challenge HTTP est actif sur l'entrypoint — il ne redirige **pas** les requêtes vers `/.well-known/acme-challenge/`, et redirige le reste si configuré.

Configuration recommandée :

```yaml
entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https
          permanent: true
  websecure:
    address: ":443"
```

➡️ Voir aussi [Méthode : Redirections](../../reverse-proxy/methodes/traefik-redirections.md) pour le détail des redirections HTTP→HTTPS.

### Étape 4 — Appliquer le certresolver sur un router

Sur un container exposé via Docker labels :

```yaml
services:
  monapp:
    image: monapp:latest
    networks:
      - proxy
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.monapp.rule=Host(`monapp.example.com`)"
      - "traefik.http.routers.monapp.entrypoints=websecure"
      - "traefik.http.routers.monapp.tls=true"
      - "traefik.http.routers.monapp.tls.certresolver=letsencrypt"
      - "traefik.http.services.monapp.loadbalancer.server.port=3000"
```

Au démarrage, Traefik lance la demande ACME pour `monapp.example.com`.

### Étape 5 — Vérifier l'émission

```bash
docker compose logs traefik | grep -iE 'acme|certificate'
```

Sortie attendue (extrait) :
```
Building ACME client for letsencrypt
Trying to challenge certificate for domain [monapp.example.com] found in HostSNI rule
Domains [\"monapp.example.com\"] need ACME certificates generation for domains [\"monapp.example.com\"].
Certificates obtained for domains [monapp.example.com]
```

Si erreur, voir la [méthode de debug acme.json](./traefik-debug-acme-json.md).

## Multi-domaines : un cert ou plusieurs ?

Par défaut, Traefik émet **un cert par router** (donc un par hostname distinct si tu n'as pas de SAN).

Pour grouper plusieurs hostnames dans **un seul cert** (plus économe en rate limits LE) :

```yaml
labels:
  - "traefik.http.routers.monapp.rule=Host(`app.example.com`) || Host(`api.example.com`)"
  - "traefik.http.routers.monapp.tls.domains[0].main=app.example.com"
  - "traefik.http.routers.monapp.tls.domains[0].sans=api.example.com"
  - "traefik.http.routers.monapp.tls.certresolver=letsencrypt"
```

Traefik émet alors un cert unique avec deux SAN. Utile si tu veux limiter le nombre de requêtes ACME.

➡️ Voir [Notion : SAN et wildcards](../notions/07-san-et-wildcards.md) pour le détail des SAN.

## Persistance de l'acme.json

```yaml
# docker-compose.yml du Traefik
services:
  traefik:
    volumes:
      - ./letsencrypt:/letsencrypt
```

⚠️ Permissions : `acme.json` doit être en `0600` (lisible/écrivable **seulement** par le user qui run Traefik). Sinon Traefik refuse de l'utiliser :

```bash
touch ./letsencrypt/acme.json
chmod 600 ./letsencrypt/acme.json
```

🔒 Le fichier contient la **clé privée du compte ACME** et **toutes les clés privées des certs émis**. À sauvegarder, jamais à committer en clair dans un repo.

## Test du challenge à blanc

Pour s'assurer que le port 80 est joignable depuis Internet :

```bash
# Depuis une machine externe (pas ton serveur)
curl -v http://monapp.example.com/.well-known/acme-challenge/test
```

Doit retourner un 404 Traefik (réponse Traefik = port joignable, juste pas de token "test" en cours). Si timeout ou refus : firewall/NAT à corriger avant de démarrer Traefik.

## Rate limits Let's Encrypt à connaître

LE applique des [limites strictes](https://letsencrypt.org/docs/rate-limits/) :

| Limite | Valeur |
|--------|--------|
| Certs par domaine principal par semaine | 50 |
| Duplicate certs (mêmes SAN) par semaine | 5 |
| Failed validations par compte/hostname/heure | 5 |
| Comptes par adresse IP / 3h | 50 |

🔑 **Toujours tester en staging** avant la prod. Un loop de redémarrage qui refait des demandes ACME peut épuiser les 5 failed validations en quelques minutes, bloquant le domaine pour une heure.

```yaml
# Staging pour tests
caServer: https://acme-staging-v02.api.letsencrypt.org/directory
```

Quand le staging fonctionne, **vider `acme.json`** et passer en prod (retirer la ligne `caServer`).

## Cas particuliers

### Apex + sous-domaines

Pas de wildcard en HTTP challenge → lister chaque hostname :

```yaml
labels:
  - "traefik.http.routers.app.rule=Host(`example.com`) || Host(`www.example.com`) || Host(`app.example.com`)"
  - "traefik.http.routers.app.tls.domains[0].main=example.com"
  - "traefik.http.routers.app.tls.domains[0].sans=www.example.com,app.example.com"
  - "traefik.http.routers.app.tls.certresolver=letsencrypt"
```

### Plusieurs services derrière le même cert

Possible mais déconseillé : chaque service devrait avoir son propre router (donc son propre cert), c'est plus propre pour les renouvellements et les diags.

### Migration HTTP challenge → DNS challenge

Pour basculer ultérieurement sur le DNS challenge (par exemple pour ajouter un wildcard) :

1. Ajouter un nouveau certresolver `letsencrypt-dns` dans `traefik.yml`
2. Sur les nouveaux routers : `tls.certresolver=letsencrypt-dns`
3. Garder l'ancien certresolver pour les certs existants (ou les régénérer)

Pas besoin de tout migrer d'un coup.

## Pièges fréquents

| Symptôme | Cause |
|----------|-------|
| `unable to obtain ACME certificate` | Port 80 pas joignable depuis Internet ; tester avec `curl` depuis un client externe |
| `Connection refused` côté LE | Traefik pas démarré ou pas bindé sur :80, ou firewall |
| `urn:ietf:params:acme:error:dns` | DNS pas encore propagé ou mauvais record A/AAAA |
| `too many failed authorizations` | Rate limit atteint — passer en staging et corriger avant de retenter |
| Cert auto-signé "Traefik default" servi | Émission a échoué, ou hostname pas dans `tls.domains` ; voir [debug acme.json](./traefik-debug-acme-json.md) |
| Pas de challenge tenté du tout | `httpChallenge.entryPoint` mal nommé, doit matcher exactement le nom de l'entrypoint |
| `Permissions are not 0600` sur acme.json | `chmod 600 acme.json` |
| Le challenge passe mais cert pas servi | Cf. [debug acme.json](./traefik-debug-acme-json.md) — souvent un problème de domaine pas dans la rule |

## À retenir

- HTTP challenge = simple, mais **port 80 ouvert obligatoire** et **pas de wildcards**.
- Toujours **tester en staging** d'abord pour ne pas griller les rate limits.
- `acme.json` doit être en `0600`, sauvegardé séparément.
- Pour grouper plusieurs hostnames dans un cert : `tls.domains[0].main` + `sans`.
- En cas d'échec : ne pas tenter en boucle — corriger d'abord, sinon rate limit.

## Pour aller plus loin

- [ACME & Let's Encrypt](../notions/05-acme-letsencrypt.md) — le protocole expliqué
- [Méthode : Let's Encrypt DNS challenge](./traefik-letsencrypt-dns-challenge.md) — alternative pour les wildcards
- [Méthode : Diagnostiquer un acme.json cassé](./traefik-debug-acme-json.md) — quand ça ne marche pas
- [Méthode : Forcer le renouvellement d'un cert Traefik](./traefik-forcer-renouvellement.md)
- [Méthode : Redirections Traefik](../../reverse-proxy/methodes/traefik-redirections.md)
- Doc officielle : [Traefik ACME](https://doc.traefik.io/traefik/https/acme/)
- [Let's Encrypt rate limits](https://letsencrypt.org/docs/rate-limits/)
