# 04 — Réseau virtuel : bridges, virtio, tap

> **Type** : Notion · **Sujet** : Virtualisation · **Prérequis** : [Hyperviseurs](./01-hyperviseurs.md), [Switching L2](../../reseau/notions/02-switching-l2-mac-arp.md)

## En une phrase

Une VM a une **carte réseau virtuelle (vNIC)** qui dialogue avec un **équivalent virtuel du switch** sur l'hôte — typiquement un **Linux bridge** auquel une **interface TAP** connecte la VM. Tout le réseau IP/Ethernet "classique" passe par cette chaîne, avec des optimisations clés (**virtio**, **vhost-net**) pour la performance.

## Les briques du réseau virtuel

```
                    ┌─────────────────────────────────────────────┐
                    │ Hôte Linux (Proxmox)                        │
                    │                                             │
                    │  ┌────────┐   ┌────────────┐   ┌─────────┐  │
                    │  │  VM    │──►│  vNIC      │──►│  TAP    │  │
                    │  │ (Linux)│   │ (virtio)   │   │ ifs     │  │
                    │  └────────┘   └────────────┘   └────┬────┘  │
                    │                                     │       │
                    │                  ┌──────────────────┴────┐  │
                    │                  │  Linux bridge (vmbr0) │  │
                    │                  └──────┬────────────────┘  │
                    │                         │                   │
                    │                  ┌──────┴──────┐            │
                    │                  │  eth0 (NIC  │            │
                    │                  │  physique)  │            │
                    │                  └──────┬──────┘            │
                    └─────────────────────────┼───────────────────┘
                                              │ câble
                                              ▼
                                          Switch physique
```

Trois éléments à distinguer :

1. **vNIC** côté VM : la carte réseau que la VM "voit" (Linux y voit `eth0` ou `enpXsY`)
2. **TAP** côté hôte : interface virtuelle Linux représentant l'autre côté du câble — c'est par là que les paquets sortent de la VM dans l'hôte
3. **Bridge Linux** côté hôte : un switch virtuel logiciel qui interconnecte les TAPs et l'interface physique

🔑 **TAP = câble réseau virtuel** entre la VM et le bridge. Une VM = une TAP par vNIC.

## Linux bridge — switch virtuel

Un **bridge** Linux (`brctl`, ou plutôt `ip link` moderne) est un **switch software de couche 2** qui :
- Connecte plusieurs interfaces (physiques, TAPs, ou même autres bridges via veth)
- Apprend les MACs comme un vrai switch (cf. [Switching L2](../../reseau/notions/02-switching-l2-mac-arp.md))
- Forward les trames Ethernet entre ses ports

Création manuelle (pour le contexte — Proxmox le fait via son UI) :

```bash
# Créer un bridge
ip link add name br0 type bridge
ip link set br0 up

# Ajouter une interface physique
ip link set eth0 master br0

# Donner une IP au bridge (pour management de l'hôte)
ip addr add 10.0.10.5/24 dev br0
ip route add default via 10.0.10.1
```

Sur **Proxmox**, le bridge par défaut s'appelle **`vmbr0`** (alias pour "virtual machine bridge 0"). Les TAPs des VMs y sont automatiquement attachées. Configuration persistée dans `/etc/network/interfaces` :

```
auto vmbr0
iface vmbr0 inet static
    address 10.0.10.5/24
    gateway 10.0.10.1
    bridge-ports eth0
    bridge-stp off
    bridge-fd 0
```

## Interface TAP

Une **TAP** est une interface virtuelle Linux **point-à-point** : ce que tu écris dedans ressort de l'autre côté. C'est le mécanisme standard pour qu'un userspace (QEMU pour une VM) injecte et reçoive des trames Ethernet.

Quand QEMU démarre une VM avec un vNIC en mode bridge, il :
1. Crée une TAP (nommée typiquement `tap<VMID>i<index>`, ex. `tap101i0`)
2. L'attache au bridge spécifié (`vmbr0`)
3. Lit/écrit les trames sur cette TAP en provenance/à destination de la VM

Visible avec :
```bash
ip link show type tap
# tap101i0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 master vmbr0

bridge link show
# tap101i0 master vmbr0 ...
```

🔑 **TUN** (l'analogue couche 3, pas couche 2) existe aussi — utilisé par les VPNs (OpenVPN, WireGuard). Mais pour les VMs, c'est **TAP** (L2).

## vNIC : émulée vs paravirtualisée

Côté guest, la VM voit une "carte réseau" qui peut être de plusieurs types — choix très important pour la performance.

| Type | Description | Perf | Compat |
|------|-------------|------|--------|
| `e1000` | Émule Intel 82540EM gigabit | Moyenne | Quasi universelle |
| `e1000e` | Émule Intel 82574L | Moyenne | Large |
| `rtl8139` | Émule Realtek 100 Mbit/s | Faible | Universelle (legacy) |
| `vmxnet3` | Émule la NIC VMware paravirtuelle | Bonne | OS avec drivers VMware |
| **`virtio` (virtio-net)** | **Paravirtualisée KVM** | **Excellente** | Linux natif, Windows avec drivers |

### Pourquoi virtio est nettement meilleur

L'émulation d'une `e1000` implique de "faire croire" à la VM qu'elle a une vraie carte Intel — chaque accès registre déclenche un VM exit, traitement par QEMU, retour. Coûteux.

**virtio** est un protocole conçu **pour la virtualisation** : pas de prétendu hardware à émuler, juste un canal de communication efficace entre guest et host via mémoire partagée et notifications légères.

Gain typique : **2-10x plus de débit, 5-20x moins de CPU**.

⚠️ Windows ne contient **pas** de drivers virtio nativement. Il faut soit :
- Installer Windows en émulant `e1000` (lent mais ça marche), puis installer les **virtio-win** drivers et basculer
- Monter l'ISO **virtio-win** au moment de l'install Windows et fournir le driver à la sélection de disque/réseau

Linux moderne (kernel 2.6.25+) a virtio nativement.

## vhost-net : encore plus performant

Au-delà de virtio "userspace", **vhost-net** déporte le traitement des paquets virtio **dans le noyau hôte**, court-circuitant QEMU userspace pour le data path.

Effet :
- **Latence réduite** (moins de context switches userspace ↔ kernel)
- **Throughput augmenté** (zero-copy, traitement kernel)

Activé par défaut sur Proxmox/libvirt quand le module `vhost_net` est chargé (ce qui est le cas par défaut sur les distros récentes).

## Modes de connexion d'une vNIC

QEMU propose plusieurs backends pour le réseau d'une vNIC. Au-delà du mode "bridge" (le 99% des cas), connaître les autres :

### Bridge (mode standard)
La VM est connectée à un bridge Linux → comme branchée à un switch. **Pleine connectivité L2** vers les autres machines du bridge (autres VMs, machine physique via NIC).

C'est ce qu'on utilise systématiquement en production / homelab sérieux.

### NAT (user-mode networking)
QEMU fait office de mini-routeur NAT. La VM voit un réseau privé interne et sort masqueradé sur l'IP de l'hôte. Pas d'inbound facile (port forwarding au cas par cas).

🔑 C'est ce que fait **VirtualBox par défaut**. Pratique sur un poste perso, inadapté en production.

### Host-only
La VM voit uniquement l'hôte et les autres VMs du même "host-only network". Pas d'Internet, pas d'accès au LAN physique.

### Internal
Les VMs entre elles uniquement. Même pas l'hôte ne participe.

### Macvtap / Macvlan
Variante du bridge où chaque vNIC a une MAC unique exposée directement sur le réseau physique, sans passer par un bridge logiciel. Plus performant, mais ne permet pas à l'hôte et à la VM de se parler sur la même interface physique.

## L'hôte et le bridge — point délicat

Si tu déclares `vmbr0` avec `eth0` comme port et que tu mets l'IP de l'hôte sur `vmbr0` (et plus sur `eth0`), c'est OK : l'hôte communique **via** le bridge. C'est ce que fait Proxmox par défaut.

```
                  ┌──────────────────┐
                  │   Proxmox host   │
                  │   IP : 10.0.10.5 │ ← portée par vmbr0, PAS par eth0
                  └────────┬─────────┘
                           │ (via vmbr0)
                  ┌────────┴─────────┐
                  │     vmbr0        │ ← l'IP est ici
                  ├────────┬─────────┤
                  │  eth0  │ tap101i0│
                  │  (port)│ (port)  │
                  └────┬───┴────┬────┘
                       │        │
                  Réseau phys.  VM
```

⚠️ Erreur classique : mettre l'IP sur `eth0` ET sur `vmbr0` → conflit, comportement aléatoire. Une seule des deux porte l'IP.

## MTU

Le MTU (Maximum Transmission Unit) standard Ethernet est **1500 octets**. Toute la chaîne doit être cohérente :

- **vNIC** : MTU côté guest
- **TAP** : MTU côté hôte (généralement adapté auto)
- **Bridge** : MTU du bridge (= max des ports)
- **NIC physique** : MTU côté hôte
- **Switch physique** : MTU configuré

🔑 **Si tu actives les jumbo frames** (MTU 9000) côté physique pour booster les transferts massifs (SAN, backups), il faut configurer **toute la chaîne** — sinon paquets fragmentés ou jetés.

⚠️ Cas spécial : si tu utilises 802.1Q ([VLANs](../../reseau/notions/03-vlans-et-802-1q.md)), le tag ajoute 4 octets → MTU effectif réduit ou besoin de "baby giant" support.

## Hairpin mode

Par défaut, un bridge Linux n'envoie **pas** une trame entrante sur un port back vers le même port (anti-loop). Cas où c'est gênant : une VM A veut accéder à un service hébergé sur une autre VM B accessible via une IP que la résolution DNS pointe sur l'hôte → la requête sort de la VM A, est NATée, revient vers le bridge, mais ne peut pas redescendre vers B sur le même bridge sans hairpin.

Solution : activer `hairpin mode` sur le port concerné :
```bash
bridge link set dev tap101i0 hairpin on
```

C'est l'équivalent du "NAT reflection" mais en couche 2.

## openvswitch (OVS) — l'alternative avancée

**Open vSwitch** est une alternative au Linux bridge classique, avec plus de features :
- VLANs avancés (gestion type Cisco)
- Quality of Service (QoS)
- Flow-based forwarding (OpenFlow)
- LACP (bonding)
- Tunneling (VXLAN, GRE, Geneve)
- Stats détaillées par port

Proxmox supporte OVS comme alternative au Linux bridge. C'est plus puissant mais plus complexe. Pour un homelab simple, **Linux bridge suffit largement**. OVS shines en SDN, multi-tenant, OpenStack.

## Bonding / LAG

Agréger **plusieurs NICs physiques** en une seule interface logique :
- Redondance (active/passive)
- Bande passante cumulée (LACP, hash-based load balancing)

Sur Linux : interface `bondX` qui regroupe `eth0`+`eth1`+…. Le bond peut ensuite être port du bridge.

Modes courants :
- `active-backup` : 1 actif, autres en standby — simple, marche partout
- `802.3ad` / LACP : nécessite switch compatible — distribution de charge active

Utile en homelab avec plusieurs NICs et un switch manageable. Pas nécessaire pour démarrer.

## Performance : ordre de grandeur

Sur du matériel commun moderne, avec virtio + vhost-net :
- Trafic VM ↔ VM **sur le même host** : 10-40 Gbps (limité par CPU)
- Trafic VM ↔ extérieur via 1 GbE physique : ~940 Mbps (line rate)
- Trafic VM ↔ extérieur via 10 GbE : 5-9 Gbps (CPU bound)

Avec passthrough PCI (NIC dédiée à la VM) : performance native, mais NIC monopolisée.

## Pièges fréquents

| Symptôme | Cause |
|----------|-------|
| VM sans connectivité | Bridge mal configuré, NIC physique pas dans le bridge |
| VM voit l'hôte mais pas Internet | Routing/NAT en amont KO, ou MTU mismatch |
| Pertes étranges sur des gros paquets | MTU mismatch sur la chaîne |
| Windows VM réseau extrêmement lent | Driver `rtl8139` ou `e1000` — installer virtio |
| Performance plafonnée | Pas de vhost-net (`lsmod \| grep vhost_net`) |
| 2 VMs avec même MAC accidentellement | Conflit ARP, l'une perd la connectivité |
| Hôte et VM ne se voient pas | Macvtap/macvlan utilisé (limitation native) |
| Pertes de paquets entre 2 VMs sur le même host | Très rare, possiblement CPU saturé |
| Bridge MAC instable | STP activé (généralement désactivé sur les bridges Proxmox) |

## À retenir

- **vNIC** côté VM, **TAP** côté hôte, **bridge** Linux entre les TAPs et la NIC physique.
- **virtio + vhost-net** = duo gagnant pour la performance. Toujours préférer aux NICs émulées.
- **`vmbr0` Proxmox** = bridge par défaut. Tu en crées d'autres pour segmenter.
- Mode **bridge** = ce qu'on utilise toujours en homelab/production. NAT = mode poste perso.
- Cohérence **MTU** sur toute la chaîne.
- L'IP de l'hôte est sur le **bridge**, pas sur l'interface physique.
- **Open vSwitch** : alternative puissante mais plus complexe — Linux bridge suffit en général.

## Pour aller plus loin

- [VLANs dans la virtualisation](./05-vlans-virtualisation.md) — la suite logique
- [KVM, QEMU, libvirt](./02-kvm-qemu-libvirt.md)
- [Switching L2, MAC, ARP](../../reseau/notions/02-switching-l2-mac-arp.md) — pour comprendre ce qu'un bridge fait
- [Outils de diagnostic réseau](../../reseau/notions/09-outils-diagnostic.md)
- Doc Proxmox : [Network Configuration](https://pve.proxmox.com/wiki/Network_Configuration)
- `man bridge`, `man ip-link`
