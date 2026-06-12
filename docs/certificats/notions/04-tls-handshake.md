# 04 — Le handshake TLS

> **Type** : Notion · **Sujet** : Certificats · **Prérequis** : [Chaîne de confiance & PKI](./03-chaine-de-confiance-pki.md)

## En une phrase

Le **handshake TLS** est le dialogue initial entre client et serveur qui, en quelques aller-retours, négocie les paramètres cryptographiques, authentifie le serveur (et parfois le client), et établit un **secret partagé** pour chiffrer la suite de la communication.

## Pourquoi c'est important

Quand un service ne marche pas en HTTPS, la cause est presque toujours dans le handshake. Comprendre ses étapes permet de lire les erreurs `openssl s_client`, identifier où ça bloque (négociation de version ? validation du cert ? SNI ?), et savoir où regarder.

## TLS 1.2 vs TLS 1.3

Aujourd'hui (2026), **TLS 1.3** (RFC 8446, 2018) domine, mais TLS 1.2 reste majoritairement supporté. TLS 1.3 :

- Est plus rapide (1 round-trip au lieu de 2 dans le cas nominal, voire 0 avec resumption)
- Force la **Perfect Forward Secrecy** (PFS) — pas de compromis possible avec RSA key exchange statique
- Supprime des dizaines d'algorithmes vieux/cassés (RC4, MD5, SHA-1, RSA static, etc.)
- Chiffre une partie de la phase de handshake elle-même

Toutes les versions antérieures à TLS 1.2 sont **dépréciées** (TLS 1.0/1.1 désactivées sur navigateurs modernes depuis 2020). SSL 2.0 et 3.0 sont mortes depuis longtemps.

## Le handshake TLS 1.3, étape par étape

```
Client                                         Serveur
  │                                              │
  │ ── ClientHello ──────────────────────────►   │
  │   • Versions TLS supportées                  │
  │   • Suites cryptographiques proposées        │
  │   • Random client                            │
  │   • SNI: "jayrine.com"   ◄── important       │
  │   • Key share (groupes ECDHE proposés)       │
  │                                              │
  │   ◄── ServerHello ──────────────────────     │
  │      • Version TLS choisie                   │
  │      • Suite crypto choisie                  │
  │      • Random serveur                        │
  │      • Key share serveur                     │
  │                                              │
  │   À ce point, les deux parties dérivent      │
  │   une clé partagée via ECDHE.                │
  │   Tout ce qui suit est CHIFFRÉ.              │
  │                                              │
  │   ◄── Certificate ───────────────────────    │
  │      • Leaf + intermédiaires                 │
  │                                              │
  │   ◄── CertificateVerify ─────────────────    │
  │      • Signature serveur sur le handshake    │
  │      • Prouve la possession de la clé privée │
  │                                              │
  │   ◄── Finished ──────────────────────────    │
  │                                              │
  │ ── Finished ─────────────────────────────►   │
  │                                              │
  │ ═══ Données applicatives chiffrées ═══      │
```

## Les notions-clés à connaître

### Cipher Suite

Le bundle d'algos négocié. Format TLS 1.3 :
```
TLS_AES_256_GCM_SHA384
└── préfixe  └── chiffrement  └── MAC/PRF
```

Format TLS 1.2 (plus verbeux) :
```
TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
    └── kex   └── auth └── chiffrement      └── MAC
```

### ECDHE (Elliptic Curve Diffie-Hellman Ephemeral)

Méthode d'échange de clés qui produit un secret de session **temporaire** (ephemeral). Garantit la **Perfect Forward Secrecy** : même si la clé privée du serveur fuite plus tard, les sessions passées restent illisibles (parce que les paramètres ECDHE ont été jetés).

### SNI (Server Name Indication)

Le **nom de domaine demandé** est envoyé en clair dans le `ClientHello`. C'est ce qui permet à un reverse proxy comme Traefik, qui héberge plusieurs domaines sur la même IP/port, de savoir **quel certificat servir**.

⚠️ Sans SNI, le serveur ne saurait pas quel cert présenter. C'est aussi pourquoi le SNI est un point de surveillance réseau (le DPI sait quel site tu visites même sans pouvoir lire le trafic). **ECH** (Encrypted Client Hello) résout ce problème mais n'est pas encore universel.

### Validation du certificat côté client

Une fois le `Certificate` reçu, le client effectue toutes les vérifications décrites dans la fiche [Chaîne de confiance & PKI](./03-chaine-de-confiance-pki.md) :

1. La chaîne remonte-t-elle à une root du trust store ?
2. Les signatures sont-elles valides ?
3. Le certificat est-il dans sa période de validité ?
4. Le SAN matche-t-il le hostname demandé (celui du SNI) ?
5. Le certificat n'est-il pas révoqué (CRL/OCSP) ?
6. Les extensions critiques sont-elles connues et compatibles ?

Si l'une échoue : erreur de validation, connexion refusée (ou warning si l'utilisateur·rice insiste).

## Inspecter un handshake en pratique

L'outil de référence est `openssl s_client`. Il joue le rôle d'un client TLS minimaliste :

```bash
openssl s_client -connect jayrine.com:443 -servername jayrine.com
```

- `-connect host:port` : où se connecter
- `-servername` : SNI à envoyer. **À toujours mettre** sinon `s_client` n'envoie pas de SNI, et tu obtiendras potentiellement un mauvais certificat (le "default" de Traefik).

Sortie typique (extraits importants) :
```
CONNECTED(00000003)
depth=2 C=US, O=Internet Security Research Group, CN=ISRG Root X1
verify return:1
depth=1 C=US, O=Let's Encrypt, CN=R3
verify return:1
depth=0 CN=jayrine.com
verify return:1
---
Certificate chain
 0 s:CN=jayrine.com
   i:C=US, O=Let's Encrypt, CN=R3
 1 s:C=US, O=Let's Encrypt, CN=R3
   i:C=US, O=Internet Security Research Group, CN=ISRG Root X1
---
SSL handshake has read 5274 bytes and written 421 bytes
---
New, TLSv1.3, Cipher is TLS_AES_256_GCM_SHA384
Server public key is 2048 bit
...
Verify return code: 0 (ok)
```

Points à lire :
- `depth=N` : chaque cran de la chaîne. `depth=0` est le leaf.
- `Certificate chain` : la chaîne servie par le serveur. S'il manque des crans, c'est ici qu'on le voit.
- `Verify return code: 0 (ok)` : la validation a réussi. Sinon, le code te dit pourquoi (`21 unable to verify the first certificate`, `10 certificate has expired`, etc.).

💡 Variantes utiles :
```bash
# Forcer une version TLS spécifique
openssl s_client -connect jayrine.com:443 -tls1_2

# Voir tous les certs servis, en PEM
openssl s_client -connect jayrine.com:443 -servername jayrine.com -showcerts

# Tester un certificat client (mTLS)
openssl s_client -connect svc.example.com:443 -cert client.crt -key client.key
```

## Erreurs fréquentes et lecture

| Erreur (s_client / curl) | Cause probable |
|---------------------------|----------------|
| `unable to get local issuer certificate` (verify code 20) | Trust store ne connaît pas la chaîne (CA interne non installée, ou bundle CA absent) |
| `unable to verify the first certificate` (verify code 21) | Le serveur ne sert pas les intermédiaires |
| `certificate has expired` (verify code 10) | Cert expiré côté serveur (ou horloge décalée côté client) |
| `Hostname mismatch` / `CN does not match` | SAN ne couvre pas le nom demandé |
| `no protocols available` / handshake failure | Version TLS ou cipher non supporté en commun |
| `tls: handshake failure` côté Go | Souvent SNI manquant ou cert serveur invalide pour le hostname |

## À retenir

- Le handshake établit version, suite crypto, secret partagé, et **authentifie le serveur** via son certificat.
- TLS 1.3 force la PFS et est plus rapide ; TLS 1.2 reste acceptable, en dessous c'est mort.
- Le **SNI** indique au serveur quel cert présenter — indispensable derrière un reverse proxy.
- `openssl s_client -servername <hostname> -connect <host>:443` est l'outil de diagnostic n°1.
- 90% des problèmes TLS se diagnostiquent en lisant `Verify return code`.

## Pour aller plus loin

- [ACME & Let's Encrypt](./05-acme-letsencrypt.md) — comment ces certs apparaissent automatiquement
- RFC 8446 — TLS 1.3 (lecture costaude mais la référence)
- Outil en ligne : [SSL Labs Server Test](https://www.ssllabs.com/ssltest/) pour scorer ta config publique
