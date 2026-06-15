# 07 — Cloud-init et provisioning automatique

> **Type** : Notion · **Sujet** : Virtualisation · **Prérequis** : [Hyperviseurs](./01-hyperviseurs.md), [Disques virtuels](./03-disques-virtuels.md)

## En une phrase

**Cloud-init** est l'outil standard de **provisioning au premier boot** d'une VM : à partir d'une image template, il configure automatiquement hostname, utilisateurs, clés SSH, réseau, paquets, et même exécute des scripts custom — **sans interaction manuelle**. C'est ce qui permet de cloner une VM en quelques secondes avec une config différente à chaque fois.

## Le problème que cloud-init résout

Sans cloud-init, créer 10 VMs identiques c'est :
1. Cloner le template (rapide)
2. Démarrer
3. Se connecter en console
4. Configurer hostname
5. Créer un utilisateur
6. Configurer les clés SSH
7. Configurer le réseau (si IP statique)
8. Installer les paquets de base
9. Recommencer 10 fois

Avec cloud-init : on prépare un **fichier de config** (1 par VM ou template paramétrable), on clone, on boote, **tout est fait** en 30 secondes.

🔑 C'est le mécanisme qui rend possible les **clouds publics** (AWS, GCP, Azure) : tu lances une instance, elle est prête en 1 minute avec tes paramètres. Cloud-init s'exécute au boot et applique la config fournie par l'API du cloud.

## Vue d'ensemble

Cloud-init s'installe **dans l'image** de la VM (cas typique : les "cloud images" officielles d'Ubuntu, Debian, Alpine, etc.). Au premier boot, il :

1. Détecte l'**environnement** (datasource = "comment et où trouver la config ?")
2. Récupère la **config** (user-data, meta-data, network-config)
3. Exécute les **modules** dans l'ordre (utilisateurs, SSH, paquets, scripts…)
4. Marque "déjà fait" et passe la main à init normal

```
[Première mise sous tension d'une nouvelle VM]
              │
              ▼
   ┌────────────────────────┐
   │  cloud-init local      │   Configure le réseau précoce
   └───────────┬────────────┘
               │
               ▼
   ┌────────────────────────┐
   │  cloud-init init       │   Datasource détectée, fetch config
   └───────────┬────────────┘
               │
               ▼
   ┌────────────────────────┐
   │  cloud-init modules    │   Apply hostname, users, SSH, packages
   └───────────┬────────────┘
               │
               ▼
   ┌────────────────────────┐
   │  cloud-init final      │   runcmd, scripts custom, fin
   └───────────┬────────────┘
               │
               ▼
   ┌────────────────────────┐
   │  Système prêt          │   prompt login disponible
   └────────────────────────┘
```

## Les trois fichiers principaux

Cloud-init lit trois "documents" :

### 1. `user-data` (la config principale)

Au format YAML, commence par `#cloud-config`. Contient ce qu'on veut configurer.

Exemple typique :
```yaml
#cloud-config
hostname: web-01
fqdn: web-01.example.com
manage_etc_hosts: true

users:
  - name: admin
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    ssh_authorized_keys:
      - ssh-ed25519 AAAAC3Nz... admin@workstation

package_update: true
package_upgrade: true
packages:
  - vim
  - htop
  - curl

runcmd:
  - systemctl enable --now nginx
  - echo "Provisioning done" > /etc/motd

timezone: Europe/Paris
locale: fr_FR.UTF-8

power_state:
  mode: reboot
  delay: 1
  condition: True
```

### 2. `meta-data` (identité de l'instance)

Contient les infos d'identité — typiquement minimaliste :

```yaml
instance-id: web-01-2026
local-hostname: web-01
```

### 3. `network-config` (configuration réseau)

Format YAML décrivant les interfaces. Optionnel — si absent, cloud-init suppose DHCP.

```yaml
version: 2
ethernets:
  eth0:
    dhcp4: false
    addresses:
      - 10.0.20.50/24
    gateway4: 10.0.20.1
    nameservers:
      addresses:
        - 1.1.1.1
        - 8.8.8.8
```

## Les datasources : où cloud-init va chercher la config

C'est la première étape — cloud-init essaie plusieurs datasources jusqu'à en trouver une qui fonctionne. Les principales :

| Datasource | Comment ça marche | Cas d'usage |
|------------|-------------------|-------------|
| **NoCloud** | Lit depuis un volume (ISO ou disque) attaché à la VM | **Le plus simple en local/Proxmox** |
| **ConfigDrive** | Volume CD-ROM ISO, format OpenStack | Lab OpenStack |
| **EC2** | Lit depuis l'API metadata d'AWS (http://169.254.169.254) | AWS |
| **GCE** | API metadata Google Cloud | GCP |
| **Azure** | API et fichiers spécifiques | Azure |
| **OpenStack** | Métadonnées OpenStack | OpenStack |
| **DigitalOcean, Hetzner, Scaleway** | Spécifiques à ces clouds | Idem |

🔑 En homelab Proxmox, c'est **NoCloud (CD-ROM ISO)** qui est utilisé. Proxmox génère automatiquement un ISO contenant `user-data` + `meta-data` + `network-config` et l'attache à la VM comme un CD virtuel.

## Cloud-init et Proxmox

Proxmox a une intégration cloud-init native :

```bash
# Définir l'utilisateur initial
qm set <VMID> --ciuser admin

# Le mot de passe (en clair, transmis à cloud-init via meta-data)
qm set <VMID> --cipassword 'MotDePasse'

# Clé SSH
qm set <VMID> --sshkeys ~/.ssh/id_ed25519.pub

# Configuration réseau (DHCP par défaut, ou statique)
qm set <VMID> --ipconfig0 ip=10.0.20.50/24,gw=10.0.20.1
qm set <VMID> --ipconfig0 ip=dhcp

# DNS
qm set <VMID> --nameserver "1.1.1.1 8.8.8.8"
qm set <VMID> --searchdomain example.com

# Attache un disque cloud-init (CD-ROM contenant les ISOs générés)
qm set <VMID> --ide2 local-lvm:cloudinit
```

Proxmox génère l'ISO NoCloud à chaque boot — modifier la config et redémarrer = nouvelle injection.

⚠️ **Cloud-init ne reconfigure pas tout à chaque boot** : il a un état `~/.cloud-init/sem/` qui marque ce qui a déjà été fait. Pour reprovisionner intégralement → effacer cet état (`cloud-init clean --logs --reboot`).

## user-data complet pour Proxmox

Au-delà des options `--ciXXX`, on peut fournir un **user-data complet** custom via un snippet :

```bash
# Activer les snippets dans Datacenter > Storage > local > Snippets
# Puis créer un fichier
cat > /var/lib/vz/snippets/web-server.yaml <<'EOF'
#cloud-config
hostname: web-server
users:
  - name: admin
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - ssh-ed25519 AAAAC3Nz... admin@workstation
packages:
  - nginx
  - certbot
runcmd:
  - systemctl enable --now nginx
EOF

# Référencer dans la VM
qm set <VMID> --cicustom "user=local:snippets/web-server.yaml"
```

Avantage : workflow GitOps possible. Le fichier YAML peut vivre dans un dépôt, être versionné, modifié, redéployé.

## Workflow template + clone

C'est le cas d'usage roi de cloud-init :

```
1. Télécharger une cloud image (cloud-init pré-installé)
   wget https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img

2. Créer une VM Proxmox "template"
   qm create 9000 --memory 2048 --cores 2 --net0 virtio,bridge=vmbr0
   qm importdisk 9000 jammy-server-cloudimg-amd64.img local-lvm
   qm set 9000 --scsihw virtio-scsi-pci --scsi0 local-lvm:vm-9000-disk-0
   qm set 9000 --ide2 local-lvm:cloudinit
   qm set 9000 --boot c --bootdisk scsi0
   qm set 9000 --serial0 socket --vga serial0   # console série pour cloud images
   qm template 9000

3. Pour chaque VM voulue, cloner + paramétrer + démarrer
   qm clone 9000 101 --name web-01
   qm set 101 --ipconfig0 ip=10.0.20.50/24,gw=10.0.20.1
   qm set 101 --ciuser admin --sshkeys ~/.ssh/id_ed25519.pub
   qm start 101

   # Quelques secondes plus tard, SSH dispo
   ssh admin@10.0.20.50
```

🔑 De la VM template à la VM utilisable : **moins d'une minute**, configurée comme tu veux, prête.

## Cas particulier : Alpine Linux

Alpine est très léger, idéal pour des VMs de test (cf. ressources du projet). Mais l'intégration cloud-init est **plus rustique** qu'avec Ubuntu/Debian :

- Le package `cloud-init` existe pour Alpine
- La cloud image officielle Alpine fonctionne avec cloud-init NoCloud / ConfigDrive
- Quelques modules cloud-init peuvent ne pas être 100% testés sur Alpine

Pour Alpine simple, alternative légère : **answerfile** d'Alpine (`setup-alpine -a answerfile`) — pas du cloud-init mais le concept est similaire.

🔑 Pour des VMs de test rapides Alpine + cloud-init : possible mais demande un peu plus d'attention que Ubuntu cloud image qui est très polished.

## Modules cloud-init utiles à connaître

Liste non exhaustive des modules les plus utiles :

| Module | Effet |
|--------|-------|
| `hostname` | Définit le hostname |
| `users` | Crée des utilisateurs, sudo, SSH keys |
| `ssh_authorized_keys` | Ajoute des clés SSH |
| `disable_root` | Désactive le login root (sécu) |
| `ssh_pwauth` | Active/désactive l'auth par mot de passe SSH |
| `package_update`, `package_upgrade` | apt update, upgrade |
| `packages` | Liste de paquets à installer |
| `runcmd` | Commandes shell à exécuter (1 fois, au boot initial) |
| `bootcmd` | Commandes à chaque boot (rarement utile) |
| `write_files` | Écrit des fichiers à un chemin donné |
| `timezone`, `locale` | Localisation |
| `power_state` | Reboot ou shutdown à la fin |
| `phone_home` | Notifie une URL "je suis up" |

## write_files : étendre la conf

Très puissant pour déposer une config complète d'un service :

```yaml
write_files:
  - path: /etc/nginx/sites-available/default
    content: |
      server {
        listen 80;
        server_name _;
        root /var/www/html;
        index index.html;
      }
    permissions: '0644'
    owner: root:root
```

Combiné avec `runcmd: - systemctl restart nginx`, ça suffit à provisioner un nginx prêt à servir.

## Debug cloud-init dans la VM

Si quelque chose se passe mal :

```bash
# Logs
sudo cat /var/log/cloud-init.log
sudo cat /var/log/cloud-init-output.log

# Status
cloud-init status --long

# Re-jouer cloud-init from scratch (DANGEREUX, mais utile en dev)
sudo cloud-init clean --logs
sudo cloud-init init --local
sudo cloud-init init
sudo cloud-init modules --mode=config
sudo cloud-init modules --mode=final

# Voir la config détectée
sudo cloud-init query userdata
sudo cloud-init query metadata
```

🔑 **Astuce** : pour tester un user-data sans détruire ta VM, créer un overlay snapshot, expérimenter, jeter et recommencer.

## Sécurité

Quelques points d'attention :

🔒 **Mots de passe en clair dans user-data** : visibles sur le CD-ROM monté de la VM. Préférer **`chpasswd` avec hash bcrypt** ou pas de password du tout (SSH keys only).

```yaml
chpasswd:
  list: |
    admin:$6$rounds=4096$xxxxx$hashe...
  expire: false
```

🔒 **Désactiver l'auth password SSH** :
```yaml
ssh_pwauth: false
disable_root: true
```

🔒 **Snippets versionnés** : éviter de committer des secrets dans le dépôt Git public.

## Alternatives à cloud-init

- **Ignition** (Fedora CoreOS, Flatcar) — équivalent mais incompatible, JSON, plus strict
- **Terraform + provisioners** — pour provisioner après création
- **Ansible** — config management généraliste, complémentaire (Ansible reprend là où cloud-init s'arrête)
- **Packer** — créer des images pré-bakées (cloud-init pour les variations, packer pour le commun)

Pattern courant : **Packer construit une image base** → **cloud-init paramètre au boot** → **Ansible/Saltstack gère ensuite**.

## À retenir

- Cloud-init = **provisioning au premier boot** de VM, à partir d'un template.
- Trois documents : `user-data` (config), `meta-data` (identité), `network-config` (réseau).
- **Datasource NoCloud** = ISO attaché à la VM. Utilisé par Proxmox.
- Workflow **template + clone** : VM utilisable en < 1 minute, paramétrée.
- Sur Proxmox : `qm set --ciuser/--cipassword/--sshkeys/--ipconfig0` + disque cloudinit (`ide2`).
- Pour aller plus loin : **snippet user-data** custom via `--cicustom`.
- **Mot de passe en clair = visible** dans le user-data. Préférer SSH keys ou hash bcrypt.
- Debug : `/var/log/cloud-init.log`, `cloud-init status`, `cloud-init clean`.

## Pour aller plus loin

- [Hyperviseurs](./01-hyperviseurs.md)
- [Disques virtuels](./03-disques-virtuels.md) — pour comprendre où vit le CD-ROM cloud-init
- [VMs vs conteneurs](./06-vms-vs-containers.md) — Docker a son propre modèle (Dockerfile + ENTRYPOINT)
- Doc cloud-init : [cloudinit.readthedocs.io](https://cloudinit.readthedocs.io/)
- Doc Proxmox : [Cloud-Init Support](https://pve.proxmox.com/wiki/Cloud-Init_Support)
- Ubuntu cloud images : [cloud-images.ubuntu.com](https://cloud-images.ubuntu.com/)
