# 03 — Disques virtuels : formats, stockages, cache, performance

> **Type** : Notion · **Sujet** : Virtualisation · **Prérequis** : [KVM, QEMU, libvirt](./02-kvm-qemu-libvirt.md)

## En une phrase

Un **disque virtuel** est un **fichier** (ou un volume logique) sur l'hôte qui apparaît à la VM comme un disque physique. Le **format** (raw, qcow2…), le **type de stockage** (LVM, ZFS, NFS…), et le **mode de cache** affectent fortement la performance, la consommation d'espace, et les capacités (snapshots, thin provisioning).

## Les deux dimensions à choisir

Quand tu crées un disque virtuel, deux décisions sont à prendre :

1. **Le format** du contenu : raw, qcow2…
2. **Le backend de stockage** : où et comment le fichier est posé (filesystem ? volume LVM ? dataset ZFS ?)

Ces deux choix sont liés mais distincts. Un qcow2 peut vivre sur un filesystem ; un volume LVM brut contient en général du raw.

## Format 1 — raw

Le plus simple : **un fichier image brut**, octet pour octet ce que la VM voit comme disque.

```
disk-vm-101.raw   →  contenu = "le disque virtuel"
```

- ✅ **Performance maximale** (pas de traduction)
- ✅ Compatible partout (peut être monté en loopback sur l'hôte avec `losetup`/`mount`)
- ✅ Simple à comprendre, à sauvegarder, à manipuler
- ❌ **Pas de snapshots** au niveau du fichier
- ❌ **Pas de thin provisioning** sur la plupart des FS (sauf FS sparse — voir plus bas)
- ❌ Pas de compression

🔑 raw est **le format de référence** pour la performance. Tout le reste se mesure contre lui.

### Sparse vs full allocation

Un fichier `.raw` peut être :
- **Full allocated** : 50 Go alloués = 50 Go pris sur le disque hôte immédiatement
- **Sparse** : 50 Go alloués mais seulement l'espace effectivement écrit consomme du disque (les "trous" ne prennent pas de place)

```bash
# Créer un raw sparse de 100 Go
truncate -s 100G disk.raw     # le fichier "fait" 100 Go mais consomme ~0

# Voir l'espace réellement utilisé
du -h disk.raw       # affiche la taille apparente
du -h --apparent-size disk.raw   # idem
ls -lh disk.raw      # taille apparente
```

Sparse sur les filesystems modernes (ext4, XFS, btrfs) = équivalent du "thin provisioning" pour le raw.

## Format 2 — qcow2 (QEMU Copy-On-Write v2)

Le format **natif de QEMU**, riche en features :

- ✅ **Sparse natif** (pas besoin de FS sparse)
- ✅ **Snapshots internes** (stockés dans le même fichier)
- ✅ **Compression** optionnelle (zlib)
- ✅ **Chiffrement** AES (optionnel)
- ✅ **Backing files** (overlay/fork — un qcow2 peut "hériter" d'un autre disque parent)
- ❌ Performance légèrement inférieure à raw (5-15% selon le workload)
- ❌ Manipulable uniquement via `qemu-img` (pas un FS monté direct)

### Cas d'usage typiques

- Snapshots fréquents (dev, test)
- Stockage économe (sparse + compression)
- Templates et clones rapides (backing file)
- Stockage sur un FS classique (ext4, NFS) où LVM n'est pas dispo

```bash
# Créer un qcow2 de 100 Go (sparse par défaut)
qemu-img create -f qcow2 disk.qcow2 100G

# Inspecter
qemu-img info disk.qcow2
# virtual size: 100 GiB
# disk size: 2.3 GiB           ← réel
# format-specific information:
#     compat: 1.1
#     compression type: zlib

# Convertir entre formats
qemu-img convert -f qcow2 -O raw disk.qcow2 disk.raw
qemu-img convert -f raw -O qcow2 -c disk.raw disk.qcow2   # -c = compressed

# Créer un overlay (backing file)
qemu-img create -f qcow2 -F qcow2 -b template.qcow2 vm.qcow2
# → vm.qcow2 hérite de template.qcow2 ; écritures séparées
```

## Format 3 — vmdk, vdi, vhdx (autres écosystèmes)

- **vmdk** : VMware (ESXi, Workstation)
- **vdi** : VirtualBox natif
- **vhdx** : Hyper-V

QEMU sait les lire/écrire (utile pour migrer une VM depuis VMware/VirtualBox). Mais en homelab Proxmox, on reste en **raw ou qcow2**.

## Choisir raw ou qcow2 — règles simples

| Critère | raw | qcow2 |
|---------|-----|-------|
| Performance pure | ✅ | ⚠️ (~5-15% perte) |
| Snapshots intégrés | ❌ | ✅ |
| Sparse facile | dépend FS | ✅ natif |
| Compression | ❌ | ✅ |
| Backup / copie simple | ✅ | ✅ |
| Thin provisioning sur LVM | via LVM-thin | inutile (qcow2 sparse) |
| Cas typique | VM perf critique sur LVM | VM dev/test, templates |

🔑 En homelab, **qcow2 sur FS classique** ou **raw sur LVM-thin** sont les deux choix dominants.

## Les types de stockage Proxmox

Proxmox abstrait le stockage en **"pools"** que tu déclares (Datacenter → Storage). Chaque pool a un **type** :

| Type | Description | Format supporté |
|------|-------------|-----------------|
| **Directory** | Un répertoire sur un FS (ext4/XFS/etc.) | raw, qcow2 |
| **LVM** | Volume Group LVM "épais" | raw |
| **LVM-thin** | Volume Group LVM avec thin pool | raw |
| **ZFS** | Pool ZFS local | raw (ZVOL) |
| **CIFS / NFS** | Partage réseau | raw, qcow2 |
| **iSCSI** | LUN distant | raw |
| **Ceph (RBD)** | Cluster Ceph | raw |
| **GlusterFS** | Cluster Gluster | raw, qcow2 |

🔑 Le storage par défaut sur une install Proxmox simple :
- `local` : répertoire `/var/lib/vz` → ISOs, templates, backups, qcow2
- `local-lvm` : LVM-thin sur le VG `pve` → disques VM en raw

### LVM-thin : thin provisioning sur volumes raw

Avantage : combinaison "raw rapide" + "économie d'espace" + "snapshots LVM-thin".

```
                         LVM-thin pool (100 Go physique)
                         ┌──────────────────────────┐
                         │                          │
   vm-101-disk-0  (raw)  │  effectivement   3 Go    │
   vm-102-disk-0  (raw)  │  effectivement  15 Go    │
   vm-103-disk-0  (raw)  │  effectivement   5 Go    │
                         │  ── libre :     77 Go    │
                         └──────────────────────────┘
   Chaque LV virtuel peut être déclaré "200 Go", l'allocation est paresseuse.
```

⚠️ Comme tout thin provisioning : **risque d'overcommit**. Si la somme effectivement écrite dépasse l'espace physique, les écritures futures plantent. **Monitorer l'occupation réelle** du pool est essentiel.

### ZFS : alternative robuste

ZFS sur Proxmox apporte :
- Snapshots instantanés ZFS (différent des qcow2)
- **Compression** (LZ4 par défaut)
- **Déduplication** (gourmande en RAM, à utiliser avec parcimonie)
- **Réplication asynchrone** entre nœuds Proxmox
- Auto-réparation si tu as plusieurs disques
- **ARC cache** très efficace

⚠️ ZFS aime la RAM (compter ~1 Go par To utile, voire plus avec dedup). Et **pas de RAID matériel** avec ZFS — il faut du passthrough disque ou du HBA en mode IT.

### Stockage partagé (NFS, Ceph, iSCSI)

Indispensable pour :
- **Live migration** sans copie de disque (cf. [HA et clustering](./08-haute-dispo-clustering.md))
- **HA Proxmox** : redémarrer une VM sur un autre nœud

Mais pour un homelab solo, le **local** suffit largement.

## Modes de cache QEMU

QEMU peut cacher les I/O entre la VM et le disque physique. Plusieurs modes existent, avec des **trade-offs performance / sécurité** :

| Mode | Description | Risque crash hôte | Perf |
|------|-------------|------------------|------|
| `none` | Pas de cache hôte, O_DIRECT | Faible (écritures directes) | Très bon |
| `writeback` | Cache hôte, fsync différé | Élevé (données en cache perdues si crash hôte) | Excellent |
| `writethrough` | Cache hôte, fsync immédiat | Très faible | Moyen |
| `unsafe` | Cache agressif, ignore fsync | Très élevé | Maximum |
| `directsync` | O_DIRECT + sync | Très faible | Faible |

🔑 **Recommandation Proxmox par défaut : `none`** pour les disques sur LVM-thin et ZFS (perf + sécurité). `writeback` peut booster les workloads I/O-bound mais aux risques. `unsafe` jamais en prod.

## Discard / TRIM

Permet à la VM de **signaler à l'hôte** que des blocs ne sont plus utilisés → l'espace peut être récupéré (thin provisioning).

Sans TRIM, un disque thin gonfle progressivement même si la VM supprime des fichiers — les blocs sont libérés côté FS de la VM mais l'hyperviseur ne le sait pas.

🔑 **Activer `discard=on` sur le disque virtuel** (option dans Proxmox UI ou `discard=on` dans `qm set`). Côté VM, monter avec `discard` (ou faire un `fstrim` périodique).

Bonus : sur SSD physique, TRIM se propage jusqu'au disque réel.

## SSD emulation

Option Proxmox : déclarer le disque virtuel comme "SSD" auprès de la VM, même si le stockage physique est HDD. Effet : la VM optimise différemment (`scheduler = none`, TRIM activé par défaut, etc.).

⚠️ Cosmétique si le stockage sous-jacent n'est pas SSD — mais utile quand on **veut** ce comportement côté guest même sur HDD.

## IOPS et latence : ce qui compte vraiment

Pour les workloads serveur, la **latence** et les **IOPS** comptent souvent plus que le débit séquentiel.

Ordre de grandeur en homelab :

| Stockage | IOPS aléatoires 4k | Latence |
|----------|--------------------|---------| 
| HDD 7200 rpm | ~100 | 5-15 ms |
| HDD 10k rpm | ~150 | 3-7 ms |
| SSD SATA | 50k-100k | 0.1-0.5 ms |
| SSD NVMe | 500k+ | < 0.1 ms |

Une VM tournant sur HDD sera **dramatiquement plus lente** au démarrage et sous charge qu'une VM sur SSD, même à débit séquentiel similaire. **Privilégier SSD pour les disques système des VMs**, HDD acceptable pour les volumes de données.

## Sauvegardes et snapshots

### Snapshot ≠ backup

Un **snapshot** est une **photo de l'état d'un disque** à un instant T, sur le même stockage. Si le stockage meurt, le snapshot meurt avec. **Ce n'est pas un backup.**

Types de snapshots :
- **qcow2 interne** : snapshot dans le fichier qcow2
- **LVM-thin** : snapshot natif du thin pool
- **ZFS** : `zfs snapshot pool/dataset@name`

### Backups Proxmox

`vzdump` est l'outil natif Proxmox pour exporter une VM complète (config + disques) vers un autre stockage. Format : `.vma` (compressé ou non). Compatible avec PBS (Proxmox Backup Server) qui ajoute dedup, incrémental, etc.

🔑 Toujours backups **hors du host** : sur un NAS, sur un PBS, sur du cloud. Sinon panne disque = perte de tout.

## Capacité, redimensionnement

Agrandir un disque virtuel :
```bash
qm resize <VMID> scsi0 +10G    # ajoute 10 Go au disque scsi0 de la VM VMID
```

Le disque hôte est agrandi. Mais la VM voit le nouveau disque agrandi → il faut **étendre la partition** et le **FS** à l'intérieur (`growpart`, `resize2fs`, `xfs_growfs`) — pas automatique.

Réduire est **beaucoup plus risqué** — éviter en règle générale (sauvegarder, recréer plus petit, restaurer).

## Pièges fréquents

| Symptôme | Cause |
|----------|-------|
| Pool LVM-thin "full" | Overcommit + écritures réelles dépassent la capacité |
| qcow2 qui grossit sans s'arrêter | TRIM pas activé, ou pas de `fstrim` côté VM |
| VM I/O lentes par rapport à `dd` sur l'hôte | Mode cache mal choisi, mauvais bus (IDE/SATA au lieu de virtio) |
| Snapshot impossible | Storage type ne supporte pas (raw direct sur LVM "épais") |
| Disque "détaché" perdu | Disque retiré de la VM mais pas du stockage — `qm rescan` peut le retrouver |
| Cannot freeze VM (snapshot live KO) | qemu-guest-agent pas installé/lancé dans le guest |
| Performance dégradée sur ZFS | RAM insuffisante pour l'ARC, ou compression sur du chiffré (inutile) |

## qemu-guest-agent

Petit agent à installer **dans la VM** qui dialogue avec l'hôte via virtio-serial. Utilité :
- **Freeze/thaw** du FS pour snapshots cohérents
- IP/hostname remontés à l'hôte
- Shutdown propre depuis l'hôte
- Sync du FS avant snapshot

🔑 **Toujours l'installer** dans les VMs (linux : `apt install qemu-guest-agent`, windows : virtio-win ISO). Et activer l'option `agent: 1` dans la config VM.

## À retenir

- **raw** : performance maximale, simple, sans features avancées.
- **qcow2** : snapshots, sparse, compression, perf légèrement inférieure.
- **Stockages Proxmox** : Directory, LVM, LVM-thin, ZFS, NFS, Ceph… chacun avec ses formats compatibles.
- **LVM-thin** = raw + thin provisioning + snapshots. **ZFS** = features avancées mais gourmand en RAM.
- **Cache `none`** par défaut, `writeback` pour booster mais aux risques.
- **discard=on** + TRIM côté guest pour récupérer l'espace thin.
- **SSD** pour les disques système, c'est la latence qui compte.
- **Snapshot ≠ backup**. Sauvegarde **hors du host** indispensable.
- **qemu-guest-agent** installé dans toutes les VMs.

## Pour aller plus loin

- [Hyperviseurs](./01-hyperviseurs.md)
- [KVM, QEMU, libvirt](./02-kvm-qemu-libvirt.md)
- [Haute dispo et clustering](./08-haute-dispo-clustering.md) — où le stockage partagé devient critique
- Doc Proxmox : [Storage](https://pve.proxmox.com/wiki/Storage), [Backup](https://pve.proxmox.com/wiki/Backup_and_Restore)
- `man qemu-img`, `man qm`
