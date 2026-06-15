# 04 — Routage L3 et inter-VLAN

> **Type** : Notion · **Sujet** : Réseau · **Prérequis** : [Modèle OSI](./01-modele-osi-tcpip.md), [VLANs et 802.1Q](./03-vlans-et-802-1q.md)

## En une phrase

Le **routage** est l'opération qui permet à un paquet IP de **traverser plusieurs réseaux** pour atteindre sa destination. Le **routeur** (ou un pare-feu qui en joue le rôle) examine l'IP destinataire, consulte sa **table de routage**, et décide vers où transmettre.

## Le besoin : sortir du segment local

Une machine ne peut envoyer directement (en Ethernet) que **dans son propre segment** (= son VLAN, son broadcast domain). Pour tout le reste, il lui faut **déléguer à un routeur**.

```
PC      A (10.0.10.50/24, VLAN 10)
         │
         │ veut joindre 10.0.20.50 (VLAN 20)
         │
         │ Mais 10.0.20.50 n'est PAS dans 10.0.10.0/24
         │ → impossible d'envoyer directement en Ethernet
         │
         ▼
        Envoie à la "default gateway" : 10.0.10.1
        (qui est le routeur, dans son segment)
                │
                ▼
            Routeur (interfaces dans VLAN 10 ET VLAN 20)
                │
                │ Consulte sa table de routage
                │ → "10.0.20.0/24 est joignable via interface VLAN 20"
                │
                ▼
            Transmet la trame dans VLAN 20 vers 10.0.20.50
```

## Concepts clés

### Subnet (sous-réseau)

Un sous-réseau IP est un bloc d'adresses défini par **adresse réseau + masque** :
- `10.0.10.0/24` = adresses `10.0.10.0` à `10.0.10.255`
- Masque `/24` = les 24 premiers bits identifient le réseau, les 8 derniers identifient l'hôte
- Adresses utilisables : `10.0.10.1` à `10.0.10.254` (la `.0` = réseau, la `.255` = broadcast du subnet)

Notations équivalentes : `255.255.255.0` (forme décimale) = `/24` (forme CIDR).

### Table de routage

Liste de **routes**. Chaque route dit : "pour atteindre tel sous-réseau, sors par telle interface et/ou via telle gateway".

Exemple typique sur Linux :
```
$ ip route
default via 10.0.10.1 dev eth0
10.0.10.0/24 dev eth0 proto kernel scope link src 10.0.10.50
```

Lecture :
- `default via 10.0.10.1 dev eth0` : pour **tout ce que tu ne sais pas**, envoie à `10.0.10.1` via `eth0`
- `10.0.10.0/24 dev eth0` : pour ce sous-réseau (le local), pas besoin de gateway, sortie directe sur `eth0`

### Default gateway

La route par défaut (`0.0.0.0/0`, ou `default`). Adresse à utiliser quand **aucune route plus spécifique ne matche**. C'est ce qui permet "de sortir vers Internet" et plus généralement de joindre tout ce qui n'est pas dans ton subnet local.

⚠️ Sans default gateway configurée, une machine ne peut joindre que son propre subnet — point.

### Longest prefix match

Quand plusieurs routes matchent, le **préfixe le plus spécifique gagne**.

Exemple :
```
10.0.0.0/8       via 192.168.1.1   # réseau privé large
10.0.20.0/24     via 192.168.1.2   # spécifique pour VLAN 20
default          via 192.168.1.254
```

Pour `10.0.20.50` :
- `10.0.0.0/8` matche (8 bits)
- `10.0.20.0/24` matche aussi (24 bits)
- Default route matche aussi (0 bits)
- → La route `/24` gagne (la plus spécifique)

## Le routeur en pratique

Un routeur a **plusieurs interfaces réseau**, chacune dans un sous-réseau distinct, chacune avec une IP. Il :

1. Reçoit une trame Ethernet sur une interface
2. Retire l'en-tête Ethernet
3. Examine l'IP destinataire du paquet
4. Consulte sa table de routage
5. Décrémente le **TTL** (Time To Live) — si 0, jette le paquet et renvoie `Time exceeded` (ICMP)
6. Construit une **nouvelle trame Ethernet** avec :
   - MAC source = son interface de sortie
   - MAC destination = MAC du prochain saut (ARP nécessaire)
7. Envoie la nouvelle trame par l'interface de sortie

🔑 À retenir : à **chaque saut**, la trame Ethernet est **reconstruite intégralement**, mais le paquet IP est le **même** (sauf TTL décrémenté). C'est la magie du routage.

## Inter-VLAN routing : 3 architectures

### 1. Routeur traditionnel "router-on-a-stick"

Un routeur a **un seul lien physique** vers le switch, en **port trunk**, avec **des sous-interfaces** logiques par VLAN.

```
Routeur
  └── eth0 (port trunk)
       ├── eth0.10 (IP 10.0.10.1, VLAN 10)
       ├── eth0.20 (IP 10.0.20.1, VLAN 20)
       └── eth0.30 (IP 10.0.30.1, VLAN 30)
```

C'est ce que fait OPNsense en VM avec un seul vNIC connecté à un bridge VLAN-aware — il crée des **interfaces VLAN logiques** taggées.

Avantage : un seul câble physique.
Inconvénient : bande passante partagée entre tous les VLANs.

### 2. Switch L3 (multilayer)

Un switch qui sait **router** entre ses propres VLANs en interne (sans avoir besoin d'un routeur externe).

Performance maximale (commutation matérielle) mais cher et moins flexible pour le filtrage. Pas le choix typique d'un homelab.

### 3. Pare-feu en multi-interfaces

Le pare-feu (OPNsense, pfSense, etc.) a **N interfaces physiques ou virtuelles**, chacune dans un VLAN. C'est typiquement ce qu'on fait sur Proxmox : N vNICs, chaque vNIC tagué d'un VLAN dans la config du bridge, vu par OPNsense comme N interfaces séparées.

C'est **router-on-a-stick** côté implémentation interne, mais présenté plus simplement à l'admin.

## Filtrage : où agit le pare-feu

Quand un paquet **traverse** un routeur pour passer du VLAN 10 au VLAN 20, c'est précisément à ce moment-là qu'un **pare-feu** peut appliquer des règles : "accepter / rejeter selon l'IP source, l'IP dest, le port, etc."

Sans pare-feu, le routeur transmet tout sans filtrage.

➡️ Détails : [Pare-feu stateful](./07-pare-feu-stateful.md).

## L'asymétrie : trafic aller vs retour

Quand A (VLAN 10) parle à B (VLAN 20), **deux flux passent par le routeur** :
- Aller : `A → router → B`
- Retour : `B → router → A`

Le pare-feu doit autoriser les **deux directions** (ou bien être stateful — voir fiche pare-feu).

⚠️ Piège classique : tu écris une règle "VLAN 10 → VLAN 20" autorisé, mais pas le retour. Sans état, ça ne marche pas — la réponse est bloquée. **OPNsense/pfSense sont stateful** par défaut, donc le retour est implicitement autorisé pour une session établie.

## Le concept de SVI (Switched Virtual Interface)

Sur un switch L3, chaque VLAN a une **SVI** = une interface virtuelle qui sert de **gateway IP** pour ce VLAN. Quand on configure `interface Vlan10 ; ip address 10.0.10.1/24`, on crée une SVI.

Sur un routeur classique ou un pare-feu en VM, c'est l'équivalent des **sous-interfaces** ou des **interfaces VLAN**.

Concept clé : l'**adresse IP de gateway** d'un sous-réseau est portée par une SVI (sur switch L3) ou par une sous-interface (sur routeur), pas par le switch lui-même.

## Routes statiques vs dynamiques

### Statiques
Tu écris manuellement chaque route. Convient pour des topologies petites et stables. C'est ce qu'on fait dans un homelab — quelques routes par défaut, plus rien à toucher.

### Dynamiques
Des **protocoles de routage** échangent les routes entre routeurs automatiquement :
- **RIP** : ancien, vector distance, peu utilisé
- **OSPF** : link state, le standard en entreprise (couche 3)
- **BGP** : entre opérateurs, et de plus en plus en datacenter
- **EIGRP** : propriétaire Cisco

Hors scope d'un homelab classique. Bon à savoir que ça existe.

## Cas particulier : routage entre subnets sur la même interface

C'est possible mais déconseillé (et appelé "secondary IP" ou "multinetting"). Préférer **un VLAN par subnet, un subnet par VLAN**.

## Outils pour examiner le routage

```bash
# Voir la table de routage Linux moderne
ip route
ip -6 route   # IPv6

# Voir le routage en temps réel d'un paquet
traceroute 8.8.8.8        # IPv4
traceroute -6 google.com  # IPv6

# Voir le cache ARP (vers qui on envoie en couche 2)
ip neigh

# Voir si la default route est bonne
ip route get 8.8.8.8
# Sortie : 8.8.8.8 via 10.0.10.1 dev eth0 src 10.0.10.50
```

➡️ Cf. [Outils de diagnostic](./09-outils-diagnostic.md).

## Pièges fréquents

| Symptôme | Cause |
|----------|-------|
| Ping vers Internet KO mais ping vers le routeur OK | Default gateway pas en route, ou routeur sans NAT |
| Ping vers une autre VLAN KO | Pas de route, ou pare-feu bloque, ou gateway mal configurée |
| Connexion sortante OK mais réponse pas reçue | Pare-feu pas stateful, ou route asymétrique |
| "No route to host" | Pas de route correspondante dans la table |
| "Network unreachable" | Pas de default gateway (subnet local OK, mais rien au-delà) |
| Routeur reçoit le paquet mais ne transmet pas | `ip_forwarding` désactivé (Linux : `sysctl net.ipv4.ip_forward=1`) |
| Loop de routage | Default routes croisées qui se renvoient à l'infini → TTL épuise → `Time exceeded` |

## IP forwarding sur Linux

Pour qu'une machine Linux puisse **router** (transmettre des paquets entre interfaces), il faut activer :

```bash
# Temporaire
sudo sysctl -w net.ipv4.ip_forward=1
sudo sysctl -w net.ipv6.conf.all.forwarding=1

# Persistant : /etc/sysctl.conf ou /etc/sysctl.d/
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
```

Sur OPNsense/pfSense, c'est automatique — c'est le rôle de la machine.

## À retenir

- Le **routeur** transmet entre subnets. Le **switch** transmet dans un subnet.
- **Default gateway** = "où aller quand on ne sait pas".
- **Longest prefix match** : la route la plus spécifique gagne.
- À chaque saut routeur, la trame Ethernet est **reconstruite**, le paquet IP **conservé** (sauf TTL).
- **Inter-VLAN routing** se fait via un routeur/pare-feu avec une interface dans chaque VLAN (souvent en sous-interfaces sur un trunk).
- Le **trafic retour** doit aussi être autorisé — d'où l'importance du **stateful firewall**.
- **`net.ipv4.ip_forward=1`** pour transformer Linux en routeur.

## Pour aller plus loin

- [VLANs et 802.1Q](./03-vlans-et-802-1q.md)
- [DHCP](./05-dhcp.md) — distribuer une default gateway aux hôtes
- [NAT (SNAT, DNAT)](./06-nat-snat-dnat.md) — sortir vers Internet
- [Pare-feu stateful](./07-pare-feu-stateful.md) — filtrer aux frontières
- [Outils de diagnostic](./09-outils-diagnostic.md) — `traceroute`, `ip route`
