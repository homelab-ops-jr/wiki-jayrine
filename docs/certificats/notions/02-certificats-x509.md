# 02 — Certificats X.509

> **Type** : Notion · **Sujet** : Certificats · **Prérequis** : [Cryptographie asymétrique](./01-cryptographie-asymetrique.md)

## En une phrase

Un certificat X.509 est un **document structuré** qui associe une clé publique à une identité, signé par une autorité de certification (CA) pour attester de cette association.

## Pourquoi "X.509" ?

C'est le nom d'une **norme UIT-T** (`ITU-T X.509`), reprise par l'IETF dans la RFC 5280. C'est le format universel utilisé pour TLS/HTTPS, S/MIME, signature de code, VPN, etc. Quand on dit "un certificat SSL", c'est un certificat X.509 utilisé pour TLS.

## Anatomie d'un certificat

Un certificat X.509 contient principalement :

| Champ | Contenu | Exemple |
|-------|---------|---------|
| **Version** | Version du format X.509 | v3 (standard actuel) |
| **Serial Number** | Identifiant unique attribué par la CA | `03:f1:a2:...` |
| **Signature Algorithm** | Algorithme utilisé pour signer ce cert | `sha256WithRSAEncryption` |
| **Issuer** | Identité de la CA qui a signé | `CN=Let's Encrypt R3, O=Let's Encrypt, C=US` |
| **Validity** | Période de validité | `Not Before: 2026-01-15 / Not After: 2026-04-15` |
| **Subject** | Identité du titulaire du certificat | `CN=jayrine.com` |
| **Subject Public Key Info** | La clé publique elle-même + son algo | RSA 2048 bits / ECDSA P-256 |
| **Extensions** | Métadonnées additionnelles (v3) | SAN, Key Usage, Basic Constraints… |
| **Signature** | Signature de la CA sur tout ce qui précède | Long blob binaire |

## Les extensions critiques en pratique

Les extensions X.509 v3 sont là où se trouve la quasi-totalité de la complexité moderne. Quelques-unes à connaître :

### Subject Alternative Name (SAN)

Liste les noms de domaine que le certificat couvre. **C'est le champ qui compte aujourd'hui**, pas le `CN` du Subject (déprécié pour cet usage depuis Chrome 58, 2017).

```
X509v3 Subject Alternative Name:
    DNS:jayrine.com, DNS:www.jayrine.com, DNS:*.jayrine.com
```

Un certificat avec un seul SAN `*.jayrine.com` est un **wildcard** : il couvre `accueil.jayrine.com`, `git.jayrine.com`, etc., mais **pas** `jayrine.com` lui-même (il faut le rajouter) ni `sub.accueil.jayrine.com` (un seul niveau de wildcard).

### Basic Constraints

Indique si ce certificat peut lui-même signer d'autres certificats :

```
X509v3 Basic Constraints: critical
    CA:TRUE   ← c'est un certificat d'autorité (CA)
    CA:FALSE  ← c'est un certificat feuille (serveur, client)
```

### Key Usage / Extended Key Usage

Précisent les usages autorisés. Pour un cert serveur web :

```
X509v3 Key Usage: Digital Signature, Key Encipherment
X509v3 Extended Key Usage: TLS Web Server Authentication
```

Pour un cert client mTLS :
```
X509v3 Extended Key Usage: TLS Web Client Authentication
```

## Subject vs CN vs SAN — la confusion classique

- **Subject** = champ complet (`CN=…, O=…, C=…`)
- **CN** (Common Name) = un attribut DU Subject (`CN=jayrine.com`)
- **SAN** = extension v3, **liste** de noms

⚠️ Historiquement le `CN` portait le nom de domaine. Aujourd'hui les navigateurs et bibliothèques modernes (curl, Go, etc.) **ignorent le CN** et ne regardent que les SAN pour valider un certificat HTTPS. Si tu génères un certificat sans SAN, il sera rejeté même si le CN matche.

## Les formats d'encodage

Le même certificat peut exister sous plusieurs formats. C'est uniquement une question d'encodage, pas de contenu :

| Format | Encodage | Extension typique | Usage |
|--------|----------|-------------------|-------|
| **PEM** | Base64 + délimiteurs ASCII | `.pem`, `.crt`, `.cer` | Tout-terrain Linux, Apache, NGINX, Traefik |
| **DER** | Binaire brut | `.der`, `.cer` | Windows, Java |
| **PKCS#7** | PEM ou DER, conteneur multi-certs | `.p7b`, `.p7c` | Microsoft, échange de chaînes |
| **PKCS#12** | Binaire chiffré, cert + clé privée | `.p12`, `.pfx` | Windows, mobile, import navigateur |

Un fichier PEM ressemble à ça :
```
-----BEGIN CERTIFICATE-----
MIIDazCCAlOgAwIBAgIUJl...
... (base64) ...
-----END CERTIFICATE-----
```

💡 Conversion fréquente : passer d'un `.pfx` (donné par un fournisseur enterprise) à `.crt` + `.key` séparés (pour Traefik/NGINX) :
```bash
openssl pkcs12 -in cert.pfx -nokeys -out cert.crt
openssl pkcs12 -in cert.pfx -nocerts -nodes -out cert.key
```

## Lire un certificat en clair

Pour décoder un certificat PEM et voir ses champs :
```bash
openssl x509 -in server.crt -noout -text
```

Sortie typique (extrait) :
```
Certificate:
    Data:
        Version: 3 (0x2)
        Serial Number: 03:e2:...
        Issuer: C=US, O=Let's Encrypt, CN=R3
        Validity
            Not Before: Jan 15 00:00:00 2026 GMT
            Not After : Apr 15 23:59:59 2026 GMT
        Subject: CN=jayrine.com
        ...
```

Voir la fiche méthode dédiée pour les variantes utiles (`openssl-inspecter-certificat.md`, à venir).

## À retenir

- Un certificat = clé publique + identité + métadonnées + signature de la CA.
- **Le SAN fait foi**, le CN seul est obsolète pour TLS web.
- Les extensions (`Basic Constraints`, `Key Usage`) déterminent ce qu'un certificat **peut faire**.
- PEM, DER, PKCS#12 = mêmes données, encodages différents.
- Un certificat ne contient **jamais** la clé privée associée. Elle est sur le serveur, à part.

## Pour aller plus loin

- [Chaîne de confiance & PKI](./03-chaine-de-confiance-pki.md) — comment ce certificat devient "valide" aux yeux d'un navigateur
- RFC 5280 — spécification de référence (dense mais c'est la source)
