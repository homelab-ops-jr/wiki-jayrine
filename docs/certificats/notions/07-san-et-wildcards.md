# 07 — SAN et wildcards (approfondi)

> **Type** : Notion · **Sujet** : Certificats · **Prérequis** : [Certificats X.509](./02-certificats-x509.md), [ACME & Let's Encrypt](./05-acme-letsencrypt.md)

## En une phrase

Le **Subject Alternative Name (SAN)** est l'extension X.509 qui liste les identités couvertes par un certificat — le seul champ pris en compte par les navigateurs modernes. Les **wildcards** (`*.example.com`) sont une forme particulière de SAN, soumise à des règles précises et souvent mal comprises.

## Le contexte historique : CN vs SAN

À l'origine, X.509 prévoyait que l'identité d'un cert serveur soit dans le **Common Name** du `Subject` :

```
Subject: CN=www.example.com
```

Problème : un seul nom par cert. Pas adapté au web moderne.

L'extension **Subject Alternative Name** (RFC 5280) a réglé ça :

```
X509v3 Subject Alternative Name:
    DNS:example.com, DNS:www.example.com, DNS:api.example.com
```

🔑 **Depuis Chrome 58 (2017)**, le CN est **complètement ignoré** pour la validation. Tous les noms doivent être dans le SAN, sinon le cert est rejeté. Firefox, Safari, Edge ont suivi. En 2026, **un certificat sans SAN est inutilisable**.

Pour la compatibilité, les CA mettent souvent le premier SAN également dans le CN — mais c'est cosmétique, seul le SAN compte.

## Les types de SAN

L'extension SAN supporte plusieurs types d'identité :

| Type | Usage | Exemple |
|------|-------|---------|
| `DNS` | Nom d'hôte (le plus courant) | `DNS:api.example.com` |
| `IP Address` | Adresse IP | `IP:203.0.113.42` |
| `URI` | URL complète (rare, parfois pour mTLS) | `URI:spiffe://example.com/server` |
| `email` | Adresse email (S/MIME) | `email:admin@example.com` |
| `otherName` | Identifiants personnalisés | divers (UPN Windows, etc.) |

Le type `DNS` couvre 99% des usages web. `IP` est légitime mais rare (accès direct par IP sans nom). Les CAs publiques restreignent fortement l'émission de certs avec SAN `IP` — internes ou Let's Encrypt n'en émettent pas.

## Les wildcards : règles précises

Un SAN peut être un **wildcard** : `*.example.com`. Il couvre **tous les sous-domaines d'un niveau exactement**.

### Ce qu'un wildcard couvre

`*.example.com` matche :
- ✅ `api.example.com`
- ✅ `www.example.com`
- ✅ `nextcloud.example.com`
- ✅ `wiki.example.com`

### Ce qu'un wildcard NE couvre PAS

- ❌ `example.com` lui-même — l'apex domain n'est **pas** couvert par `*.example.com`
- ❌ `app.api.example.com` — deux niveaux de profondeur, le wildcard est mono-niveau
- ❌ `api.example.org` — TLD différent évidemment

Donc si tu veux couvrir à la fois l'apex et les sous-domaines, **il faut deux SAN** dans le cert :

```
DNS:example.com, DNS:*.example.com
```

Ou plus précis :

```
DNS:example.com, DNS:www.example.com, DNS:*.example.com
```

### Wildcards imbriqués : impossibles

`*.*.example.com` est **invalide** selon la RFC. Les CAs refusent d'émettre. Pour couvrir plusieurs niveaux, soit lister explicitement, soit émettre plusieurs certs séparés.

### Wildcards partiels : techniquement possibles, mais...

`web*.example.com` ou `*-staging.example.com` sont **techniquement valides** selon la RFC 6125, mais :

- Les CAs publiques (Let's Encrypt, DigiCert, etc.) **refusent** de les émettre
- Beaucoup de clients TLS les rejettent (Chrome, navigateurs mobiles)

En pratique, considère qu'un wildcard occupe l'**entier** de son label. Pas de wildcards partiels.

### Position du wildcard

Le wildcard doit être le **label le plus à gauche** :

- ✅ `*.example.com`
- ✅ `*.api.example.com`
- ❌ `api.*.example.com` (refusé par les CAs et la plupart des clients)

## Wildcards et ACME / Let's Encrypt

Let's Encrypt **émet des wildcards depuis 2018**, mais uniquement via le **DNS challenge** (cf. [ACME & Let's Encrypt](./05-acme-letsencrypt.md)).

Pourquoi ? Le HTTP challenge prouve que tu contrôles `app.example.com` en répondant sur ce nom précis. Mais pour un wildcard `*.example.com`, **il n'existe pas de "hostname" précis** à challenger — Let's Encrypt exige donc une preuve **au niveau de la zone DNS** : créer un enregistrement TXT sur `_acme-challenge.example.com`, ce qui démontre le contrôle de toute la zone.

➡️ Voir [Méthode : Let's Encrypt avec DNS challenge](../methodes/traefik-letsencrypt-dns-challenge.md).

## Wildcards vs SAN explicites : ce que tu sacrifies en sécurité

Un wildcard est **pratique** : un cert couvre N sous-domaines, un seul renouvellement à gérer. Mais :

- **Compromission = explosion du blast radius** : si la clé privée d'un cert wildcard fuite, tous les sous-domaines sont vulnérables à un MITM.
- **Visibilité moindre** dans les CT logs : tu publies "j'émets pour `*.example.com`" sans détailler les sous-domaines effectivement servis.
- **Couplage des renouvellements** : un seul cert pour beaucoup de services → si le renouvellement casse, beaucoup tombent en même temps.

Inversement, **N certs distincts** :

- Isolation des compromis
- Auditabilité dans les CT logs
- Plus de gestion (mais avec ACME et automatisation, le coût est faible)

### Recommandations

- **Homelab personnel solo** : wildcard pragmatique, surface d'attaque limitée.
- **Multi-tenant ou production** : certs distincts par service, renouvellement automatisé.
- **Cas hybride** : un wildcard pour les services internes/admin + certs distincts pour les services exposés.

## SAN dans la CSR vs cert final

Quand on génère une CSR (Certificate Signing Request), on **propose** les SAN voulus, mais c'est la CA qui décide d'émettre ou non.

- Les **CAs publiques** vérifient le contrôle (ACME, validation manuelle) avant d'inclure chaque SAN
- Les **CAs internes** (la tienne) acceptent ce que tu mets dans la CSR sans vérification

➡️ Application : [Méthode : Émettre un cert via sa CA interne](../methodes/openssl-emettre-cert-via-ca-interne.md).

## Inspecter les SAN d'un cert

```bash
# Cert local
openssl x509 -in cert.pem -noout -ext subjectAltName

# Cert distant
openssl s_client -connect example.com:443 -servername example.com </dev/null 2>/dev/null \
  | openssl x509 -noout -ext subjectAltName
```

➡️ Détaillé dans [Méthode : Inspecter et valider un certificat](../methodes/openssl-inspecter-valider-cert.md).

## Limites pratiques par CA

- **Let's Encrypt** : jusqu'à 100 SAN par cert (DNS uniquement), pas d'IP, wildcards via DNS challenge.
- **CAs commerciales (DigiCert, Sectigo, etc.)** : limites variables, parfois payant au-delà d'un seuil (3, 10, ou 25 SAN).
- **CA interne** : pas de limite technique sauf celle imposée par l'outil (OpenSSL accepte largement plus que ce qu'on aura besoin).

## Pièges fréquents

- **Oublier l'apex** : tu génères un cert pour `*.example.com` puis tu visites `https://example.com` → erreur cert. Toujours inclure les deux SAN si l'apex est servi.
- **Compter sur le CN** : il est ignoré. Inutile de mettre `CN=www.example.com` sans le mettre aussi en SAN.
- **Cert wildcard côté serveur ≠ cert wildcard pour mTLS** : un cert client pour mTLS n'utilise pas de wildcard sur ses noms — l'identité d'un client est en général unique.
- **Renouvellement Let's Encrypt qui casse parce qu'un SAN change** : ajouter/retirer un SAN = nouveau cert. Le renouvellement automatique se base sur la liste exacte des SAN.
- **`CN=*` sans SAN** : invalide en 2026. Le SAN est obligatoire.

## À retenir

- **Le SAN est obligatoire**, le CN est ignoré depuis 2017.
- **Wildcard = mono-niveau**, et ne couvre pas l'apex.
- Wildcards Let's Encrypt = **DNS challenge obligatoire**.
- Wildcard pratique mais **blast radius plus grand** en cas de compromission.
- Pas de wildcards partiels (`web*`) en pratique.
- Inspecter les SAN d'un cert : `openssl x509 -noout -ext subjectAltName`.

## Pour aller plus loin

- [Méthode : Inspecter et valider un certificat](../methodes/openssl-inspecter-valider-cert.md)
- [Méthode : Émettre un cert via sa CA interne](../methodes/openssl-emettre-cert-via-ca-interne.md)
- [Méthode : Let's Encrypt avec DNS challenge](../methodes/traefik-letsencrypt-dns-challenge.md)
- RFC 5280 (X.509) — section sur Subject Alternative Name
- RFC 6125 — règles de matching des identifiants
