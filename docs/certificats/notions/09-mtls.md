# 09 — mTLS : authentification mutuelle

> **Type** : Notion · **Sujet** : Certificats · **Prérequis** : [Handshake TLS](./04-tls-handshake.md), [Chaîne de confiance & PKI](./03-chaine-de-confiance-pki.md)

## En une phrase

Dans TLS classique, **le serveur prouve son identité** au client via son certificat. Dans **mTLS** (mutual TLS), **le client prouve aussi son identité** au serveur, via son propre certificat. C'est une auth forte, cryptographique, sans mot de passe.

## La différence avec TLS classique

### TLS classique (one-way auth)
```
Client                          Serveur
  │                                │
  │── ClientHello ────────────────►│
  │                                │
  │◄────────── ServerHello ────────│
  │◄────────── Certificate ────────│   (le serveur prouve son identité)
  │◄──────── ServerHelloDone ──────│
  │                                │
  │── ClientKeyExchange ──────────►│
  │── ChangeCipherSpec/Finished ──►│
  │                                │
  │◄── ChangeCipherSpec/Finished ──│
  │                                │
  │═══ Données chiffrées ══════════│
```

Le client est **anonyme** côté TLS. L'authentification de l'utilisateur (login/mot de passe, token, etc.) se fait au niveau applicatif après l'établissement TLS.

### mTLS (two-way auth)
```
Client                          Serveur
  │                                │
  │── ClientHello ────────────────►│
  │                                │
  │◄────────── ServerHello ────────│
  │◄────────── Certificate ────────│   (serveur prouve son identité)
  │◄────── CertificateRequest ─────│   ★ NOUVEAU : demande cert client
  │◄──────── ServerHelloDone ──────│
  │                                │
  │── Certificate ────────────────►│   ★ NOUVEAU : client envoie son cert
  │── ClientKeyExchange ──────────►│
  │── CertificateVerify ──────────►│   ★ NOUVEAU : preuve de possession de la clé privée
  │── ChangeCipherSpec/Finished ──►│
  │                                │
  │◄── ChangeCipherSpec/Finished ──│
  │                                │
  │═══ Données chiffrées ══════════│
```

Trois étapes supplémentaires en gras. Cf. [Handshake TLS](./04-tls-handshake.md) pour le détail du flow général.

L'élément clé est **`CertificateVerify`** : le client signe un défi avec sa clé privée, prouvant qu'il **possède** vraiment la clé privée associée au cert (sinon n'importe qui pourrait présenter le cert public d'autrui).

## Pourquoi utiliser mTLS

mTLS apporte une **authentification forte cryptographique** :

- Pas de mot de passe à transmettre, stocker, hasher
- Pas de risque de réutilisation d'un token volé (signature à chaque handshake)
- Pas de phishing — la clé privée ne se "tape" pas
- Le serveur sait précisément **qui** est le client, avec une identité signée par une CA

### Cas d'usage typiques

- **APIs internes entre microservices** : le service A appelle le service B, mTLS garantit que c'est bien A.
- **Accès admin à des outils sensibles** : remplacement de basic auth pour des dashboards critiques.
- **IoT** : capteurs/devices avec un cert provisionné en usine.
- **VPN / Zero Trust** : briques de Wireguard alternatives, ou couche supplémentaire.
- **Connexions inter-cloud / B2B** : entre deux organisations qui se font confiance mutuellement.
- **Webhooks signés** : un service externe te notifie, mTLS confirme son identité.

## L'architecture d'une mise en place mTLS

```
        ┌──────────────────────┐
        │ CA cliente (interne) │   ← émet les certs clients
        └──────────┬───────────┘
                   │ signe
                   ▼
        ┌──────────────────────┐
        │ Certs clients        │   ← un par utilisateur/service/device
        │ (clé privée + cert)  │
        └──────────────────────┘
                   │
                   │ présentés lors du handshake
                   ▼
        ┌──────────────────────┐
        │ Serveur / Reverse    │
        │ proxy configuré      │
        │ pour exiger mTLS     │
        └──────────────────────┘
                   │
                   │ vérifie la signature avec
                   ▼
        ┌──────────────────────┐
        │ Cert CA cliente      │   ← fourni au serveur en confiance
        │ (public, sert        │
        │  d'ancre de trust)   │
        └──────────────────────┘
```

Le serveur a besoin du **cert public de la CA cliente** pour valider les certs présentés. Il **n'a pas** besoin des certs des clients individuels — la signature par la CA suffit.

## CA cliente : séparée ou partagée ?

Deux approches.

### CA dédiée aux clients

Une CA spécialement émise pour les certs clients, distincte de la CA qui signe les certs serveurs.

- ✅ Séparation propre : un cert signé par cette CA est **forcément** un cert client
- ✅ Révocation et politiques de durée de vie peuvent diverger
- ✅ Plus simple à scoper côté serveur (on ne fait confiance qu'à cette CA pour les clients)

C'est la pratique recommandée pour un déploiement propre.

### CA unique pour serveurs + clients

Une seule CA qui émet tout, distingué par les extensions :
- Cert serveur : `Extended Key Usage = serverAuth`
- Cert client : `Extended Key Usage = clientAuth`

- ✅ Une seule racine à gérer
- ❌ Mélange des préoccupations, audit plus complexe

Possible pour des homelabs simples, mais la séparation est plus propre dès qu'il y a plusieurs utilisateurs/services.

➡️ [Méthode : Créer une CA interne](../methodes/openssl-creer-ca-interne.md) — couvre la création de CA, applicable aussi pour une CA dédiée mTLS.

## Identifier un client dans son cert

Quels champs identifient un cert client ?

- **Common Name (CN)** : souvent utilisé en mTLS, contrairement aux certs serveur. C'est l'identité "humaine" du client (`CN=alice@example.com`, `CN=service-a`).
- **Subject Alternative Name** : peut contenir un email, URI SPIFFE, ou autre.
- **Organizational Unit (OU)** : parfois utilisé pour un rôle (`OU=admins`).
- **Numéro de série** : unique par cert, utilisable comme identifiant stable.

Le **serveur applicatif derrière le reverse proxy** doit pouvoir lire ces informations pour autoriser ou non l'accès à des ressources spécifiques. Les reverse proxies (Traefik, Nginx) peuvent transmettre les champs du cert client au backend via des headers HTTP custom.

## Modes de vérification côté serveur

Les serveurs/proxies offrent typiquement plusieurs modes :

| Mode | Comportement |
|------|--------------|
| `NoClientCert` | Pas de mTLS, TLS classique |
| `RequestClientCert` | Le serveur demande mais accepte si pas de cert |
| `RequireAnyClientCert` | Exige un cert, mais ne vérifie pas la chaîne |
| `VerifyClientCertIfGiven` | Si un cert est présenté, le valide ; sinon accepte |
| `RequireAndVerifyClientCert` | Exige un cert et valide la chaîne — **le mode "vrai mTLS"** |

➡️ [Méthode : Configurer mTLS dans Traefik](../methodes/traefik-mtls.md) — application avec ces modes.

## Provisioning : distribuer les certs clients

C'est la **partie la plus difficile** de mTLS en pratique.

Il faut :
1. Générer un cert pour chaque client (utilisateur, service, device)
2. Le distribuer **de manière sécurisée** au client
3. L'installer dans le bon endroit (trust store OS, ou config app)
4. Le renouveler avant expiration
5. Le révoquer si compromis

Approches courantes :

- **Manuel** (homelab) : générer une CSR, signer, distribuer via canal sécurisé (PKCS#12 par email chiffré, transfert hors bande)
- **ACME pour clients** : possible mais peu d'outillage public
- **SPIFFE/SPIRE** : standard pour identités de services en cloud
- **mTLS interne aux meshes** (Istio, Linkerd) : auto-provisioning par sidecar
- **MDM** (mobile device management) : pour distribuer à des téléphones/laptops d'entreprise

Format de livraison typique : **PKCS#12 (.p12)** avec mot de passe pour les clients humains, **PEM** pour les services.

➡️ [Notion : Formats de certificats](./06-formats-cert-pem-der-pkcs12.md) pour comprendre PKCS#12.

## Révocation en mTLS

Contrairement au web public où la révocation est en quasi-déclin (cf. [Révocation](./08-revocation-crl-ocsp.md)), en mTLS interne **la révocation reste critique** :

- Tu contrôles **à la fois** la CA et le serveur qui vérifie
- Tu peux donc imposer **hard-fail** sur CRL/OCSP
- C'est souvent la seule façon de couper l'accès rapidement à un utilisateur compromis (avant expiration)

Concrètement : ta CA interne maintient une CRL, ton serveur la consulte régulièrement, et un cert révoqué est rejeté immédiatement.

## Forces et limites — synthèse

### Forces
- Auth cryptographique forte, sans mot de passe
- Pas de session/cookie à voler
- Identité connue dès le handshake (avant tout traitement applicatif)
- Bien adapté aux échanges machine-à-machine

### Limites
- **Provisioning lourd** : distribuer un cert à des utilisateurs non techniques est compliqué
- **UX dégradée** côté humain : pas d'écran de login, ce qui surprend
- **Renouvellement** : si un cert client expire, l'utilisateur est bloqué jusqu'à émission d'un nouveau
- **Pas de granularité fine** par défaut : un cert valide donne l'accès à tout ce que la CA couvre, sauf si l'app fait du contrôle d'accès fin sur les champs du cert
- **Debugging plus complexe** que des logins classiques

🔑 mTLS shine pour les **APIs internes**, **services machine-à-machine**, **admin techniques**. Pour des utilisateurs grand public, on combine plutôt avec d'autres facteurs (OAuth + WebAuthn par exemple).

## À retenir

- mTLS = TLS où **le client présente aussi un certificat**, validé par le serveur.
- Repose sur une **CA cliente** dont le serveur a le cert public.
- 5 modes côté serveur, le "vrai mTLS" étant **`RequireAndVerifyClientCert`**.
- L'identité du client se lit dans son **CN/SAN/OU** — utilisable pour l'autorisation.
- Le **provisioning** est la grosse difficulté pratique.
- La **révocation** reste pertinente (contrairement au web public) car tu contrôles toute la chaîne.

## Pour aller plus loin

- [Méthode : Configurer mTLS dans Traefik](../methodes/traefik-mtls.md)
- [Méthode : Émettre un cert via sa CA interne](../methodes/openssl-emettre-cert-via-ca-interne.md) — pour produire les certs clients
- [Méthode : Inspecter et valider un certificat](../methodes/openssl-inspecter-valider-cert.md) — pour debug
- [Notion : Formats de certificats](./06-formats-cert-pem-der-pkcs12.md) — pour distribuer en PKCS#12
- [Notion : Révocation](./08-revocation-crl-ocsp.md) — pertinent en mTLS
- RFC 8446 (TLS 1.3) — section sur l'auth client
- [SPIFFE](https://spiffe.io/) — standard d'identité pour services
