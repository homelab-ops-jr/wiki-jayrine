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
