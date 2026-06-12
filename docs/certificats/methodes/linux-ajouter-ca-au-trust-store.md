# Méthode — Ajouter une CA au trust store Linux

> **Type** : Méthode · **OS** : Debian/Ubuntu, RHEL/Fedora, Alpine · **Difficulté** : ⭐ Débutant

## Quand l'utiliser

- Tu as créé une **CA interne** et tu veux que les certs émis par elle soient acceptés par `curl`, `git`, `wget`, `apt`, Docker, etc. sur une machine
- Tu utilises un cert auto-signé pour un service interne et tu veux que la machine cliente arrête de râler
- Tu travailles derrière un **proxy SSL/MITM d'entreprise** qui injecte sa propre CA et il faut la faire reconnaître

🔒 Rappel sécurité : ajouter une CA au trust store, c'est **donner à cette CA le pouvoir de produire des certs pour n'importe quel domaine** qui seront acceptés. À ne faire qu'avec une CA dont tu maîtrises l'origine.

## Important : deux trust stores cohabitent

Sur une machine Linux, tu as **au minimum** :

1. **Le trust store système** — utilisé par `curl`, `git`, `wget`, `apt`, Docker engine, la plupart des binaires liés à OpenSSL ou GnuTLS.
2. **Le trust store Firefox** (et autres apps Mozilla) — base NSS, **séparée**.

Et parfois :

3. **Le trust store Java** (`cacerts` du JRE) — pour les apps Java
4. **Le trust store Python `certifi`** — utilisé par `requests`, `pip` parfois

La procédure ci-dessous traite **le trust store système**. Pour les autres, voir la section dédiée en bas.

## Procédure — Debian / Ubuntu

### Étape 1 — Préparer le fichier

Le cert doit être :
- En format **PEM** (texte ASCII, `-----BEGIN CERTIFICATE-----`)
- Avec l'extension **`.crt`** (Debian/Ubuntu est strict là-dessus, `.pem` est **ignoré**)

Vérifier le format :
```bash
file homelab-ca.crt
# homelab-ca.crt: PEM certificate
```

Si tu as un `.der` ou `.cer` binaire, convertir :
```bash
openssl x509 -inform der -in ca.der -out ca.crt
```

### Étape 2 — Copier dans `/usr/local/share/ca-certificates/`

```bash
sudo cp homelab-ca.crt /usr/local/share/ca-certificates/
sudo chmod 644 /usr/local/share/ca-certificates/homelab-ca.crt
```

💡 Pour s'organiser quand on a plusieurs CA, créer un sous-dossier :
```bash
sudo mkdir -p /usr/local/share/ca-certificates/homelab
sudo cp homelab-ca.crt /usr/local/share/ca-certificates/homelab/
```

⚠️ **Ne touche pas à `/etc/ssl/certs/` directement** — c'est généré automatiquement par la commande suivante.

### Étape 3 — Mettre à jour le bundle

```bash
sudo update-ca-certificates
```

Sortie attendue :
```
Updating certificates in /etc/ssl/certs...
1 added, 0 removed; done.
Running hooks in /etc/ca-certificates/update.d...
done.
```

Si la sortie indique `0 added`, c'est que le fichier n'a pas été détecté — vérifier l'extension (`.crt`, pas `.pem`).

### Étape 4 — Vérifier

```bash
# Le cert doit apparaître dans le bundle global
grep -l "Homelab Root CA" /etc/ssl/certs/*.pem | head
```

Test fonctionnel :
```bash
curl https://nas.local
# Pas d'erreur → ça marche
```

Test avec OpenSSL en explicitant le bundle :
```bash
openssl s_client -connect nas.local:443 -servername nas.local \
  -CAfile /etc/ssl/certs/ca-certificates.crt </dev/null 2>&1 \
  | grep 'Verify return'
# Verify return code: 0 (ok)
```

## Procédure — RHEL / Fedora / Rocky / Alma

### Étape 1 — Copier dans `/etc/pki/ca-trust/source/anchors/`

```bash
sudo cp homelab-ca.crt /etc/pki/ca-trust/source/anchors/
```

Format accepté : PEM **ou** DER, extensions `.crt`, `.pem`, `.cer`. Plus tolérant que Debian.

### Étape 2 — Mettre à jour le trust store

```bash
sudo update-ca-trust
```

Pas de sortie en cas de succès (RHEL est silencieux).

### Étape 3 — Vérifier

```bash
trust list | grep -A2 "Homelab Root CA"
```

Ou test fonctionnel :
```bash
curl https://nas.local
```

## Procédure — Alpine

Alpine utilise un système similaire à Debian :

```bash
sudo cp homelab-ca.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates
```

Si la commande `update-ca-certificates` est absente :
```bash
sudo apk add ca-certificates
```

⚠️ Sur les **conteneurs Alpine** très épurés (`alpine:latest` sans `ca-certificates` installé), il n'y a souvent **pas de trust store du tout**. Toujours `apk add ca-certificates` dans le Dockerfile avant de pouvoir utiliser HTTPS.

## Cas particuliers

### Trust store Firefox

Firefox **n'utilise PAS** le trust store système (sauf si tu as activé `security.enterprise_roots.enabled` dans `about:config`). Il faut :

**Option A — par GUI** :
1. `about:preferences#privacy` → section "Certificates"
2. "View Certificates" → onglet "Authorities" → "Import…"
3. Choisir le `.crt`, cocher "Trust this CA to identify websites"

**Option B — par CLI** (NSS) :
```bash
sudo apt install libnss3-tools
certutil -d sql:$HOME/.mozilla/firefox/<profile>.default-release \
  -A -t "CT,c,c" -n "Homelab Root CA" -i homelab-ca.crt
```

**Option C — activer l'import auto du trust system** :
Dans `about:config`, mettre `security.enterprise_roots.enabled = true`. Firefox ira lire le trust store système. C'est la plus pratique en homelab.

### Trust store Java

Pour les apps Java (vieux Sonarr/Radarr en .NET — non, c'est pas Java désolé ; mais Jenkins, Elasticsearch, OpenJDK en général) :

```bash
# Trouver le keystore
sudo find / -name cacerts 2>/dev/null
# Typique : /etc/ssl/certs/java/cacerts ou $JAVA_HOME/lib/security/cacerts

# Importer
sudo keytool -import \
  -trustcacerts \
  -alias homelab-ca \
  -file homelab-ca.crt \
  -keystore /etc/ssl/certs/java/cacerts \
  -storepass changeit
```

Le mot de passe par défaut est **`changeit`** (oui, vraiment).

Redémarrer les apps Java après ça.

### Trust store Python `requests` / `certifi`

`requests` n'utilise pas le trust store système par défaut. Il utilise le bundle de `certifi`. Trois options :

**Option A — variable d'environnement** (le plus propre) :
```bash
export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
```
À mettre dans `.bashrc` ou dans le `Environment=` d'une unit systemd.

**Option B — paramètre explicite dans le code** :
```python
requests.get('https://nas.local', verify='/etc/ssl/certs/ca-certificates.crt')
```

**Option C — patcher le bundle certifi** (fragile, à éviter — sera écrasé au prochain upgrade) :
```bash
cat homelab-ca.crt >> $(python -c "import certifi; print(certifi.where())")
```

### Docker engine

Docker engine n'utilise pas non plus le trust store système pour ses pulls de registries privés en HTTPS. Configurer par registry :

```bash
sudo mkdir -p /etc/docker/certs.d/registry.example.com
sudo cp homelab-ca.crt /etc/docker/certs.d/registry.example.com/ca.crt
sudo systemctl restart docker
```

### Conteneurs Docker

Le trust store **du container** est isolé de celui de l'hôte. Pour qu'un container fasse confiance à ta CA, il faut **inclure le cert dans l'image** :

```dockerfile
COPY homelab-ca.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates
```

Ou en volume au runtime (Debian/Ubuntu-based) :
```yaml
volumes:
  - ./homelab-ca.crt:/usr/local/share/ca-certificates/homelab-ca.crt:ro
command: sh -c "update-ca-certificates && <commande originale>"
```

## Retirer une CA

### Debian/Ubuntu
```bash
sudo rm /usr/local/share/ca-certificates/homelab-ca.crt
sudo update-ca-certificates --fresh
```

`--fresh` reconstruit tout le bundle depuis zéro.

### RHEL/Fedora
```bash
sudo rm /etc/pki/ca-trust/source/anchors/homelab-ca.crt
sudo update-ca-trust extract
```

## Pièges fréquents

| Symptôme | Cause |
|----------|-------|
| `update-ca-certificates` dit "0 added" | Mauvaise extension (`.pem` au lieu de `.crt` sur Debian/Ubuntu) ou format DER au lieu de PEM |
| `curl` voit le cert mais une app Python pas | Python utilise `certifi`, pas le trust système — voir section Python |
| Firefox refuse même après installation système | Firefox a son propre store NSS — activer `security.enterprise_roots.enabled` |
| Docker `pull` refuse un registry interne | Trust store de Docker engine séparé — copier dans `/etc/docker/certs.d/<registry>/` |
| Ça marche en SSH direct mais pas via Ansible | Ansible utilise Python `requests` → variable `REQUESTS_CA_BUNDLE` |
| Le cert disparaît après reboot | Tu l'avais mis dans `/etc/ssl/certs/` directement au lieu de `/usr/local/share/ca-certificates/` |
| Cert bien installé mais `Verify return code: 19` | "self-signed certificate in chain" — la chaîne est OK mais s'arrête à un cert qui n'est pas dans le trust ; ajouter aussi les intermédiaires si applicable |

## À retenir

| Tâche | Debian/Ubuntu | RHEL/Fedora |
|-------|---------------|-------------|
| Dépôt du cert | `/usr/local/share/ca-certificates/*.crt` | `/etc/pki/ca-trust/source/anchors/` |
| Commande de MAJ | `sudo update-ca-certificates` | `sudo update-ca-trust` |
| Bundle global | `/etc/ssl/certs/ca-certificates.crt` | `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem` |

- Firefox, Java, Python, Docker ont des **trust stores séparés** — adapter au cas par cas.
- Pour les **conteneurs**, inclure la CA dans l'image (`COPY` + `update-ca-certificates`).

## Voir aussi

- [Créer sa propre CA interne avec OpenSSL](./openssl-creer-ca-interne.md)
- [Notion : Chaîne de confiance & PKI](../notions/03-chaine-de-confiance-pki.md)
