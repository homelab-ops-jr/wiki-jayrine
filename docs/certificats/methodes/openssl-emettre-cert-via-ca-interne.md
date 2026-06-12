# Méthode — Émettre un certificat signé par sa CA interne

> **Type** : Méthode · **Outil** : OpenSSL · **Difficulté** : ⭐⭐ Intermédiaire

## Quand l'utiliser

- Tu as déjà créé une CA interne (cf. [Créer une CA interne](./openssl-creer-ca-interne.md))
- Tu veux émettre un cert pour un service interne, une machine, ou un client mTLS
- Tu veux contrôler les SAN, durées de vie, usages

C'est la suite directe de la création de CA. Sans CA, voir d'abord [Créer une CA interne](./openssl-creer-ca-interne.md).

## Vue d'ensemble du workflow

```
┌─────────────────────────┐
│ 1. Générer une clé      │   sur la machine cible (idéalement)
│    privée pour le cert  │
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ 2. Créer une CSR        │   contient pubkey + identité demandée
│    (avec SAN voulus)    │
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ 3. Transférer la CSR    │
│    à la CA              │
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ 4. La CA signe          │   produit le cert .pem
│    et émet le cert      │
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ 5. Retourner le cert    │
│    + chaîne au client   │
└─────────────────────────┘
```

Étape clé : **la clé privée ne quitte jamais la machine cible**. Seule la CSR (qui contient la pubkey, pas la privkey) voyage.

## Prérequis

- Une CA interne fonctionnelle : `ca.crt` + `ca.key` (+ `openssl-ca.cnf` si tu as suivi la méthode de référence)
- La CA est sur une machine de confiance (idéalement isolée, clé chiffrée par passphrase)

## Étape 1 — Générer la clé privée du cert

Sur la machine qui va utiliser le cert (server, client) :

```bash
# Clé EC (recommandé, plus rapide et plus court qu'RSA)
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out service.key

# Ou clé RSA 2048 (compatibilité maximale)
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out service.key
```

🔒 **Permissions strictes** sur la clé privée :
```bash
chmod 600 service.key
```

💡 EC P-256 est préférable en 2026 pour la plupart des cas. RSA reste utile si on a besoin d'une compatibilité avec des clients très anciens.

## Étape 2 — Créer la CSR

### Approche 1 — interactive (rapide, prototypage)

```bash
openssl req -new -key service.key -out service.csr
```

OpenSSL pose les questions interactivement (CN, O, etc.). Pour les SAN, voir l'approche 2 (interactive ne permet pas de SAN facilement).

### Approche 2 — fichier de config (recommandé, reproductible)

Créer `service.cnf` :

```ini
[ req ]
default_bits       = 2048
default_md         = sha256
prompt             = no
distinguished_name = dn
req_extensions     = req_ext

[ dn ]
C  = FR
ST = Region
L  = City
O  = HomeLab
OU = Services
CN = service.example.com

[ req_ext ]
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = service.example.com
DNS.2 = service.internal
IP.1  = 192.168.1.10
```

Générer la CSR :
```bash
openssl req -new -key service.key -out service.csr -config service.cnf
```

Vérifier ce qu'on a produit :
```bash
openssl req -in service.csr -noout -text -verify
```

➡️ Pour comprendre les SAN : [Notion : SAN et wildcards](../notions/07-san-et-wildcards.md). Pour inspecter en détail : [Inspecter et valider un certificat](./openssl-inspecter-valider-cert.md).

## Étape 3 — Transférer la CSR à la machine CA

Méthodes courantes :
- `scp service.csr ca-machine:/tmp/`
- Copier manuellement (la CSR n'est pas sensible — pas de clé privée)

⚠️ La CSR est **publique** (elle ne contient pas la clé privée). On peut la transmettre par n'importe quel canal. Seule la signature de la CA en fait un cert utilisable.

## Étape 4 — Signer la CSR avec la CA

### Approche minimaliste (sans config CA)

```bash
openssl x509 -req \
  -in service.csr \
  -CA ca.crt \
  -CAkey ca.key \
  -CAcreateserial \
  -out service.crt \
  -days 365 \
  -sha256
```

⚠️ **Problème** : les extensions de la CSR (notamment les SAN) **ne sont pas copiées** par défaut dans le cert final. Il faut les rajouter explicitement avec `-extfile` :

```bash
# Crée un fichier d'extensions
cat > service-ext.cnf <<EOF
authorityKeyIdentifier = keyid,issuer
basicConstraints       = CA:FALSE
keyUsage               = digitalSignature, keyEncipherment
extendedKeyUsage       = serverAuth
subjectAltName         = @alt_names

[alt_names]
DNS.1 = service.example.com
DNS.2 = service.internal
IP.1  = 192.168.1.10
EOF

openssl x509 -req \
  -in service.csr \
  -CA ca.crt \
  -CAkey ca.key \
  -CAcreateserial \
  -out service.crt \
  -days 365 \
  -sha256 \
  -extfile service-ext.cnf
```

### Approche propre (config CA + DB serial)

Si tu as suivi [Créer une CA interne](./openssl-creer-ca-interne.md), tu as un `openssl-ca.cnf` avec une structure `[ ca ]` et une base d'index. Signer devient :

```bash
openssl ca \
  -config openssl-ca.cnf \
  -extensions server_cert \
  -days 365 \
  -notext \
  -md sha256 \
  -in service.csr \
  -out service.crt
```

La section `server_cert` dans la config CA définit les extensions appliquées. Exemple typique :

```ini
[ server_cert ]
basicConstraints       = CA:FALSE
nsCertType             = server
nsComment              = "OpenSSL Generated Server Certificate"
subjectKeyIdentifier   = hash
authorityKeyIdentifier = keyid,issuer:always
keyUsage               = critical, digitalSignature, keyEncipherment
extendedKeyUsage       = serverAuth
subjectAltName         = @alt_names
```

Cette approche **tient une base d'émissions** (`index.txt`, `serial`, `crlnumber`) → tu peux ensuite révoquer, regénérer une CRL, etc. (cf. [Révocation](../notions/08-revocation-crl-ocsp.md)).

### Émettre un cert client (pour mTLS)

Le cert client diffère par son **extendedKeyUsage** : `clientAuth` au lieu (ou en plus) de `serverAuth` :

```ini
[ client_cert ]
basicConstraints       = CA:FALSE
keyUsage               = critical, digitalSignature
extendedKeyUsage       = clientAuth
subjectKeyIdentifier   = hash
authorityKeyIdentifier = keyid,issuer
# Le SAN d'un cert client est typiquement un email ou un identifiant unique
subjectAltName         = email:alice@example.com
```

Signature avec `-extensions client_cert`.

➡️ Voir [Notion : mTLS](../notions/09-mtls.md) et [Méthode : mTLS dans Traefik](./traefik-mtls.md).

## Étape 5 — Retourner le cert à la machine cible

Renvoyer **deux fichiers** :
- `service.crt` — le cert qu'on vient d'émettre
- `ca.crt` — le cert public de la CA (pour que les clients puissent valider, ou pour construire le fullchain)

Côté machine cible, créer le **fullchain** que les serveurs attendent en général :

```bash
cat service.crt ca.crt > service-fullchain.pem
```

Ordre : leaf en premier, puis chaîne intermédiaire (ici juste la racine puisque pas d'intermédiaire en CA simple), pas la clé privée.

## Vérification

```bash
# Inspecter le cert produit
openssl x509 -in service.crt -noout -text | grep -A 1 "Subject Alternative Name"

# Vérifier la chaîne
openssl verify -CAfile ca.crt service.crt
# Sortie attendue : service.crt: OK

# Vérifier le match cert <-> clé
openssl x509 -in service.crt -noout -pubkey | openssl md5
openssl pkey -in service.key -pubout | openssl md5
# Les deux md5 doivent être identiques
```

Cf. [Méthode : Inspecter et valider un certificat](./openssl-inspecter-valider-cert.md) pour le détail des vérifications.

## Déployer le cert

### Sur un serveur web (Nginx, Apache, Traefik)

Configurer le serveur pour pointer vers `service.key` et `service-fullchain.pem`.

Pour Traefik via fileProvider, voir [Traefik certificat statique](./traefik-certificat-statique.md).

### Sur un client mTLS

Le format dépend du client :
- **Linux/serveur** : PEM (cert + clé)
- **Windows/macOS/iOS/Android** : convertir en PKCS#12 (cf. [Convertir entre formats](./openssl-convertir-formats-cert.md))

Pour qu'un client externe accepte le cert serveur signé par cette CA, il doit **ajouter `ca.crt` à son trust store** (cf. [Ajouter une CA au trust store Linux](./linux-ajouter-ca-au-trust-store.md), et pour les autres OS [Trust stores Windows/macOS/mobile](./trust-store-windows-macos-mobile.md)).

## Durées de vie recommandées

| Usage | Durée |
|-------|-------|
| Cert serveur de service court terme | 90 jours (mimétisme Let's Encrypt) |
| Cert serveur de service interne long terme | 1 an |
| Cert client mTLS (humain) | 1 an |
| Cert client mTLS (service automatisé) | 90 jours, ou plus court avec automatisation |
| Cert intermédiaire d'une CA | 5-10 ans |
| Cert racine d'une CA | 10-20 ans |

⚠️ Plus la durée est longue, plus l'impact d'une compromission est élevé. Pour les services en homelab personnel, 1 an est un compromis raisonnable.

## Pièges fréquents

- **SAN manquants dans le cert final** : oubli de `-extfile` ou `-extensions`. Toujours vérifier avec `openssl x509 -text` que les SAN attendus sont présents.
- **Signer avec `openssl x509 -req` sans extensions** : produit un cert "nu", sans usage défini, refusé par beaucoup de clients modernes.
- **`Serial number reuse`** : sans approche propre (`-CAcreateserial` ou config CA), tu peux émettre deux certs avec le même serial — interdit dans les usages stricts.
- **Cert d'1 jour à 1 jour de validité** : `-days 0` produit un cert déjà expiré. Toujours préciser une valeur > 0 cohérente.
- **Erreur "TXT_DB error number 2"** lors d'une signature `openssl ca` : doublon dans `index.txt` (même CN déjà émis). Solution : émettre un nouveau cert avec un CN différent ou révoquer/nettoyer l'index.
- **Cert "client" présenté à un serveur** : si l'EKU est `clientAuth` uniquement, ne fonctionnera pas en cert serveur. Vérifier l'extension `Extended Key Usage`.

## À retenir

- Workflow : clé privée locale → CSR → signature CA → cert + chaîne au client.
- **La clé privée ne sort jamais** de la machine cible.
- Les **extensions** (SAN, EKU) doivent être explicitement appliquées à la signature — elles ne suivent pas automatiquement la CSR.
- Distinguer `serverAuth` (cert serveur) et `clientAuth` (cert client mTLS).
- Vérifier systématiquement avec `openssl x509 -text` et `openssl verify`.

## Pour aller plus loin

- [Créer une CA interne](./openssl-creer-ca-interne.md) — prérequis
- [Inspecter et valider un certificat](./openssl-inspecter-valider-cert.md) — pour vérifier
- [Convertir un cert entre formats](./openssl-convertir-formats-cert.md) — pour distribuer en PKCS#12
- [Méthode : Configurer mTLS dans Traefik](./traefik-mtls.md)
- [Notion : SAN et wildcards](../notions/07-san-et-wildcards.md)
- [Notion : mTLS](../notions/09-mtls.md)
- Référence : `man openssl-ca`, `man openssl-req`, `man openssl-x509`
