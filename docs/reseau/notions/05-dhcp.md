# 05 — DHCP

> **Type** : Notion · **Sujet** : Réseau · **Prérequis** : [Switching L2](./02-switching-l2-mac-arp.md), [Routage L3](./04-routage-l3-inter-vlan.md)

## En une phrase

**DHCP** (Dynamic Host Configuration Protocol) automatise l'attribution d'IPs et de paramètres réseau (gateway, DNS, etc.) aux machines d'un segment. Comprendre son échange en 4 étapes (**DORA**) est essentiel pour diagnostiquer "ma VM n'a pas d'IP".

## L'échange DORA

DHCP fonctionne en **4 messages**, surnommés DORA :

```
┌──────────┐                                          ┌──────────────┐
│  Client  │                                          │ Serveur DHCP │
│ (no IP)  │                                          │              │
└────┬─────┘                                          └──────┬───────┘
     │                                                       │
     │  1. DISCOVER                                          │
     │  Broadcast L2 : ff:ff:ff:ff:ff:ff                     │
     │  Broadcast L3 : 255.255.255.255                       │
     │  Source IP : 0.0.0.0                                  │
     │  "Y'a quelqu'un qui peut me donner une IP ?"          │
     │ ────────────────────────────────────────────────────► │
     │                                                       │
     │                                  2. OFFER             │
     │       (broadcast ou unicast selon l'implémentation)   │
     │                                                       │
     │       "Je te propose 10.0.20.50/24, gw 10.0.20.1,     │
     │        DNS 10.0.20.1, bail 24h"                       │
     │ ◄──────────────────────────────────────────────────── │
     │                                                       │
     │  3. REQUEST                                           │
     │  "OK je veux bien 10.0.20.50, c'est toi qui me        │
     │   l'attribues"                                        │
     │  (broadcast — au cas où plusieurs serveurs DHCP)      │
     │ ────────────────────────────────────────────────────► │
     │                                                       │
     │                                  4. ACK               │
     │       "OK, c'est à toi. Voici tes options finales."   │
     │ ◄──────────────────────────────────────────────────── │
     │                                                       │
     │  Client configure son interface, le bail démarre      │
     └───────────────────────────────────────────────────────┘
```

## Pourquoi broadcast pour le DISCOVER ?

Le client **n'a pas d'IP** au démarrage et ne sait pas où est le serveur DHCP. Il envoie en **broadcast L2 (`ff:ff:ff:ff:ff:ff`) ET broadcast L3 (`255.255.255.255`)**. Tous les hôtes du segment reçoivent — seul le serveur DHCP répond.

🔑 Conséquence : **DHCP est confiné au broadcast domain** (donc au VLAN). Un serveur DHCP placé dans VLAN 10 ne répond pas aux clients de VLAN 20 — sauf via **DHCP relay** (voir plus bas).

## Les options DHCP

L'OFFER et l'ACK transportent des **options** : ce sont les paramètres réseau communiqués au client. Les plus courantes :

| Code | Nom | Contenu typique |
|------|-----|-----------------|
| 1 | Subnet mask | `255.255.255.0` |
| 3 | Router (gateway) | `10.0.20.1` |
| 6 | DNS server | `10.0.20.1` ou `1.1.1.1, 8.8.8.8` |
| 15 | Domain name | `lab.local` |
| 28 | Broadcast address | `10.0.20.255` |
| 42 | NTP server | `10.0.10.1` |
| 51 | Lease time | `86400` (s = 24h) |
| 66 | TFTP server name | (PXE boot) |
| 67 | Bootfile name | `pxelinux.0` (PXE boot) |
| 119 | Domain search list | `lab.local intra.example.com` |
| 121 | Classless static routes | routes statiques additionnelles |

Le **client demande** les options qu'il veut. Le serveur **fournit** ce qu'il connaît.

⚠️ Toutes les implémentations DHCP ne supportent pas toutes les options. Vérifier la doc du serveur (OPNsense, ISC dhcpd, dnsmasq).

## Bail (lease) et renouvellement

L'IP n'est pas attribuée pour toujours — elle a une **durée de validité (lease time)**.

```
┌───────────────────────────────────────────────────────────┐
│  Bail = 24h                                               │
│                                                           │
│  T=0       T=12h (50%)        T=21h (87.5%)      T=24h    │
│  ↓         ↓                  ↓                  ↓        │
│  ACK    RENEW unicast      REBIND broadcast    Expire     │
│         vers le serveur    vers tout serveur              │
└───────────────────────────────────────────────────────────┘
```

- À **50%** du bail (T1), le client tente un **RENEW** unicast vers le serveur qui l'a servi
- Si pas de réponse, à **87.5%** (T2), il bascule en **REBIND** broadcast (n'importe quel serveur)
- Si expiration sans renouvellement, le client perd son IP et refait un DISCOVER

🔑 Implications pratiques :
- Bail court (1h) → renouvelle souvent, table à jour, plus lourd
- Bail long (24h-1 semaine) → moins de trafic, mais l'IP "colle" même quand la machine n'est plus là

## Statique vs dynamique vs réservation

Trois façons d'attribuer une IP dans un sous-réseau :

| Méthode | Description |
|---------|-------------|
| **Statique** | Configurée à la main sur la machine, pas via DHCP. Cas serveurs, routeurs. |
| **Dynamique** | Le serveur DHCP attribue parmi un pool. La même MAC peut avoir une IP différente à chaque bail. |
| **Réservation DHCP** | Le serveur DHCP attribue **toujours la même IP** à une MAC donnée. La machine "voit" du DHCP, mais reçoit "son" IP. |

🔑 **Best practice** : pour les serveurs/services, **réservation DHCP** plutôt que statique. Avantage : la conf réseau (gateway, DNS) reste centralisée côté serveur DHCP — si tu changes la gateway, tu modifies un seul endroit, pas chaque machine.

## DHCP relay (relai DHCP)

Comment un VLAN sans serveur DHCP local peut quand même recevoir des IPs ?

Réponse : **DHCP relay**. Une fonction du routeur/pare-feu (ou d'un agent dédié) qui :

1. Reçoit le DISCOVER broadcast sur son interface VLAN
2. **Transforme en unicast** vers le serveur DHCP situé ailleurs
3. Ajoute l'option **82** (subnet de provenance) pour que le serveur DHCP sache de quel VLAN ça vient
4. Relaie la réponse du serveur vers le client

```
   Client    Routeur (DHCP relay)              Serveur DHCP
   VLAN 30   intf VLAN 30 : 10.0.30.1          dans VLAN 10
             intf VLAN 10 : 10.0.10.1          IP 10.0.10.5

   DISCOVER broadcast → reçu → unicast vers 10.0.10.5 (avec option 82)
                                                ↓
   ACK ← relay ← réponse adressée à 10.0.30.1 ←┘
```

Utile en entreprise (un DHCP central pour N VLANs). En homelab, on met souvent **un serveur DHCP par VLAN, embarqué sur le pare-feu** (OPNsense).

## Conflits et anomalies

### Doublon de serveurs DHCP

Si deux serveurs DHCP répondent dans le même segment, c'est le **premier arrivé** qui gagne (le client utilise la première OFFER reçue). Les machines voient une distribution aléatoire d'IPs depuis l'un ou l'autre — chaos garanti.

🔒 **DHCP snooping** sur les switches manageables : empêche un port "non trusté" d'émettre des OFFER. Protection contre les serveurs DHCP rogues.

### Adresse APIPA / link-local

Quand un client ne reçoit **aucune** réponse DHCP, certains OS s'auto-attribuent une IP dans le range **`169.254.0.0/16`** (IPv4 link-local) ou **`fe80::/10`** (IPv6).

Symptôme classique : tu vois une IP `169.254.x.x` sur une machine → **le DHCP a échoué**. La machine est isolée (cette plage n'est routable que sur le segment local).

### Pool épuisé

Si toutes les IPs du pool sont attribuées, le DISCOVER échoue. Solutions :
- Réduire le lease time pour récupérer les anciens
- Élargir le pool
- Vérifier qu'il n'y a pas de fuite (machines qui se reconnectent avec des MACs aléatoires — voir Wi-Fi)

## DHCP et MAC randomization (Wi-Fi moderne)

Sur smartphone (iOS, Android, Windows 11), la MAC du Wi-Fi est **randomisée par SSID** par défaut, pour la vie privée. Conséquences :

- À chaque connexion, **nouvelle IP** depuis le pool (la réservation ne marche plus)
- Sur le long terme, le pool peut s'épuiser
- Les filtres MAC du captive portal/firewall ne sont plus stables

Solutions : désactiver la randomization pour les SSID où on a besoin (côté client), ou faire avec et provisionner large.

## DHCPv6 vs SLAAC (IPv6)

Pour IPv6, deux mécanismes coexistent :

- **SLAAC** (StateLess Address AutoConfiguration) : la machine forge son IP à partir du **préfixe annoncé par le routeur** + son MAC ou un identifiant aléatoire. Sans serveur DHCP. C'est l'approche IPv6 native.
- **DHCPv6** : équivalent IPv6 du DHCP. Souvent utilisé pour les options (DNS, etc.) en complément de SLAAC.

En homelab, beaucoup utilisent **uniquement IPv4 + DHCP**, c'est plus simple à appréhender. IPv6 vient ensuite.

## DHCP sur OPNsense / pfSense (vue d'ensemble)

Sur un pare-feu de type OPNsense, pour chaque interface (donc VLAN) on peut :
- Activer un **DHCP server** intégré
- Définir le **pool** (range d'IPs à distribuer)
- Définir les **options** (gateway, DNS, NTP, etc.)
- Ajouter des **réservations** par MAC
- Configurer les **leases time**

Configuration distincte par interface : DHCP du VLAN 10 = serveur dans 10.0.10.0/24, DHCP du VLAN 20 = serveur dans 10.0.20.0/24, etc. Chaque pare-feu écoute sur ses propres interfaces VLAN.

## Diagnostic DHCP

```bash
# Côté client Linux (observer le dialogue)
sudo tcpdump -i eth0 -n port 67 or port 68

# Forcer un renouvellement (dhclient)
sudo dhclient -r eth0    # release
sudo dhclient eth0       # renew

# Avec systemd-networkd
sudo systemctl restart systemd-networkd

# Avec NetworkManager
nmcli connection up <connection>

# Voir le bail actuel
cat /var/lib/dhcp/dhclient.leases             # ISC dhcp
cat /var/lib/NetworkManager/internal-*.lease  # NetworkManager
```

Ports DHCP : **67 (serveur)** et **68 (client)**, en UDP.

## À retenir

- **DORA** : Discover, Offer, Request, Ack — l'échange DHCP.
- **Broadcast L2 + L3** côté client → confiné au broadcast domain (VLAN).
- **Options** transportent gateway, DNS, NTP, et bien d'autres paramètres.
- **Lease** = durée du bail, avec renouvellement à 50% (T1) puis rebind à 87.5% (T2).
- **Réservation DHCP** > IP statique pour les serveurs (config centralisée).
- **DHCP relay** pour qu'un serveur DHCP serve plusieurs VLANs.
- IP `169.254.x.x` (APIPA) = DHCP a échoué.
- Ports **UDP 67/68**.

## Pour aller plus loin

- [Routage L3 et inter-VLAN](./04-routage-l3-inter-vlan.md) — comment la gateway distribuée par DHCP est utilisée
- [Outils de diagnostic](./09-outils-diagnostic.md) — `tcpdump`, `dhclient`
- [Architecture segmentée](./08-architecture-segmentee.md) — placer les DHCP par VLAN
- RFC 2131 (DHCPv4)
- RFC 8415 (DHCPv6)
