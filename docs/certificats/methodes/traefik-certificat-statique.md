# Méthode — Servir un certificat statique dans Traefik (fileProvider)

> **Type** : Méthode · **Outil** : Traefik v3 · **Difficulté** : ⭐⭐ Intermédiaire

## Quand l'utiliser

- Tu as un cert émis par une **autre source** que Let's Encrypt :
  - Cert payant (DigiCert, Sectigo, OV/EV…)
  - Cert émis par une **CA interne**
  - Cert auto-signé pour un service de test
  - Cert fourni par ton entreprise / fournisseur cloud
- Tu veux **forcer un cert spécifique** pour un nom de domaine donné, sans laisser Traefik décider
- Tu veux configurer un cert **par défaut** quand aucun SNI ne matche
- Tu fais du **mTLS** (à venir dans une fiche dédiée — la partie cert client passe aussi par fileProvider)

## Concept

Traefik a deux providers de configuration :

- **Provider statique** — `traefik.yml`, lu au démarrage, contient l'infra (entrypoints, providers, certresolvers…)
- **Providers dynamiques** — relus à chaud, contiennent routers, middlewares, services, **et les définitions de certificats statiques**

Les certs statiques se déclarent dans la **config dynamique**, via le **fileProvider**. Le fileProvider watch un dossier et recharge à chaque modification.

## Architecture cible

```
traefik.yml (statique)
  └── providers.file.directory = /etc/traefik/dynamic
                                       │
                                       ▼
/etc/traefik/dynamic/certs.yml (dynamique)
  └── tls.certificates: liste de couples (cert + key) à monter

/etc/traefik/certs/ (volume)
  ├── nas.crt
  ├── nas.key
  ├── monservice.crt
  └── monservice.key
```

## Prérequis

- Traefik v3 fonctionnel
- Le ou les certs déjà obtenus (cf. fiches OpenSSL si CA interne, ou export du fournisseur)
- Une fileProvider activée dans la config statique

## Procédure

### Étape 1 — Activer le fileProvider (config statique)

Dans `traefik.yml`, vérifier la présence de :

```yaml
providers:
  file:
    directory: /etc/traefik/dynamic
    watch: true
  docker:
    exposedByDefault: false
```

`watch: true` permet le rechargement à chaud sans redémarrer Traefik.

### Étape 2 — Préparer les fichiers cert/key

Sur l'hôte, dans le dossier du stack Traefik (par exemple `/data/services/traefik/`) :

```
/data/services/traefik/
├── docker-compose.yml
├── traefik.yml
├── dynamic/
│   └── certs.yml          ← config dynamique des certs
├── certs/                 ← les fichiers cert/key
│   ├── nas.crt
│   ├── nas.key
│   ├── homelab-ca.crt     ← optionnel : la chaîne
│   └── ...
└── letsencrypt/
    └── acme.json
```

Sécuriser :
```bash
chmod 644 certs/*.crt
chmod 600 certs/*.key
chown root:root certs/*
```

### Étape 3 — Déclarer les certs dans le fichier dynamique

`dynamic/certs.yml` :

```yaml
tls:
  certificates:
    # Cert pour nas.example.com (émis par la CA interne)
    - certFile: /etc/traefik/certs/nas.crt
      keyFile: /etc/traefik/certs/nas.key
    # Cert pour un autre service
    - certFile: /etc/traefik/certs/monservice.crt
      keyFile: /etc/traefik/certs/monservice.key

  # Cert par défaut servi quand aucun SNI ne matche
  # (utile pour éviter de fuiter le cert Let's Encrypt à un scanner qui se connecte par IP)
  options:
    default:
      minVersion: VersionTLS12

  stores:
    default:
      defaultCertificate:
        certFile: /etc/traefik/certs/default.crt
        keyFile: /etc/traefik/certs/default.key
```

⚠️ Les chemins sont **dans le conteneur** Traefik, pas sur l'hôte.

### Étape 4 — Monter les volumes dans docker-compose.yml

```yaml
services:
  traefik:
    image: traefik:v3.1
    # ...
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./traefik.yml:/etc/traefik/traefik.yml:ro
      - ./dynamic:/etc/traefik/dynamic:ro
      - ./certs:/etc/traefik/certs:ro       ← nouveau
      - ./letsencrypt:/letsencrypt
```

`:ro` (read-only) : Traefik n'a pas besoin d'écrire dans ce dossier.

### Étape 5 — Configurer le router du service

Sur le service à servir avec ce cert spécifique :

```yaml
services:
  monservice:
    # ...
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.nas.rule=Host(`nas.example.com`)"
      - "traefik.http.routers.nas.entrypoints=websecure"
      - "traefik.http.routers.nas.tls=true"
      # PAS de certresolver=myresolver ici !
      # Traefik va piocher dans les certs déclarés en fileProvider
      # et matcher par SAN.
```

🔑 **Le matching est automatique par SAN**. Traefik examine tous les certs déclarés et utilise celui dont un SAN matche le hostname demandé en SNI. Tu n'as **rien à préciser de plus** dans les labels.

### Étape 6 — Redémarrer ou recharger

Si tu venais juste de modifier le dynamique (et que `watch: true` est actif), Traefik recharge tout seul, observable dans les logs :
```bash
docker compose logs --tail=20 traefik
# Configuration file 'dynamic/certs.yml' reloaded
```

Si modification de la config statique (`traefik.yml`) :
```bash
docker compose down && docker compose up -d
# ⚠️ docker restart ne suffit PAS pour recharger les fichiers ni les .env
```

### Étape 7 — Vérifier

```bash
curl -vI https://nas.example.com 2>&1 | grep -E 'subject:|issuer:'
```

Le `issuer` doit correspondre à ta CA interne (ou ton fournisseur), pas à Let's Encrypt.

## Cas particuliers

### Servir une chaîne complète

Si le client n'a pas l'intermédiaire dans son trust store, il faut le lui servir. Concaténer dans le `.crt` :

```bash
cat nas.crt intermediate-ca.crt > nas-fullchain.crt
```

Et utiliser `nas-fullchain.crt` dans `certFile`.

L'ordre est important : **leaf → intermédiaire(s) → root (optionnelle)**.

### Cocher avec un cert Let's Encrypt en plus

Tu peux **mélanger** : certains services en Let's Encrypt (via `certresolver=myresolver`), d'autres en cert statique (via fileProvider). Traefik les gère en parallèle.

Si un même hostname est couvert par les deux (Let's Encrypt **et** un cert statique), **le statique gagne**.

### Cert "par défaut" (catch-all)

Si quelqu'un se connecte à ton IP en HTTPS sans SNI valide, Traefik sert par défaut :
- Soit le premier cert disponible
- Soit le `defaultCertificate` du `tls.stores.default` si déclaré

Bonne pratique : déclarer un cert auto-signé minimal comme défaut, pour ne pas fuiter d'info sur les vrais certs en place :

```yaml
tls:
  stores:
    default:
      defaultCertificate:
        certFile: /etc/traefik/certs/default-fake.crt
        keyFile: /etc/traefik/certs/default-fake.key
```

Générer un auto-signé `default-fake.*` qui ne révèle rien (CN générique type `localhost`).

### Plusieurs certs pour le même domaine (rotation)

Tu peux déclarer **simultanément** deux certs avec des SAN qui se chevauchent — Traefik utilisera celui dont la période de validité est la plus appropriée (pas expiré, et le plus récent). Pratique pour rotation sans downtime : on déploie le nouveau cert, on attend que Traefik le détecte, on retire l'ancien.

## Pièges fréquents

| Symptôme | Cause |
|----------|-------|
| Le cert ne se charge pas, pas d'erreur claire | Vérifier les permissions (`.key` doit être lisible par l'utilisateur du conteneur Traefik) |
| `unable to find a default cipher suite for the certificate` | Cert/key dépareillés ou clé corrompue |
| Le cert apparaît mais Traefik sert toujours Let's Encrypt | Le router a `certresolver=myresolver` ; le retirer pour laisser le fileProvider gagner |
| Le wildcard Let's Encrypt prend le pas sur ton cert spécifique | Comportement attendu si les SAN se chevauchent et que le cert LE matche d'abord. Préciser explicitement le cert dans `tls.certificates` avec `stores: [default]` ne change rien — il faut retirer le wildcard ou changer le hostname |
| Modification du `certs.yml` non prise en compte | `watch: true` manquant dans le file provider, ou le volume `dynamic/` n'est pas monté correctement |
| `key values mismatch` | Le `.crt` et le `.key` ne sont pas une paire (erreur de copie) |

## À retenir

- Certs statiques = **config dynamique** via le file provider (à ne pas confondre avec config statique).
- Matching automatique **par SAN**, pas besoin de configurer le router au-delà de `tls=true`.
- Permissions strictes : `.crt` en `644`, `.key` en `600`.
- Compatible avec Let's Encrypt en parallèle.
- Un cert par défaut (catch-all) évite la fuite d'info sur les vrais hostnames.

## Voir aussi

- [Générer un certificat auto-signé](./openssl-generer-cert-autosigne.md)
- [Créer sa propre CA interne](./openssl-creer-ca-interne.md)
- [Notion : Certificats X.509](../notions/02-certificats-x509.md)
