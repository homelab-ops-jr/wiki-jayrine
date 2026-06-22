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

Schéma type pour un homelab :

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

## Cartes d'entraînement

### Faits & terminologie

??? question "Que veut dire l'acronyme VLAN ?"
    **Virtual LAN** — un réseau local virtuel, c'est-à-dire un broadcast domain logique séparé sur un switch manageable.

??? question "Quelle est la plage utilisable des VLAN ID ?"
    **1 à 4094**.
    
    Les valeurs 0 et 4095 sont réservées.

??? question "Sur combien de bits est codé le VLAN ID dans un tag 802.1Q ?"
    **12 bits**, ce qui donne 4096 valeurs possibles dont 4094 utilisables (0 et 4095 réservés).

??? question "Quels VLAN ID sont réservés et donc non utilisables ?"
    **0 et 4095**.
    
    Le VLAN 0 signale une trame avec QoS taggée mais sans VLAN spécifique (rare, parfois rejeté). Le VLAN 4095 est réservé par convention IEEE pour signifier "tous VLANs".

??? question "Combien d'octets ajoute un tag 802.1Q à une trame Ethernet ?"
    **4 octets** (2 pour le TPID `0x8100`, 2 pour le TCI).

??? question "Que contient le champ TCI d'un tag 802.1Q ?"
    Le **TCI** (Tag Control Information) fait 2 octets et contient :
    
    - **12 bits de VLAN ID** (1 à 4094 utilisables)
    - **3 bits de PCP** (Priority Code Point, QoS)
    - **1 bit de DEI** (Drop Eligible Indicator)

??? question "Que signifie PCP dans un tag 802.1Q ?"
    **Priority Code Point** — 3 bits de QoS (valeurs 0 à 7) qui indiquent la priorité de la trame pour le traitement en cas de congestion.

??? question "Que signifie DEI dans un tag 802.1Q ?"
    **Drop Eligible Indicator** — 1 bit qui marque la trame comme prioritairement droppable en cas de congestion.

??? question "Quel VLAN est par défaut sur tous les switches à l'allumage usine ?"
    Le **VLAN 1**. Tous les ports y sont initialement assignés. À éviter pour la production.

??? question "Qu'est-ce qu'un baby giant frame ?"
    Une trame Ethernet de **1504 octets** au lieu des 1500 du MTU standard — la différence vient des **4 octets ajoutés par le tag 802.1Q**.
    
    Certains switches acceptent ces trames sans broncher (option "baby giant frames"), évitant des problèmes de fragmentation quand on traverse du trafic taggé.

??? question "Qu'est-ce que QinQ (802.1ad) ?"
    Une extension qui permet d'**imbriquer deux tags 802.1Q** dans une même trame : un VLAN externe (typiquement opérateur) qui contient des VLANs internes (typiquement client).
    
    Utilisé par les opérateurs télécom pour transporter le trafic VLAN de plusieurs clients sur leur backbone sans collision d'IDs. Hors scope homelab classique.

??? question "Définition d'un port access ?"
    Un port qui appartient à **un seul VLAN**. Les trames y circulent **sans tag** — le PC connecté ignore tout des VLANs.
    
    Le switch ajoute le tag VLAN à l'entrée du fabric interne, et le retire à la sortie vers un autre port access du même VLAN.

??? question "Définition d'un port trunk ?"
    Un port qui transporte **plusieurs VLANs simultanément**. Les trames y circulent **taggées 802.1Q** (sauf celles du VLAN natif).
    
    L'équipement de l'autre côté doit être VLAN-aware pour lire les tags. Cas typique : liaison switch-à-switch ou switch-à-hyperviseur.

??? question "Que veut dire VLAN-aware ?"
    Capacité d'un équipement à **comprendre les tags 802.1Q** : lire le VLAN ID d'une trame entrante, ajouter un tag à une trame sortante, et router/filtrer en fonction.
    
    Concerne les switches manageables, les bridges Linux configurés en mode VLAN-aware, les hyperviseurs, les bornes Wi-Fi compatibles, etc.

??? question "Qu'est-ce que le VLAN natif sur un trunk ?"
    Le VLAN dont les trames passent **sans tag** sur un trunk, contrairement aux autres VLANs qui sont taggés 802.1Q.
    
    Par défaut, c'est généralement le **VLAN 1**. Le mécanisme existe pour compatibilité avec d'anciens équipements non-VLAN-aware qui se trouveraient sur un trunk.

### Concepts

??? question "Quel problème les VLANs résolvent-ils par rapport à plusieurs switches physiques ?"
    Avant les VLANs, séparer des réseaux pour des raisons de sécurité ou d'organisation imposait d'**acheter plusieurs switches physiques** — coûteux, rigide, et non évolutif.
    
    Les VLANs permettent à un **switch manageable unique** d'héberger plusieurs broadcast domains logiques, chacun se comportant comme un switch indépendant — sur le même matériel. On gagne en coût, en flexibilité (reconfiguration logicielle) et en densité.

??? question "Comment se comporte un access port quand une trame entre et sort du switch ?"
    Côté PC, le port access est **transparent** : le PC envoie et reçoit des trames Ethernet normales, **sans tag**.
    
    À l'**entrée** sur le switch, le fabric interne **ajoute le tag VLAN** correspondant au VLAN configuré sur ce port. À la **sortie** vers un autre port access du même VLAN, le tag est **retiré** avant d'envoyer la trame au PC destinataire.

??? question "Quelle est la différence fondamentale entre un port access et un port trunk ?"
    Un **port access** appartient à **un seul VLAN** et transmet/reçoit des trames **sans tag** — il est destiné aux machines clientes (PC, imprimante, IoT).
    
    Un **port trunk** transporte **plusieurs VLANs** simultanément avec leurs trames **taggées 802.1Q** — il est destiné aux liaisons entre équipements VLAN-aware (switch-à-switch, switch-à-hyperviseur, switch-à-borne Wi-Fi multi-SSID).

??? question "Pourquoi le mécanisme de VLAN natif existe-t-il sur un trunk ?"
    Pour assurer la **compatibilité avec des équipements anciens non-VLAN-aware** qui se trouveraient sur un trunk : ces équipements ne savent pas lire les tags 802.1Q, donc on leur fait passer les trames du VLAN natif sans tag, comme du trafic Ethernet ordinaire.
    
    En pratique moderne, ce mécanisme est surtout une **source de bugs et d'attaques** (VLAN hopping), et les best practices recommandent de l'éviter quand c'est possible.

??? question "Explique le mécanisme précis du VLAN hopping par double tagging."
    L'attaquant est sur un port access dans le **VLAN natif** d'un trunk en aval. Il forge une trame avec **deux tags 802.1Q empilés** : le tag extérieur correspond au VLAN natif, le tag intérieur au VLAN cible.
    
    Quand la trame atteint le trunk, le switch **retire le tag extérieur** (puisque le VLAN natif voyage sans tag sur le trunk). La trame ressort avec le tag intérieur encore en place, et est interprétée comme appartenant au **VLAN cible** par l'équipement suivant.
    
    L'attaquant a ainsi sauté d'un VLAN à un autre sans franchir de routeur — d'où le nom "VLAN hopping".

??? question "Pourquoi VLAN (L2) et sous-réseau IP (L3) sont-ils techniquement indépendants ?"
    Un **VLAN** est un concept de **couche 2** : il segmente les trames Ethernet selon un tag, indépendamment de leur contenu.
    
    Un **sous-réseau IP** est un concept de **couche 3** : il définit une plage d'adresses IP et un masque, totalement décorrélés du tagging Ethernet.
    
    Rien dans les protocoles n'impose qu'un VLAN corresponde à un sous-réseau précis — on peut techniquement avoir deux sous-réseaux dans le même VLAN, ou un sous-réseau réparti sur deux VLANs (cas tordu à éviter).

??? question "Pourquoi associe-t-on en pratique systématiquement un VLAN à un sous-réseau IP ?"
    Pour la **lisibilité** et la **simplicité opérationnelle** : VLAN 10 → `10.0.10.0/24`, VLAN 20 → `10.0.20.0/24`, etc.
    
    Avantages : un routeur/pare-feu peut filtrer "par interface VLAN", ce qui correspond exactement à "par sous-réseau" — l'équivalence rend les règles de flux beaucoup plus claires. Le diagnostic est aussi simplifié, car connaître l'IP suffit à déduire le VLAN.

??? question "Pourquoi un switch L2 ne fait-il pas circuler le trafic entre VLANs, et qu'est-ce qui le fait ?"
    Par construction, un switch L2 **n'examine pas les en-têtes IP** — il ne fait que commuter les trames Ethernet selon leur MAC destination et leur tag VLAN. Les VLANs sont donc **étanches** au niveau du switch, c'est même tout l'intérêt de la segmentation.
    
    Pour que VLAN 10 parle à VLAN 20, il faut un **routeur** (ou un pare-feu jouant ce rôle, type OPNsense/pfSense) qui a une **interface dans chaque VLAN**, une **IP de gateway dans chaque sous-réseau**, et qui **route les paquets entre les sous-réseaux** selon ses règles. C'est l'**inter-VLAN routing**.

??? question "Comment mapper des SSID Wi-Fi à des VLANs ?"
    Sur une borne Wi-Fi capable de tagger (Unifi, MikroTik, etc.), chaque **SSID** est associé à un **VLAN ID** dans la configuration de la borne.
    
    Les trames émises par les clients du SSID "Invités" sortent vers le switch **taggées VLAN 30** (par exemple), tandis que celles du SSID "Maison" sortent **taggées VLAN 10**. La borne doit être raccordée au switch par un **port trunk** transportant les VLANs concernés.
    
    Cas d'usage classique : isoler les invités du LAN interne sans déployer plusieurs bornes physiques.

??? question "Décris le cas typique d'un serveur Proxmox raccordé au switch par un port trunk."
    **Côté switch** : un port configuré en **trunk** transporte plusieurs VLANs (par exemple 10, 20, 30) vers le serveur, avec leurs trames taggées 802.1Q.
    
    **Côté Proxmox** : l'hyperviseur est **VLAN-aware**. Il lit les tags 802.1Q entrants et **présente chaque VLAN comme une interface réseau distincte** aux VMs. Une VM affectée au VLAN 10 voit son interface comme un réseau ordinaire, sans savoir qu'elle est sur un trunk physique.
    
    Avantage : un seul câble physique transporte tout le trafic réseau de toutes les VMs, quel que soit leur VLAN.

??? question "Décris le trajet complet d'une trame depuis PC1 (port access VLAN 10) jusqu'à une VM (hébergée sur un hyperviseur connecté au switch par un trunk)."
    **1.** PC1 envoie une trame Ethernet **sans tag** sur son port access (VLAN 10).
    
    **2.** Le switch reçoit la trame, l'**associe au VLAN 10** dans son fabric interne et **ajoute le tag 802.1Q VLAN 10**.
    
    **3.** Le switch consulte sa table MAC pour le VLAN 10, trouve la MAC destination (celle de la VM) apprise via le **port trunk** vers l'hyperviseur, et y forwarde la trame **avec son tag** 802.1Q intact.
    
    **4.** L'hyperviseur, **VLAN-aware**, reçoit la trame taggée, lit le tag VLAN 10, **retire le tag**, et délivre la trame à la VM via son interface virtuelle connectée au VLAN 10.
    
    **5.** La VM voit une trame Ethernet ordinaire, sans savoir qu'elle a voyagé sur un trunk taggé.

### Diagnostic

??? question "Tu branches un PC sur un port trunk par inadvertance — où se retrouve-t-il et pourquoi est-ce dangereux ?"
    Le PC ne sait pas lire les tags 802.1Q : il ignore les trames taggées et ne voit que celles du **VLAN natif** (qui passent sans tag).
    
    Par défaut, le VLAN natif est souvent le **VLAN 1**, qui est aussi fréquemment le VLAN **management** dans les configurations non durcies. L'attaquant qui branche un PC sur un tel port se retrouve donc directement dans le réseau d'administration — accès aux interfaces de gestion des switches, du routeur, etc.
    
    C'est pour ça que les best practices recommandent de **ne jamais utiliser le VLAN 1** pour la production ni comme VLAN natif.

??? question "Tu veux que VLAN 10 et VLAN 20 puissent communiquer — quelle est la pièce manquante et comment la configurer ?"
    Il manque un **routeur** (ou un pare-feu jouant ce rôle, type OPNsense/pfSense). Le switch L2 seul ne fera jamais circuler le trafic entre VLANs — c'est l'inter-VLAN routing.
    
    Configuration nécessaire :
    
    - Une **interface du routeur dans chaque VLAN** (physique séparée, ou virtuelle via sous-interfaces taggées sur un trunk).
    - Une **IP de gateway dans chaque sous-réseau** (par exemple `10.0.10.1` et `10.0.20.1`).
    - Les hôtes des deux VLANs configurés avec **leur gateway respective**.
    - Des **règles de filtrage** sur le routeur qui autorisent explicitement le flux souhaité (par défaut, on filtre tout et on ouvre au cas par cas).

??? question "Tu veux donner du Wi-Fi à des invités sans qu'ils accèdent au LAN interne — quelle solution VLAN ?"
    Créer un **VLAN dédié "invités"** (par exemple VLAN 30), avec son propre sous-réseau IP.
    
    Sur la borne Wi-Fi capable de tagger, créer un **SSID "Invités"** mappé au VLAN 30. La borne est raccordée au switch par un **port trunk** qui transporte au moins les VLANs interne et invités.
    
    Sur le routeur/pare-feu, configurer une **interface dans le VLAN 30** qui sert de gateway, et des **règles** qui autorisent le VLAN 30 à accéder à Internet mais **bloquent tout flux** depuis le VLAN 30 vers les VLANs internes.
