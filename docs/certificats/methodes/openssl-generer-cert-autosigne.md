# Méthode — Générer un certificat auto-signé avec OpenSSL

> **Type** : Méthode · **Outil** : OpenSSL · **Difficulté** : ⭐ Débutant

## Quand l'utiliser

- Tester rapidement une config TLS sans dépendre d'une CA
- Exposer en HTTPS un service interne **non accessible publiquement** (donc Let's Encrypt impossible) — ex. : un NAS, un Raspberry Pi sur le LAN, une VM de dev
- Mettre en place un service de chiffrement où **la validation du nom de domaine n'a pas d'importance** (ex. communication entre deux services dont on contrôle les deux côtés)

⚠️ Un cert auto-signé déclenche un avertissement dans tous les navigateurs et clients par défaut. Tant qu'il n'est pas explicitement ajouté au trust store du client, il sera rejeté. Pour plusieurs hôtes, **monter une CA interne** (cf. fiche dédiée) est plus propre que multiplier les auto-signés.

## Prérequis

- OpenSSL installé (présent par défaut sur Ubuntu/Debian)
- Savoir quel(s) nom(s) doit couvrir le certificat (hostname, IP, FQDN)

Vérifier la version :
```bash
openssl version
# OpenSSL 3.0.x ou 1.1.1x conviennent
```

## Procédure

### Étape 1 — Préparer le fichier de configuration

Les noms doivent être listés dans un **SAN** (rappel : le CN seul ne suffit plus). Le plus propre est de passer par un fichier de config :

Créer `/tmp/cert/openssl.cnf` :

```ini
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
C  = FR
ST = Auvergne-Rhone-Alpes
L  = Lyon
O  = Homelab
CN = nas.local

[v3_req]
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = nas.local
DNS.2 = nas
IP.1  = 192.168.1.50
```

Adapter :
- `CN` et `DNS.x` pour ton hostname
- `IP.x` si tu accèdes au service par IP directe (sinon retirer ces lignes)

### Étape 2 — Générer la clé privée et le certificat en un coup

```bash
cd /tmp/cert

openssl req -x509 \
  -newkey rsa:2048 \
  -keyout nas.key \
  -out nas.crt \
  -days 365 \
  -nodes \
  -config openssl.cnf
```

Décomposition :
- `req -x509` : générer un cert auto-signé (sans passer par une CSR séparée)
- `-newkey rsa:2048` : générer en même temps une clé RSA 2048. Pour ECDSA : `-newkey ec -pkeyopt ec_paramgen_curve:P-256`
- `-keyout` / `-out` : fichiers de sortie
- `-days 365` : validité (peut aller jusqu'à plusieurs années en auto-signé, contrairement aux CA publiques)
- `-nodes` : "no DES" — clé privée non chiffrée (sinon il faudra taper un passphrase à chaque restart du service). Pour un service automatique, c'est ce qu'on veut.
- `-config` : pointe le fichier de config préparé

Résultat :
```
nas.key  ← clé privée (à protéger)
nas.crt  ← certificat (peut être distribué)
```

### Étape 3 — Vérifier le certificat généré

```bash
openssl x509 -in nas.crt -noout -text | grep -E 'Subject:|Issuer:|DNS:|IP:|Not '
```

Sortie attendue :
```
        Issuer: C=FR, ST=Auvergne-Rhone-Alpes, L=Lyon, O=Homelab, CN=nas.local
            Not Before: ...
            Not After : ...
        Subject: C=FR, ST=Auvergne-Rhone-Alpes, L=Lyon, O=Homelab, CN=nas.local
                DNS:nas.local, DNS:nas, IP Address:192.168.1.50
```

Note : `Issuer == Subject` → c'est bien auto-signé.

### Étape 4 — Sécuriser les permissions de la clé

```bash
chmod 600 nas.key
chown root:root nas.key
```

### Étape 5 — Déployer

Copier les deux fichiers à l'emplacement attendu par ton service. Exemples :

- **NGINX** : dans `/etc/nginx/ssl/`, puis dans le `server` block :
  ```
  ssl_certificate     /etc/nginx/ssl/nas.crt;
  ssl_certificate_key /etc/nginx/ssl/nas.key;
  ```

- **Traefik** (file provider, cf. fiche [traefik-certificat-statique](./traefik-certificat-statique.md)) : référencer le couple `.crt`/`.key` dans la config dynamique.

- **Docker container** : monter en volume read-only :
  ```yaml
  volumes:
    - ./certs/nas.crt:/etc/ssl/server.crt:ro
    - ./certs/nas.key:/etc/ssl/server.key:ro
  ```

### Étape 6 — Faire confiance au cert sur les clients

Sans ça, ton navigateur affichera `NET::ERR_CERT_AUTHORITY_INVALID`.

Deux options :
1. **Bourrin** : cliquer "Accepter le risque" à chaque navigateur. Suffisant pour un test ponctuel.
2. **Propre** : ajouter le `.crt` au trust store de chaque client (cf. fiche [linux-ajouter-ca-au-trust-store](./linux-ajouter-ca-au-trust-store.md)). À ne faire qu'avec un cert que tu maîtrises — un auto-signé est conceptuellement une "CA" à un seul certificat.

💡 Si tu vas avoir **plusieurs** services internes en TLS, ne multiplie pas les auto-signés (impraticable à distribuer). Crée plutôt **une CA interne unique** qui signera tous tes certs, et installe **seulement la CA** dans les trust stores. C'est la fiche suivante.

## Variantes utiles

### En une commande sans fichier de config

Plus rapide mais moins versionnable :

```bash
openssl req -x509 -newkey rsa:2048 -keyout nas.key -out nas.crt -days 365 -nodes \
  -subj "/CN=nas.local" \
  -addext "subjectAltName=DNS:nas.local,DNS:nas,IP:192.168.1.50"
```

### Renouveler un cert auto-signé (régénération propre)

Un auto-signé ne se "renouvelle" pas, on le **régénère** :

```bash
# Réutiliser la clé existante (les clients qui ont épinglé la clé continueront de fonctionner)
openssl req -x509 -key nas.key -out nas.crt -days 365 -config openssl.cnf
```

### Convertir au format PKCS#12 (.pfx) pour Windows ou import navigateur

```bash
openssl pkcs12 -export -out nas.pfx -inkey nas.key -in nas.crt
# (te demandera un mot de passe d'export)
```

## Vérifications post-déploiement

Tester l'effective présentation du cert :

```bash
# Depuis une machine cliente
openssl s_client -connect nas.local:443 -servername nas.local </dev/null 2>&1 | grep -E 'subject=|issuer='
```

Attendu : `subject=` et `issuer=` identiques au cert généré.

Test avec `curl` (qui va échouer tant que la CA n'est pas dans le trust store) :
```bash
curl https://nas.local
# curl: (60) SSL certificate problem: self signed certificate
```

Bypass temporaire pour vérifier que le service répond :
```bash
curl -k https://nas.local   # -k = insecure, à NE PAS automatiser en prod
```

## Pièges fréquents

| Symptôme | Cause |
|----------|-------|
| Le client refuse alors que le CN est bon | Pas de SAN, ou SAN ne couvre pas le hostname réellement utilisé |
| L'accès par IP échoue mais le hostname marche | Pas de `IP:` dans les SAN |
| Erreur `key values mismatch` au reload du service | La clé et le cert ne correspondent pas (régénération séparée, erreur de copie) |
| Le cert "se renouvelle" mais les clients voient l'ancien | Cache du service (NGINX/Apache à recharger : `systemctl reload nginx`) |
| `chmod 600` cassé après un `git checkout` | Git ne préserve pas les modes exotiques. **Ne jamais committer une clé privée** de toute façon. |

🔒 **Jamais** committer une clé privée dans un dépôt Git. Ajouter `*.key` et `*.pem` dans `.gitignore`. Pour stocker des clés en GitOps, utiliser SOPS+age (ton workflow habituel).

## À retenir

- `openssl req -x509 -newkey rsa:2048 -keyout … -out … -days 365 -nodes -config …` : la commande de base.
- **SAN obligatoire**, le `CN` seul ne suffit pas.
- Cert auto-signé = pratique pour 1-2 services, devient ingérable au-delà → passer à une **CA interne**.
- Le cert doit être ajouté au trust store des clients pour ne pas générer d'avertissement.

## Voir aussi

- [Créer sa propre CA interne avec OpenSSL](./openssl-creer-ca-interne.md) — meilleure solution dès 2-3 services
- [Ajouter une CA au trust store Linux](./linux-ajouter-ca-au-trust-store.md)
- [Notion : Certificats X.509](../notions/02-certificats-x509.md)
