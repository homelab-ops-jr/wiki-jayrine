# Réseau

Tout ce qui concerne le **fonctionnement bas niveau d'un réseau IP** : commutation (switching), VLANs, routage, pare-feu, NAT, DHCP, et la diagnostic au quotidien. Le sujet est volontairement indépendant de la couche virtualisation — un VLAN reste un VLAN, qu'il soit transporté par un câble cuivre ou par un bridge Linux.

## Parcours suggéré

Si tu connais Internet "côté utilisateur" mais que tu n'as jamais conçu un réseau, lis dans l'ordre :

1. [Modèle OSI et TCP/IP](./notions/01-modele-osi-tcpip.md) — pour situer chaque concept dans sa couche
2. [Switching L2 : MAC, ARP](./notions/02-switching-l2-mac-arp.md) — comment les trames circulent dans un segment
3. [VLANs et 802.1Q](./notions/03-vlans-et-802-1q.md) — segmenter un réseau physique en plusieurs réseaux logiques
4. [Routage L3 et inter-VLAN](./notions/04-routage-l3-inter-vlan.md) — passer d'un segment à un autre
5. [DHCP](./notions/05-dhcp.md) — distribution d'adresses
6. [NAT (SNAT, DNAT, port forwarding)](./notions/06-nat-snat-dnat.md) — sortir vers Internet, exposer un service
7. [Pare-feu stateful : règles, ordre, default deny](./notions/07-pare-feu-stateful.md)
8. [Architecture segmentée : DMZ, defense in depth](./notions/08-architecture-segmentee.md)
9. [Outils de diagnostic réseau](./notions/09-outils-diagnostic.md)

## Fiches notions

| Fiche | À comprendre avant de… |
|-------|------------------------|
| [01 — Modèle OSI et TCP/IP](./notions/01-modele-osi-tcpip.md) | Lire de la doc réseau, situer un problème par couche |
| [02 — Switching L2, MAC, ARP](./notions/02-switching-l2-mac-arp.md) | Comprendre ce qu'un switch fait vraiment |
| [03 — VLANs et 802.1Q](./notions/03-vlans-et-802-1q.md) | Configurer un switch manageable, des bridges VLAN-aware |
| [04 — Routage L3 et inter-VLAN](./notions/04-routage-l3-inter-vlan.md) | Configurer un pare-feu/routeur entre VLANs |
| [05 — DHCP](./notions/05-dhcp.md) | Distribuer des IPs sur un nouveau segment |
| [06 — NAT (SNAT, DNAT)](./notions/06-nat-snat-dnat.md) | Donner accès Internet à un VLAN, exposer un service |
| [07 — Pare-feu stateful](./notions/07-pare-feu-stateful.md) | Écrire des règles cohérentes et auditables |
| [08 — Architecture segmentée](./notions/08-architecture-segmentee.md) | Concevoir un plan de VLANs et une matrice de flux |
| [09 — Outils de diagnostic](./notions/09-outils-diagnostic.md) | Valider la connectivité, comprendre une panne |

## À ajouter plus tard

- [ ] DNS récursif vs autoritaire (notion + méthode déploiement)
- [ ] IPv6 — préfixes, NDP, SLAAC vs DHCPv6
- [ ] Spanning Tree (STP, RSTP, MSTP)
- [ ] Link aggregation (LACP, bonding)
- [ ] QoS (CoS, DSCP, files d'attente)
- [ ] Multicast (IGMP, snooping)
- [ ] VPN site-à-site et nomade (IPsec, WireGuard)
- [ ] Configuration concrète d'un switch (par marque)
- [ ] Configuration concrète d'OPNsense / pfSense
