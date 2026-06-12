# Méthode — Convertir un certificat entre formats

> **Type** : Méthode · **Outil** : OpenSSL (+ `keytool` pour JKS) · **Difficulté** : ⭐ Débutant

## Quand l'utiliser

- Tu as un cert PEM mais l'application cible demande du PKCS#12
- Tu reçois un `.pfx` Windows et tu veux extraire en PEM pour Nginx
- Tu déploies sur un appareil mobile (PKCS#12 requis)
- Tu migres d'un Java legacy (JKS) vers PKCS#12
- Tu dois inverser l'encodage PEM ↔ DER pour un outil pointilleux

➡️ Prérequis de lecture : [Notion : Formats de certificats](../notions/06-formats-cert-pem-der-pkcs12.md).

## Table de conversion rapide

| De → Vers | Commande de référence |
|-----------|------------------------|
| PEM → DER | `openssl x509 -in c.pem -outform der -out c.der` |
| DER → PEM | `openssl x509 -in c.der -inform der -out c.pem` |
| Cert+clé PEM → PKCS#12 | `openssl pkcs12 -export -in cert.pem -inkey key.pem -out bundle.p12` |
| PKCS#12 → cert PEM | `openssl pkcs12 -in bundle.p12 -nokeys -clcerts -out cert.pem` |
| PKCS#12 → clé PEM | `openssl pkcs12 -in bundle.p12 -nocerts -nodes -out key.pem` |
| PKCS#12 → chaîne CA | `openssl pkcs12 -in bundle.p12 -nokeys -cacerts -out chain.pem` |
| Clé RSA PKCS#1 → PKCS#8 | `openssl pkey -in rsa-pkcs1.pem -out rsa-pkcs8.pem` |
| PKCS#12 → JKS | passer par `keytool -importkeystore` |
| JKS → PKCS#12 | `keytool -importkeystore -srckeystore in.jks -destkeystore out.p12 -deststoretype PKCS12` |

## Conversion PEM ↔ DER

C'est juste un changement d'encodage du même contenu ASN.1. Aucune perte d'information.

```bash
# PEM → DER
openssl x509 -in cert.pem -outform der -out cert.der

# DER → PEM
openssl x509 -in cert.der -inform der -out cert.pem
```

Pour une clé privée :
```bash
# PEM → DER
openssl pkey -in privkey.pem -outform der -out privkey.der

# DER → PEM
openssl pkey -in privkey.der -inform der -out privkey.pem
```

Pour une CSR :
```bash
openssl req -in csr.pem -outform der -out csr.der
openssl req -in csr.der -inform der -out csr.pem
```

💡 Conseil universel : **rester en PEM** côté Linux/serveur, ne convertir en DER que pour des outils qui l'exigent explicitement.

## Construire un PKCS#12 depuis PEM

### Cas le plus courant : cert + clé + chaîne

Tu as :
- `cert.pem` — le cert leaf
- `privkey.pem` — la clé privée
- `chain.pem` — les intermédiaires (et éventuellement la racine)

```bash
openssl pkcs12 -export \
  -in cert.pem \
  -inkey privkey.pem \
  -certfile chain.pem \
  -out bundle.p12 \
  -name "mon-service"
```

OpenSSL demande un **mot de passe d'export** (à retenir pour l'import côté destinataire).

Options utiles :
- `-name "nom-friendly"` : le "friendly name" qui apparaît dans le keystore importé (utile pour le retrouver)
- `-passout pass:MOTDEPASSE` : passe le mot de passe en argument (pour les scripts, **évite l'historique shell** sinon)
- `-passout file:fichier-mdp.txt` : depuis un fichier (mieux)

### Cas particulier : compatibilité legacy

Beaucoup d'outils anciens (Java < 11, OS anciens) ne lisent pas les PKCS#12 modernes (chiffrement AES-256-CBC par défaut depuis OpenSSL 3). Pour la compatibilité maximale :

```bash
openssl pkcs12 -export \
  -in cert.pem \
  -inkey privkey.pem \
  -certfile chain.pem \
  -out bundle-legacy.p12 \
  -name "mon-service" \
  -legacy
```

L'option `-legacy` (OpenSSL 3+) utilise les anciens algos de chiffrement, compatibles partout.

⚠️ Ne pas utiliser `-legacy` par défaut — c'est moins sécurisé. Uniquement si l'outil cible refuse.

## Extraire depuis un PKCS#12

### Extraire le cert (sans clé privée)

```bash
openssl pkcs12 -in bundle.p12 -nokeys -clcerts -out cert.pem
```

- `-nokeys` : ne pas extraire les clés
- `-clcerts` : seulement le cert client (leaf), pas les certs CA

### Extraire la clé privée

```bash
openssl pkcs12 -in bundle.p12 -nocerts -nodes -out privkey.pem
```

- `-nocerts` : pas les certs
- `-nodes` : ne pas re-chiffrer la clé extraite ("no DES")

⚠️ Sans `-nodes`, la clé extraite sera re-chiffrée avec un nouveau mot de passe (demandé interactivement). Pour un usage automatisé (serveur web qui lit la clé au démarrage), `-nodes` est généralement souhaité — la protection de la clé repose alors sur les **permissions fichier** (`chmod 600`).

### Extraire la chaîne (CA intermediaires + racine)

```bash
openssl pkcs12 -in bundle.p12 -nokeys -cacerts -out chain.pem
```

### Tout en une commande (cert + clé séparés)

```bash
# Cert
openssl pkcs12 -in bundle.p12 -nokeys -clcerts -out cert.pem
# Clé
openssl pkcs12 -in bundle.p12 -nocerts -nodes -out privkey.pem
# Chaîne CA (si présente)
openssl pkcs12 -in bundle.p12 -nokeys -cacerts -out chain.pem 2>/dev/null
```

## Conversions de clés privées

### PKCS#1 (RSA-spécifique) ↔ PKCS#8 (générique)

Vieux format RSA :
```
-----BEGIN RSA PRIVATE KEY-----
```

Format PKCS#8 moderne :
```
-----BEGIN PRIVATE KEY-----
```

Conversion :
```bash
# PKCS#1 → PKCS#8 (non chiffré)
openssl pkey -in rsa-pkcs1.pem -out key-pkcs8.pem

# PKCS#8 → PKCS#1 (rare, mais possible)
openssl rsa -in key-pkcs8.pem -traditional -out rsa-pkcs1.pem
```

### Chiffrer / déchiffrer une clé privée

```bash
# Ajouter un chiffrement (mot de passe demandé)
openssl pkey -in privkey.pem -aes-256-cbc -out privkey-encrypted.pem

# Retirer le chiffrement
openssl pkey -in privkey-encrypted.pem -out privkey.pem
```

🔒 La majorité des serveurs web démarrent en mode non-interactif et **ne peuvent pas saisir un mot de passe de clé**. La clé est donc en clair sur le disque, protégée par les permissions (`chmod 600` + owner approprié).

## Conversions impliquant JKS (Java)

JKS est une plaie en 2026, mais on en croise encore. Conversions via `keytool` (livré avec le JDK) :

### JKS → PKCS#12 (recommandé)

```bash
keytool -importkeystore \
  -srckeystore in.jks \
  -srcstoretype JKS \
  -destkeystore out.p12 \
  -deststoretype PKCS12
```

Mot de passe source + destination demandés. Tous les aliases sont migrés.

### PKCS#12 → JKS (legacy)

```bash
keytool -importkeystore \
  -srckeystore in.p12 \
  -srcstoretype PKCS12 \
  -destkeystore out.jks \
  -deststoretype JKS
```

⚠️ JKS est déprécié depuis Java 9. Si possible, garder en PKCS#12 et laisser Java le lire (toutes les JVM modernes supportent PKCS#12 nativement).

### Lister le contenu d'un JKS

```bash
keytool -list -v -keystore in.jks
```

## Concaténer une chaîne PEM (pas une conversion mais souvent nécessaire)

Pour produire un **fullchain** : cert leaf + intermédiaire(s), dans l'ordre :

```bash
cat cert.pem intermediate.pem > fullchain.pem
```

Et la version "tout-en-un" si tu sers aussi la clé (rare, certains outils l'attendent) :
```bash
cat cert.pem intermediate.pem privkey.pem > combined.pem
```

⚠️ L'ordre dans un PEM concaténé pour un serveur HTTPS : **leaf en premier**, puis intermédiaires en remontant vers la racine. Pas la racine elle-même (elle est censée être dans le trust store du client, pas servie).

## Vérifications après conversion

### Le cert est-il intact ?

```bash
openssl x509 -in cert-converti.pem -noout -subject -issuer -dates
```

Doit afficher les mêmes valeurs qu'avant conversion.

### La clé extraite correspond-elle au cert ?

```bash
openssl x509 -in cert.pem -noout -pubkey | openssl md5
openssl pkey -in privkey.pem -pubout | openssl md5
# Les deux md5 doivent matcher
```

➡️ Détaillé dans [Inspecter et valider un certificat](./openssl-inspecter-valider-cert.md).

### Le PKCS#12 produit s'importe-t-il ?

Test à blanc :
```bash
openssl pkcs12 -info -in bundle.p12 -noout
# Demande le mot de passe, affiche les "friendly names" et infos sur les bags
```

Si l'outil cible refuse l'import, tester avec `-legacy` (cf. ci-dessus).

## Pièges fréquents

- **PEM avec extension `.cer`** : pris pour du DER par certains outils. Forcer `-inform pem` ou renommer en `.pem`.
- **`.cer` qui est en réalité du DER** : forcer `-inform der`.
- **Mot de passe oublié d'un PKCS#12** : aucune récupération possible — il faut regénérer depuis les PEM source.
- **PKCS#12 récent refusé par Java 8** : `-legacy` lors de la création.
- **Clé PKCS#1 vs PKCS#8** : un outil qui veut "PRIVATE KEY" rejette une "RSA PRIVATE KEY". Convertir avec `openssl pkey`.
- **Concaténation dans le mauvais ordre** : root en premier au lieu du leaf → certains clients TLS rejettent. Toujours leaf en premier.
- **Linux line endings (CRLF)** dans un PEM venant de Windows : `dos2unix` règle ça.
- **Caractères BOM** au début d'un PEM ouvert en Windows : visible avec `hexdump -C cert.pem | head -1`.

## À retenir

- PEM ↔ DER = changement d'encodage trivial, aucune perte.
- PEM → PKCS#12 = bundle complet (cert + clé + chaîne) avec mot de passe.
- PKCS#12 → PEM = extraction individualisée (cert, clé, chaîne).
- Toujours **vérifier après conversion** (cert intact + clé qui match).
- `-legacy` pour la compat ancienne en PKCS#12.
- Préférer PKCS#12 à JKS en 2026.

## Pour aller plus loin

- [Notion : Formats de certificats](../notions/06-formats-cert-pem-der-pkcs12.md)
- [Méthode : Inspecter et valider un certificat](./openssl-inspecter-valider-cert.md)
- [Méthode : Émettre un cert via sa CA interne](./openssl-emettre-cert-via-ca-interne.md) — souvent suivie d'une conversion vers PKCS#12 pour distribution
- [Méthode : Trust stores Windows/macOS/mobile](./trust-store-windows-macos-mobile.md)
- `man openssl-pkcs12`, `man keytool` (du JDK)
