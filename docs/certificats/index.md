# Certificats

Tout ce qui concerne TLS/SSL, PKI, certificats X.509, et leur gestion concrète derrière un reverse proxy Traefik sur des machines Linux. Le sujet couvre aussi le mTLS, la révocation, les formats de stockage, et la distribution sur tous les OS.

## Parcours suggéré

Si tu débutes sur le sujet, lis les notions dans l'ordre avant d'attaquer les méthodes :

1. [Cryptographie asymétrique](./notions/01-cryptographie-asymetrique.md) — la primitive de base
2. [Certificats X.509](./notions/02-certificats-x509.md) — le format universel
3. [Chaîne de confiance & PKI](./notions/03-chaine-de-confiance-pki.md) — pourquoi un certificat est "valide"
4. [Le handshake TLS](./notions/04-tls-handshake.md) — ce qui se passe quand un client se connecte
5. [ACME & Let's Encrypt](./notions/05-acme-letsencrypt.md) — l'automatisation moderne

Pour aller plus loin une fois les bases acquises :

6. [Formats de certificats](./notions/06-formats-cert-pem-der-pkcs12.md) — PEM, DER, PKCS#12, JKS
7. [SAN et wildcards](./notions/07-san-et-wildcards.md) — la version approfondie
8. [Révocation](./notions/08-revocation-crl-ocsp.md) — CRL, OCSP, et l'état en 2026
9. [mTLS](./notions/09-mtls.md) — authentification mutuelle

## Fiches notions

| Fiche | À comprendre avant de… |
|-------|------------------------|
| [01 — Cryptographie asymétrique](./notions/01-cryptographie-asymetrique.md) | Générer une clé, comprendre `.key` vs `.crt` |
| [02 — Certificats X.509](./notions/02-certificats-x509.md) | Lire un certificat, comprendre CN/SAN |
| [03 — Chaîne de confiance & PKI](./notions/03-chaine-de-confiance-pki.md) | Créer une CA interne, debug "untrusted certificate" |
| [04 — Handshake TLS](./notions/04-tls-handshake.md) | Debug `openssl s_client`, comprendre les erreurs TLS |
| [05 — ACME & Let's Encrypt](./notions/05-acme-letsencrypt.md) | Configurer un certresolver Traefik |
| [06 — Formats de certificats](./notions/06-formats-cert-pem-der-pkcs12.md) | Convertir entre PEM/DER/PKCS#12, distribuer sur un appareil |
| [07 — SAN et wildcards (approfondi)](./notions/07-san-et-wildcards.md) | Concevoir un cert multi-domaines ou wildcard correctement |
| [08 — Révocation : CRL, OCSP, 2026](./notions/08-revocation-crl-ocsp.md) | Décider de la stratégie de durée de vie + révocation |
| [09 — mTLS](./notions/09-mtls.md) | Mettre en place une authentification client par cert |

## Fiches méthodes

### Avec OpenSSL

| Méthode | Cas d'usage |
|---------|-------------|
| [Générer un certificat auto-signé](./methodes/openssl-generer-cert-autosigne.md) | Service interne sans nom de domaine public, test rapide |
| [Créer sa propre CA interne](./methodes/openssl-creer-ca-interne.md) | Émettre plusieurs certificats reconnus par tous les hôtes du réseau |
| [Émettre un certificat via sa CA interne](./methodes/openssl-emettre-cert-via-ca-interne.md) | Workflow CSR → signature, certs serveur ou client (mTLS) |
| [Inspecter et valider un certificat](./methodes/openssl-inspecter-valider-cert.md) | Lire, vérifier, diagnostiquer un cert local ou distant |
| [Convertir un cert entre formats](./methodes/openssl-convertir-formats-cert.md) | PEM ↔ DER ↔ PKCS#12 ↔ JKS pour adapter à la cible |

### Sur Linux et autres OS

| Méthode | Cas d'usage |
|---------|-------------|
| [Ajouter une CA au trust store Linux](./methodes/linux-ajouter-ca-au-trust-store.md) | Faire reconnaître une CA interne par `curl`, `git`, Docker, etc. |
| [Trust stores Windows, macOS, iOS, Android](./methodes/trust-store-windows-macos-mobile.md) | Distribuer une CA interne ou un cert client sur tous les OS |

### Avec Traefik

| Méthode | Cas d'usage |
|---------|-------------|
| [Let's Encrypt avec DNS challenge & wildcard](./methodes/traefik-letsencrypt-dns-challenge.md) | Couvrir `*.example.com` en un seul certificat |
| [Let's Encrypt avec HTTP challenge](./methodes/traefik-letsencrypt-http-challenge.md) | Setup simple, port 80 ouvert, pas de wildcard nécessaire |
| [Servir un certificat statique (fileProvider)](./methodes/traefik-certificat-statique.md) | Utiliser un certificat émis par une CA interne ou un fournisseur tiers |
| [Configurer mTLS dans Traefik](./methodes/traefik-mtls.md) | Protéger un endpoint par authentification cryptographique du client |
| [Forcer le renouvellement d'un certificat](./methodes/traefik-forcer-renouvellement.md) | Test, suspicion de compromission, changement de SAN |
| [Diagnostiquer un acme.json cassé](./methodes/traefik-debug-acme-json.md) | Certificats qui ne se génèrent plus, erreurs de challenge |

## À ajouter plus tard

Le sujet est désormais couvert dans ses fondamentaux et ses extensions. Pour les futures itérations :

- [ ] Certificate Transparency monitoring (méthode avec outils comme Cert Spotter)
- [ ] Cert pinning côté applicatif (notion)
- [ ] DANE et DNSSEC pour TLS (notion + méthode)
- [ ] Plugins Traefik / CrowdSec pour la détection d'anomalies TLS (méthode)
