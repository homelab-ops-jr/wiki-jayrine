# Méthode — Trust stores Windows, macOS, iOS, Android

> **Type** : Méthode · **Outils** : OS natifs + outils dédiés · **Difficulté** : ⭐⭐ Intermédiaire (gère 4 OS)

## Quand l'utiliser

- Tu as une **CA interne** que tu veux faire reconnaître par tes appareils non-Linux
- Tu déploies un cert auto-signé pour un service interne et veux éviter les warnings navigateur
- Tu fournis un cert client mTLS à un utilisateur sur son téléphone ou son laptop
- Tu travailles dans un environnement multi-OS (perso, équipe, clients)

➡️ Prérequis : avoir compris le trust store en général (cf. [Linux : ajouter une CA au trust store](./linux-ajouter-ca-au-trust-store.md)). Cette fiche couvre les **autres systèmes**.

## Concept général

Chaque OS maintient sa propre liste de CAs de confiance, dans son propre format, manipulée par ses propres outils. Plus, parfois, **les applications maintiennent leur propre store** (Firefox, Java, Python).

Pour faire reconnaître ta CA interne sur N appareils :
1. Récupérer le **cert public de la CA** au format adéquat (PEM ou DER selon l'OS)
2. L'importer dans le store **système**
3. Marquer la CA comme **trustée pour le SSL/TLS**
4. (Optionnellement) l'importer dans les stores **applicatifs** si nécessaire

➡️ Pour produire le bon format de cert : [Méthode : Convertir un cert entre formats](./openssl-convertir-formats-cert.md).

## Windows

### Trust store système (Windows Certificate Store)

Trois magasins principaux :
- **Personal** : tes propres certs (clients mTLS)
- **Trusted Root Certification Authorities** : les CAs racines de confiance
- **Intermediate Certification Authorities** : les intermédiaires

Pour qu'une CA interne soit reconnue par **toute la machine** (Chrome, Edge, IE, .NET, Outlook…), elle doit aller dans **Trusted Root Certification Authorities**.

### Import en GUI (utilisateur courant)

1. Avoir le cert au format `.crt` ou `.cer` (PEM ou DER, l'extension `.crt` est conventionnelle)
2. Double-clic sur le fichier → **Install Certificate**
3. Choisir le **Store Location** :
   - "Current User" → uniquement pour ton compte
   - "Local Machine" → pour toute la machine (requiert admin)
4. Cocher **Place all certificates in the following store** → **Browse** → **Trusted Root Certification Authorities**
5. Finir, accepter le warning de sécurité (Windows alerte avant d'ajouter une racine — c'est normal)

### Import en CLI (PowerShell, admin)

```powershell
# Pour la machine
Import-Certificate -FilePath "C:\path\ca.crt" -CertStoreLocation "Cert:\LocalMachine\Root"

# Pour l'utilisateur courant
Import-Certificate -FilePath "C:\path\ca.crt" -CertStoreLocation "Cert:\CurrentUser\Root"
```

### Vérifier

```powershell
Get-ChildItem Cert:\LocalMachine\Root | Where-Object {$_.Subject -like "*HomeLab*"}
```

### Cert client (PKCS#12) pour mTLS

Double-clic sur le `.p12` → wizard d'import → choisir **Personal** comme magasin de destination. Mot de passe demandé.

Une fois importé, Chrome/Edge le proposent automatiquement quand un site demande un cert client.

### Particularités Windows

- **Firefox** sur Windows ne lit **pas** le store Windows par défaut — il a son propre store NSS (cf. plus bas). Depuis Firefox 49 (option `security.enterprise_roots.enabled = true` dans `about:config`), il peut.
- **Java** sur Windows utilise son propre `cacerts` (cf. plus bas).

## macOS

### Trust store système (Keychain Access)

L'OS maintient les CAs de confiance dans le **System keychain** (ou **Login keychain** pour l'utilisateur uniquement).

### Import en GUI

1. Avoir le cert au format `.crt` ou `.cer`
2. Double-cliquer dessus → **Keychain Access** s'ouvre
3. Choisir le keychain (`System` pour toute la machine, `login` pour l'utilisateur)
4. Le cert apparaît avec une icône **bleue barrée** (= importé mais pas trusté)
5. Double-clic sur le cert → section **Trust** → **When using this certificate** → **Always Trust**
6. Fermer (mot de passe admin demandé pour confirmer)

L'icône passe à **rouge avec +** = trusté pour SSL/TLS.

### Import en CLI

```bash
# Pour la machine (admin requis)
sudo security add-trusted-cert -d -r trustRoot \
  -k /Library/Keychains/System.keychain ca.crt

# Pour l'utilisateur courant
security add-trusted-cert -d -r trustRoot \
  -k ~/Library/Keychains/login.keychain-db ca.crt
```

- `-d` : ajout pour le domaine SSL (`Default` policy)
- `-r trustRoot` : "toujours faire confiance" en tant que racine

### Cert client (PKCS#12)

Double-clic sur le `.p12` → mot de passe → cert importé dans le keychain `login` par défaut. Safari et Chrome utilisent le keychain.

### Vérifier

```bash
security find-certificate -c "Nom de la CA" /Library/Keychains/System.keychain
```

### Particularités macOS

- **Firefox** sur macOS lit **par défaut** le keychain depuis Firefox 49 (`security.enterprise_roots.enabled = true` est `true` par défaut sur macOS depuis quelques versions).
- **Safari** et **Chrome** utilisent le keychain nativement.
- **`curl`** macOS utilise le keychain depuis Big Sur — un cert ajouté au keychain est reconnu en CLI.

## iOS / iPadOS

iOS est plus contraignant : ajouter une CA n'est pas seulement importer, c'est aussi **l'activer manuellement** dans les réglages.

### Procédure

1. Convertir le cert en PEM ou DER avec extension `.cer` ou `.crt`
2. **Distribuer** le fichier au téléphone par :
   - Email pièce jointe (depuis l'app Mail)
   - AirDrop (depuis un Mac)
   - Téléchargement HTTPS via Safari (depuis un serveur interne)
3. Sur iOS, ouvrir le fichier → un **profil de configuration** est proposé
4. **Settings** → **General** → **VPN & Device Management** (ou "Profiles") → trouver le profil → **Install**
5. Saisir le code de déverrouillage du téléphone
6. ⚠️ **Étape critique** : **Settings** → **General** → **About** → **Certificate Trust Settings** → activer le toggle pour la CA importée

Sans l'étape 6, le cert est importé mais **pas trusté pour le SSL**. Beaucoup d'utilisateurs ratent cette étape et concluent que ça ne marche pas.

### Profil de configuration `.mobileconfig` (pour plusieurs CAs à la fois ou distribution massive)

Un fichier XML signé qui peut contenir plusieurs certs + configurations. Génération via Apple Configurator 2 (gratuit, macOS) ou outils MDM.

Pour le homelab : la méthode simple ci-dessus suffit.

### Cert client (PKCS#12)

Distribuer le `.p12` par email ou AirDrop. Ouvrir → import dans **Settings** → **General** → **VPN & Device Management**. Mot de passe demandé. Le cert peut être utilisé par les apps qui supportent mTLS (Safari, certaines apps tierces).

### Particularités iOS

- **Firefox iOS** utilise le store iOS (pas de NSS séparé sur iOS).
- **App-Transport-Security (ATS)** : par défaut iOS exige TLS 1.2+, cert valide, etc. Une CA correctement trustée passe l'ATS, sauf si l'app a un pinning spécifique.
- Depuis iOS 13, les certs **doivent avoir au max 825 jours** pour être considérés valides par Safari — viser 1 an pour les certs de CA interne.

## Android

Android est le plus compliqué — la situation a évolué fortement entre versions, et il existe deux stores **distincts**.

### Les deux stores Android

| Store | Contenu | Apps qui l'utilisent |
|-------|---------|----------------------|
| **System** | CAs livrées avec l'OS | Toutes les apps par défaut |
| **User** | CAs ajoutées par l'utilisateur | Navigateur, mais **pas la plupart des apps** depuis Android 7 |

🔑 **Android 7+ (2016)** : les apps **n'utilisent plus** par défaut les CAs du store **user**. Seul le store système est consulté. Une CA importée par l'utilisateur ne marchera que pour le navigateur natif et certaines apps qui ont explicitement opté pour le user store via `network_security_config.xml`.

### Import (store user)

1. Récupérer le cert au format `.crt` (PEM)
2. Le placer sur le téléphone (Downloads, USB, email)
3. **Settings** → **Security** (ou **Biometrics and Security**) → **Encryption & credentials** (ou similaire, ça varie par constructeur) → **Install a certificate** → **CA certificate**
4. Accepter le warning ("Your network may be monitored")
5. Choisir le fichier `.crt`

Cert importé dans le store **user**. Chrome et Firefox Android peuvent l'utiliser. Beaucoup d'apps (banque, messagerie) ne le verront pas et continueront de rejeter le cert.

### Pour qu'une CA soit trustée par **toutes les apps** (store system)

Sur un **téléphone non rooté**, impossible. C'est verrouillé.

Sur un **téléphone rooté** :
```bash
# Calculer le hash de la CA
openssl x509 -inform PEM -subject_hash_old -in ca.crt | head -1
# Renommer en <hash>.0 et copier dans /system/etc/security/cacerts/
```

Réservé aux développeurs avec rooting + Magisk modules ou équivalent.

### Cert client (PKCS#12)

**Settings** → **Security** → **Encryption & credentials** → **Install a certificate** → **VPN & app user certificate** → choisir le `.p12`. Mot de passe demandé.

### Particularités Android

- **Firefox Android** : a son propre store NSS depuis Firefox 68. Importer la CA directement dans Firefox (`about:preferences#privacy` → Certificates) si besoin.
- **Chrome Android** : utilise le store Android system + user (selon la version Android, cf. ci-dessus).
- **Apps de banque** : pinning courant — même une CA légitime peut être rejetée si l'app a hardcodé un fingerprint.

## Firefox (multi-OS) — store NSS propre

Firefox **n'utilise pas** le trust store de l'OS par défaut sur Linux et Windows. Il a son propre store NSS, à manipuler séparément.

### Activer la lecture du store système (recommandé)

`about:config` → `security.enterprise_roots.enabled` → `true`. Firefox prend alors aussi les CAs du store OS.

(Sur macOS et Android, c'est `true` par défaut depuis longtemps.)

### Import direct dans Firefox

**Settings** → **Privacy & Security** → **Certificates** → **View Certificates** → onglet **Authorities** → **Import**. Cocher "Trust this CA to identify websites".

## Java cacerts (apps JVM)

Java a un keystore `cacerts` séparé. Pour ajouter une CA :

```bash
# Localiser le cacerts (sur Linux JDK 11+)
JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
CACERTS="$JAVA_HOME/lib/security/cacerts"

# Ajouter la CA (mot de passe par défaut : changeit)
sudo keytool -importcert \
  -keystore "$CACERTS" \
  -storepass changeit \
  -file ca.crt \
  -alias "HomeLab-CA" \
  -trustcacerts
```

À refaire à chaque mise à jour majeure de la JVM (le keystore est rarement préservé).

## Distribution automatisée (entreprise / homelab plus avancé)

| Volume | Approche |
|--------|----------|
| < 5 appareils | Manuel par appareil (ce qui précède) |
| 5-50 appareils | Profils `.mobileconfig` (iOS/macOS), GPO Active Directory (Windows) |
| > 50 appareils | MDM (Mosyle, Intune, Jamf), Ansible (Linux/macOS) |
| Très automatisé | Auto-provisioning ACME ↔ MDM (rare) |

Pour un homelab perso : manuel suffit. Penser à **documenter quels appareils ont la CA installée** pour la rotation/migration future.

## Vérification cross-OS

Après import, test universel : ouvrir `https://service.example.com` avec un navigateur du device → pas de warning cert.

En CLI (Linux/macOS) :
```bash
openssl s_client -connect service.example.com:443 -servername service.example.com </dev/null 2>&1 \
  | grep "Verify return code"
# Verify return code: 0 (ok) → cert reconnu
```

➡️ Cf. [Inspecter et valider un certificat](./openssl-inspecter-valider-cert.md).

## Pièges fréquents

| OS | Symptôme | Cause |
|----|----------|-------|
| Windows | Cert importé mais pas reconnu | Importé dans "Personal" au lieu de "Trusted Root" |
| macOS | Cert importé mais "non trusté" | Étape "Always Trust" oubliée |
| iOS | Cert importé visible mais warning persiste | **Certificate Trust Settings** pas activé |
| Android 7+ | App rejette le cert même après import | Importé en store user, app n'utilise pas le user store |
| Android | Banque rejette le cert | App pinning, impossible à contourner sans root |
| Tous | Firefox seul ne reconnaît pas | `security.enterprise_roots.enabled = false` |
| Tous | Cert importé puis modifié → Firefox cache l'ancien | Firefox n'invalide pas automatiquement, supprimer manuellement |
| Java apps | Pas reconnu malgré import système | Java a son propre cacerts (cf. ci-dessus) |

## À retenir

- Chaque OS a son trust store, manipulé par ses outils propres.
- **Windows** : Trusted Root Certification Authorities, via certmgr ou PowerShell.
- **macOS** : Keychain Access, marquer **Always Trust**.
- **iOS** : import + **Certificate Trust Settings** à activer manuellement.
- **Android** : Settings → Security → Encryption & credentials. Le store user **ne suffit pas** pour la plupart des apps depuis Android 7.
- **Firefox** a son store NSS propre, ou activer `security.enterprise_roots.enabled`.
- **Java** a son `cacerts` séparé, géré par `keytool`.

## Pour aller plus loin

- [Méthode : Linux — ajouter une CA au trust store](./linux-ajouter-ca-au-trust-store.md) — pour Linux/Unix
- [Méthode : Créer une CA interne](./openssl-creer-ca-interne.md)
- [Méthode : Convertir un cert entre formats](./openssl-convertir-formats-cert.md) — pour produire le bon format
- [Notion : Chaîne de confiance & PKI](../notions/03-chaine-de-confiance-pki.md)
- Apple : [Profiles documentation](https://support.apple.com/guide/deployment/welcome/web)
- Android : [Network Security Config](https://developer.android.com/training/articles/security-config)
