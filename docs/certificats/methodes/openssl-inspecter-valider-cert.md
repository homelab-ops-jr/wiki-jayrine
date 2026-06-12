# Méthode — Inspecter et valider un certificat avec OpenSSL

> **Type** : Méthode · **Outil** : OpenSSL · **Difficulté** : ⭐ Débutant

## Quand l'utiliser

- Vérifier le contenu d'un cert qu'on vient de recevoir/générer
- Diagnostiquer un problème TLS (mauvais cert servi, chaîne cassée, dates expirées)
- Auditer un cert distant en prod
- Vérifier qu'une clé privée correspond bien à un cert
- Identifier ce que contient un fichier `.pem`/`.crt`/`.p12` inconnu

Cette méthode est la **boîte à outils universelle** d'OpenSSL côté inspection. À combiner avec [Formats de certificats](../notions/06-formats-cert-pem-der-pkcs12.md) pour savoir d'abord à quoi on a affaire.

## Inspecter un cert PEM/DER local

### Affichage complet (lisible)

```bash
openssl x509 -in cert.pem -noout -text
```

- `-noout` : ne réaffiche pas le PEM brut à la fin
- `-text` : affichage humain de tous les champs

Pour un cert DER :
```bash
openssl x509 -in cert.cer -inform der -noout -text
```

### Lecture ciblée — champs précis

```bash
# Sujet (à qui appartient le cert)
openssl x509 -in cert.pem -noout -subject

# Émetteur (la CA qui l'a signé)
openssl x509 -in cert.pem -noout -issuer

# Dates de validité
openssl x509 -in cert.pem -noout -dates

# Date d'expiration en format lisible
openssl x509 -in cert.pem -noout -enddate

# Numéro de série
openssl x509 -in cert.pem -noout -serial

# Empreinte (fingerprint) SHA-256
openssl x509 -in cert.pem -noout -fingerprint -sha256

# SAN (Subject Alternative Name)
openssl x509 -in cert.pem -noout -ext subjectAltName

# Toutes les extensions
openssl x509 -in cert.pem -noout -ext "extendedKeyUsage,keyUsage,basicConstraints,subjectAltName"

# Hash du cert (utile pour les liens dans /etc/ssl/certs/)
openssl x509 -in cert.pem -noout -hash
```

### Vérifier rapidement la fraîcheur

```bash
# Expire dans moins de 30 jours ? (code retour 0 = oui, 1 = non)
openssl x509 -in cert.pem -noout -checkend $((30*24*3600))

# Combien de jours avant expiration ?
expiry=$(openssl x509 -in cert.pem -noout -enddate | cut -d= -f2)
echo "Expire le : $expiry"
echo "$(( ($(date -d "$expiry" +%s) - $(date +%s)) / 86400 )) jours restants"
```

Très utile en script de monitoring.

## Inspecter un cert distant (HTTPS)

### Récupérer la chaîne complète

```bash
openssl s_client -connect example.com:443 -servername example.com -showcerts </dev/null 2>/dev/null
```

- `-connect host:port` : la cible
- `-servername` : indique le SNI (essentiel quand plusieurs vhosts partagent une IP)
- `-showcerts` : affiche **tous** les certs renvoyés (chaîne complète), pas seulement le leaf
- `</dev/null` : ferme stdin pour éviter d'attendre une entrée

### Extraire seulement le cert leaf (server)

```bash
openssl s_client -connect example.com:443 -servername example.com </dev/null 2>/dev/null \
  | openssl x509 -noout -text
```

### Vérifier la chaîne renvoyée

```bash
openssl s_client -connect example.com:443 -servername example.com </dev/null 2>&1 \
  | grep -E "Verify return code|depth=|subject=|issuer="
```

Sortie attendue si OK :
```
depth=2 C = US, O = ...CA Root...
depth=1 C = US, O = Let's Encrypt, CN = R10
depth=0 CN = example.com
Verify return code: 0 (ok)
```

Le `Verify return code: 0 (ok)` valide la chaîne contre le trust store système. Tout autre code → problème :

| Code | Sens fréquent |
|------|--------------|
| 0 | OK |
| 2 | Unable to get issuer certificate (chaîne incomplète) |
| 10 | Cert has expired |
| 18 | Self-signed certificate (CA inconnue) |
| 19 | Self-signed certificate in chain (cas typique CA interne non installée) |
| 20 | Unable to get local issuer certificate (cf. [trust store](./linux-ajouter-ca-au-trust-store.md)) |
| 21 | Unable to verify the first certificate |

### Tester un cert avec un TLS spécifique

```bash
# Forcer TLS 1.2
openssl s_client -connect example.com:443 -tls1_2 </dev/null 2>&1 | grep -E "Protocol|Cipher"

# Forcer TLS 1.3
openssl s_client -connect example.com:443 -tls1_3 </dev/null 2>&1 | grep -E "Protocol|Cipher"

# Tester un cipher spécifique
openssl s_client -connect example.com:443 -cipher 'ECDHE-ECDSA-AES256-GCM-SHA384' </dev/null 2>&1 \
  | grep -E "Cipher|Protocol"
```

## Vérifier une chaîne (verify)

Vérifier qu'un cert leaf est correctement signé, en fournissant la chaîne :

```bash
# Cert leaf + chaîne intermédiaire dans un fichier
openssl verify -CAfile ca-bundle.pem cert.pem
```

Sortie OK : `cert.pem: OK`.

Si la racine n'est pas dans le trust store système, fournir la racine également :

```bash
openssl verify -CAfile racine.pem -untrusted intermediaire.pem cert.pem
```

- `-CAfile` : la (les) racine(s) en qui on a confiance
- `-untrusted` : les intermédiaires (non "trusted" en soi, mais utilisés comme maillons)
- Le dernier argument : le cert leaf à vérifier

Permet de vérifier la chaîne d'une PKI interne (cf. [CA interne](./openssl-creer-ca-interne.md)).

## Vérifier qu'une clé privée correspond à un cert

Indispensable quand on reçoit un cert et qu'on doit savoir avec quelle clé l'utiliser :

```bash
# Le modulus (clé RSA) ou le pubkey doit matcher
openssl x509 -in cert.pem -noout -modulus | openssl md5
openssl rsa -in privkey.pem -noout -modulus | openssl md5
# Les deux md5 doivent être IDENTIQUES
```

Pour les clés EC (et plus générique) :

```bash
openssl x509 -in cert.pem -noout -pubkey | openssl md5
openssl pkey -in privkey.pem -pubout | openssl md5
```

Si différent → la clé ne va pas avec ce cert. À ne jamais déployer en l'état.

## Inspecter une CSR (Certificate Signing Request)

```bash
openssl req -in csr.pem -noout -text -verify
```

- `-verify` : vérifie que la signature de la CSR est cohérente (le demandeur possède bien la clé privée correspondant à la pubkey de la CSR)

Important pour valider une CSR reçue avant de la signer avec sa CA interne.

➡️ [Méthode : Émettre un cert via sa CA interne](./openssl-emettre-cert-via-ca-interne.md).

## Inspecter un PKCS#12

### Lister le contenu (sans extraire)

```bash
openssl pkcs12 -info -in bundle.p12 -noout
# Demande le mot de passe d'import
```

### Extraire le cert (sans clé privée)

```bash
openssl pkcs12 -in bundle.p12 -nokeys -clcerts -out cert.pem
```

### Extraire la clé privée

```bash
openssl pkcs12 -in bundle.p12 -nocerts -nodes -out privkey.pem
```

- `-nodes` ("no DES") : ne re-chiffre PAS la clé extraite. Sans ça, OpenSSL demande un nouveau mot de passe pour la clé extraite.

### Extraire toute la chaîne (CA incluses)

```bash
openssl pkcs12 -in bundle.p12 -nokeys -cacerts -out chain.pem
```

➡️ Pour comprendre les formats : [Notion : Formats de certificats](../notions/06-formats-cert-pem-der-pkcs12.md). Pour convertir : [Méthode : Convertir entre formats](./openssl-convertir-formats-cert.md).

## Diagnostiquer la chaîne renvoyée par un serveur

Cas classique : "le navigateur dit chaîne incomplète". Test :

```bash
openssl s_client -connect example.com:443 -servername example.com -showcerts </dev/null 2>/dev/null \
  | awk '/-----BEGIN CERTIFICATE-----/,/-----END CERTIFICATE-----/' \
  | grep -c "BEGIN CERTIFICATE"
```

Doit être ≥ 2 (leaf + au moins un intermédiaire). Si = 1, le serveur ne sert que le leaf — la chaîne n'est pas complète. Réémission ou config à corriger.

### Identifier chaque cert de la chaîne

```bash
openssl s_client -connect example.com:443 -servername example.com -showcerts </dev/null 2>/dev/null \
  | awk '/-----BEGIN CERTIFICATE-----/{c++; out=c".pem"} c{print > out}'
```

Crée `1.pem`, `2.pem`, etc. Tu peux ensuite les inspecter individuellement :

```bash
for f in *.pem; do
  echo "=== $f ==="
  openssl x509 -in "$f" -noout -subject -issuer
done
```

## Outils web alternatifs (en complément)

- [SSL Labs Server Test](https://www.ssllabs.com/ssltest/) — analyse complète d'un serveur HTTPS (note A-F, ciphers, chaîne, etc.)
- [crt.sh](https://crt.sh) — historique CT logs pour un domaine
- [whatsmychaincert.com](https://whatsmychaincert.com) — corrige une chaîne incomplète

Utiles en complément, mais OpenSSL en CLI reste **le** outil de debug fin.

## Cheatsheet condensée

| Action | Commande |
|--------|----------|
| Lire un cert PEM | `openssl x509 -in c.pem -noout -text` |
| Lire un cert DER | `openssl x509 -in c.cer -inform der -noout -text` |
| Voir le SAN | `openssl x509 -in c.pem -noout -ext subjectAltName` |
| Voir l'expiration | `openssl x509 -in c.pem -noout -enddate` |
| Récupérer cert distant | `openssl s_client -connect h:443 -servername h </dev/null` |
| Vérifier la chaîne distante | `openssl s_client … 2>&1 \| grep "Verify return"` |
| Vérifier une chaîne locale | `openssl verify -CAfile ca.pem c.pem` |
| Match cert ↔ clé | comparer `openssl x509 -modulus` et `openssl rsa -modulus` |
| Lire une CSR | `openssl req -in csr.pem -noout -text -verify` |
| Contenu d'un PKCS#12 | `openssl pkcs12 -info -in b.p12 -noout` |

## Pièges fréquents

- **`-servername` oublié** : sur un serveur multi-vhost (ce qui est presque toujours le cas avec un reverse proxy), oublier `-servername` renvoie le cert par défaut, pas celui du hostname demandé.
- **`-noout` oublié** : OpenSSL réaffiche le PEM en plus du texte, polluant la sortie.
- **Vérification self-signed** : `Verify return code: 18 (self-signed certificate)` est attendu pour une CA interne non installée localement — pas une erreur si c'est le contexte.
- **Comparer modulus avec un cert EC** : `openssl x509 -modulus` ne fonctionne que sur RSA. Utiliser `-pubkey` pour EC.

## À retenir

- `openssl x509 -text` pour tout voir, options ciblées pour les champs précis.
- `openssl s_client -connect host:443 -servername host` pour les certs distants.
- `Verify return code: 0` = chaîne OK contre le trust store système.
- Vérifier le match cert ↔ clé via comparaison des modulus/pubkey hashés.
- `openssl pkcs12` pour examiner et extraire un bundle.

## Pour aller plus loin

- [Méthode : Convertir un cert entre formats](./openssl-convertir-formats-cert.md)
- [Méthode : Émettre un cert via sa CA interne](./openssl-emettre-cert-via-ca-interne.md)
- [Méthode : Diagnostiquer un acme.json cassé](./traefik-debug-acme-json.md)
- [Handshake TLS](../notions/04-tls-handshake.md) — pour comprendre ce qui se passe pendant `s_client`
- Doc OpenSSL : `man openssl-x509`, `man openssl-s_client`, `man openssl-verify`
