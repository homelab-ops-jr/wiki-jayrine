# 03 — Chaîne de confiance & PKI

> **Type** : Notion · **Sujet** : Certificats · **Prérequis** : [Certificats X.509](./02-certificats-x509.md)

## En une phrase

La **PKI** (Public Key Infrastructure) est l'écosystème qui permet à un navigateur de décider, sans intervention humaine, qu'un certificat présenté par un serveur est légitime — grâce à une chaîne de signatures qui remonte jusqu'à une autorité reconnue.

## Le problème

Si je présente un certificat qui dit "je suis `bank.example.com`, signé par moi-même", n'importe qui peut faire pareil et usurper l'identité de la banque. Il faut donc qu'un **tiers de confiance** atteste de l'association entre l'identité et la clé publique.

Ce tiers, c'est l'**Autorité de Certification** (CA en anglais — *Certificate Authority*).

## La chaîne

Une chaîne de certification typique pour un site web ressemble à ça :

```
┌─────────────────────────────────────┐
│ Root CA (auto-signée)               │ ← présente dans le trust store du navigateur
│   ex: ISRG Root X1                  │
└──────────────┬──────────────────────┘
               │ signe
               ▼
┌─────────────────────────────────────┐
│ Intermediate CA                     │ ← présentée par le serveur
│   ex: Let's Encrypt R3              │
└──────────────┬──────────────────────┘
               │ signe
               ▼
┌─────────────────────────────────────┐
│ Leaf certificate                    │ ← le cert "réel" du site
│   ex: jayrine.com                   │
└─────────────────────────────────────┘
```

Trois niveaux, parfois deux (pas d'intermédiaire), rarement plus.

### Pourquoi un intermédiaire ?

La clé privée de la **root CA** est ultra-sensible : si elle fuite, toutes les CA publiques sont à révoquer. On la met donc dans un coffre-fort hors-ligne (HSM dans une cage Faraday). Pour ne pas y toucher au quotidien, on utilise une **CA intermédiaire** dont la clé privée est en ligne et signe les certificats des clients.

Si l'intermédiaire est compromis, on le révoque et on en émet un nouveau, sans toucher à la root.

## Comment la validation se passe

Quand un navigateur reçoit un certificat lors d'un handshake TLS, il :

1. Récupère le **leaf** (envoyé par le serveur) et la ou les **CA intermédiaires** (le serveur DOIT les fournir aussi).
2. Vérifie la signature du leaf avec la clé publique de l'intermédiaire.
3. Vérifie la signature de l'intermédiaire avec la clé publique de la root.
4. Vérifie que la **root** est présente dans son **trust store** local.
5. Vérifie : période de validité, SAN qui matche le hostname demandé, statut de révocation (CRL ou OCSP), absence d'extensions critiques inconnues, etc.

Si **un seul de ces points échoue**, le navigateur affiche l'erreur classique (`NET::ERR_CERT_AUTHORITY_INVALID`, `SEC_ERROR_UNKNOWN_ISSUER`, etc.).

⚠️ **Piège fréquent** : un serveur qui ne sert que son leaf sans les intermédiaires. Le client moderne peut parfois fetcher l'intermédiaire via l'extension `AIA` du certificat (Authority Information Access), mais beaucoup de bibliothèques (vieilles JVM, certaines apps mobiles, `curl` sans `--ca-native`) ne le font pas et tombent en erreur. **Toujours servir la chaîne complète** (sauf la root).

## Le trust store

Le **trust store** est la liste des CA root auxquelles ton système (ou ton navigateur) fait confiance par défaut. Sa localisation varie :

| Système / Logiciel | Emplacement |
|--------------------|-------------|
| Debian/Ubuntu | `/etc/ssl/certs/ca-certificates.crt` (bundle), `/usr/local/share/ca-certificates/` (ajouts admin) |
| RHEL/Fedora | `/etc/pki/ca-trust/source/anchors/` |
| Alpine | `/etc/ssl/certs/` |
| Firefox | Trust store **propre** (NSS) — `~/.mozilla/firefox/<profile>/cert9.db` |
| Chrome/Chromium | Trust store système (Linux) |
| Java | `cacerts` dans le `JRE` (`$JAVA_HOME/lib/security/cacerts`) |
| macOS | Keychain Access |
| Windows | Certificate Manager (`certmgr.msc`) |

Quand tu crées une **CA interne** (cf. fiche méthode), tu dois la déposer dans le trust store de chaque machine/app qui doit lui faire confiance.

🔒 Le contenu du trust store est **la racine** de la sécurité TLS de la machine. Y ajouter une CA, c'est lui donner le pouvoir de produire des certs pour **n'importe quel domaine** (y compris `google.com`) qui seront acceptés. À faire en connaissance de cause.

## CA publiques vs CA privées

| | CA publique | CA privée (interne) |
|---|-------------|---------------------|
| Présente dans les trust stores ? | ✅ Oui, partout par défaut | ❌ Non, à ajouter manuellement |
| Validation de domaine | Obligatoire (DV/OV/EV) | Tu décides |
| Coût | Souvent gratuit (Let's Encrypt) ou payant | Gratuit (c'est toi qui l'opères) |
| Cas d'usage | Sites publics | Réseau interne, mTLS, dev, IoT |
| Exemples | Let's Encrypt, ZeroSSL, DigiCert, Sectigo | Ta CA OpenSSL maison, [step-ca](https://smallstep.com/docs/step-ca/), Vault PKI |

Pour un homelab où tout passe par Traefik avec des domaines publics (`*.jayrine.com`), **Let's Encrypt suffit toujours** : pas besoin de CA interne.

La CA interne devient utile quand :
- Tu as des services **non exposés** sur Internet sans nom de domaine public (machines internes, IoT)
- Tu fais du **mTLS** (authentification client par certificat)
- Tu as un environnement **air-gapped** sans accès à Let's Encrypt
- Tu veux des certificats pour des **noms d'hôte courts** (`nas`, `printer`) ou des IPs

## La PKI en pratique : que faut-il pour en monter une ?

Une PKI privée minimale comprend :

1. **Une clé privée + un certificat root** auto-signés
2. **Optionnel** : une CA intermédiaire signée par la root (pour les bonnes pratiques)
3. **Un processus d'émission** : générer une CSR (Certificate Signing Request), la signer, livrer le cert au demandeur
4. **Un trust store** sur chaque machine qui doit faire confiance à la CA
5. **Idéalement** : un mécanisme de révocation (CRL ou OCSP) et de renouvellement

Pour un homelab modeste, OpenSSL en ligne de commande suffit (cf. [méthode dédiée](../methodes/openssl-creer-ca-interne.md)). Pour quelque chose de plus sérieux (rotation auto, ACME interne), regarder `step-ca` ou Vault PKI.

## À retenir

- Un certificat n'est "valide" que parce qu'on remonte sa chaîne de signatures jusqu'à une **CA dans le trust store**.
- Toujours servir le **leaf + intermédiaires**, jamais la root.
- Le trust store est **le** point de confiance, à protéger comme tel.
- Pour un homelab à domaines publics, **Let's Encrypt** dispense de monter une PKI interne.
- CA interne = solution pour le mTLS, l'air-gap, les noms d'hôte courts.

## Pour aller plus loin

- [Le handshake TLS](./04-tls-handshake.md) — la chaîne en action
- [Créer sa propre CA interne avec OpenSSL](../methodes/openssl-creer-ca-interne.md)
- [Ajouter une CA au trust store Linux](../methodes/linux-ajouter-ca-au-trust-store.md)
