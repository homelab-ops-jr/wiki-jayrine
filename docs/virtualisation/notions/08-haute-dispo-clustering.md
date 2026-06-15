# 08 — Haute disponibilité et clustering

> **Type** : Notion · **Sujet** : Virtualisation · **Prérequis** : [Hyperviseurs](./01-hyperviseurs.md), [Disques virtuels](./03-disques-virtuels.md)

## En une phrase

Un **cluster** d'hyperviseurs permet de **mutualiser plusieurs hôtes physiques** pour gérer un parc de VMs comme un seul ensemble, et la **haute disponibilité (HA)** automatise le redémarrage d'une VM sur un autre hôte si son host actuel tombe. Hors scope d'un homelab solo, mais culture indispensable pour situer Proxmox dans son ensemble.

## Pourquoi un cluster ?

Avec **un seul host**, plusieurs limites :

- **SPOF** (Single Point of Failure) : si le serveur meurt, tout est down
- **Maintenance** : impossible de redémarrer le host sans interrompre les VMs
- **Scalabilité** : limité par la machine
- **Pas de live migration** vers un autre host (forcément)
- **Backup vers ce même host** : risque de perte totale si crash

Un **cluster** de N hosts résout ces problèmes — et introduit ses propres :

- Coût (matériel × N)
- Complexité (gestion, réseau, stockage partagé)
- Nouveaux modes de défaillance (split-brain, latence, fencing)

🔑 Pour un homelab personnel : 1 host suffit. **Apprendre le concept** sans le déployer.

## Le cluster Proxmox

Proxmox VE supporte nativement le clustering. Un cluster est un groupe de **nodes Proxmox** qui se connaissent, se synchronisent, et présentent une **interface web unifiée**.

```
              ┌────────────────────────────────┐
              │       Cluster Proxmox         │
              ├──────────┬──────────┬──────────┤
              │ Node 1   │ Node 2   │ Node 3   │
              │ pve01    │ pve02    │ pve03    │
              ├──────────┼──────────┼──────────┤
              │  VMs A,B │  VM C    │  VMs D,E │
              └─────┬────┴────┬─────┴─────┬────┘
                    │         │           │
                    └─────────┼───────────┘
                              │
                  ┌───────────┴───────────┐
                  │  Stockage partagé    │
                  │  (Ceph, NFS, iSCSI)  │
                  └──────────────────────┘
```

Caractéristiques :
- Min recommandé : **3 nodes** (pour le quorum)
- Communication via **Corosync** (cluster messaging)
- Filesystem cluster `/etc/pve` (pmxcfs) synchronisé sur tous les nodes
- Une UI web unifiée à n'importe quel node

## Les briques techniques d'un cluster

### Corosync

**Corosync** est le protocole de messagerie utilisé par le cluster pour échanger des heartbeats et synchroniser les états. Il a besoin d'un **réseau dédié rapide et fiable** :
- Latence < 1-2 ms idéalement
- Pas de paquets perdus
- Pas saturé par d'autres trafics (genre VMs)

🔑 **Best practice** : un VLAN ou réseau physique séparé pour Corosync, pour ne pas être perturbé par le trafic des VMs.

### Quorum

Pour qu'un cluster prenne des décisions (ex. "ce node est mort"), il faut une **majorité de nodes en vie** (le quorum). Avec N nodes, quorum = `⌊N/2⌋ + 1`.

- 1 node : quorum = 1 → tout va bien tant qu'il vit
- 2 nodes : quorum = 2 → si 1 tombe, plus de quorum → **risque de split-brain**
- 3 nodes : quorum = 2 → tolère 1 défaillance
- 5 nodes : quorum = 3 → tolère 2 défaillances

⚠️ **2 nodes seuls = mauvaise pratique**. Soit ajouter un 3e node, soit utiliser un **QDevice** (votant externe léger, non hyperviseur).

### Split-brain

Cauchemar des clusters : un partitionnement réseau coupe le cluster en deux groupes qui ne se voient plus, chacun pensant que les autres sont morts. Si chaque groupe a (à tort) le quorum, chacun pourrait redémarrer les VMs des autres → deux instances de la même VM tournent → données corrompues.

Le quorum strict prévient ça : avec 3 nodes et 2 en vie d'un côté, 1 isolé de l'autre, seul le groupe majoritaire (2) prend les décisions. Le node isolé se "fence" lui-même.

### Fencing

Mécanisme pour **forcer un node défaillant à s'arrêter** (ou être certain qu'il l'est), avant que les autres redémarrent ses VMs.

- **Self-fencing** (watchdog) : le node lui-même se reboot si quelque chose va mal (par exemple, perte de quorum)
- **External fencing** : un mécanisme externe (PDU contrôlable, IPMI) coupe physiquement le node mort

Sans fencing fiable → risque que la VM "morte" soit en réalité en train de tourner sur le node isolé, et qu'on en démarre une autre instance ailleurs.

Proxmox utilise principalement le **watchdog** : le kernel d'un node sans quorum se hard-reset au bout d'un certain temps (configurable).

## Live migration

**Live migration** = déplacer une VM **en cours d'exécution** d'un host à un autre, sans interruption (ou presque) du service.

Comment ça marche, en simplifié :
1. Copier la **mémoire** de la VM source vers la destination, pendant qu'elle tourne
2. Re-copier les pages mémoire modifiées entre temps (plusieurs itérations)
3. Quand le delta est très petit, **figer brièvement** la VM source (microsecondes-ms)
4. Copier le delta final + état CPU
5. Démarrer la VM côté destination, l'arrêter côté source

Pour un client extérieur (qui ouvre un socket TCP, par exemple), la migration est **transparente** — quelques ms de latence supplémentaire.

### Prérequis

🔑 **Stockage partagé indispensable** (ou réplication ZFS) : la VM ne peut migrer "en vie" que si son disque est accessible des deux nodes.

- **Shared storage** (NFS, Ceph RBD, iSCSI…) : le disque est sur un stockage tiers, les deux nodes y accèdent
- **Local storage + replication** (ZFS replication) : le disque est local, mais une copie est régulièrement répliquée vers l'autre node → live migration possible avec une fenêtre de catch-up

Sans stockage partagé ni replication : **migration "offline"** seulement (arrêter la VM, copier le disque, redémarrer).

### Cas d'usage

- Maintenance d'un host (déplacer ses VMs avant de le redémarrer)
- Équilibrage de charge (DRS dans VMware, manuel sur Proxmox)
- Décommissionnement d'un host

## Haute disponibilité (HA) Proxmox

HA va au-delà du cluster : c'est le **redémarrage automatique** d'une VM sur un autre node quand son host est down.

### Configuration

Sur Proxmox : **HA groups** + **HA resources**.

- Un **HA group** = un ensemble de nodes qui peuvent héberger une ressource (`primary nodes`, `failback`, etc.)
- Une **HA resource** = une VM marquée comme "doit rester up". Si son node tombe, elle redémarre sur un autre node du groupe

🔑 Au minimum : 3 nodes, stockage partagé, HA configuré pour les VMs critiques.

### Mécanisme

```
1. Le cluster surveille en permanence ses nodes (Corosync heartbeats)
2. Un node tombe (réseau coupé, crash hardware, etc.)
3. Au bout d'un timeout, les autres nodes "constatent" : ce node n'a plus le quorum
4. Le node fenceé (watchdog auto-reboot, ou fencing externe)
5. Les VMs étaient marquées HA → un node survivant prend le relais
6. Le ressource manager redémarre la VM (depuis son disque sur le stockage partagé)
7. La VM est de retour up, sur un autre host
```

Temps total : ~1-3 minutes selon la config.

⚠️ **Ce n'est pas la même chose que "zéro downtime"**. La VM **redémarre** (donc reboot complet). Pour du vrai "zéro downtime", il faut de la redondance applicative (cluster de DB, load balancer + N instances, etc.).

### Limites

- HA n'aide pas si l'app dans la VM crashe — seulement si l'host crashe
- HA peut **provoquer** des incidents si mal configurée (false positive sur node "tombé" mais en réalité juste lent)
- Storage partagé est lui-même un SPOF — il doit être redondant

## Stockage partagé : les options

### NFS / CIFS

Un serveur NFS/CIFS exporte un partage que tous les nodes montent. Simple, performant pour des homelabs avancés.

⚠️ Le serveur NFS est un SPOF — sauf à le doubler (HA NFS, gluster, etc.).

### iSCSI

Block storage exposé sur le réseau (TCP/IP). Un LUN par VM (avec LVM par-dessus typiquement). Performance bonne, mais réseau dédié recommandé.

### Ceph

**Stockage distribué** : les nodes Proxmox eux-mêmes hébergent les disques, agrégés en un pool **redondant et auto-réparant**. Configurable sur 3+ nodes Proxmox.

- ✅ Pas de SPOF (réplique 3x par défaut)
- ✅ Performance correcte (variable selon hardware réseau)
- ✅ Scale horizontalement
- ❌ Complexe à apprendre/exploiter
- ❌ Demande des disques et du réseau dédiés
- ❌ Min 3 nodes pour être robuste

🔑 Ceph est le **stockage cluster Proxmox typique en entreprise** ou homelab très avancé.

### ZFS replication

Disques **locaux** ZFS sur chaque node, avec **réplication asynchrone** vers un autre node toutes les X minutes.

- ✅ Simple à configurer (Datacenter → Replication)
- ✅ Pas de stockage partagé requis
- ❌ La live migration utilise la dernière réplique → courte coupure d'I/O au switch (selon RPO)
- ❌ RPO = la fréquence de replication (perte de données possible jusqu'à 1 cycle)

Bon compromis pour homelab 2-3 nodes sans Ceph.

## QDevice (votant léger)

Pour les clusters à 2 nodes où on ne veut pas un 3e Proxmox complet, un **QDevice** peut servir de "votant" externe :
- Une simple machine Linux (même un Raspberry Pi)
- Fait tourner le service `corosync-qdevice`
- Vote dans les décisions de quorum, sans héberger de VMs

Ça évite le risque de split-brain en 2 nodes. C'est un pattern courant en homelab.

## Resource Pools, Tags

Pour gérer les VMs à grande échelle :

- **Pools** : regrouper des VMs (ex. "Prod", "Dev"), permissions par pool
- **Tags** : étiquettes libres pour filtrer/automatiser

Pas spécifique HA mais important quand le cluster grandit.

## Limites et anti-patterns

| Anti-pattern | Pourquoi c'est mauvais |
|--------------|------------------------|
| Cluster à 2 nodes sans QDevice | Split-brain garanti tôt ou tard |
| Corosync sur le même réseau que les VMs | Latence imprédictible, fausses détections de panne |
| HA activé avec stockage local non répliqué | La VM redémarre, mais sans son disque — fail |
| Trop de nodes (10+) sans expérience | Complexité de troubleshooting énorme |
| Mélange de versions Proxmox dans un cluster | Bugs et comportements bizarres |
| Cluster + Internet WAN défaillant | Si Corosync passe par Internet, tout casse aux coupures |
| Live migration avec stockage local seul | Pas possible — confondre avec replication |

## Cas pratique : homelab 3 nodes

Setup ambitieux mais réaliste pour quelqu'un qui veut apprendre :

```
3 mini-PCs (Intel NUC, MinisForum, etc.) avec 32 Go RAM chacun
1 NIC dédiée 2.5 GbE pour Corosync
1 NIC dédiée 2.5 GbE pour Ceph
1 NIC dédiée 1 GbE pour management/VMs

Ceph avec 1 NVMe par node → pool redondant
Quelques VMs HA-protected (homelab "prod")
Quelques VMs non-HA (sandbox, tests)
```

C'est un projet sérieux (200-300 W de consommation continue, 3 machines à entretenir). Mais c'est ce qui rapproche un homelab d'un mini-datacenter.

## Et OPNsense en cluster ? CARP

OPNsense (et pfSense) supportent leur propre clustering via **CARP** (Common Address Redundancy Protocol). Deux instances OPNsense :
- Une **MASTER** active
- Une **BACKUP** passive, qui prend le relais si la MASTER tombe

Le mécanisme repose sur :
- IP virtuelle partagée (VIP) que les MASTER porte
- Synchronisation d'état pfsync entre les deux
- Heartbeat — le BACKUP devient MASTER si la MASTER ne répond plus

🔑 Indépendant du cluster Proxmox. On peut faire CARP entre **deux VMs OPNsense** (sur deux Proxmox différents si possible — sinon perte du Proxmox = perte des deux).

## À retenir

- **Cluster Proxmox** : groupe de nodes, communication Corosync, filesystem pmxcfs synchronisé.
- **Quorum** : majorité requise pour décider — **3 nodes minimum**, sinon QDevice.
- **Live migration** = déplacer une VM en cours. Nécessite **stockage partagé ou ZFS replication**.
- **HA** = redémarrage auto sur un autre node si crash. Pas du "zéro downtime" — c'est un reboot.
- **Fencing** (watchdog auto-reboot) évite le split-brain.
- **Stockage partagé** : NFS/iSCSI (simple, SPOF), Ceph (robuste, complexe), ZFS replication (compromis).
- **CARP** pour OPNsense : indépendant du cluster Proxmox, sa propre HA.
- Homelab personnel = 1 node largement suffisant. Cluster pour l'apprentissage ou production.

## Pour aller plus loin

- [Hyperviseurs](./01-hyperviseurs.md)
- [Disques virtuels](./03-disques-virtuels.md) — stockage partagé en détail
- [Réseau virtuel](./04-reseau-virtuel.md)
- Doc Proxmox : [Cluster Manager](https://pve.proxmox.com/wiki/Cluster_Manager), [HA Manager](https://pve.proxmox.com/wiki/High_Availability), [Ceph](https://pve.proxmox.com/wiki/Deploy_Hyper-Converged_Ceph_Cluster)
- Doc OPNsense : [High Availability](https://docs.opnsense.org/manual/hacarp.html)
