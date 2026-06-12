# 06 — Formats de certificats : PEM, DER, PKCS#12, JKS

> **Type** : Notion · **Sujet** : Certificats · **Prérequis** : [Certificats X.509](./02-certificats-x509.md)

## En une phrase

Un certificat X.509 (et sa clé privée associée) peut être stocké dans **plusieurs formats** — textuel ou binaire, isolé ou bundlé, chiffré ou non. Choisir le bon dépend de l'outil qui va le consommer (serveur web, application Java, mobile, navigateur).

## Le cœur de l'affaire

Tous ces formats encodent la même **structure ASN.1** définie par X.509. Ce qui change, c'est :

- **L'encodage** : texte (base64) ou binaire brut
- **Le contenu groupé** : cert seul, cert + chaîne, cert + chaîne + clé privée
- **La protection** : avec ou sans mot de passe

## Les formats à connaître

### PEM (Privacy Enhanced Mail) — le plus courant

Encodage **base64 ASCII**, lisible dans un éditeur texte, délimité par des marqueurs explicites :

```
-----BEGIN CERTIFICATE-----
MIIDXTCCAkWgAwIBAgIJAKL...
-----END CERTIFICATE-----
```

- Extensions courantes : `.pem`, `.crt`, `.cer`, `.key`
- Plusieurs blocs peuvent coexister dans un même fichier (cert + chaîne + clé)
- Format **par défaut sur Linux/Unix**, accepté par Nginx, Apache, Traefik, HAProxy, Postfix, etc.
- Reconnaissable au préfixe `-----BEGIN ...-----`

Types de blocs PEM les plus fréquents :

| Marqueur | Contenu |
|----------|---------|
| `-----BEGIN CERTIFICATE-----` | Certificat X.509 |
| `-----BEGIN PRIVATE KEY-----` | Clé privée non chiffrée (PKCS#8) |
| `-----BEGIN ENCRYPTED PRIVATE KEY-----` | Clé privée chiffrée (PKCS#8) |
| `-----BEGIN RSA PRIVATE KEY-----` | Clé privée RSA "traditionnelle" (PKCS#1) |
| `-----BEGIN EC PRIVATE KEY-----` | Clé privée EC |
| `-----BEGIN CERTIFICATE REQUEST-----` | CSR (demande de signature) |
| `-----BEGIN DH PARAMETERS-----` | Paramètres Diffie-Hellman |

### DER (Distinguished Encoding Rules) — binaire brut

C'est le **format binaire** de l'ASN.1. PEM = DER encodé en base64 entre des marqueurs. Donc PEM contient un DER.

- Extensions courantes : `.der`, `.cer`, `.crt`
- Pas lisible en texte
- Format natif du **monde Windows** et de **Java** (avant PKCS#12)
- Souvent utilisé pour les certs publiés par les autorités

⚠️ L'extension `.cer` est ambiguë : sur Windows c'est typiquement du DER, sur Linux c'est typiquement du PEM. Toujours vérifier en ouvrant le fichier avec un éditeur texte.

### PKCS#12 (.p12 / .pfx) — bundle complet protégé

Un **conteneur chiffré** qui peut contenir, en un seul fichier :
- La clé privée
- Le certificat
- La chaîne d'intermédiaires
- (Optionnellement) plusieurs certs/clés

- Extensions : `.p12`, `.pfx`
- Toujours **protégé par un mot de passe** (parfois vide en pratique, mais le slot existe)
- Format pivot pour **importer dans Windows, macOS, iOS, Android, Java**
- Standard PKCS issu de la spec RSA Labs

C'est le format à utiliser quand tu veux **déployer un cert sur un poste utilisateur** ou un client mTLS (cf. [mTLS](./09-mtls.md)).

### PKCS#7 (.p7b / .p7c) — chaîne sans clé

Conteneur pour **une chaîne de certificats** sans clé privée. Utilisé pour distribuer une chaîne complète, par exemple lors de l'import d'une CA.

- Extensions : `.p7b`, `.p7c`
- Binaire ou base64 selon les implémentations
- Moins utilisé en homelab — souvent rencontré dans les exports Windows

### JKS (Java KeyStore) — historique Java

Format propriétaire **Sun/Oracle**, manipulé via l'outil `keytool` du JDK.

- Extension : `.jks` (ou `.keystore`)
- Protégé par mot de passe
- Réservé au monde Java
- **Déprécié depuis Java 9** — les versions récentes recommandent PKCS#12 (Oracle a basculé le defaut en PKCS#12 dans Java 9)

🔑 En 2026, sauf legacy explicite, **utiliser PKCS#12 partout où on pensait JKS**. Java moderne (8u282+, 9+) lit PKCS#12 nativement.

### BKS (BouncyCastle KeyStore)

Variante du JKS de la librairie BouncyCastle, parfois utilisée sur Android avant que les keystores système soient matures. Mention pour info — rarement nécessaire en 2026.

## Identifier rapidement un format

| Commande | Indication |
|----------|------------|
| `file mon-fichier` | Donne souvent le type ("PEM certificate", "Java KeyStore", "data") |
| `head mon-fichier` | Si on voit `-----BEGIN ...-----` → PEM |
| `openssl pkcs12 -info -in mon-fichier.p12 -noout` | Liste le contenu d'un PKCS#12 |
| `keytool -list -v -keystore mon-fichier.jks` | Liste le contenu d'un JKS |

Si rien ne se reconnaît, essayer de l'ouvrir comme DER :
```bash
openssl x509 -inform der -in mon-fichier.cer -noout -text
```

## Quand utiliser quoi

| Contexte | Format conseillé |
|----------|------------------|
| Serveur web Linux (Nginx, Apache, Traefik) | PEM |
| Reverse proxy moderne, conteneurs | PEM |
| Import dans Windows (utilisateur, machine) | PKCS#12 (avec mot de passe) |
| Import dans macOS / iOS | PKCS#12 |
| Import dans Android | PKCS#12 (.p12), parfois PEM (.crt) selon la version |
| Application Java moderne | PKCS#12 |
| Application Java legacy < 9 | JKS |
| Email signé/chiffré (S/MIME) | PKCS#12 |
| Cert client pour mTLS distribué à des utilisateurs | PKCS#12 |
| Distribuer une chaîne (sans clé privée) | PEM ou PKCS#7 |

## Pièges fréquents

- **Mélanger les contenus dans un fichier PEM** : pas un piège, c'est même conseillé pour les serveurs web ("fullchain.pem" = cert serveur + intermédiaires concaténés). Mais l'ordre compte : cert serveur en premier, puis intermédiaire(s), puis (parfois) racine.
- **Clé privée RSA "traditionnelle" (PKCS#1) vs PKCS#8** : certains vieux outils n'acceptent que PKCS#1 (`-----BEGIN RSA PRIVATE KEY-----`), d'autres exigent PKCS#8 (`-----BEGIN PRIVATE KEY-----`). OpenSSL convertit entre les deux.
- **PKCS#12 sans mot de passe** : possible techniquement (mot de passe vide), mais beaucoup d'outils refusent de l'importer. Toujours fournir un mot de passe, même trivial.
- **Confusion `.cer` PEM vs DER** : toujours ouvrir le fichier pour vérifier.
- **PEM avec encoding line endings Windows** (`\r\n`) : provoque parfois des erreurs sur outils Linux pointilleux. `dos2unix` règle ça.

## À retenir

- **PEM** = base64 ASCII, format Linux par défaut, lisible.
- **DER** = binaire brut, monde Windows/historique.
- **PKCS#12** = bundle complet (cert + clé + chaîne), chiffré, format pivot pour les imports utilisateur.
- **JKS** = Java legacy, à remplacer par PKCS#12.
- L'extension ne suffit pas : `file` ou `head` pour confirmer.

## Pour aller plus loin

- [Méthode : Convertir un certificat entre formats](../methodes/openssl-convertir-formats-cert.md) — application directe de cette fiche
- [Méthode : Inspecter et valider un certificat](../methodes/openssl-inspecter-valider-cert.md) — pour identifier ce qu'on a vraiment
- [Certificats X.509](./02-certificats-x509.md) — la structure sous-jacente commune à tous les formats
