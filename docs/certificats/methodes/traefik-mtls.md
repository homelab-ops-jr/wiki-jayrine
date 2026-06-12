# Méthode — Configurer mTLS dans Traefik

> **Type** : Méthode · **Outil** : Traefik v3 · **Difficulté** : ⭐⭐⭐ Avancé

## Quand l'utiliser

- Tu veux protéger une URL/API par authentification cryptographique au lieu (ou en plus) de mots de passe / forward auth
- Tu exposes une API consommée par d'autres services contrôlés
- Tu déploies un endpoint admin et tu veux le restreindre fortement
- Tu construis un setup Zero Trust où chaque accès doit prouver son identité

➡️ Pour comprendre le mécanisme : [Notion : mTLS](../notions/09-mtls.md). Prérequis sur la PKI : [Créer une CA interne](./openssl-creer-ca-interne.md).

## Architecture cible

```
┌─────────────────────────┐
│ CA cliente (interne)    │   ── tu en es maître
│ ca-clients.crt          │
│ ca-clients.key          │
└────────┬────────────────┘
         │
         │ signe N certs clients
         ▼
┌─────────────────────────┐         ┌──────────────────────┐
│ Cert client + clé       │── TLS ──│ Traefik              │
│ (PKCS#12 ou PEM)        │  handshake │ - tlsOption avec  │
└─────────────────────────┘  + mTLS   │   clientAuth        │
                                     │ - cert ca-clients   │
                                     │   en confiance      │
                                     └──────────────────────┘
```

## Vue d'ensemble du workflow

1. Créer une **CA cliente** (cf. [Créer une CA interne](./openssl-creer-ca-interne.md))
2. Émettre **un cert client** pour chaque consommateur (cf. [Émettre un cert via sa CA interne](./openssl-emettre-cert-via-ca-interne.md))
3. Configurer **un TLSOption** dans Traefik pour exiger mTLS
4. Appliquer le TLSOption sur le **router à protéger**
5. Distribuer les certs clients (PKCS#12 typiquement)
6. Tester

## Étape 1 — Préparer la CA cliente

Si tu n'as pas encore de CA dédiée mTLS, suivre [Créer une CA interne](./openssl-creer-ca-interne.md) en nommant les fichiers de manière à les distinguer (par exemple `ca-clients.crt` / `ca-clients.key`).

Tu peux aussi réutiliser une CA existante, mais une CA dédiée aux certs **clients** simplifie l'audit. Voir [Notion : mTLS](../notions/09-mtls.md#ca-cliente-separee-ou-partagee).

Copier le cert public de la CA dans le dossier de config Traefik :
```bash
cp ca-clients.crt /data/services/traefik/certs/ca-clients.crt
```

⚠️ **Seul le cert public** de la CA va sur le serveur. La clé privée de la CA reste sur la machine d'émission.

## Étape 2 — Émettre un cert client

Voir [Émettre un cert via sa CA interne](./openssl-emettre-cert-via-ca-interne.md), avec ces particularités pour un cert client :

```ini
# Extension d'émission (signée avec ca-clients)
[ client_cert ]
basicConstraints       = CA:FALSE
keyUsage               = critical, digitalSignature
extendedKeyUsage       = clientAuth
subjectKeyIdentifier   = hash
authorityKeyIdentifier = keyid,issuer
subjectAltName         = email:alice@example.com
```

Identité dans le CN ou les SAN selon ce que tu veux exposer au backend. Exemple pour Alice :
```
Subject: CN=alice, O=HomeLab, OU=Admins
```

Le cert client final + sa clé privée seront convertis en PKCS#12 pour distribution (cf. [Convertir entre formats](./openssl-convertir-formats-cert.md)) :

```bash
openssl pkcs12 -export \
  -in alice.crt \
  -inkey alice.key \
  -certfile ca-clients.crt \
  -out alice.p12 \
  -name "alice@example.com"
```

## Étape 3 — Déclarer une TLSOption dans Traefik

Les `tlsOptions` sont en **fileProvider** (config dynamique). Créer `dynamic/tls-options.yml` :

```yaml
tls:
  options:
    # Option mTLS strict — exige un cert client valide
    mtls-required:
      clientAuth:
        caFiles:
          - /certs/ca-clients.crt
        clientAuthType: RequireAndVerifyClientCert
      minVersion: VersionTLS12

    # Option mTLS souple — cert client optionnel, mais vérifié si fourni
    mtls-optional:
      clientAuth:
        caFiles:
          - /certs/ca-clients.crt
        clientAuthType: VerifyClientCertIfGiven
      minVersion: VersionTLS12
```

Les valeurs de `clientAuthType` (voir [Notion : mTLS](../notions/09-mtls.md#modes-de-verification-cote-serveur)) :

| Valeur | Comportement |
|--------|--------------|
| `NoClientCert` | Pas de mTLS (défaut Traefik) |
| `RequestClientCert` | Demande mais accepte sans |
| `RequireAnyClientCert` | Exige un cert, ne vérifie pas la chaîne |
| `VerifyClientCertIfGiven` | Si présenté, validé ; sinon accepté |
| `RequireAndVerifyClientCert` | Exige et valide — **le vrai mTLS** |

Pour un endpoint vraiment protégé : **`RequireAndVerifyClientCert`**.

Monter le dossier `/certs` dans le container Traefik :
```yaml
# docker-compose.yml de Traefik
volumes:
  - ./certs:/certs:ro
  - ./dynamic:/etc/traefik/dynamic:ro
```

Et déclarer le fileProvider dans `traefik.yml` s'il n'y est pas déjà :
```yaml
providers:
  file:
    directory: /etc/traefik/dynamic
    watch: true
```

## Étape 4 — Appliquer le TLSOption au router

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.admin.rule=Host(`admin.example.com`)"
  - "traefik.http.routers.admin.entrypoints=websecure"
  - "traefik.http.routers.admin.tls=true"
  - "traefik.http.routers.admin.tls.certresolver=letsencrypt"
  - "traefik.http.routers.admin.tls.options=mtls-required@file"   # ← clé
  - "traefik.http.services.admin.loadbalancer.server.port=3000"
```

⚠️ Suffixe `@file` indispensable (cf. [Notion : Providers](../../reverse-proxy/notions/02-providers-static-dynamic.md)).

## Étape 5 — Tester avec curl

Sans cert client → la connexion doit être refusée :

```bash
curl -v https://admin.example.com
# Sortie attendue :
# * SSL alert: bad_certificate / handshake_failure
# curl: (35) error:0A00045C:SSL routines::tlsv13 alert certificate required
```

Avec cert client (PEM directement) :

```bash
curl -v --cert alice.crt --key alice.key https://admin.example.com
# HTTP/2 200
```

Avec PKCS#12 :

```bash
curl -v --cert-type P12 --cert alice.p12:MOTDEPASSE https://admin.example.com
```

## Étape 6 — Transmettre l'identité au backend

Le backend derrière Traefik veut souvent savoir **qui** est le client authentifié. Traefik peut transmettre les infos du cert client via des headers :

```yaml
# dynamic/middlewares.yml
http:
  middlewares:
    mtls-headers:
      passTLSClientCert:
        pem: false                 # pas tout le cert en header (volumineux)
        info:
          subject:
            commonName: true
            organization: true
            organizationalUnit: true
          issuer:
            commonName: true
          notAfter: true
          serialNumber: true
```

Application :
```yaml
labels:
  - "traefik.http.routers.admin.middlewares=mtls-headers@file"
```

Le backend reçoit :
```
X-Forwarded-Tls-Client-Cert-Info: Subject="CN=alice,O=HomeLab,OU=Admins";Issuer="CN=ca-clients";...
```

À parser côté backend pour autoriser ou non.

➡️ Sur les headers transmis : [Notion : Headers HTTP et X-Forwarded-*](../../reverse-proxy/notions/05-headers-x-forwarded.md).

## Mixer mTLS et autres mécanismes

mTLS au niveau Traefik peut se combiner avec d'autres middlewares :

```yaml
labels:
  - "traefik.http.routers.admin.tls.options=mtls-required@file"
  - "traefik.http.routers.admin.middlewares=rate-limit@file,mtls-headers@file"
```

Mais **pas avec un middleware d'auth web** (Authelia, basic auth) qui attendrait un login — l'expérience deviendrait incohérente. Choisir l'un OU l'autre par endpoint.

## Variante : mTLS sur sous-chemin uniquement

Tu veux que `/admin/*` exige mTLS mais que `/` reste publique ? Deux routers sur le même service :

```yaml
labels:
  - "traefik.enable=true"

  # Router public (pas mTLS)
  - "traefik.http.routers.app.rule=Host(`example.com`)"
  - "traefik.http.routers.app.entrypoints=websecure"
  - "traefik.http.routers.app.tls=true"
  - "traefik.http.routers.app.tls.certresolver=letsencrypt"

  # Router admin (mTLS requis)
  - "traefik.http.routers.app-admin.rule=Host(`example.com`) && PathPrefix(`/admin`)"
  - "traefik.http.routers.app-admin.entrypoints=websecure"
  - "traefik.http.routers.app-admin.tls=true"
  - "traefik.http.routers.app-admin.tls.certresolver=letsencrypt"
  - "traefik.http.routers.app-admin.tls.options=mtls-required@file"

  - "traefik.http.services.app.loadbalancer.server.port=3000"
```

⚠️ **Limite technique** : la TLSOption s'applique au **handshake TLS**, donc à toute la connexion HTTPS. Si une connexion sert à la fois `/` et `/admin` (HTTP/2 multiplexé), le client doit présenter un cert dès le handshake — sinon `/admin` sera bloqué mais `/` aussi tant qu'aucun cert client n'est fourni. En pratique : utiliser **deux hostnames** distincts (`app.example.com` et `admin.example.com`) est plus propre.

## Révocation

En mTLS interne, la révocation reste utile (cf. [Notion : Révocation](../notions/08-revocation-crl-ocsp.md)).

Traefik v3 ne supporte pas nativement la consultation de CRL externe. Approches :

1. **Régénérer la liste autorisée** : retirer le cert du `caFiles` (impossible — c'est la CA qui est listée, pas les certs individuels)
2. **Renouvellement de la CA cliente** : émettre une nouvelle CA, redéployer tous les certs clients, basculer la config (lourd mais efficace)
3. **Durées courtes** : émettre les certs clients pour 30-90 jours, ne pas révoquer mais ne pas renouveler (équivalent fonctionnel)
4. **Plugin / proxy intermédiaire** : un plugin Traefik ou un proxy backend qui consulte une CRL

En pratique, **durées de vie courtes + révocation par non-renouvellement** est l'approche la plus simple en homelab.

## Pièges fréquents

| Symptôme | Cause |
|----------|-------|
| Tous les clients refusés (même avec cert valide) | `caFiles` pointe vers un fichier inaccessible (mauvais path dans le container) |
| Cert client refusé mais valide | Le cert est signé par une autre CA que celle dans `caFiles` |
| `tls.options` ignoré | Suffixe `@file` oublié, ou la TLSOption est dans Docker labels au lieu de fileProvider |
| Curl refuse même avec `--cert` | Cert client expiré, ou `extendedKeyUsage` ne contient pas `clientAuth` |
| Le navigateur ne propose pas le cert | Le cert n'est pas dans le keystore navigateur, ou pas reconnu pour ce site |
| Erreur `bad certificate` côté serveur | Cert client mal formé ou clé/cert mal appariés |
| Backend ne voit pas l'identité du client | Middleware `passTLSClientCert` pas appliqué, ou backend ne lit pas les headers |

## Côté client : importer un PKCS#12

### Navigateurs Firefox/Chrome
Settings → Privacy & Security → Certificates → Import (un keystore par navigateur sur Firefox ; Chrome utilise le trust store OS sur Windows/macOS).

### macOS / iOS
Double-cliquer sur le .p12, importer dans Keychain Access.

### Linux (curl, wget, scripts)
Garder le PKCS#12, l'utiliser avec `--cert-type P12 --cert fichier.p12:mdp`.
Ou extraire en PEM (cf. [Convertir entre formats](./openssl-convertir-formats-cert.md)).

### Windows
Double-cliquer sur le .p12, Certificate Import Wizard. Détaillé dans [Trust stores Windows/macOS/mobile](./trust-store-windows-macos-mobile.md).

## À retenir

- mTLS dans Traefik = **TLSOption fileProvider** avec `clientAuth.caFiles` + `clientAuthType: RequireAndVerifyClientCert`.
- Appliquer via `tls.options=NOM@file` sur le router.
- Tester avec `curl --cert/--key` ou `--cert-type P12`.
- Pour transmettre l'identité au backend : middleware `passTLSClientCert`.
- Préférer **deux hostnames distincts** pour public + admin mTLS (plutôt que sous-chemin).
- Révocation en mTLS = renouvellement court + non-renouvellement, plus simple que CRL.

## Pour aller plus loin

- [Notion : mTLS](../notions/09-mtls.md)
- [Notion : Handshake TLS](../notions/04-tls-handshake.md)
- [Méthode : Créer une CA interne](./openssl-creer-ca-interne.md)
- [Méthode : Émettre un cert via sa CA interne](./openssl-emettre-cert-via-ca-interne.md)
- [Méthode : Convertir un cert entre formats](./openssl-convertir-formats-cert.md)
- [Méthode : Trust stores Windows/macOS/mobile](./trust-store-windows-macos-mobile.md) — pour distribuer la CA aux clients
- Doc Traefik : [TLS options](https://doc.traefik.io/traefik/https/tls/#client-authentication-mtls)
