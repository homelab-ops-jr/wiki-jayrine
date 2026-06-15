# 02 — KVM, QEMU, libvirt : la stack Linux native

> **Type** : Notion · **Sujet** : Virtualisation · **Prérequis** : [Hyperviseurs](./01-hyperviseurs.md)

## En une phrase

Sur Linux, la virtualisation moderne s'appuie sur **trois briques empilées** : **KVM** (module noyau), **QEMU** (userspace) et **libvirt** (couche de management). Comprendre cette pile éclaire ce que fait **Proxmox sous le capot** — Proxmox = Debian + KVM + QEMU + sa propre interface.

## La pile : qui fait quoi

```
┌────────────────────────────────────────────┐
│  Outils de gestion : Proxmox / virsh / virt-manager  │  ← Ce qu'on voit
├────────────────────────────────────────────┤
│  libvirt (daemon libvirtd)                 │  ← API et gestion
├────────────────────────────────────────────┤
│  QEMU (processus userspace par VM)         │  ← Émulation matériel
├────────────────────────────────────────────┤
│  KVM (module noyau /dev/kvm)               │  ← Virtualisation CPU+RAM
├────────────────────────────────────────────┤
│  Noyau Linux                               │
├────────────────────────────────────────────┤
│  Matériel (CPU avec VT-x/AMD-V)            │
└────────────────────────────────────────────┘
```

Chaque couche a un rôle précis et n'est **pas remplaçable** par celle d'à côté.

## KVM (Kernel-based Virtual Machine)

**KVM est un module du noyau Linux** qui transforme le noyau en hyperviseur de type 1. Il expose un device `/dev/kvm` et utilise les **extensions matérielles** VT-x/AMD-V (cf. [Hyperviseurs](./01-hyperviseurs.md)).

KVM **seul** ne sait rien faire de visible :
- Pas d'émulation de périphériques (pas de carte réseau, pas de disque)
- Pas d'interface utilisateur
- Pas de format de disque

Il fait **uniquement** :
- Création d'un contexte d'exécution VM (vCPU, mémoire)
- Bascule entre mode invité et mode hôte sur les VM exits
- Gestion des pages mémoire EPT/RVI

🔑 KVM = le **moteur CPU/mémoire** de la VM. Il a besoin d'un partenaire pour tout le reste.

### Vérifier KVM

```bash
# Module chargé ?
lsmod | grep kvm
# kvm_intel        ou kvm_amd
# kvm

# Device présent ?
ls -l /dev/kvm
# crw-rw----+ 1 root kvm

# Accès utilisateur (pour les hyperviseurs en userspace)
groups | grep kvm    # doit être dans le groupe kvm
```

## QEMU (Quick EMUlator)

**QEMU est un émulateur de machine complet en userspace** : carte mère, BIOS, CPU, disques, réseau, USB, etc. Il peut tourner **sans KVM** en émulant tout en logiciel (utile pour émuler une autre architecture CPU, ex. ARM sur x86), mais c'est extrêmement lent.

Combiné à KVM, QEMU se contente d'**émuler les périphériques** (le matériel virtuel) et **délègue à KVM** l'exécution du CPU et la gestion mémoire. C'est ce qu'on appelle "QEMU/KVM" — la combinaison standard.

### Ce que QEMU fournit

- **Émulation matériel** : carte mère i440FX ou Q35 (chipsets émulés), BIOS/UEFI (SeaBIOS, OVMF), périphériques (USB, CD-ROM, son…)
- **Périphériques paravirtualisés** : drivers virtio pour disque, réseau, ballon mémoire (perf maximale)
- **Formats de disques** : qcow2, raw, vmdk, vdi (avec conversion)
- **Backends réseau** : tap, user-mode, socket, vhost
- **Snapshots, migration, monitor console**

### Un processus QEMU par VM

Chaque VM = **un processus QEMU** (`qemu-system-x86_64`) sur l'hôte. Visible avec :

```bash
ps aux | grep qemu-system
# /usr/bin/qemu-system-x86_64 -name VM101 -drive file=...qcow2 -netdev tap...
```

L'ensemble des paramètres passés en ligne de commande (souvent plusieurs centaines) définit la VM. C'est ce que les outils de management construisent pour toi.

## libvirt — la couche de management

**libvirt est une bibliothèque + un daemon (`libvirtd`)** qui fournit :

- Une **API stable** pour gérer des VMs (indépendamment de l'hyperviseur)
- Un **format de configuration XML** pour décrire les VMs
- Un système de **stockage et réseaux** abstrait
- Gestion du **cycle de vie** (start, stop, snapshot, migrate)

Libvirt n'est pas spécifique à KVM — il supporte aussi Xen, LXC, VMware ESX, etc. Mais en pratique, c'est surtout utilisé avec QEMU/KVM.

### Le format XML libvirt

Chaque VM est décrite par un fichier XML, typiquement dans `/etc/libvirt/qemu/` :

```xml
<domain type='kvm'>
  <name>web-server</name>
  <memory unit='KiB'>2097152</memory>
  <vcpu>2</vcpu>
  <os>
    <type arch='x86_64' machine='pc-q35-7.2'>hvm</type>
    <boot dev='hd'/>
  </os>
  <devices>
    <disk type='file' device='disk'>
      <driver name='qemu' type='qcow2'/>
      <source file='/var/lib/libvirt/images/web.qcow2'/>
      <target dev='vda' bus='virtio'/>
    </disk>
    <interface type='bridge'>
      <source bridge='br0'/>
      <model type='virtio'/>
    </interface>
  </devices>
</domain>
```

Édition typique : `virsh edit <vm-name>`.

### Commandes virsh

`virsh` est la CLI de libvirt. Commandes typiques :

```bash
virsh list --all                  # toutes les VMs
virsh start web-server            # démarrer
virsh shutdown web-server         # arrêter proprement (ACPI)
virsh destroy web-server          # power off brutal
virsh edit web-server             # éditer le XML
virsh dumpxml web-server          # exporter le XML
virsh snapshot-create-as <vm> snap1
virsh net-list --all              # réseaux libvirt
virsh pool-list                   # pools de stockage
```

🔑 Sur un Linux "nu" (Debian, Ubuntu, Fedora), `virsh` + `virt-manager` (GUI) constituent une stack légère pour faire tourner des VMs.

## Et Proxmox dans tout ça ?

🔑 **Proxmox VE n'utilise PAS libvirt.** C'est une **alternative à libvirt**, qui pilote directement QEMU/KVM (et LXC pour les conteneurs) avec sa propre logique.

```
┌────────────────────────────────────────────┐
│  Interface web Proxmox + outils CLI (qm, pct) │
├────────────────────────────────────────────┤
│  Démons Proxmox : pveproxy, pve-cluster... │
├────────────────────────────────────────────┤
│  QEMU (un processus par VM)                │
├────────────────────────────────────────────┤
│  KVM (kernel)                              │
├────────────────────────────────────────────┤
│  Debian (OS hôte)                          │
└────────────────────────────────────────────┘
```

Les fichiers de config des VMs Proxmox ne sont **pas du XML libvirt** mais des fichiers `.conf` au format clé-valeur, dans `/etc/pve/qemu-server/<VMID>.conf` :

```
agent: 1
balloon: 0
boot: order=scsi0;ide2;net0
cores: 2
memory: 4096
name: web-server
net0: virtio=AA:BB:CC:DD:EE:FF,bridge=vmbr0,tag=30
ostype: l26
scsi0: local-lvm:vm-101-disk-0,size=32G
scsihw: virtio-scsi-pci
sockets: 1
vmgenid: ...
```

À comparer au XML libvirt précédent : le contenu est équivalent, le format diffère.

### Pourquoi Proxmox ne suit pas libvirt

- Choix historique (Proxmox VE est antérieur à la maturité de libvirt)
- Permet une intégration cluster native (PVE Cluster filesystem)
- Plus simple à appréhender que libvirt XML pour les opérateurs
- Performance et contrôle direct sur QEMU

### Commandes Proxmox équivalentes

| libvirt (virsh) | Proxmox (qm pour VMs, pct pour CT) |
|-----------------|-------------------------------------|
| `virsh list --all` | `qm list` |
| `virsh start <vm>` | `qm start <VMID>` |
| `virsh shutdown <vm>` | `qm shutdown <VMID>` |
| `virsh destroy <vm>` | `qm stop <VMID>` |
| `virsh edit <vm>` | éditer `/etc/pve/qemu-server/<VMID>.conf` |
| `virsh dumpxml <vm>` | `cat /etc/pve/qemu-server/<VMID>.conf` |
| `virsh snapshot-create-as <vm> snap1` | `qm snapshot <VMID> snap1` |
| `virsh migrate <vm> ...` | `qm migrate <VMID> <node>` |

🔑 Pour les **conteneurs LXC** (l'autre type de "VM" supporté nativement par Proxmox), c'est `pct` (Proxmox Container Toolkit), même logique que `qm` mais pour les CTs.

## Autres hyperviseurs et leur stack

Pour situer KVM/QEMU/libvirt parmi les autres stacks :

| Hyperviseur | Architecture |
|-------------|--------------|
| **Proxmox VE** | Debian + KVM/QEMU + outils Proxmox |
| **VMware ESXi** | OS propriétaire VMkernel + vmx (userspace) |
| **Microsoft Hyper-V** | Couche fine au-dessus de Windows Server avec ses "child partitions" |
| **VirtualBox** | Module noyau propriétaire + frontends GUI/CLI (type 2) |
| **Xen** | Hyperviseur propre type 1 + dom0 Linux + dom1+ guests |
| **XCP-ng** | Xen + Citrix XAPI + interface |
| **OpenStack Nova** | Orchestre KVM (généralement) à grande échelle |
| **AWS, GCP, Azure** | KVM-dérivés (Nitro, KVM-Andromeda, Hyper-V) — cloud-scale |

🔑 **KVM est partout** dans le cloud Linux. Apprendre la stack KVM/QEMU = comprendre les fondations de l'IaaS moderne.

## QEMU sans KVM (émulation pure)

Si tu lances `qemu-system-x86_64` **sans** l'option `-enable-kvm` (ou si KVM n'est pas dispo) :
- Tout est émulé en software, y compris les instructions CPU
- Très lent (10-100x plus lent qu'avec KVM)
- Utile pour **émuler une autre architecture** : `qemu-system-arm` sur x86 pour lancer une image Raspberry Pi

C'est ce que fait Docker pour les images multi-arch via `binfmt_misc` + QEMU.

## Périphériques émulés vs paravirtualisés

QEMU peut "présenter" à la VM différents matériels virtuels :

| Type de NIC | Performance | Compat invité |
|-------------|------------|---------------|
| `e1000` (Intel emulated) | Moyenne | Très large (drivers natifs) |
| `rtl8139` (Realtek emulated) | Faible | Très large (legacy) |
| `vmxnet3` (VMware emulated) | Bonne | Limité hors VMware |
| **`virtio` (paravirtualisé)** | **Excellente** | Nécessite drivers virtio (Linux natifs, Windows à installer) |

Disques :
| Type de bus | Performance | Compat |
|-------------|------------|--------|
| IDE | Faible | Universelle |
| SATA | Moyenne | Universelle |
| SCSI | Bonne | Large |
| **virtio-blk / virtio-scsi** | **Excellente** | Nécessite drivers |

🔑 **Toujours préférer virtio** quand l'invité le supporte. Windows : installer les **virtio-win** ISO drivers (Fedora Project).

## Stockage : QEMU connaît plein de formats

QEMU peut directement utiliser et convertir :
- **raw** — image disque brute, performance maximale, sans features
- **qcow2** — natif QEMU, snapshots, compression, sparse
- **vmdk** — VMware
- **vdi** — VirtualBox
- **vhdx** — Hyper-V

Outil de conversion : `qemu-img convert -f qcow2 -O raw source.qcow2 dest.raw`.

➡️ Détails : [Disques virtuels](./03-disques-virtuels.md).

## En résumé pratique

Si tu veux **comprendre Proxmox** :
- **KVM** = ce qui fait tourner le CPU/RAM de la VM (transparent, pas grand-chose à savoir au quotidien)
- **QEMU** = ce qui définit le matériel virtuel (NIC virtio, disque virtio-scsi, BIOS UEFI…)
- **libvirt** : **non utilisé** par Proxmox, mais utilisé partout ailleurs sur Linux

Pour **dépanner une VM Proxmox** :
- Process QEMU : `ps aux | grep VMID`
- Config : `/etc/pve/qemu-server/<VMID>.conf`
- Logs : `journalctl -u pveproxy`, `/var/log/syslog`

## À retenir

- **KVM** : module noyau Linux, virtualisation CPU+mémoire via VT-x/AMD-V.
- **QEMU** : userspace, émule le reste (carte mère, périphériques, disques).
- **libvirt** : couche de management (API + XML + `virsh`). **Non utilisé par Proxmox.**
- **Proxmox** = Debian + QEMU/KVM + ses propres outils (`qm`, `pct`, web UI), config dans `/etc/pve/qemu-server/`.
- Toujours préférer **virtio** (paravirtualisation) aux périphériques émulés.
- KVM est la base de la quasi-totalité du cloud public moderne.

## Pour aller plus loin

- [Hyperviseurs](./01-hyperviseurs.md)
- [Disques virtuels](./03-disques-virtuels.md)
- [Réseau virtuel](./04-reseau-virtuel.md)
- [VMs vs conteneurs](./06-vms-vs-containers.md)
- Doc Proxmox : [qm](https://pve.proxmox.com/pve-docs/qm.1.html), [pct](https://pve.proxmox.com/pve-docs/pct.1.html)
- Doc libvirt : [libvirt.org](https://libvirt.org/)
- Doc QEMU : [qemu.readthedocs.io](https://qemu.readthedocs.io/)
