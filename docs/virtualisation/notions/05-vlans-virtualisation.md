# 05 — VLANs dans la virtualisation

> **Type** : Notion · **Sujet** : Virtualisation · **Prérequis** : [Réseau virtuel](./04-reseau-virtuel.md), [VLANs et 802.1Q](../../reseau/notions/03-vlans-et-802-1q.md)

## En une phrase

Faire transiter des **VLANs 802.1Q** dans un hyperviseur permet à plusieurs VMs (ou à une seule, type pare-feu) de "vivre" dans des réseaux logiques séparés via **un seul câble physique**. La technique repose sur des **bridges VLAN-aware** et sur des règles de **tagging** explicites par vNIC ou par interface.

## Le besoin

Pourquoi voudrait-on des VLANs en virtualisation ? Quelques cas typiques :

- **Segmentation** : la VM "DB" dans VLAN 30, la VM "web" dans VLAN 40, isolation native
- **Multi-tenant** : différents clients/projets sur le même host, chacun dans son VLAN
- **Pare-feu en VM** (OPNsense, pfSense) : la VM reçoit **tous les VLANs sur une seule vNIC** et joue le routeur inter-VLAN
- **Réutiliser une infra physique segmentée** : ton switch a déjà des VLANs configurés, tu veux les "présenter" aux VMs

## Le câble unique : trunk vers l'hyperviseur

Architecture typique :

```
Switch physique
  Port 1  ──► PC du VLAN 10 (access)
  Port 2  ──► PC du VLAN 20 (access)
  Port 24 ──► Serveur Proxmox (TRUNK : VLANs 10, 20, 30, 40)
                                          │
                                          │ un seul câble
                                          │ transporte 4 VLANs (taggés)
                                          ▼
                                   ┌──────────────┐
                                   │   eth0       │ (NIC physique du serveur)
                                   └──────┬───────┘
                                          │
                                   ┌──────┴───────┐
                                   │   vmbr0      │ (bridge VLAN-aware)
                                   └─┬─┬─┬─┬──────┘
                                     │ │ │ │
                                  taps de VMs taguées
                                  par VLAN
```

L'hyperviseur **doit savoir tagger/détagger** correctement les trames qui sortent/arrivent par cette interface — c'est le rôle du bridge **VLAN-aware**.

## Bridge VLAN-aware sur Linux/Proxmox

Un Linux bridge **classique** ne s'occupe pas des tags 802.1Q : il les fait passer comme tout autre payload. Pour qu'il gère les VLANs intelligemment, il faut le déclarer **VLAN-aware**.

Sur Proxmox, dans `/etc/network/interfaces` :

```
auto vmbr0
iface vmbr0 inet static
    address 10.0.10.5/24
    gateway 10.0.10.1
    bridge-ports eth0
    bridge-stp off
    bridge-fd 0
    bridge-vlan-aware yes
    bridge-vids 2-4094
```

Lignes clés :
- `bridge-vlan-aware yes` : active la gestion VLAN
- `bridge-vids 2-4094` : plage de VLANs autorisés à transiter (utile de restreindre en prod)

Côté UI Proxmox : Datacenter → Node → Network → vmbr0 → ☑ VLAN aware.

🔑 **Sans VLAN-aware**, tu peux quand même faire des VLANs en créant **un bridge par VLAN** + une **sous-interface** par VLAN sur la NIC physique. C'est l'ancienne méthode, plus lourde. VLAN-aware est la moderne, recommandée.

## Les deux approches : VLAN-aware vs sous-interfaces

### Approche 1 — VLAN-aware (moderne, recommandée)

**Un seul bridge** `vmbr0` qui gère tous les VLANs. Le tag est porté **par la vNIC** dans la config de la VM :

```
# Config VM Proxmox (extrait)
net0: virtio=AA:BB:CC:DD:EE:FF,bridge=vmbr0,tag=20
```

→ La VM voit son trafic "non taggé" (comme un PC sur un port access du switch). À la sortie du bridge sur eth0 (port trunk), Proxmox **ajoute le tag VLAN 20**.

À l'inverse, une trame entrant sur eth0 taggée VLAN 20 a son tag **retiré** avant d'être délivrée à la TAP de la VM.

**C'est exactement le comportement d'un port access côté switch physique.**

### Approche 2 — Sous-interfaces VLAN (legacy)

**Un bridge par VLAN**. Sur la NIC physique, on crée des **sous-interfaces** `eth0.10`, `eth0.20` etc., chacune taggée d'un VLAN, et on les attache à des bridges distincts :

```
auto eth0
iface eth0 inet manual

auto eth0.20
iface eth0.20 inet manual
    vlan-raw-device eth0

auto vmbr20
iface vmbr20 inet manual
    bridge-ports eth0.20
    bridge-stp off
    bridge-fd 0
```

Côté VM :
```
net0: virtio=AA:BB:CC:DD:EE:FF,bridge=vmbr20    # pas de tag, le bridge entier est VLAN 20
```

**Plus verbeux**, mais identique fonctionnellement. À éviter en 2026 sauf cas particulier (compatibilité, isolation stricte).

## Comment Proxmox tag les trames d'une VM

Quand tu configures `tag=20` sur une vNIC dans une config Proxmox VLAN-aware :

```
VM ───► vNIC (envoit en clair) ───► TAP ───► bridge vmbr0 (VLAN-aware)
                                                  │
                                                  │ Le port du bridge associé à
                                                  │ cette TAP est configuré en
                                                  │ "PVID 20" (Port VLAN ID)
                                                  │
                                                  │ Les trames entrant non-taggées
                                                  │ se voient assigner VLAN 20
                                                  │ pour le forwarding interne
                                                  │
                                                  ▼
                                          Sortie vers eth0 (trunk vers switch)
                                          → trame taggée VLAN 20
```

Ce mécanisme est **strictement identique** au comportement d'un switch matériel managéable. Le bridge Linux VLAN-aware **EST** un switch L2 logiciel avec VLAN support.

## Cas spécial : une VM "trunk" (OPNsense, pare-feu)

Tu veux qu'une VM reçoive **tous les VLANs sur une seule vNIC** pour les router (cas classique d'un OPNsense en VM).

Deux variantes :

### Variante A — vNIC sans tag, VM gère les sous-interfaces

```
# Config VM
net0: virtio=AA:BB:CC:DD:EE:FF,bridge=vmbr0    # PAS de tag=
```

La vNIC reçoit **toutes les trames taggées intactes**. Côté guest (OPNsense), on crée des **interfaces VLAN logiques** :

```
# Côté OPNsense (équivalent conceptuel)
vtnet0 (vNIC, reçoit toutes les trames taggées)
vtnet0.10 (interface logique VLAN 10)
vtnet0.20 (interface logique VLAN 20)
vtnet0.30 (interface logique VLAN 30)
vtnet0.40 (interface logique VLAN 40)
```

Chaque interface logique a son IP, son DHCP, ses règles. C'est **router-on-a-stick** côté OPNsense (cf. [Routage L3](../../reseau/notions/04-routage-l3-inter-vlan.md)).

⚠️ Pour que ça marche, le bridge `vmbr0` ne doit pas filtrer les VLANs avant de les délivrer à la TAP — donc ne pas configurer `tag=` sur la vNIC, et autoriser les VIDs voulus dans `bridge-vids`.

### Variante B — Une vNIC par VLAN

```
# Config VM
net0: virtio=AA:BB:CC:DD:EE:FF,bridge=vmbr0,tag=10
net1: virtio=AA:BB:CC:DD:EE:FF,bridge=vmbr0,tag=20
net2: virtio=AA:BB:CC:DD:EE:FF,bridge=vmbr0,tag=30
net3: virtio=AA:BB:CC:DD:EE:FF,bridge=vmbr0,tag=40
net4: virtio=AA:BB:CC:DD:EE:FF,bridge=vmbr1                  # WAN (séparé)
```

Côté OPNsense, **5 interfaces vues comme physiques** : vtnet0 = LAN VLAN10, vtnet1 = LAN VLAN20… et vtnet4 = WAN.

**Plus simple à configurer dans OPNsense** (pas d'interfaces VLAN logiques à créer manuellement), mais plus de vNICs à gérer côté Proxmox.

🔑 Les deux approches marchent. La variante A (une vNIC trunk) est plus "propre" et plus proche de l'architecture physique réelle. La variante B est plus simple si tu débutes avec OPNsense.

## VLAN tag direct sur la NIC physique

Tu peux aussi tagger côté **hôte Proxmox** lui-même, pas seulement pour les VMs.

Exemple : tu veux que Proxmox soit administrable **via VLAN 10** (Management), même quand le port physique reçoit du trafic taggé sur un trunk.

```
auto eth0
iface eth0 inet manual

auto eth0.10
iface eth0.10 inet manual

auto vmbr0
iface vmbr0 inet static
    address 10.0.10.5/24
    gateway 10.0.10.1
    bridge-ports eth0.10
    bridge-stp off
    bridge-fd 0
```

Ici `vmbr0` n'est PAS VLAN-aware ; il a un seul port `eth0.10` qui ne reçoit que les trames VLAN 10 (détaggées par la sous-interface). L'hôte est ainsi "dans" le VLAN 10.

Pour les **autres VLANs** des VMs, créer en parallèle un `vmbr1` VLAN-aware sur `eth0` direct (sans tag), ou des `vmbrN` avec sous-interfaces.

⚠️ **Erreur fréquente** : tagger côté hôte ET configurer aussi `tag=10` sur les vNICs → double tagging → trames invalides. Choisir une approche et s'y tenir.

## Comparaison avec un switch physique

Petit tableau de correspondance pour fixer les idées :

| Concept switch physique | Équivalent virtualisation |
|-------------------------|---------------------------|
| Port **access** VLAN 20 | vNIC avec `tag=20` sur bridge VLAN-aware |
| Port **trunk** allow 10,20,30 | vNIC **sans tag** sur bridge VLAN-aware + `bridge-vids 10,20,30` |
| Switch lui-même | Bridge VLAN-aware (`vmbr0`) |
| Port uplink trunk vers backbone | NIC physique attachée au bridge VLAN-aware |
| VLAN configuré sur le switch | Plage `bridge-vids` du bridge |
| **PVID** (Port VLAN ID) du port access | Valeur `tag=` de la vNIC |

🔑 La virtualisation **reproduit fidèlement** le modèle switch + VLAN — c'est volontaire et conceptuellement utile.

## Plan de bataille typique : Proxmox + OPNsense + 4 VLANs

```
Switch physique
  Port 1  : port access VLAN 99 (WAN — IP fournie par la box)
  Port 24 : port TRUNK (VLANs 10, 20, 30, 40 taggés + VLAN 99 pour WAN)
              │
              ▼
Serveur Proxmox
  eth0 ──► reçoit le trunk
              │
              ▼
  vmbr0 : VLAN-aware (bridge-vids 2-4094, port eth0)
              │
              ├─► tap0 ─► OPNsense VM, vNIC sans tag (= trunk vu par la VM)
              │           OPNsense crée vtnet0.10, vtnet0.20, vtnet0.30, vtnet0.40
              │           pour faire le routeur-on-a-stick
              │
              ├─► tap1 ─► OPNsense VM, vNIC avec tag=99 (= WAN)
              │
              ├─► tap2 ─► VM-Admin (VLAN 10), vNIC tag=10
              ├─► tap3 ─► VM-Dev (VLAN 20), vNIC tag=20
              ├─► tap4 ─► VM-Service (VLAN 30), vNIC tag=30
              └─► tap5 ─► VM-Exposée (VLAN 40), vNIC tag=40
```

(Beaucoup de variantes existent — c'est une parmi d'autres.)

OPNsense :
- WAN = vtnet1 (tag 99 vu comme interface)
- LAN10/20/30/40 = vtnet0 + interfaces logiques VLAN
- DHCP server par interface
- Règles de pare-feu inter-VLAN (cf. [Architecture segmentée](../../reseau/notions/08-architecture-segmentee.md))

## VLAN-aware bridge ET sous-interfaces : peut coexister

Tu peux avoir :
- `vmbr0` VLAN-aware sur `eth0` (pour les VMs taggées)
- `vmbr1` non-VLAN-aware sur `eth0.99` (pour quelque chose de spécifique au VLAN 99, par exemple le WAN)

Les deux bridges utilisent la même NIC physique, mais des sous-flux distincts. Configuration légèrement plus complexe mais parfois utile.

## VLANs en LXC (containers)

Les conteneurs LXC sur Proxmox aussi acceptent l'option `tag=` :
```
net0: name=eth0,bridge=vmbr0,tag=20,hwaddr=...
```

Même logique : tag côté config Proxmox, conteneur voit du trafic non-taggé. C'est plus simple que côté VM (pas de drivers à installer dans le conteneur — il partage le kernel hôte).

## Open vSwitch et VLANs

Si tu utilises **OVS** au lieu du Linux bridge, la syntaxe diffère mais le concept est identique :
```
ovs_options tag=20
ovs_options trunks=10,20,30,40
```

OVS offre **plus de granularité** (par exemple PVID séparé du tag, support QinQ natif, etc.) mais Linux bridge VLAN-aware couvre 99% des besoins.

## Pièges fréquents

| Symptôme | Cause |
|----------|-------|
| VM dans le VLAN n'a pas d'IP DHCP | Bridge pas VLAN-aware, ou `bridge-vids` ne contient pas le VLAN |
| Trafic VM passe mais pas tagged en sortie | NIC physique pas un trunk côté switch |
| Trafic VM tagged en double | Tag côté hôte (sous-interface) + tag côté vNIC |
| Hôte Proxmox plus joignable après changement bridge | Mauvais bridge-port, ou IP perdue dans la transition |
| VM "trunk" (OPNsense) ne voit pas les VLANs | `tag=` configuré par erreur sur la vNIC trunk, ou bridge filtré |
| Throughput VLAN dégradé | MTU non ajusté (cf. plus bas) |
| VLAN 1 visible alors qu'on ne le veut pas | VLAN natif du trunk côté switch, à reconfigurer |

## MTU et VLAN

Le tag 802.1Q ajoute **4 octets** à la trame Ethernet. Cas typique :

- MTU côté guest : 1500 (normal)
- Trame Ethernet : 1500 + headers
- Avec tag VLAN ajouté côté hôte : 1500 + 4 = 1504
- Beaucoup de NICs/switches l'acceptent par "baby giant frames" sans config
- D'autres exigent un MTU 1504 explicite ou des "jumbo frames" (MTU 9000)

Si tu vois des **pertes inexplicables sur de gros paquets** dans un setup VLAN, vérifier la cohérence MTU bout en bout.

## À retenir

- **Bridge VLAN-aware** : un seul bridge gère tous les VLANs, tag par vNIC. **L'approche moderne.**
- **Sous-interfaces** : `eth0.X` + bridge dédié par VLAN. Plus lourd, parfois nécessaire.
- **vNIC `tag=N`** = port **access** VLAN N côté switch physique.
- **vNIC sans tag sur bridge VLAN-aware** = port **trunk** vu par la VM.
- Pour un **pare-feu en VM** : un seul vNIC trunk + interfaces VLAN logiques dans le guest (OPNsense, pfSense).
- Le hyperviseur **reproduit fidèlement** le modèle switch + VLAN.
- Cohérence **MTU** quand VLAN actif.

## Pour aller plus loin

- [VLANs et 802.1Q](../../reseau/notions/03-vlans-et-802-1q.md) — la base théorique
- [Réseau virtuel](./04-reseau-virtuel.md) — les bridges sans VLANs
- [Routage L3 et inter-VLAN](../../reseau/notions/04-routage-l3-inter-vlan.md) — comment OPNsense route entre VLANs
- [Architecture segmentée](../../reseau/notions/08-architecture-segmentee.md) — concevoir un plan VLAN
- Doc Proxmox : [VLAN](https://pve.proxmox.com/wiki/Network_Configuration#_vlan_802_1q)
