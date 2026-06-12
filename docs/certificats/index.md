# Certificats

Tout ce qui concerne TLS/SSL, PKI, certificats X.509, et leur gestion concrète derrière un reverse proxy Traefik sur des machines Linux.

## Parcours suggéré

Si tu débutes sur le sujet, lis les notions dans l'ordre avant d'attaquer les méthodes :

1. [Cryptographie asymétrique](./notions/01-cryptographie-asymetrique.md) — la primitive de base
2. [Certificats X.509](./notions/02-certificats-x509.md) — le format universel
3. [Chaîne de confiance & PKI](./notions/03-chaine-de-confiance-pki.md) — pourquoi un certificat est "valide"
4. [Le handshake TLS](./notions/04-tls-handshake.md) — ce qui se passe quand un client se connecte
5. [ACME & Let's Encrypt](./notions/05-acme-letsencrypt.md) — l'automatisation moderne

## Fiches notions

| Fiche | À comprendre avant de… |
|-------|------------------------|
| [01 — Cryptographie asymétrique](./notions/01-cryptographie-asymetrique.md) | Générer une clé, comprendre `.key` vs `.crt` |
| [02 — Certificats X.509](./notions/02-certificats-x509.md) | Lire un certificat, comprendre CN/SAN |
| [03 — Chaîne de confiance & PKI](./notions/03-chaine-de-confiance-pki.md) | Créer une CA interne, debug "untrusted certificate" |
| [04 — Handshake TLS](./notions/04-tls-handshake.md) | Debug `openssl s_client`, comprendre les erreurs TLS |
| [05 — ACME & Let's Encrypt](./notions/05-acme-letsencrypt.md) | Configurer un certresolver Traefik |

## Fiches méthodes

### Avec OpenSSL

| Méthode | Cas d'usage |
|---------|-------------|
| [Générer un certificat auto-signé](./methodes/openssl-generer-cert-autosigne.md) | Service interne sans nom de domaine public, test rapide |
| [Créer sa propre CA interne](./methodes/openssl-creer-ca-interne.md) | Émettre plusieurs certificats reconnus par tous les hôtes du réseau |

### Sur Linux

| Méthode | Cas d'usage |
|---------|-------------|
| [Ajouter une CA au trust store système](./methodes/linux-ajouter-ca-au-trust-store.md) | Faire reconnaître une CA interne par `curl`, `git`, Docker, etc. |

### Avec Traefik

| Méthode | Cas d'usage |
|---------|-------------|
| [Let's Encrypt avec DNS challenge & wildcard](./methodes/traefik-letsencrypt-dns-challenge.md) | Couvrir `*.example.com` en un seul certificat |
| [Servir un certificat statique (fileProvider)](./methodes/traefik-certificat-statique.md) | Utiliser un certificat émis par une CA interne ou un fournisseur tiers |
| [Diagnostiquer un acme.json cassé](./methodes/traefik-debug-acme-json.md) | Certificats qui ne se génèrent plus, erreurs de challenge |

## À ajouter plus tard

- [ ] mTLS — authentification mutuelle client/serveur (notion + méthode Traefik)
- [ ] Let's Encrypt avec HTTP challenge (méthode Traefik)
- [ ] Émettre un certificat signé par sa CA interne (méthode OpenSSL)
- [ ] Inspecter et valider un certificat (méthode OpenSSL — `s_client`, `x509`, `verify`)
- [ ] Formats de certificats : PEM, DER, PKCS#12, JKS (notion)
- [ ] SAN et wildcards (notion approfondie)
- [ ] Révocation : CRL et OCSP (notion)
- [ ] Forcer le renouvellement d'un certificat Traefik (méthode)
- [ ] Trust store sur Windows, Android, iOS (méthode multi-OS)
