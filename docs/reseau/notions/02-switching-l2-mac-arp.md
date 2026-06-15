# 02 — Switching L2 : MAC, ARP, broadcast domain

> **Type** : Notion · **Sujet** : Réseau · **Prérequis** : [Modèle OSI](./01-modele-osi-tcpip.md)

## En une phrase

Un **switch** (commutateur) opère en couche 2 : il **apprend les adresses MAC** présentes sur chacun de ses ports et **commute les trames Ethernet** vers la bonne destination. Il ne lit pas les IPs, ne comprend pas les paquets — il fait circuler des trames dans un **broadcast domain**.

## Adresses MAC : ce qu'il faut savoir

Une **adresse MAC** identifie une carte réseau (NIC) au niveau matériel :
- **48 bits**, écrits en hexadécimal sur 6 octets : `aa:bb:cc:dd:ee:ff`
- Censée être **unique au monde** (mais on peut la changer logiciellement)
- Les **3 premiers octets** = **OUI** (Organizationally Unique Identifier), attribué au constructeur
- Les **3 derniers** = numéro séquentiel par le constructeur

Trois MACs spéciales :
- `ff:ff:ff:ff:ff:ff` → **broadcast** (toutes les machines du segment)
- Plage `01:00:5e:xx:xx:xx` → **multicast IPv4**
- MAC qui commence par un **bit 0** sur l'octet 1 = unicast ; **bit 1** = multicast/broadcast

⚠️ Une MAC n'est valable que dans le **segment local**. Elle n'est jamais "routée" — à chaque saut de routeur, la trame Ethernet est entièrement reconstruite avec de nouvelles MACs.

## Le switch : apprentissage et table MAC

À la première trame qu'il voit, un switch ne sait rien. Il **apprend en observant** : pour chaque trame entrante sur un port P, il enregistre `MAC source → port P` dans sa **table MAC** (aussi appelée CAM table).

Exemple : un switch 8 ports, des PCs A et B branchés sur les ports 1 et 3.

```
État initial :    Table MAC vide.

A envoie à B :    Trame [src=MAC-A, dst=MAC-B] sur port 1
  → Switch apprend : MAC-A est sur port 1
  → Mais ne connaît pas MAC-B → flood la trame sur tous les autres ports
                                 (2, 3, 4, 5, 6, 7, 8)

B répond à A :    Trame [src=MAC-B, dst=MAC-A] sur port 3
  → Switch apprend : MAC-B est sur port 3
  → MAC-A connue sur port 1 → forward uniquement sur port 1 (pas de flood)

Conversation établie : flood plus de flood, juste du forwarding ciblé.
```

L'entrée expire au bout d'un délai (typiquement 300s) si plus de trafic — la table reste fraîche.

### Trois comportements de transfert

| Type de trame | Comportement du switch |
|---------------|------------------------|
| **Unicast connu** (MAC dest dans la table) | Forward sur le port appris uniquement |
| **Unicast inconnu** | **Flood** sur tous les ports sauf celui d'entrée |
| **Broadcast** (`ff:ff:ff:ff:ff:ff`) | **Flood** sur tous les ports sauf celui d'entrée |
| **Multicast** | Flood par défaut (avec IGMP snooping : forward ciblé) |

🔑 Conséquence : tant qu'un switch n'a pas appris une MAC, la trame est **floodée** — c'est légèrement bavard mais inévitable au démarrage.

## Broadcast domain et collision domain

Deux concepts à ne pas confondre :

- **Collision domain** : où deux trames peuvent entrer en collision. Un switch **isole chaque port** dans son propre collision domain (contrairement à un hub, antédiluvien). En pratique, en full-duplex moderne, ce concept est devenu historique.

- **Broadcast domain** : où une trame `ff:ff:ff:ff:ff:ff` est délivrée. **Un broadcast domain = un segment réseau = un VLAN**. Un switch standard a un seul broadcast domain. Un switch manageable peut en avoir plusieurs (un par VLAN, cf. [VLANs et 802.1Q](./03-vlans-et-802-1q.md)).

🔑 **Limiter la taille des broadcast domains** est une décision de conception. Trop grand → broadcast storm, perf dégradée, sécurité moins fine.

## ARP : du L3 au L2

ARP (Address Resolution Protocol) répond à la question : **"Quelle est la MAC de la machine ayant cette IP ?"**

Sans ARP, impossible d'envoyer une trame — la couche 2 ne comprend que les MACs.

### Échange ARP (request/reply)

```
A (192.168.1.10, MAC-A) veut joindre B (192.168.1.20, MAC inconnue)

1. A → Broadcast :   "ARP Who-has 192.168.1.20 ? Tell 192.168.1.10"
                     Trame: src=MAC-A, dst=ff:ff:ff:ff:ff:ff
   → Reçu par TOUTES les machines du segment

2. B → A :           "ARP 192.168.1.20 is-at MAC-B"
                     Trame: src=MAC-B, dst=MAC-A (unicast)

3. A met à jour son cache ARP :
   192.168.1.20  →  MAC-B  (durée typique : 60-300s)

4. A peut maintenant envoyer la trame Ethernet vers MAC-B
```

Le **cache ARP** (visible avec `ip neigh` ou `arp -a`) évite de refaire la résolution à chaque paquet. Il expire après quelques minutes.

### ARP et le routeur

Pour joindre une IP **hors du segment local** (ex. Internet), la machine fait un ARP non pas pour l'IP destinataire, mais pour **la passerelle par défaut** (default gateway). Le routeur reçoit la trame, retire l'en-tête Ethernet, examine l'IP destinataire, et transmet via une nouvelle trame vers le saut suivant.

➡️ Détaillé dans [Routage L3](./04-routage-l3-inter-vlan.md).

## Variantes ARP à connaître

### Gratuitous ARP

Une machine annonce sa propre association IP/MAC sans qu'on lui ait demandé. Utilisé :
- Au boot (pour annoncer son arrivée)
- Lors d'un failover (la nouvelle machine prend l'IP)
- Pour détecter les conflits d'IP

### Proxy ARP

Un routeur répond aux ARP pour des IPs qui ne sont pas dans son segment, comme s'il était la machine cible. Vieux mécanisme, rarement utilisé volontairement aujourd'hui — peut causer des bizarreries.

### ARP spoofing (attaque)

Un attaquant envoie de faux ARP reply : "192.168.1.1 is-at MAC-attaquant". Les machines mettent à jour leur cache et envoient leur trafic vers l'attaquant qui peut le rediriger (MITM).

🔒 Protections :
- **Dynamic ARP Inspection** (DAI) sur les switches manageables
- 802.1X pour authentifier les machines sur les ports
- Surveillance des changements ARP (`arpwatch`, IDS)

## Le piège du "VLAN natif" sur les trunks

Sur un port **trunk** entre deux switches (cf. [VLANs](./03-vlans-et-802-1q.md)), les trames sont taggées 802.1Q **sauf** celles du **VLAN natif**, qui passent sans tag. Si un attaquant injecte des trames non-taggées sur un port access, il peut **tomber** dans le VLAN natif côté trunk → **VLAN hopping**.

🔒 Best practice : ne pas utiliser le VLAN 1 comme VLAN natif, et idéalement ne pas avoir de VLAN natif (forcer le tag de tous les VLANs sur le trunk).

## STP en deux phrases

Si tu boucles deux switches entre eux, les broadcasts circulent à l'infini → **broadcast storm**, réseau effondré. Le **Spanning Tree Protocol (STP)** détecte les boucles et bloque un lien pour éviter ça (au prix de perdre la redondance, sauf avec RSTP/MSTP).

En homelab simple sans redondance switch-à-switch, STP est rarement un sujet. Mais bon à savoir : si tu vois un port "bloqué" sur un switch manageable, c'est probablement STP.

## Tables MAC : taille et limites

Un switch a une mémoire CAM finie pour sa table MAC. Capacité typique :
- Switch home : 1k-8k entrées
- Switch entreprise : 32k-256k+

**CAM overflow attack** : un attaquant injecte des milliers de fausses MACs → la table déborde → le switch passe en "fail-open" et flood tout → l'attaquant capte tout le trafic.

🔒 Protection : **port security** sur les switches manageables (limiter le nombre de MACs par port, ou pinner une MAC spécifique).

## Liens MAC ↔ Wi-Fi

Les bornes Wi-Fi sont des **bridges L2** : elles font le pont entre le médium radio et le segment Ethernet filaire. Les clients Wi-Fi ont des MAC visibles dans la table MAC du switch.

Note : Wi-Fi moderne implémente **MAC randomization** côté client par défaut sur smartphone — la MAC change par SSID pour la vie privée. Casse les filtres par MAC.

## À retenir

- Un switch **apprend les MACs** par port en observant les trames source.
- **Unicast inconnu = flood** sur tous les ports. Évite avec le temps.
- **MAC ≠ IP** : une MAC ne traverse pas un routeur ; chaque saut reconstruit la trame.
- **ARP** résout IP → MAC. Cache local typique ~5 min.
- **Broadcast domain = VLAN** sur un switch manageable.
- ARP spoofing et CAM overflow sont les attaques classiques L2.
- Sur un trunk, **éviter le VLAN natif** ou ne pas utiliser le VLAN 1.

## Pour aller plus loin

- [VLANs et 802.1Q](./03-vlans-et-802-1q.md) — la suite logique
- [Routage L3 et inter-VLAN](./04-routage-l3-inter-vlan.md) — pour sortir du broadcast domain
- [Outils de diagnostic](./09-outils-diagnostic.md) — `ip neigh`, `arp`, `tcpdump`
- RFC 826 (ARP)
- IEEE 802.1D (bridging / STP)
