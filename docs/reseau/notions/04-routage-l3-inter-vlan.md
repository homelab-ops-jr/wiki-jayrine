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

## Cartes d'entraînement

### Faits & terminologie

??? question "Quelle est la notation décimale pointée équivalente à `/24` ?"
    `255.255.255.0`.

??? question "Pour le sous-réseau `10.0.10.0/24`, quelles sont l'adresse réseau et l'adresse de broadcast ?"
    Adresse réseau : `10.0.10.0`. Broadcast : `10.0.10.255`.

??? question "Combien d'adresses sont utilisables dans un `/24`, et lesquelles sont exclues ?"
    **254** adresses utilisables (`.1` à `.254`).
    
    Sont exclues : l'**adresse réseau** (`.0`) et l'**adresse de broadcast** (`.255`) du subnet.

??? question "Que signifie l'acronyme CIDR, et que représente la notation `/24` ?"
    **Classless Inter-Domain Routing** — méthode de notation des sous-réseaux IP qui remplace les anciennes classes A/B/C en permettant un préfixe de longueur variable.
    
    La notation `/N` indique que les **N premiers bits** de l'adresse identifient le réseau, et les bits restants identifient l'hôte. Pour `/24` : 24 bits de réseau, 8 bits d'hôte → équivalent à `255.255.255.0` → 256 adresses dont 254 utilisables.
    
    CIDR a remplacé le système des classes (qui imposait des tailles fixes : /8, /16, /24) en permettant n'importe quelle taille de subnet — ce qui économise massivement l'espace d'adressage IPv4.

??? question "Comment s'écrit la route par défaut en notation CIDR ?"
    `0.0.0.0/0` — un préfixe de longueur 0 qui matche **toutes** les adresses IP possibles. C'est la route de dernier recours.

??? question "Que signifie l'acronyme SVI ?"
    **Switched Virtual Interface** — interface virtuelle sur un switch L3 qui sert de **gateway IP** pour un VLAN. Elle porte l'adresse IP que les hôtes du VLAN utilisent comme default gateway.

??? function "Cite les 4 protocoles de routage dynamique mentionnés et leur usage."
    - **RIP** : ancien, vector distance, peu utilisé aujourd'hui.
    - **OSPF** : link state, standard en entreprise.
    - **BGP** : entre opérateurs Internet, et de plus en plus en datacenter.
    - **EIGRP** : propriétaire Cisco.

??? question "Quel protocole de routage dynamique est le standard en entreprise ?"
    **OSPF** (Open Shortest Path First), un protocole de type link state.

??? question "Quel protocole de routage est utilisé entre opérateurs Internet ?"
    **BGP** (Border Gateway Protocol). Il est aussi de plus en plus utilisé en datacenter.

??? question "Qu'est-ce que le multinetting (ou secondary IP) ?"
    Configuration où **plusieurs subnets cohabitent sur la même interface physique**, sans VLAN pour les séparer.
    
    Techniquement possible, mais déconseillé — préférer la règle **un VLAN par subnet, un subnet par VLAN** pour la clarté et la sécurité.

### Concepts

??? question "Pourquoi une machine ne peut-elle envoyer directement en Ethernet que dans son propre segment ?"
    Parce que la **couche 2 (Ethernet) n'a de portée que sur le segment local** : une trame est commutée selon des MACs, qui ne sont valides que dans le broadcast domain courant.
    
    Pour joindre une IP en dehors du subnet local, la machine doit donc **déléguer à un routeur** : elle envoie la trame à la MAC de sa **default gateway**, et c'est le routeur qui se charge de transmettre le paquet IP vers le subnet de destination, en reconstruisant une nouvelle trame Ethernet adaptée au segment de sortie.

??? question "Qu'est-ce qu'une table de routage, et comment se lit une entrée typique sous Linux ?"
    Une **table de routage** est la liste des routes connues d'une machine. Chaque entrée dit : « pour atteindre tel sous-réseau, sors par telle interface, éventuellement via telle gateway ».
    
    Exemple :
    
    ​```
    default via 10.0.10.1 dev eth0
    10.0.10.0/24 dev eth0 proto kernel scope link src 10.0.10.50
    ​```
    
    Lecture :
    
    - `default via 10.0.10.1 dev eth0` : pour **tout ce que la table ne couvre pas explicitement**, envoyer à `10.0.10.1` via `eth0`.
    - `10.0.10.0/24 dev eth0` : pour le subnet local, **sortie directe** sur `eth0`, pas besoin de gateway.

??? question "Qu'est-ce que la default gateway, et que se passe-t-il sans elle ?"
    La **default gateway** est la route `0.0.0.0/0` — l'adresse à utiliser quand **aucune route plus spécifique ne matche** dans la table de routage. C'est ce qui permet de joindre tout ce qui n'est pas dans le subnet local, et en particulier Internet.
    
    **Sans default gateway configurée**, la machine ne peut joindre **que son propre subnet local**. Tout autre destination renverra une erreur "Network unreachable" parce qu'il n'y a littéralement aucune route correspondante.

??? question "Explique le principe du longest prefix match avec un exemple."
    Quand **plusieurs routes matchent** une IP destination, c'est la route avec le **préfixe le plus spécifique** (le plus long) qui gagne.
    
    Exemple, pour joindre `10.0.20.50` avec la table :
    
    ​```
    10.0.0.0/8     via 192.168.1.1
    10.0.20.0/24   via 192.168.1.2
    default        via 192.168.1.254
    ​```
    
    - `10.0.0.0/8` matche (8 bits de préfixe)
    - `10.0.20.0/24` matche aussi (24 bits)
    - `default` matche (0 bits)
    
    La route `/24` gagne car c'est la plus spécifique. C'est ce mécanisme qui permet d'avoir une default route large **et** des routes plus précises pour des cas particuliers.

??? question "Décris les 7 étapes que fait un routeur quand un paquet arrive sur une interface."
    1. **Reçoit la trame Ethernet** sur une interface.
    2. **Retire l'en-tête Ethernet** (la trame est désencapsulée).
    3. **Examine l'IP destinataire** du paquet IP.
    4. **Consulte sa table de routage** pour décider de l'interface de sortie et du prochain saut.
    5. **Décrémente le TTL** — si TTL = 0, jette le paquet et renvoie un ICMP `Time exceeded` à la source.
    6. **Construit une nouvelle trame Ethernet** avec MAC source = son interface de sortie, MAC destination = MAC du prochain saut (résolue par **ARP** si pas en cache).
    7. **Envoie la nouvelle trame** par l'interface de sortie.
    
    À chaque saut, la trame Ethernet est **reconstruite intégralement**, mais le paquet IP reste **le même** (sauf TTL décrémenté).

??? question "Qu'est-ce que le router-on-a-stick ?"
    Architecture inter-VLAN où un routeur a **un seul lien physique** vers le switch, configuré en **port trunk**, et utilise des **sous-interfaces logiques** (une par VLAN) pour porter une IP de gateway dans chaque VLAN.
    
    Exemple :
    
    ​```
    eth0       (trunk, sans IP)
      ├── eth0.10  (IP 10.0.10.1, VLAN 10)
      ├── eth0.20  (IP 10.0.20.1, VLAN 20)
      └── eth0.30  (IP 10.0.30.1, VLAN 30)
    ​```
    
    **Avantage** : un seul câble physique.  
    **Inconvénient** : bande passante partagée entre tous les VLANs.

??? question "Quelle est la différence entre un switch L3 et un routeur traditionnel pour faire de l'inter-VLAN routing ?"
    Un **switch L3 (multilayer)** sait **router en interne** entre ses propres VLANs, sans avoir besoin d'un routeur externe. Le routage se fait en **commutation matérielle**, ce qui donne des performances maximales.
    
    Inconvénients : matériel **plus cher**, options de **filtrage applicatif plus limitées** que sur un pare-feu logiciel. Pas le choix typique pour un homelab, qui préfère un pare-feu logiciel (OPNsense/pfSense) pour la flexibilité des règles.

??? question "Comment OPNsense/pfSense fait-il de l'inter-VLAN routing sur Proxmox en pratique ?"
    L'hyperviseur Proxmox héberge la VM pare-feu et lui présente **N vNICs**, chacune **taggée d'un VLAN** dans la configuration du bridge VLAN-aware.
    
    Côté OPNsense/pfSense, ces N vNICs apparaissent comme **N interfaces séparées**, chacune dans un VLAN, chacune portant une IP de gateway dans le sous-réseau correspondant. Le pare-feu route et filtre entre ces interfaces selon ses règles.
    
    C'est techniquement du **router-on-a-stick** côté implémentation (un seul lien physique trunk vers le switch en amont), mais présenté à l'admin comme du multi-interface classique.

??? question "Pourquoi le pare-feu doit-il autoriser le trafic dans les deux directions, et qu'est-ce qui sauve un firewall stateful ?"
    Quand A (VLAN 10) parle à B (VLAN 20), **deux flux** traversent le routeur : le trafic **aller** (`A → routeur → B`) et le trafic **retour** (`B → routeur → A`). Les deux doivent être autorisés pour que la communication fonctionne.
    
    **Piège classique** : tu écris une règle "VLAN 10 → VLAN 20 autorisé" sans rien pour le retour. Sans état, la réponse de B est bloquée et la connexion ne s'établit jamais.
    
    Un **pare-feu stateful** (comme OPNsense ou pfSense par défaut) suit l'état des connexions : dès qu'une session est autorisée dans un sens, le **trafic retour est implicitement autorisé** tant que la session est active. Pas besoin d'écrire la règle inverse.

??? question "Qu'est-ce qu'une SVI sur un switch L3, et quel est son équivalent sur un routeur classique ou un pare-feu ?"
    Une **SVI** (Switched Virtual Interface) est une interface virtuelle sur un switch L3 qui sert de **gateway IP** pour un VLAN. Quand on configure `interface Vlan10 ; ip address 10.0.10.1/24`, on crée une SVI.
    
    L'équivalent sur un **routeur classique** ou un **pare-feu** est la **sous-interface VLAN** (ex. `eth0.10`) ou l'**interface VLAN logique** dans la GUI d'OPNsense/pfSense.
    
    Concept clé commun : l'**IP de gateway** d'un sous-réseau est portée par une **interface logique** (SVI ou sous-interface), pas par le switch ou le routeur en tant que tel.

??? question "Routes statiques vs routes dynamiques : différence et cas d'usage."
    **Statiques** : on écrit **manuellement** chaque route. Convient aux topologies **petites et stables** — un homelab typique a quelques routes statiques (essentiellement la default) et n'a plus rien à toucher.
    
    **Dynamiques** : des **protocoles de routage** (OSPF, BGP, RIP, EIGRP) **échangent les routes automatiquement** entre routeurs. Indispensable en entreprise ou chez les opérateurs où la topologie évolue et où il y a beaucoup de routeurs interconnectés. Hors scope homelab classique.

??? question "Pourquoi Linux ne route pas par défaut, et comment l'activer ?"
    Par défaut, un noyau Linux **ne forwarde pas** les paquets entre interfaces : si un paquet arrive sur `eth0` et n'est pas destiné à la machine, il est **jeté**. C'est un choix de sécurité — la grande majorité des machines Linux sont des end-hosts, pas des routeurs.
    
    Pour activer le forwarding :
    
    ​```bash
    sudo sysctl -w net.ipv4.ip_forward=1
    sudo sysctl -w net.ipv6.conf.all.forwarding=1
    ​```
    
    Pour rendre persistant, ajouter dans `/etc/sysctl.conf` ou un fichier dans `/etc/sysctl.d/` :
    
    ​```
    net.ipv4.ip_forward = 1
    net.ipv6.conf.all.forwarding = 1
    ​```
    
    Sur OPNsense/pfSense, c'est **automatique** — c'est leur rôle.

??? question "Décris le parcours complet d'un paquet de A (`10.0.10.50`, VLAN 10) vers B (`10.0.20.50`, VLAN 20) à travers un router-on-a-stick."
    **1. A constate que B n'est pas dans son subnet** (`10.0.20.50` ∉ `10.0.10.0/24`) → A doit passer par sa **default gateway** `10.0.10.1`.
    
    **2. A fait un ARP** pour `10.0.10.1` (s'il n'a pas déjà la MAC en cache), puis envoie une trame Ethernet `src=MAC-A, dst=MAC-routeur` contenant un paquet IP `src=10.0.10.50, dst=10.0.20.50`.
    
    **3. Le switch** commute cette trame dans le VLAN 10, l'envoie taggée VLAN 10 sur le port trunk vers le routeur.
    
    **4. Le routeur** reçoit la trame sur sa sous-interface `eth0.10`, retire l'en-tête Ethernet, examine l'IP dest `10.0.20.50`, **consulte sa table de routage** qui dit "`10.0.20.0/24` est directement connecté via `eth0.20`", **décrémente le TTL**.
    
    **5. Le routeur fait un ARP** pour `10.0.20.50` (via `eth0.20`) si nécessaire, puis **construit une nouvelle trame** `src=MAC-routeur-VLAN20, dst=MAC-B`, contenant le **même paquet IP** (TTL décrémenté).
    
    **6. Cette trame ressort taggée VLAN 20** sur le trunk vers le switch, qui la commute jusqu'à B.
    
    **7. B reçoit une trame** apparemment "directe" sur son segment, et répond — le retour suit le chemin inverse, autorisé implicitement par le pare-feu stateful.

### Diagnostic

??? question "Ping vers Internet KO mais ping vers le routeur OK — causes probables ?"
    La couche 2 et la connectivité locale sont OK (puisque tu joins le routeur), donc le problème est **au-delà du routeur** :
    
    - **Default gateway pas en route** sur la machine — vérifier `ip route` côté client.
    - **Routeur sans NAT** vers Internet — il route bien les paquets mais ils repartent avec une IP privée non routable sur Internet.
    - **Routeur sans route vers Internet** ou sans connectivité WAN — vérifier la table de routage et les interfaces du routeur lui-même.

??? question "Ping vers une autre VLAN KO depuis une machine — causes possibles ?"
    - **Pas de route** vers l'autre subnet — la machine n'a pas de default gateway, ou aucune route ne matche.
    - **Le pare-feu bloque** le flux entre les deux VLANs.
    - **Gateway mal configurée** côté client (mauvaise IP, ou la gateway n'a pas d'interface dans le VLAN cible).
    - **IP forwarding désactivé** sur le routeur si c'est un Linux qui doit router (`net.ipv4.ip_forward=0`).
    
    Vérifier dans l'ordre : `ip route` côté client, joignabilité de la gateway (`ping <gateway>`), règles du pare-feu, table de routage côté routeur.

??? question "Connexion sortante OK mais réponse pas reçue — qu'est-ce que ça suggère ?"
    Deux causes principales :
    
    - **Pare-feu non stateful** ou règle de retour manquante : la requête passe, mais la réponse est bloquée parce qu'aucune règle explicite ne l'autorise.
    - **Route asymétrique** : la requête sort par un chemin, la réponse revient par un autre chemin qui ne sait pas (ou refuse) de la traiter — typique quand il y a plusieurs routeurs ou interfaces WAN.

??? question "Erreur 'No route to host' — cause ?"
    Aucune route correspondante dans la table de routage **et pas de default gateway** qui matche cette destination. La machine sait littéralement où chercher pour rien.
    
    Vérifier `ip route` : il manque soit une route spécifique, soit la default route.

??? question "Erreur 'Network unreachable' — cause et différence avec 'No route to host' ?"
    **Network unreachable** : pas de **default gateway** configurée. La machine peut joindre son subnet local mais rien au-delà — il n'existe aucune route pour atteindre les autres réseaux.
    
    **No route to host** : il y a bien une default route ou des routes, mais aucune ne matche cette destination précise (cas plus rare en pratique courante).
    
    En homelab, **Network unreachable** est le symptôme typique d'une machine qui a une IP mais pas reçu de gateway via DHCP, ou d'une config statique incomplète.

??? question "Le routeur reçoit les paquets mais ne les transmet pas — quel paramètre vérifier sur Linux ?"
    L'**IP forwarding** : `net.ipv4.ip_forward` (et `net.ipv6.conf.all.forwarding` pour IPv6).
    
    Vérifier l'état actuel :
    
    ​```bash
    sysctl net.ipv4.ip_forward
    ​```
    
    Si la valeur est `0`, le noyau jette les paquets non destinés à la machine elle-même. Activer avec `sysctl -w net.ipv4.ip_forward=1` (temporaire) ou via `/etc/sysctl.d/` (persistant).

??? question "Tu vois des `Time exceeded` ICMP renvoyés au client — qu'est-ce que ça suggère ?"
    Le **TTL** des paquets atteint **0** avant d'arriver à destination, et un routeur sur le chemin renvoie l'ICMP `Time exceeded` au client.
    
    Causes possibles :
    
    - **Loop de routage** : deux routeurs avec des default routes croisées se renvoient le paquet à l'infini jusqu'à épuisement du TTL.
    - **Chemin trop long** (rare en pratique avec un TTL initial de 64 ou 128).
    - **Usage normal de `traceroute`** : `traceroute` envoie volontairement des paquets avec un TTL faible pour faire répondre chaque routeur du chemin.

### Outils

??? question "Quelle commande pour savoir par où Linux va envoyer un paquet vers une IP précise, avant même de l'envoyer ?"
    ​```bash
    ip route get <ip>
    ​```
    
    Exemple : `ip route get 8.8.8.8` → sortie du type `8.8.8.8 via 10.0.10.1 dev eth0 src 10.0.10.50`. Très utile pour vérifier que la default route et le choix d'interface sont conformes à ce qu'on attend, sans avoir à envoyer de paquet réel.

??? question "Quelle commande pour activer l'IP forwarding IPv4 de manière temporaire sur Linux ?"
    ​```bash
    sudo sysctl -w net.ipv4.ip_forward=1
    ​```
    
    Pour IPv6 : `sudo sysctl -w net.ipv6.conf.all.forwarding=1`. Le changement est perdu au reboot — pour le rendre persistant, éditer `/etc/sysctl.conf` ou créer un fichier dans `/etc/sysctl.d/`.

??? question "Comment rendre l'IP forwarding persistant sur Linux ?"
    Ajouter dans `/etc/sysctl.conf` ou dans un fichier dédié sous `/etc/sysctl.d/` (par exemple `/etc/sysctl.d/99-routing.conf`) :
    
    ​```
    net.ipv4.ip_forward = 1
    net.ipv6.conf.all.forwarding = 1
    ​```
    
    Appliquer immédiatement sans reboot : `sudo sysctl --system` (recharge tous les fichiers sysctl).
