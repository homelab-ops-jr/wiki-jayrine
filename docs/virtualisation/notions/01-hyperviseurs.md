# 01 — Hyperviseurs : type 1 vs type 2, virtualisation matérielle

> **Type** : Notion · **Sujet** : Virtualisation · **Prérequis** : Aucun (notions OS générales utiles)

## En une phrase

Un **hyperviseur** est le logiciel qui permet de **faire tourner plusieurs systèmes d'exploitation (VMs) simultanément** sur un même matériel physique, en mutualisant CPU, RAM, stockage, et I/O. La distinction **type 1 (bare-metal) vs type 2 (hosted)** structure les choix d'architecture.

## Le concept fondamental

Sans virtualisation, un serveur = un OS = un usage. Avec virtualisation, un serveur = N OS isolés (VMs), chacun voyant son propre "matériel" (en réalité émulé/paravirtualisé par l'hyperviseur).

```
Avant virtualisation :         Avec virtualisation (type 1) :

┌──────────────────┐           ┌──────┐ ┌──────┐ ┌──────┐
│   Application   │           │ App  │ │ App  │ │ App  │
├──────────────────┤           ├──────┤ ├──────┤ ├──────┤
│       OS         │           │ OS A │ │ OS B │ │ OS C │
├──────────────────┤           ├──────┴─┴──────┴─┴──────┤
│   Matériel       │           │      Hyperviseur       │
│ (CPU, RAM, ...)  │           ├────────────────────────┤
└──────────────────┘           │      Matériel          │
                               └────────────────────────┘
```

## Type 1 — bare-metal (natif)

L'hyperviseur **tourne directement sur le matériel**, sans OS hôte sous lui. Il **est** le système qui gère le hardware et orchestre les VMs.

Exemples :
- **Proxmox VE** — basé Linux/KVM, open source, leader homelab
- **VMware ESXi** — propriétaire, dominant en entreprise
- **Microsoft Hyper-V Server** — sous Windows Server
- **XCP-ng** / **Citrix Hypervisor** — basé Xen
- **Nutanix AHV**, **Proxmox VE** — Linux + KVM

### Caractéristiques

- ✅ Performance maximale (pas de double couche OS)
- ✅ Stabilité (moins de couches → moins de bugs)
- ✅ Conçu pour de la production
- ❌ Le matériel "appartient" à l'hyperviseur — on ne peut pas faire autre chose sur la même machine
- ❌ Compatibilité matérielle limitée à ce que l'hyperviseur supporte (drivers)

🔑 Proxmox est techniquement un type 1, même s'il a un OS sous-jacent Debian — c'est l'hyperviseur qui pilote, Debian sert d'environnement de gestion.

## Type 2 — hosted (sur un OS hôte)

L'hyperviseur est une **application** qui tourne **sur un OS standard** (Windows, macOS, Linux). Les VMs sont des processus de cet OS.

Exemples :
- **VirtualBox** — Oracle, open source, multiplateforme
- **VMware Workstation / Fusion** — propriétaire
- **QEMU** seul (sans KVM) — userspace
- **Parallels Desktop** — macOS

### Caractéristiques

- ✅ Installable sur n'importe quelle machine (poste perso)
- ✅ Pratique pour tester un OS, dev local
- ✅ N'empêche pas d'utiliser la machine normalement
- ❌ Performance réduite (double couche)
- ❌ Pas adapté à la production
- ❌ Resource sharing chaotique avec l'OS hôte

🔑 Cas typique : un dev qui lance Ubuntu dans VirtualBox sur son Windows pour tester un projet.

## La virtualisation matérielle (VT-x, AMD-V)

La virtualisation **moderne** repose sur des **extensions matérielles** des CPUs :
- **Intel VT-x** (depuis ~2006) — extensions VMX
- **AMD-V** — équivalent AMD

Ces instructions permettent au CPU de fonctionner en **mode invité** : la VM exécute son code à pleine vitesse, et seules les instructions "sensibles" (accès matériel) déclenchent un **VM exit** vers l'hyperviseur. Avant ces extensions, la virtualisation devait **émuler tout le CPU** — extrêmement lent.

🔑 **Aucune virtualisation moderne sérieuse ne fonctionne sans VT-x/AMD-V.** Sur un CPU qui ne les a pas (ou désactivés dans le BIOS), tu ne peux pas créer de VM efficacement.

### Vérifier la dispo

```bash
# Linux
egrep -c '(vmx|svm)' /proc/cpuinfo
# > 0 = présent. 0 = absent.

# Vérifier l'activation
kvm-ok       # Ubuntu/Debian
lscpu | grep Virtualization
```

⚠️ Si présent dans le CPU mais désactivé dans le BIOS : aller dans le BIOS, activer "Intel Virtualization Technology" ou "SVM Mode".

### Extensions complémentaires

- **EPT (Intel) / RVI (AMD)** : Extended Page Tables — accélère la traduction d'adresses mémoire pour les VMs (gain énorme)
- **VT-d (Intel) / AMD-Vi (AMD)** : **IOMMU**, permet le **passthrough** de matériel à une VM (GPU, NIC dédiée…)

## IOMMU et PCI passthrough

L'**IOMMU** (Input/Output Memory Management Unit) est un composant matériel qui traduit les adresses mémoire pour les périphériques PCI. Indispensable pour exposer un périphérique **directement à une VM** sans virtualisation logicielle.

Cas d'usage typiques :
- **GPU passthrough** : VM Windows avec GPU dédié pour gaming/CAD
- **NIC passthrough** : VM pare-feu avec une carte réseau physique dédiée (perf maximale, isolation)
- **HBA passthrough** : VM TrueNAS qui gère directement les disques

🔑 Pour activer le passthrough sur Linux/Proxmox :
1. Activer IOMMU dans le BIOS
2. Ajouter `intel_iommu=on` (ou `amd_iommu=on`) au kernel
3. Identifier le device PCI à passer (`lspci`)
4. L'attribuer à une VM (UI Proxmox ou config QEMU)

⚠️ Le **groupage IOMMU** importe : le matériel regroupe les devices PCI en "IOMMU groups". On ne peut passer qu'**un groupe entier** à une VM, pas un device isolé du groupe. Certaines cartes mères ont un groupement fin (bien), d'autres regroupent tout (passthrough impossible).

## Paravirtualisation

Concept : **modifier légèrement l'OS invité** pour qu'il sache qu'il est virtualisé et coopère avec l'hyperviseur, au lieu d'émuler tout matériel.

Avantage : performance bien supérieure à l'émulation pure (notamment I/O).

Exemple : **virtio** sur KVM = drivers paravirtualisés pour disque, réseau, balloon mémoire. Les Linux modernes ont les drivers virtio nativement ; Windows nécessite d'installer les **virtio drivers** au boot.

➡️ Détails : [Réseau virtuel](./04-reseau-virtuel.md), [Disques virtuels](./03-disques-virtuels.md).

## Type 1 vs Type 2 : quel choix selon l'usage

| Usage | Type recommandé | Outil |
|-------|-----------------|-------|
| Serveur de production | Type 1 | Proxmox, ESXi |
| Homelab dédié | Type 1 | Proxmox |
| Lab temporaire sur PC perso | Type 2 | VirtualBox, VMware Workstation |
| Tester un OS rapidement | Type 2 | VirtualBox, GNOME Boxes |
| Dev environnement isolé | Type 2 | Vagrant + VirtualBox, ou Linux + KVM |
| Service intensif (DB, gros calcul) | Type 1 | Proxmox + dedicated host |
| GPU passthrough (gaming) | Type 1 | Proxmox + IOMMU |

## Surcommittement (overcommit)

Capacité de **promettre plus de ressources** aux VMs que ce que la machine a physiquement.

Exemples :
- 16 Go RAM physique → 24 Go alloués cumulés à des VMs
- 8 cœurs CPU → 16 vCPUs alloués

Possible parce que les VMs **ne consomment pas en permanence** ce qu'elles ont. Mais risqué si toutes consomment en même temps.

### CPU overcommit

Généralement sain (1 vCPU = 1 thread, le scheduler partage). Ratio 2:1, 4:1 raisonnable selon la charge.

### RAM overcommit

Plus délicat. Mécanismes :
- **Ballooning** (virtio_balloon) : l'hyperviseur récupère de la RAM "non utilisée" dans une VM
- **KSM** (Kernel Same-page Merging) : détecte les pages mémoire identiques entre VMs et les fusionne
- **Swap** : si tout déborde, swap sur disque (lent, à éviter)

⚠️ Trop d'overcommit RAM → ballooning + swap massif → perfs catastrophiques. **Mieux vaut dimensionner sain que overcommit agressif.**

## Vocabulaire courant

| Terme | Définition |
|-------|------------|
| **Host** (hôte) | La machine physique qui exécute l'hyperviseur |
| **Guest** (invité) | Une VM tournant sur l'hôte |
| **VM** (Virtual Machine) | Une machine virtuelle complète |
| **vCPU** | Cœur CPU virtuel attribué à une VM |
| **Hypervisor** / **VMM** (Virtual Machine Monitor) | L'hyperviseur, synonymes |
| **Bare-metal** | Sans OS sous-jacent (= type 1) |
| **Hosted** | Au-dessus d'un OS (= type 2) |
| **Snapshot** | État figé d'une VM à un instant T |
| **Live migration** | Déplacer une VM en cours d'exécution d'un host à un autre |
| **Template** | VM "modèle" servant à cloner d'autres VMs |
| **Datastore** / **Pool de stockage** | Espace de stockage utilisé pour les disques de VMs |

## Limites de la virtualisation

À ne pas oublier :

- **Overhead** : même paravirtualisé, ~5-15% de perte vs bare-metal
- **Latence I/O** : un disque virtualisé est moins rapide qu'un SSD direct
- **Time drift** : les VMs peuvent avoir une horloge qui dérive — NTP est encore plus crucial qu'ailleurs
- **Side-channels** : les vulnérabilités CPU (Spectre, Meltdown, etc.) sont particulièrement dangereuses sur un host partagé — patcher l'hyperviseur ET les guests
- **Bruyance entre VMs** : une VM gourmande peut affecter les autres si pas de cgroups/limits

## À retenir

- **Type 1 (bare-metal)** : hyperviseur direct sur matériel — Proxmox, ESXi. Pour la production.
- **Type 2 (hosted)** : hyperviseur dans un OS — VirtualBox, VMware Workstation. Pour le poste perso/dev.
- **VT-x / AMD-V** : instructions CPU obligatoires pour la virtualisation moderne.
- **EPT / RVI** : accélération mémoire ; **IOMMU (VT-d / AMD-Vi)** : passthrough PCI.
- **Paravirtualisation (virtio)** : performances proches du bare-metal, drivers spéciaux.
- **Overcommit** : possible mais risqué côté RAM, normal côté CPU.
- Le serveur "host", les VMs "guests". Les **vCPUs** sont des threads attribués à des VMs.

## Pour aller plus loin

- [KVM, QEMU, libvirt](./02-kvm-qemu-libvirt.md) — la stack utilisée par Proxmox
- [Réseau virtuel](./04-reseau-virtuel.md) — comment une VM se connecte
- [VMs vs conteneurs](./06-vms-vs-containers.md) — choisir la bonne abstraction
- [Haute dispo et clustering](./08-haute-dispo-clustering.md) — au-delà d'une VM solo
- Doc Proxmox : [pve-docs](https://pve.proxmox.com/pve-docs/)
- Wikipedia : [Hypervisor](https://en.wikipedia.org/wiki/Hypervisor)
