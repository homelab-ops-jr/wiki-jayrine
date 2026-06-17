# 01 — Modèle OSI et TCP/IP

> **Type** : Notion · **Sujet** : Réseau · **Prérequis** : Aucun

## En une phrase

Le **modèle OSI** (7 couches) et le **modèle TCP/IP** (4 couches) sont des cartes mentales pour situer chaque concept réseau — quand on dit "il y a un problème de couche 2", on sait immédiatement qu'il s'agit de switching/MAC, pas de routing ni de TLS.

## Les deux modèles côte à côte

```
   OSI                                   TCP/IP                   Exemples concrets
┌─────────────────────────────┐       ┌──────────────────┐
│ 7  Application              │       │                  │      HTTP, SSH, DNS, SMTP
├─────────────────────────────┤       │                  │
│ 6  Présentation             │  ──►  │  Application     │      TLS (techniquement multi-couche)
├─────────────────────────────┤       │                  │
│ 5  Session                  │       │                  │      Sessions HTTP, RPC
├─────────────────────────────┤       ├──────────────────┤
│ 4  Transport                │  ──►  │  Transport       │      TCP, UDP, QUIC
├─────────────────────────────┤       ├──────────────────┤
│ 3  Réseau                   │  ──►  │  Internet        │      IP (v4/v6), ICMP, routage
├─────────────────────────────┤       ├──────────────────┤
│ 2  Liaison                  │       │                  │      Ethernet, MAC, ARP, VLAN
├─────────────────────────────┤  ──►  │  Accès réseau    │
│ 1  Physique                 │       │                  │      Câbles, ondes, signaux
└─────────────────────────────┘       └──────────────────┘
```

Le modèle OSI est plus **pédagogique** (plus fin), TCP/IP est plus **proche de la réalité** (ce qu'on implémente). En pratique, on utilise les **numéros OSI** ("c'est de la couche 3") mais on raisonne en **noms TCP/IP** ("c'est le routage IP").

## Ce qui se passe à chaque couche — décortiqué

### Couche 1 — Physique
Les bits sont effectivement transmis sur un médium : cuivre, fibre, ondes radio. Connecteurs, voltages, modulations.

À ce niveau, **rien ne sait** ce qu'il transporte. Un câble Ethernet ne distingue pas un paquet HTTP d'un ping ICMP.

Pannes typiques : câble débranché, mauvais connecteur, port mort, interférences.

### Couche 2 — Liaison (Ethernet)
On regroupe les bits en **trames Ethernet**. Chaque trame a :
- une **adresse MAC source** (48 bits, normalement unique au monde)
- une **adresse MAC destination**
- un **EtherType** qui dit ce qu'elle transporte (IPv4 = `0x0800`, IPv6 = `0x86DD`, ARP = `0x0806`, **VLAN tag 802.1Q = `0x8100`**)
- la **charge utile** (le contenu)
- un **CRC** de vérification

C'est la couche du **switching** et des **VLANs**. Le domaine de validité d'une adresse MAC est le **segment local** — les MACs ne traversent pas les routeurs.

➡️ Détails : [Switching L2, MAC, ARP](./02-switching-l2-mac-arp.md), [VLANs et 802.1Q](./03-vlans-et-802-1q.md).

### Couche 3 — Réseau (IP)
On encapsule la charge utile dans un **paquet IP**, avec :
- une **IP source** (32 bits IPv4, 128 bits IPv6)
- une **IP destination**
- un **TTL** (Time To Live, décrémenté à chaque routeur)
- un **protocole** transporté (TCP = `6`, UDP = `17`, ICMP = `1`)
- la **charge utile**

C'est la couche du **routage**. Une IP est valable **globalement** (à travers Internet), contrairement à une MAC.

À chaque saut de routeur, la trame Ethernet est **complètement reconstruite** (nouvelles MAC source/dest), mais le paquet IP reste le même (sauf TTL décrémenté).

➡️ Détails : [Routage L3 et inter-VLAN](./04-routage-l3-inter-vlan.md).

### Couche 4 — Transport (TCP, UDP)
Identifier **quelle application** sur la machine destination, et fournir des garanties.

- **TCP** : connecté (handshake 3-way), ordonné, fiable (retransmission). Used by HTTP, SSH, etc.
- **UDP** : sans connexion, sans ordre, sans garantie. Used by DNS, NTP, vidéo en streaming, jeux.
- **QUIC** : récent, basé sur UDP, multiplexé, intègre TLS (utilisé par HTTP/3).

Identification par **port** (16 bits = 0-65535). HTTPS = 443, SSH = 22, DNS = 53.

Une "connexion" TCP est identifiée par le **5-tuple** : `(IP src, port src, IP dest, port dest, protocole)`.

### Couches 5-7 — Sessions, présentation, application

En pratique on les regroupe en "application" (cf. modèle TCP/IP). HTTP, HTTPS, SSH, DNS, SMTP, etc. vivent ici.

**TLS** est techniquement un cas spécial — il s'insère entre TCP (couche 4) et l'application (couche 7) : on parle parfois de "couche 5/6". Pour fixer les idées : HTTPS = HTTP **sur** TLS **sur** TCP.

## Encapsulation : la matriochka

Quand tu envoies une requête HTTPS, chaque couche **ajoute son en-tête** autour des données :

```
┌──────────────────────────────────────────────────────────────────┐
│ Trame Ethernet                                                   │
│ ┌──────┬─────────────────────────────────────────────────┬─────┐ │
│ │ Hdr  │ Paquet IP                                       │ FCS │ │
│ │ Eth  │ ┌──────┬───────────────────────────────────┐    │     │ │
│ │ (MAC │ │ Hdr  │ Segment TCP                       │    │     │ │
│ │  src │ │  IP  │ ┌──────┬───────────────────────┐  │    │     │ │
│ │ MAC  │ │      │ │ Hdr  │ Données chiffrées TLS │  │    │     │ │
│ │ dest │ │      │ │ TCP  │ → contient HTTP       │  │    │     │ │
│ │ type)│ │      │ │      │                       │  │    │     │ │
│ │      │ │      │ └──────┴───────────────────────┘  │    │     │ │
│ │      │ └──────┴───────────────────────────────────┘    │     │ │
│ └──────┴─────────────────────────────────────────────────┴─────┘ │
└──────────────────────────────────────────────────────────────────┘
```

Chaque équipement réseau "déballe" jusqu'à la couche dont il a besoin :
- Un **switch** lit l'en-tête Ethernet et s'arrête là (couche 2)
- Un **routeur** lit jusqu'à l'IP destination (couche 3)
- Un **pare-feu stateful** lit TCP/UDP et garde l'état (couche 4)
- Un **reverse proxy** lit jusqu'à HTTP (couche 7) — d'où "pare-feu de couche 7" pour les WAF

## Pourquoi connaître ce modèle change la vie

Quand quelque chose ne marche pas, **savoir à quelle couche localiser le problème** divise par 10 le temps de diagnostic :

| Symptôme | Couche probable | Premier outil |
|----------|----------------|---------------|
| `Destination unreachable` | 3 (IP) | `ip route`, `traceroute` |
| Ping qui ne passe pas dans le LAN | 2 (ARP, switch) ou 3 (IP) | `arp -a`, `ip neigh`, vérifier câble |
| Connexion TCP refused | 4 (port fermé) ou 7 (service down) | `ss -tlnp`, `nc -zv` |
| `Connection timed out` | 3, 4, ou 7 (firewall ?) | `tcpdump`, `nc`, examiner pare-feu |
| Cert TLS invalide | 5-6 (TLS) | `openssl s_client` |
| HTTP 502 Bad Gateway | 7 (backend down ou inatteignable) | logs reverse proxy |
| Pas d'IP attribuée au boot | DHCP (4/7 sur UDP) | `journalctl`, `tcpdump port 67 or 68` |

➡️ [Outils de diagnostic réseau](./09-outils-diagnostic.md) détaille chaque commande.

## Le piège des "couches" non normalisées

Tu liras des termes comme **"firewall de couche 7"**, **"load balancer L4"**, **"VPN L2 vs L3"**. C'est utile mais **pas toujours rigoureux** par rapport à OSI :

- "Firewall L7" = pare-feu qui inspecte HTTP/applicatif (en plus de L3/L4)
- "Load balancer L4" = répartit selon IP:port, sans regarder HTTP
- "Load balancer L7" = répartit selon le path HTTP, l'host, etc.
- "VPN L2" = transporte des trames Ethernet (WireGuard non, OpenVPN tap oui)
- "VPN L3" = transporte des paquets IP (WireGuard, OpenVPN tun)

À chaque fois, le numéro indique **la couche la plus haute que l'équipement comprend**.

## À retenir

- **7 couches OSI** : Physique, Liaison, Réseau, Transport, Session, Présentation, Application.
- **4 couches TCP/IP** : Accès réseau, Internet, Transport, Application.
- **L2 = Ethernet/MAC**, **L3 = IP**, **L4 = TCP/UDP**, **L7 = applicatif**.
- Une trame Ethernet ne traverse jamais un routeur ; un paquet IP, oui.
- Localiser un problème **par couche** accélère énormément le diagnostic.

## Pour aller plus loin

- [Switching L2, MAC, ARP](./02-switching-l2-mac-arp.md)
- [VLANs et 802.1Q](./03-vlans-et-802-1q.md)
- [Routage L3 et inter-VLAN](./04-routage-l3-inter-vlan.md)
- [Outils de diagnostic réseau](./09-outils-diagnostic.md)
- RFC 1122 (Host requirements) — la formalisation TCP/IP

## Cartes d'entraînement

### Faits & terminologie

??? question "Combien de couches a le modèle OSI ?"
    7 couches.

??? question "Combien de couches a le modèle TCP/IP ?"
    4.

??? question "Cite les 7 couches OSI dans l'ordre, de 1 à 7."
    1. Physique
    2. Liaison
    3. Réseau
    4. Transport
    5. Session
    6. Présentation
    7. Application

??? question "Cite les 4 couches TCP/IP dans l'ordre."
    1. Accès réseau
    2. Internet
    3. Transport
    4. Application

??? question "À quelle couche OSI correspond Ethernet / MAC ?"
    Couche 2 (Liaison).

??? question "À quelle couche OSI correspond IP ?"
    Couche 3 (Réseau).

??? question "À quelle couche OSI correspond TCP/UDP ?"
    Couche 4 (Transport).

??? question "À quelle couche OSI correspond HTTP ?"
    Couche 7 (Application).

??? question "Quelle est la taille d'une adresse MAC ?"
    48 bits.

??? question "Quelle est la taille d'une adresse IPv4 ?"
    32 bits.

??? question "Quelle est la taille d'une adresse IPv6 ?"
    128 bits.

??? question "Quel EtherType identifie IPv4 dans une trame Ethernet ?"
    `0x0800`.

??? question "Quel EtherType identifie IPv6 ?"
    `0x86DD`.

??? question "Quel EtherType identifie ARP ?"
    `0x0806`.

??? question "Quel EtherType identifie un tag VLAN 802.1Q ?"
    `0x8100`.

??? question "Quel numéro de protocole IP identifie TCP ?"
    `6`.

??? question "Quel numéro de protocole IP identifie UDP ?"
    `17`.

??? question "Quel numéro de protocole IP identifie ICMP ?"
    `1`.

??? question "Quel port utilise HTTPS ?"
    443.

??? question "Quel port utilise SSH ?"
    22.

??? question "Quel port utilise DNS ?"
    53.

??? question "Que veut dire l'acronyme TTL dans un paquet IP ?"
    **Time To Live** — un compteur décrémenté à chaque saut de routeur. Quand il atteint 0, le paquet est jeté et un ICMP `Time Exceeded` est renvoyé à la source. C'est ce qui permet à `traceroute` de cartographier le chemin.

??? question "Quels sont les 5 éléments d'un 5-tuple TCP ?"
    `(IP source, port source, IP destination, port destination, protocole)`.
    
    C'est cette combinaison qui identifie de manière unique une connexion TCP — deux connexions différentes qui partagent 4 éléments sur 5 sont distinctes.

??? question "Sur combien de bits est codé un numéro de port, et quelle est la plage possible ?"
    16 bits, donc 0 à 65535.

### Concepts

??? question "Explique la différence entre TCP et UDP."
    **TCP** est connecté : il établit un handshake 3-way (SYN → SYN-ACK → ACK) avant tout échange, garantit l'ordre, retransmet les paquets perdus. Utilisé par HTTP, SSH, SMTP.
    
    **UDP** est sans connexion : pas de handshake, pas d'ordre garanti, pas de retransmission. Plus rapide et léger. Utilisé par DNS, NTP, vidéo en streaming, jeux temps réel — bref, quand la vitesse compte plus que la fiabilité, ou quand l'application gère elle-même la fiabilité.

??? question "Pourquoi une trame Ethernet ne traverse jamais un routeur, alors qu'un paquet IP oui ?"
    Une adresse MAC est locale au segment Ethernet — elle identifie un équipement sur le réseau local mais n'a pas de portée au-delà.
    
    Quand un paquet doit traverser un routeur, ce dernier déballe la trame Ethernet entrante, garde le paquet IP intact (sauf le TTL qui décrémente), et **reconstruit une nouvelle trame Ethernet** avec des MACs adaptées au segment de sortie.
    
    C'est pour ça que la MAC source change à chaque saut, alors que l'IP source reste la même de bout en bout.

??? question "Qu'est-ce qui change dans une trame Ethernet à chaque saut de routeur ? Qu'est-ce qui reste ?"
    **Change** : MAC source et MAC destination (reconstruites par chaque routeur pour le segment de sortie), CRC.
    
    **Reste** : tout le paquet IP encapsulé, sauf le **TTL qui décrémente** de 1 à chaque saut.

??? question "Qu'est-ce que QUIC, et qu'est-ce qui le distingue de TCP ?"
    **QUIC** est un protocole de transport récent, basé sur **UDP**, qui intègre nativement TLS et le multiplexage de plusieurs flux dans une même connexion.
    
    Il évite le head-of-line blocking de TCP (où un paquet perdu bloque tous les flux multiplexés au-dessus), et permet d'établir une connexion + TLS en un seul aller-retour. C'est le transport de **HTTP/3**.

??? question "Comment positionner TLS dans le modèle OSI ? Pourquoi c'est ambigu ?"
    TLS s'insère **entre TCP (couche 4) et l'application (couche 7)**, ce qui ne correspond à aucune couche OSI nette — on parle souvent de "couche 5/6" par convention.
    
    En pratique : **HTTPS = HTTP sur TLS sur TCP**. TLS prend les données applicatives en clair, les chiffre, et les passe à TCP pour transport.

??? question "Explique le principe d'encapsulation réseau, depuis HTTPS jusqu'à la trame Ethernet."
    Chaque couche **ajoute son en-tête autour des données** de la couche supérieure, comme des matriochkas :
    
    - L'application produit une requête HTTP.
    - TLS chiffre ces données et les passe à TCP.
    - TCP ajoute son en-tête (port source/dest, n° de séquence) → segment TCP.
    - IP ajoute son en-tête (IP source/dest, TTL, protocole) → paquet IP.
    - Ethernet ajoute son en-tête (MAC source/dest, EtherType) et un CRC en fin → trame Ethernet.
    
    À la réception, chaque couche désencapsule la sienne et passe le contenu à la couche supérieure.

??? question "Comment se compose une trame Ethernet (champs principaux) ?"
    - **MAC source** (48 bits)
    - **MAC destination** (48 bits)
    - **EtherType** — indique ce qui est transporté (IPv4 = `0x0800`, IPv6 = `0x86DD`, ARP = `0x0806`, VLAN tag = `0x8100`)
    - **Charge utile** (le paquet IP ou autre)
    - **CRC** (frame check sequence) de vérification

??? question "Comment se compose un paquet IP (champs principaux) ?"
    - **IP source** (32 bits IPv4, 128 bits IPv6)
    - **IP destination**
    - **TTL** (Time To Live, décrémenté à chaque saut)
    - **Protocole transporté** (TCP = 6, UDP = 17, ICMP = 1)
    - **Charge utile** (le segment TCP/UDP ou autre)

??? question "Pourquoi le modèle OSI reste utilisé en pratique alors que c'est TCP/IP qui est implémenté ?"
    Parce que les **numéros de couche OSI** (L2, L3, L4, L7) sont devenus un vocabulaire universel pour situer un problème ou un équipement. On dit "switch L2", "routeur L3", "firewall L7" — tout le monde comprend, alors que les noms TCP/IP ("Accès réseau", "Internet") sont moins précis.
    
    En pratique, on utilise les **numéros OSI** mais on raisonne en **noms TCP/IP**.

??? question "Que signifie 'load balancer L4' vs 'load balancer L7' ?"
    **L4** : répartit le trafic en se basant uniquement sur IP et port (couche 4). Il ne regarde pas le contenu HTTP. Rapide, simple, mais aveugle à l'applicatif.
    
    **L7** : décode HTTP et peut répartir selon le path (`/api/*` vers backend A, `/static/*` vers backend B), le Host header, les cookies, etc. Plus puissant, plus coûteux en CPU.

??? question "Que signifie 'VPN L2' vs 'VPN L3' ? Donne un exemple de chaque."
    **VPN L2** : transporte des **trames Ethernet** complètes. Le client semble être physiquement sur le LAN distant (broadcast, ARP, VLAN traversent). Exemple : OpenVPN en mode `tap`.
    
    **VPN L3** : transporte uniquement des **paquets IP**. Pas de broadcast, pas d'ARP au-delà du tunnel. Exemple : WireGuard, OpenVPN en mode `tun`, IPsec.

??? question "Que signifie 'firewall L7' ?"
    Un pare-feu qui inspecte les couches applicatives (HTTP, DNS, SMTP…) **en plus** des couches L3/L4. Il peut bloquer une requête HTTP selon son path, son User-Agent, son body, etc.
    
    Les **WAF** (Web Application Firewall) comme Coraza ou ModSecurity sont des firewalls L7 spécialisés HTTP.

??? question "Jusqu'à quelle couche du modèle remontent un switch, un routeur, un firewall stateful, un reverse proxy ?"
    - **Switch** : couche 2 (lit MAC source/dest).
    - **Routeur** : couche 3 (lit IP destination pour décider du prochain saut).
    - **Firewall stateful** : couche 4 (suit l'état des connexions TCP/UDP).
    - **Reverse proxy** : couche 7 (décode HTTP).

### Diagnostic

??? question "Tu vois `Destination unreachable` — quelle couche soupçonner et quel premier outil utiliser ?"
    **Couche 3** (IP / routage). Un routeur sur le chemin n'a pas de route vers la destination.
    
    Premier outil : `ip route` pour vérifier ta propre table de routage, puis `traceroute` pour voir où le chemin s'interrompt.

??? question "Tu fais un ping dans le LAN local et ça ne passe pas — quelle couche soupçonner ?"
    **Couche 2** (ARP, switch, câble) ou **couche 3** (IP mal configurée).
    
    Vérifier : `ip neigh` ou `arp -a` pour voir si l'ARP résout la MAC du destinataire. Vérifier le câble, le port du switch, et la config IP des deux machines.

??? question "Tu obtiens `Connection refused` sur un port — couche probable et premier outil ?"
    **Couche 4** (port explicitement fermé) ou **couche 7** (service down). Le paquet TCP a bien atteint la machine, mais elle a renvoyé un RST.
    
    Premier réflexe : `ss -tlnp` côté serveur pour confirmer que le service écoute. Si oui, problème applicatif. Si non, le service n'a pas démarré.

??? question "Tu obtiens `Connection timed out` — couches possibles et outils ?"
    **Couche 3** (route inexistante), **couche 4** (firewall qui drop les paquets sans répondre), ou **couche 7** (service injoignable).
    
    Outils : `tcpdump` pour voir si tes paquets sortent et si quelque chose revient, `nc -zv` pour tester le port, et vérifier les règles de pare-feu côté serveur et intermédiaires.

??? question "Tu as une erreur de certificat TLS — couche et outil ?"
    **Couches 5-6** (TLS).
    
    Outil : `openssl s_client -connect host:443 -servername host` pour voir le cert présenté, sa chaîne, son expiration, et le détail du handshake.

??? question "Tu obtiens HTTP 502 Bad Gateway — couche et où chercher ?"
    **Couche 7**. Le reverse proxy a reçu la requête mais le backend est down, inatteignable, ou répond mal.
    
    Chercher dans les **logs du reverse proxy** (Traefik, nginx) — il indique généralement pourquoi le backend n'a pas répondu (timeout, refus de connexion, mauvais status).

??? question "Une machine ne reçoit pas d'IP au boot — quel protocole, sur quels ports, comment debugger ?"
    **DHCP**, qui tourne sur **UDP ports 67 (serveur) et 68 (client)**.
    
    Debug : `tcpdump -i <iface> port 67 or 68` pour voir si la machine envoie bien des DHCPDISCOVER, et si un serveur répond. Compléter par `journalctl` pour les logs du client DHCP (NetworkManager, systemd-networkd, dhclient).

### Outils

??? question "Quelle commande pour afficher la table de routage IP ?"
    ​```bash
    ip route
    ​```
    
    Variante : `ip -6 route` pour IPv6.

??? question "Quelle commande pour afficher le cache ARP / table des voisins ?"
    ​```bash
    ip neigh
    ​```
    
    Ancienne syntaxe (toujours disponible) : `arp -a`.

??? question "Quelle commande pour lister les ports en écoute avec le processus associé ?"
    ​```bash
    ss -tlnp
    ​```
    
    `-t` TCP, `-l` listening, `-n` numérique (pas de DNS), `-p` processus. Pour UDP : `ss -ulnp`.

??? question "Quelle commande pour tester si un port TCP est ouvert sur une machine distante ?"
    ​```bash
    nc -zv <host> <port>
    ​```
    
    `-z` mode scan (n'envoie pas de données), `-v` verbeux. Alternative : `nmap -p <port> <host>`.

??? question "Quelle commande pour tracer le chemin réseau vers une destination ?"
    ​```bash
    traceroute <host>
    ​```
    
    Variante TCP (utile si ICMP est filtré) : `traceroute -T -p 443 <host>`. Plus récent et précis : `mtr <host>`.

??? question "Quelle commande pour capturer le trafic DHCP ?"
    ​```bash
    tcpdump -i <iface> port 67 or 68
    ​```
    
    Ajouter `-w fichier.pcap` pour enregistrer et analyser ensuite avec Wireshark.

??? question "Quelle commande pour inspecter une négociation TLS depuis le terminal ?"
    ​```bash
    openssl s_client -connect host:443 -servername host
    ​```
    
    Le `-servername` est crucial pour SNI (sans lui, beaucoup de serveurs renvoient le mauvais cert). Ajouter `-showcerts` pour voir toute la chaîne.
