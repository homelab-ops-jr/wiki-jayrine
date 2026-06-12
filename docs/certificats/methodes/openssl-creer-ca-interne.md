# Méthode — Créer sa propre CA interne avec OpenSSL

> **Type** : Méthode · **Outil** : OpenSSL · **Difficulté** : ⭐⭐ Intermédiaire

## Quand l'utiliser

Tu veux pouvoir émettre **plusieurs certificats** pour ton infrastructure interne (NAS, imprimante, IoT, services internes…), sans dépendre d'une CA publique, et **sans devoir ajouter chaque cert individuellement** dans les trust stores. La solution : créer une **CA interne** une bonne fois pour toutes, l'ajouter au trust store des clients, et signer ensuite autant de certs que nécessaire avec elle.

🔒 Une CA interne est **puissante** : elle peut émettre des certs pour n'importe quel domaine (y compris `google.com`, `microsoft.com`…) qui seront acceptés par les machines où elle est installée. Limite son trust store aux machines de ton réseau et garde sa clé privée hors-ligne.

## Architecture cible

```
┌──────────────────────────┐
│ Ta CA interne (root)     │   ← installée dans les trust stores des clients
│   homelab-ca.crt         │
│   homelab-ca.key  (TOP SECRET)
└──────────┬───────────────┘
           │ signe
           ├──────► nas.local.crt     (signé par ta CA)
           ├──────► printer.local.crt (signé par ta CA)
           └──────► dev.local.crt     (signé par ta CA)
```

## Prérequis

- OpenSSL 3.x ou 1.1.1x
- Un dossier dédié pour stocker la CA, **hors du serveur de production** idéalement (ex. : sur un poste sécurisé, ou un volume chiffré). Pour un homelab personnel, un répertoire sur la machine principale + sauvegarde chiffrée suffit.

## Procédure

### Étape 1 — Préparer le répertoire de la CA

```bash
mkdir -p ~/ca-homelab/{certs,private,csr,newcerts}
cd ~/ca-homelab
chmod 700 private
touch index.txt
echo 1000 > serial
```

Structure :
- `private/` — clé privée de la CA (mode 700)
- `certs/` — certs émis
- `csr/` — CSR reçues
- `newcerts/` — copie de tous les certs émis (archive, nommée par n° de série)
- `index.txt` — base de données interne d'OpenSSL (lignes au format simple)
- `serial` — compteur de numéros de série

### Étape 2 — Créer le fichier de config de la CA

`~/ca-homelab/openssl.cnf` :

```ini
[ca]
default_ca = CA_default

[CA_default]
dir              = /home/USER/ca-homelab
certs            = $dir/certs
crl_dir          = $dir/crl
new_certs_dir    = $dir/newcerts
database         = $dir/index.txt
serial           = $dir/serial
RANDFILE         = $dir/private/.rand

private_key      = $dir/private/homelab-ca.key
certificate      = $dir/certs/homelab-ca.crt

default_days     = 825
default_md       = sha256
preserve         = no
policy           = policy_loose

[policy_loose]
countryName             = optional
stateOrProvinceName     = optional
localityName            = optional
organizationName        = optional
organizationalUnitName  = optional
commonName              = supplied
emailAddress            = optional

[req]
default_bits        = 4096
distinguished_name  = req_distinguished_name
string_mask         = utf8only
default_md          = sha256
x509_extensions     = v3_ca
prompt              = no

[req_distinguished_name]
C  = FR
ST = Auvergne-Rhone-Alpes
L  = Lyon
O  = Homelab Jayrine
CN = Homelab Root CA

[v3_ca]
subjectKeyIdentifier   = hash
authorityKeyIdentifier = keyid:always,issuer
basicConstraints       = critical, CA:true
keyUsage               = critical, digitalSignature, cRLSign, keyCertSign

[v3_server_cert]
basicConstraints       = CA:FALSE
nsCertType             = server
nsComment              = "Homelab generated server certificate"
subjectKeyIdentifier   = hash
authorityKeyIdentifier = keyid,issuer:always
keyUsage               = critical, digitalSignature, keyEncipherment
extendedKeyUsage       = serverAuth
```

⚠️ Remplacer `/home/USER/` par ton chemin réel — OpenSSL n'expand pas `~`.

### Étape 3 — Générer la clé privée + le cert de la CA

```bash
cd ~/ca-homelab

# Clé privée de la CA (4096 bits, chiffrée par passphrase)
openssl genrsa -aes256 -out private/homelab-ca.key 4096
chmod 400 private/homelab-ca.key
```

OpenSSL demandera un passphrase. **Ne le perds pas** — il est nécessaire pour signer tout nouveau cert. Stocke-le dans Bitwarden.

```bash
# Cert auto-signé de la CA (validité 10 ans)
openssl req -config openssl.cnf \
  -key private/homelab-ca.key \
  -new -x509 -days 3650 -sha256 \
  -extensions v3_ca \
  -out certs/homelab-ca.crt
chmod 444 certs/homelab-ca.crt
```

Vérifier :
```bash
openssl x509 -in certs/homelab-ca.crt -noout -text | grep -A1 'Basic Constraints\|Subject:\|Issuer:'
```

Attendu :
```
Issuer: C=FR, ST=..., O=Homelab Jayrine, CN=Homelab Root CA
Subject: C=FR, ST=..., O=Homelab Jayrine, CN=Homelab Root CA
X509v3 Basic Constraints: critical
    CA:TRUE
```

`Issuer == Subject` (auto-signé), `CA:TRUE` (peut signer d'autres certs). 

### Étape 4 — Distribuer le cert de la CA dans les trust stores

C'est `certs/homelab-ca.crt` qu'il faut **installer sur chaque machine** qui doit faire confiance aux certs émis. Cf. [linux-ajouter-ca-au-trust-store](./linux-ajouter-ca-au-trust-store.md).

🔒 **Ne jamais distribuer la clé privée** (`private/homelab-ca.key`). Elle reste **uniquement** sur la machine où tu signes les certs.

## Émettre un certificat avec la CA

### Étape A — Sur la machine du service (ou pour le service)

Générer la clé privée et la CSR :

```bash
# Sur le serveur où le service tournera, ou en central peu importe
openssl genrsa -out nas.key 2048
chmod 600 nas.key

# Créer un mini-fichier de config pour la CSR avec SAN
cat > nas.csr.cnf <<EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
C  = FR
O  = Homelab Jayrine
CN = nas.local

[v3_req]
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = nas.local
DNS.2 = nas
IP.1  = 192.168.1.50
EOF

openssl req -new -key nas.key -out nas.csr -config nas.csr.cnf
```

### Étape B — Transmettre la CSR à la CA et signer

Sur la machine CA :

```bash
cd ~/ca-homelab
cp /chemin/vers/nas.csr csr/

openssl ca -config openssl.cnf \
  -extensions v3_server_cert \
  -days 825 -notext -md sha256 \
  -in csr/nas.csr \
  -out certs/nas.crt
```

OpenSSL demandera :
1. Le passphrase de la CA
2. De confirmer la signature deux fois

⚠️ La limite **825 jours** vient des règles du CA/Browser Forum (max pour les certs publics depuis 2020). Pour une CA interne tu peux mettre plus, mais 825 est un bon défaut.

Vérifier le cert émis :
```bash
openssl x509 -in certs/nas.crt -noout -text | grep -E 'Issuer:|Subject:|DNS:|IP:|Not '
```

`Issuer` doit être ton CN de CA, `Subject` celui du serveur.

### Étape C — Livrer le cert au serveur

Copier `nas.crt` (et la chaîne — ici uniquement la root, qui est dans le trust store, donc pas nécessaire) au serveur. Configurer le service comme avec n'importe quel cert :

```nginx
ssl_certificate     /etc/nginx/ssl/nas.crt;
ssl_certificate_key /etc/nginx/ssl/nas.key;
```

💡 Si tu veux servir une chaîne complète (cas où la CA n'est pas dans le trust store de certains clients), concatène :
```bash
cat nas.crt homelab-ca.crt > nas-fullchain.crt
```

## Vérification end-to-end

Depuis un client où la CA est installée :

```bash
curl https://nas.local
# Doit fonctionner sans -k ni avertissement
```

Sinon :
```bash
openssl s_client -connect nas.local:443 -servername nas.local </dev/null 2>&1 \
  | grep -E 'Verify return|subject=|issuer='
```

Attendu :
```
Verify return code: 0 (ok)
subject=CN = nas.local
issuer=O = Homelab Jayrine, CN = Homelab Root CA
```

## Révoquer un certificat

Si une clé fuite :

```bash
cd ~/ca-homelab
openssl ca -config openssl.cnf -revoke certs/nas.crt
```

`index.txt` est mis à jour. Pour publier une CRL utilisable par les clients :
```bash
openssl ca -config openssl.cnf -gencrl -out crl/homelab-ca.crl
```

Servir cette CRL via HTTP, et faire pointer le `crlDistributionPoints` des certs futurs vers son URL. C'est rapidement de l'over-engineering pour un homelab — souvent on **régénère le cert** et on laisse l'ancien expirer.

## Pièges fréquents

| Symptôme | Cause |
|----------|-------|
| `unable to get local issuer certificate` côté client | CA non installée dans le trust store du client |
| `unable to verify the first certificate` | Le serveur ne sert pas la chaîne complète ET le client n'a pas l'intermédiaire — non applicable si CA root direct, sinon ajouter la chaîne |
| `failed to update database` lors du `openssl ca` | `index.txt` corrompu ou serial déjà utilisé |
| Le navigateur Firefox refuse alors que Chrome accepte | Firefox a son **propre** trust store (NSS), à mettre à jour séparément |
| `key values mismatch` côté serveur | Tu as utilisé la clé d'un autre service avec ce cert |

## Au-delà : alternatives plus modernes

Pour quelque chose de plus carré que la ligne de commande OpenSSL :

- **[step-ca](https://smallstep.com/docs/step-ca/)** — CA privée qui parle ACME ! Tes services peuvent s'inscrire auprès d'elle comme avec Let's Encrypt. Idéal pour un homelab plus mature.
- **[HashiCorp Vault PKI](https://developer.hashicorp.com/vault/docs/secrets/pki)** — niveau entreprise, intégration API.
- **[mkcert](https://github.com/FiloSottile/mkcert)** — outil "trop simple" qui crée une CA locale + l'installe dans tous tes trust stores en une commande. Excellent pour le dev.

Pour démarrer et comprendre, OpenSSL en direct reste la meilleure école. Ensuite, step-ca est l'évolution naturelle.

## À retenir

- Une CA interne = une paire root + un workflow de signature. La clé privée de la CA est **le** secret.
- Distribue **uniquement le `.crt`** de la CA aux clients (dans leurs trust stores).
- Signer un cert = CSR du serveur → `openssl ca` côté CA → cert renvoyé au serveur.
- Le SAN reste obligatoire sur chaque cert émis (le CN ne suffit pas).
- Pour aller plus loin et industrialiser : `step-ca` parle ACME, ce qui revient à un Let's Encrypt privé.

## Voir aussi

- [Ajouter une CA au trust store Linux](./linux-ajouter-ca-au-trust-store.md)
- [Notion : Chaîne de confiance & PKI](../notions/03-chaine-de-confiance-pki.md)
