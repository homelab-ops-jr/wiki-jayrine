# 03 — VLANs et 802.1Q

> **Type** : Notion · **Sujet** : Réseau · **Prérequis** : [Switching L2](./02-switching-l2-mac-arp.md)

## En une phrase

Un **VLAN** (Virtual LAN) permet de **diviser un switch physique en plusieurs réseaux logiques étanches**, et de **transporter ces réseaux multiples sur un seul câble** entre équipements via le **tagging 802.1Q**. C'est la brique fondamentale de toute segmentation réseau moderne.

## Le problème que résolvent les VLANs

Sans VLAN, un switch = un seul **broadcast domain** (cf. [Switching L2](./02-switching-l2-mac-arp.md)) : toutes les machines branchées voient les broadcasts des autres, peuvent se joindre, font partie du même réseau.

Pour séparer (sécurité, organisation), il fallait avant **plusieurs switches physiques** — coûteux et rigide.

Les VLANs résolvent ça : **un switch manageable peut héberger plusieurs broadcast domains logiques**, chacun se comportant comme un switch indépendant — mais sur le même matériel.

## Vocabulaire essentiel

| Terme | Définition |
|-------|------------|
| **VLAN ID** | Identifiant numérique (1 à 4094) du VLAN |
| **Port access** | Port appartenant à **un seul** VLAN ; les trames y circulent **sans tag** |
| **Port trunk** | Port qui transporte **plusieurs** VLANs ; les trames sont **taggées** 802.1Q (sauf le VLAN natif) |
| **Tag 802.1Q** | 4 octets insérés dans la trame Ethernet, contenant le VLAN ID |
| **VLAN natif** | Le VLAN dont les trames passent **sans tag** sur un trunk (souvent VLAN 1 par défaut) |
| **VLAN-aware** | Capacité d'un équipement à comprendre les tags 802.1Q (switch manageable, bridge Linux configuré) |

## Le tag 802.1Q en détail

Une trame Ethernet **normale** :
```
| MAC dst | MAC src | EtherType | Charge utile      | FCS |
   6 oct.    6 oct.   2 oct.       46-1500 oct.       4 oct.
```

Une trame **802.1Q-taggée** :
```
| MAC dst | MAC src | TPID  | TCI    | EtherType | Charge utile | FCS |
   6 oct.    6 oct.   2 oct.  2 oct.   2 oct.        ...           4 oct.
                      0x8100  ↑
                              └─ contient 12 bits de VLAN ID + 3 bits PCP + 1 bit DEI
```

Le **TPID = `0x8100`** signale "trame taggée VLAN". Le **TCI** contient :
- **VLAN ID** sur 12 bits → valeurs 0-4095, mais **0 et 4095 réservés** → **VLANs utilisables : 1 à 4094**
- **PCP** (Priority Code Point) sur 3 bits → QoS, 0-7
- **DEI** (Drop Eligible Indicator) sur 1 bit → marquage pour drop prioritaire en congestion

⚠️ Le tag ajoute **4 octets** à chaque trame. Sur un MTU standard de 1500, ça peut faire dépasser à 1504 — d'où l'option **baby giant frames** sur certains switches (accepter 1504 sans broncher).

## Access ports vs trunk ports — la distinction critique

### Access port

Configuration la plus simple : "ce port appartient au VLAN X".

```
PC ─── port access (VLAN 20) ─── Switch
```

- Le PC envoie ses trames **sans tag** (il ne sait rien des VLANs)
- Le switch **ajoute le tag VLAN 20** quand la trame entre dans le fabric interne
- Au sortir vers un autre port access du même VLAN, le tag est **retiré**

Côté PC : transparent, comme un switch normal. C'est le port "normal" pour une machine cliente.

### Trunk port (uplink)

Configuration entre équipements : "ce port transporte plusieurs VLANs taggés".

```
Switch_A ─── port trunk (VLAN 10, 20, 30) ─── port trunk ─── Switch_B (ou serveur)
```

- Les trames circulent **avec leur tag** 802.1Q
- L'équipement de l'autre côté doit savoir lire ces tags (= VLAN-aware)
- Permet à un même câble de transporter le trafic de N réseaux

🔑 **Cas typique en homelab** : un serveur Proxmox connecté au switch par **un port trunk**, et l'hyperviseur "présente" chaque VLAN aux VMs comme des interfaces séparées. Voir [VLANs en virtualisation](../../virtualisation/notions/05-vlans-virtualisation.md).

### Récap visuel

```
  PC1 (VLAN 10)             PC2 (VLAN 20)
       │ access                  │ access
       │ (sans tag)              │ (sans tag)
       ▼                         ▼
  ┌─────────────────────────────────┐
  │      Switch manageable          │
  │  VLAN 10 : ports 1, 2, 3       │
  │  VLAN 20 : ports 4, 5, 6       │
  │  Trunk  : port 8 (10+20)       │
  └─────────────────────────────────┘
                │ trunk
                │ (trames taggées 802.1Q)
                ▼
        ┌──────────────────────┐
        │   Serveur Proxmox    │
        │   (VLAN-aware)       │
        │  ┌────┐ ┌────┐       │
        │  │VM1 │ │VM2 │       │
        │  │V10 │ │V20 │       │
        │  └────┘ └────┘       │
        └──────────────────────┘
```

## Le VLAN natif — précautions

Sur un port trunk, **un VLAN** est dit "natif" : ses trames passent **sans tag**. Par défaut, c'est généralement le **VLAN 1**.

Pourquoi ce mécanisme existe : compatibilité avec des équipements anciens non-VLAN-aware qui se trouveraient sur un trunk.

Problèmes :

⚠️ **VLAN 1 par défaut partout** : un attaquant qui branche un PC sur un port trunk se retrouve dans le VLAN 1 — souvent le VLAN management.

🔒 **VLAN hopping (double tagging)** : un attaquant sur un port access dans le VLAN natif peut envoyer une trame avec **deux tags** (extérieur = natif, intérieur = VLAN cible). Le switch retire le tag extérieur (puisque natif = sans tag à l'arrivée sur le trunk), puis transmet — la trame se retrouve dans le VLAN cible.

🔒 **Best practices** :
- **Ne jamais utiliser VLAN 1** pour la production. Le déclarer comme "trou noir" (shutdown des ports access en VLAN 1).
- **Utiliser un VLAN natif différent** sur les trunks (ex. VLAN 999, sans hôtes).
- **Mieux** : configurer le trunk pour **tagger tous les VLANs**, même le natif (option `tagged native` selon les vendeurs).

## VLAN ID 1, 0 et 4095 : cas particuliers

- **VLAN 1** : VLAN par défaut sur tous les switches, à l'allumage usine tous les ports y sont. À éviter pour la production.
- **VLAN 0** (`tag = 0x000`) : signale "trame avec QoS taggée mais sans VLAN spécifique". Rare en pratique, certains équipements le rejettent.
- **VLAN 4095** : réservé, "tous VLANs" en convention IEEE.
- **VLANs réservés vendor** : certains switches réservent 4090-4094 pour usage interne — vérifier la doc.

## Plage utile : 1-4094

Avec 12 bits, on a 4094 VLANs utilisables. C'est large pour un homelab (qui en utilise typiquement 3-10).

Pour des besoins industriels au-delà : **QinQ (802.1ad)** ajoute un deuxième tag — un VLAN externe (operateur) qui contient des VLANs internes (client). Hors scope homelab classique.

## VLANs et adressage IP : c'est séparé

Un VLAN est un concept de **couche 2** (segmentation Ethernet). Un sous-réseau IP est un concept de **couche 3**. Il n'y a **aucun lien obligatoire** entre les deux.

En pratique, **la quasi-totalité des architectures associent un VLAN à un sous-réseau IP** :
- VLAN 10 → `10.0.10.0/24`
- VLAN 20 → `10.0.20.0/24`

C'est plus simple, plus lisible, et permet à un routeur/pare-feu de filtrer "par interface VLAN" qui correspond à "par sous-réseau" — équivalence pratique.

⚠️ Mais techniquement, rien n'empêche d'avoir deux sous-réseaux dans le même VLAN, ou un sous-réseau réparti sur deux VLANs (cas tordu, à éviter).

## Le rôle du routeur (ou pare-feu)

Un switch L2 **ne fait pas circuler le trafic entre VLANs**. Les VLANs sont **étanches par construction** au niveau du switch — c'est tout l'intérêt.

Pour que VLAN 10 parle à VLAN 20, il faut un **routeur** (ou un pare-feu jouant ce rôle, comme OPNsense/pfSense) qui :
- A une **interface dans chaque VLAN** (physique ou virtuelle)
- A une **IP dans chaque sous-réseau** (sert de gateway)
- **Route** les paquets entre les sous-réseaux selon ses règles

C'est le concept d'**inter-VLAN routing**, détaillé dans [Routage L3 et inter-VLAN](./04-routage-l3-inter-vlan.md).

## Cas d'usage typiques

| Scenario | VLANs typiques |
|----------|----------------|
| Domestique simple | 1 seul VLAN (par défaut) |
| Homelab segmenté | 2-5 VLANs (mgmt, lab, IoT, DMZ) |
| Petite entreprise | 5-15 VLANs (mgmt, employés, invités, ToIP, caméras, prod, etc.) |
| Datacenter | Dizaines à centaines |

Schéma type pour un homelab "Le Chaudron" :

```
VLAN 10  Management  10.0.10.0/24  Admin Proxmox, OPNsense
VLAN 20  Lab/Dev     10.0.20.0/24  VMs de développement
VLAN 30  Services    10.0.30.0/24  Apps, conteneurs internes
VLAN 40  DMZ         10.0.40.0/24  Services exposés Internet
```

Avec une **matrice de flux** définissant qui peut parler à qui — cf. [Architecture segmentée](./08-architecture-segmentee.md).

## VLANs sur Wi-Fi

Plusieurs SSID sur une borne Wi-Fi peuvent être mappés à des VLANs différents — les trames Wi-Fi du SSID "Invités" sortent taggées VLAN 30 vers le switch, par exemple. Pratique pour donner accès à des invités sans les laisser entrer dans le LAN interne.

Nécessite borne Wi-Fi capable de tagger (Unifi, MikroTik, etc.) et un trunk vers le switch.

## À retenir

- **VLAN** = broadcast domain logique séparé sur un switch manageable.
- **Access port** : un seul VLAN, trames sans tag, côté PC.
- **Trunk port** : N VLANs, trames taggées 802.1Q, côté switch-à-switch ou switch-à-hyperviseur.
- **Tag 802.1Q** : 4 octets, VLAN ID sur 12 bits → 1 à 4094 utilisables.
- **VLAN natif = trames sans tag sur un trunk**. Source de bugs et d'attaques — ne pas utiliser VLAN 1.
- VLAN (L2) et sous-réseau IP (L3) sont **techniquement indépendants** mais **toujours associés en pratique**.
- Le **routage entre VLANs** passe par un routeur/pare-feu — pas par le switch.

## Pour aller plus loin

- [Routage L3 et inter-VLAN](./04-routage-l3-inter-vlan.md) — comment faire parler les VLANs entre eux
- [Architecture segmentée](./08-architecture-segmentee.md) — concevoir un plan de VLANs
- [VLANs en virtualisation](../../virtualisation/notions/05-vlans-virtualisation.md) — Proxmox, bridges VLAN-aware
- [Switching L2, MAC, ARP](./02-switching-l2-mac-arp.md) — pour comprendre ce qu'un switch fait
- IEEE 802.1Q (la norme officielle)
