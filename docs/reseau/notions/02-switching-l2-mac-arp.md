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

## Cartes d'entraînement

### Faits & terminologie

??? question "Comment s'écrit une adresse MAC ?"
    En hexadécimal sur 6 octets séparés par des deux-points : `aa:bb:cc:dd:ee:ff`.

??? question "Que veut dire l'acronyme OUI dans le contexte d'une adresse MAC ?"
    **Organizationally Unique Identifier** — identifiant attribué au constructeur de la carte réseau.

??? question "Que représentent les 3 premiers octets d'une adresse MAC ?"
    L'**OUI** (Organizationally Unique Identifier), attribué au constructeur de la carte réseau.

??? question "Que représentent les 3 derniers octets d'une adresse MAC ?"
    Un numéro séquentiel attribué par le constructeur.

??? question "Quelle est l'adresse MAC de broadcast ?"
    `ff:ff:ff:ff:ff:ff`.

??? question "Quelle plage d'adresses MAC identifie le multicast IPv4 ?"
    `01:00:5e:xx:xx:xx`.

??? question "Comment distinguer une MAC unicast d'une MAC multicast/broadcast au niveau du premier octet ?"
    Le **bit de poids faible** du premier octet : **0** = unicast, **1** = multicast/broadcast.

??? question "Comment s'appelle la table où un switch stocke l'association MAC → port ?"
    La **table MAC**, aussi appelée **CAM table** (Content-Addressable Memory).

??? question "Délai typique d'expiration d'une entrée dans la table MAC d'un switch ?"
    Environ **300 secondes** (5 minutes) sans trafic.

??? question "Durée typique d'une entrée du cache ARP ?"
    Entre **60 et 300 secondes** (1 à 5 minutes).

??? question "À quelle question répond le protocole ARP ?"
    « Quelle est la MAC de la machine ayant cette IP ? » — résolution **IP → MAC** sur le segment local.

??? question "Capacité typique de la table MAC d'un switch home vs un switch entreprise ?"
    Switch home : **1k à 8k** entrées. Switch entreprise : **32k à 256k+**.

### Concepts

??? question "Comment un switch apprend-il quelle MAC est derrière quel port ?"
    Il observe la **MAC source** de chaque trame entrante sur un port P, et enregistre l'association `MAC → port P` dans sa table MAC.
    
    L'apprentissage est **passif et continu** — le switch n'envoie jamais de requête pour découvrir. Si une MAC se déplace (machine débranchée puis rebranchée ailleurs), la nouvelle entrée écrase l'ancienne au prochain trafic.

??? question "Que fait un switch d'une trame unicast dont la MAC destination est inconnue de sa table ?"
    Il la **flood** sur tous les ports sauf celui d'entrée. C'est le comportement par défaut tant qu'il n'a pas appris où se trouve la destination.
    
    Conséquence : au démarrage d'un switch, le réseau est légèrement bavard. Ça se stabilise dès que les conversations s'établissent et que les MACs sont apprises dans les deux sens.

??? question "Résume les trois comportements de transfert d'un switch selon le type de trame."
    - **Unicast connu** (MAC dest dans la table) : forward sur le port appris uniquement.
    - **Unicast inconnu** : flood sur tous les ports sauf celui d'entrée.
    - **Broadcast** (`ff:ff:ff:ff:ff:ff`) : flood sur tous les ports sauf celui d'entrée.
    
    Le multicast est floodé par défaut, sauf si l'**IGMP snooping** est activé (forward ciblé uniquement vers les ports qui ont rejoint le groupe).

??? question "Décris le scénario complet d'apprentissage d'un switch quand deux machines A et B (branchées sur ports 1 et 3) échangent leurs premières trames."
    **État initial** : table MAC vide.
    
    **A envoie à B** (trame `src=MAC-A, dst=MAC-B` sur port 1) :
    
    - Le switch apprend `MAC-A → port 1`.
    - Il ne connaît pas `MAC-B` → il **flood** la trame sur tous les autres ports.
    
    **B répond à A** (trame `src=MAC-B, dst=MAC-A` sur port 3) :
    
    - Le switch apprend `MAC-B → port 3`.
    - `MAC-A` est connue sur port 1 → forward uniquement sur port 1, **pas de flood**.
    
    À partir de là, la conversation entre A et B est entièrement ciblée — plus aucun flood tant que les entrées n'expirent pas.

??? question "Quelle est la différence entre collision domain et broadcast domain ?"
    Un **collision domain** est la zone où deux trames peuvent entrer en collision. Un switch isole chaque port dans son propre collision domain (contrairement à un vieux hub). En full-duplex moderne, ce concept est devenu historique.
    
    Un **broadcast domain** est la zone où une trame `ff:ff:ff:ff:ff:ff` est délivrée. Un switch standard a un seul broadcast domain ; un switch manageable peut en avoir plusieurs, un par VLAN.

??? question "Pourquoi dit-on qu'un broadcast domain équivaut à un VLAN sur un switch manageable ?"
    Un VLAN crée une **séparation logique** des trames Ethernet au sein du switch : les trames d'un VLAN ne sont jamais commutées vers les ports d'un autre VLAN, **broadcast inclus**.
    
    Chaque VLAN constitue donc son propre broadcast domain isolé. Limiter la taille d'un broadcast domain (en le segmentant en plusieurs VLANs) réduit les broadcast storms et améliore la sécurité.

??? question "Décris l'échange ARP request/reply quand A (192.168.1.10) veut joindre B (192.168.1.20)."
    **1.** A envoie un **ARP request en broadcast** : « Who-has 192.168.1.20 ? Tell 192.168.1.10 ». Trame `src=MAC-A, dst=ff:ff:ff:ff:ff:ff`, reçue par toutes les machines du segment.
    
    **2.** B répond en **unicast** à A : « 192.168.1.20 is-at MAC-B ». Trame `src=MAC-B, dst=MAC-A`.
    
    **3.** A met à jour son **cache ARP** : `192.168.1.20 → MAC-B`, valable quelques minutes.
    
    **4.** A peut maintenant envoyer ses trames Ethernet directement vers `MAC-B`.

??? question "Quand une machine veut joindre une IP hors de son segment local, pour quelle IP fait-elle un ARP ?"
    Pour la **passerelle par défaut** (default gateway), pas pour l'IP destinataire finale.
    
    La couche 2 n'a pas de portée au-delà du segment local. La machine envoie donc la trame à la MAC du routeur, qui se chargera de retirer l'en-tête Ethernet, d'examiner l'IP destinataire, et de la transmettre vers le saut suivant via une nouvelle trame.

??? question "Qu'est-ce qu'un gratuitous ARP et dans quels cas est-il utilisé ?"
    Un **gratuitous ARP** est une annonce ARP émise par une machine sans qu'on lui ait demandé : elle déclare sa propre association IP/MAC à tout le segment.
    
    Cas d'usage :
    
    - **Au boot**, pour annoncer son arrivée et peupler les caches voisins.
    - Lors d'un **failover**, quand une machine prend l'IP d'une autre (HA, VRRP).
    - Pour **détecter les conflits d'IP** sur le réseau.

??? question "Qu'est-ce que le proxy ARP ?"
    Un routeur répond aux requêtes ARP pour des IPs qui ne sont **pas dans son segment**, comme s'il était la machine cible. Les hôtes envoient donc leur trafic au routeur, qui le relaie.
    
    Vieux mécanisme, rarement utilisé volontairement aujourd'hui — peut causer des comportements bizarres si activé par inadvertance.

??? question "Explique comment fonctionne une attaque ARP spoofing."
    Un attaquant envoie des **ARP reply falsifiés** sur le segment, par exemple : « 192.168.1.1 (la gateway) is-at MAC-attaquant ».
    
    Les machines mettent à jour leur cache ARP et envoient désormais tout leur trafic destiné à la gateway vers la MAC de l'attaquant. Celui-ci peut alors **intercepter, lire, modifier** le trafic avant de le relayer (**MITM**, man-in-the-middle).
    
    ARP n'a aucun mécanisme d'authentification — n'importe quelle machine peut prétendre être n'importe quelle IP.

??? question "Quelles protections existent contre l'ARP spoofing ?"
    - **Dynamic ARP Inspection** (DAI) sur les switches manageables : le switch vérifie les ARP reply contre une table de bail DHCP et droppe les incohérents.
    - **802.1X** pour authentifier les machines sur les ports avant tout trafic.
    - Surveillance des changements ARP avec des outils comme `arpwatch` ou un **IDS** — pour détecter a posteriori.

??? question "Qu'est-ce qu'une attaque CAM overflow et pourquoi est-elle dangereuse ?"
    La table MAC (CAM) d'un switch a une capacité finie. Un attaquant injecte **des milliers de fausses MACs** sur un port, jusqu'à saturer la table.
    
    Une fois la table pleine, beaucoup de switches passent en **fail-open** : ils flood toutes les trames inconnues sur tous les ports, comme un vieux hub. L'attaquant capte alors **tout le trafic** du segment, ce qui transforme l'attaque en interception massive.

??? question "Quelle protection contre le CAM overflow sur un switch manageable ?"
    La **port security** : limiter le nombre de MACs apprises par port (par exemple 1 ou 2), ou **pinner** une MAC spécifique à un port.
    
    Quand la limite est dépassée, le port peut être configuré pour droppe les trames, alerter, ou se désactiver complètement.

??? question "Qu'est-ce que le VLAN hopping via le VLAN natif sur un trunk ?"
    Sur un trunk 802.1Q, les trames du **VLAN natif** passent **sans tag**. Si un attaquant injecte des trames non-taggées (ou en double-tagging) qui atteignent un trunk, elles seront interprétées comme appartenant au VLAN natif côté trunk.
    
    L'attaquant peut alors **sortir de son VLAN d'origine** et tomber dans le VLAN natif côté trunk, court-circuitant l'isolation logique entre VLANs.

??? question "Quelles best practices concernant le VLAN natif sur un trunk ?"
    - **Ne pas utiliser le VLAN 1** comme VLAN natif (c'est le défaut sur la plupart des switches, donc une cible évidente).
    - Idéalement, **ne pas avoir de VLAN natif** du tout : forcer le tag 802.1Q sur **tous** les VLANs traversant le trunk.

??? question "Pourquoi le STP existe-t-il, en deux phrases ?"
    Si tu boucles deux switches entre eux, les trames de broadcast circulent indéfiniment dans la boucle → **broadcast storm**, réseau effondré.
    
    Le **Spanning Tree Protocol** détecte les boucles et **bloque un lien** pour les casser, au prix de la redondance (sauf avec **RSTP/MSTP** qui réagissent plus vite).

??? question "Comment une borne Wi-Fi s'intègre-t-elle dans un réseau L2 ?"
    Une borne Wi-Fi est un **bridge L2** : elle fait le pont entre le médium radio et le segment Ethernet filaire.
    
    Les clients Wi-Fi apparaissent comme des MACs ordinaires dans la table MAC du switch en amont — la borne relaie les trames dans les deux sens, de manière transparente.

??? question "Pourquoi le filtrage par adresse MAC est-il devenu peu fiable sur smartphones modernes ?"
    Les smartphones (iOS, Android récents) implémentent la **MAC randomization** par défaut : ils utilisent une MAC différente par SSID, et la régénèrent périodiquement.
    
    Conséquence : un filtre par MAC sur le Wi-Fi devient inopérant — la MAC du téléphone ne correspondra à aucune entrée la prochaine fois qu'il se reconnecte. La MAC randomization est conçue pour la vie privée (anti-tracking), pas pour la sécurité du LAN.

### Diagnostic

??? question "Tu vois un port marqué 'bloqué' sur un switch manageable — cause probable ?"
    Très probablement **STP** (Spanning Tree Protocol). Le switch a détecté une boucle physique et a désactivé un des liens redondants pour la casser.
    
    C'est normal en présence de redondance switch-à-switch. Vérifier la topologie pour confirmer qu'une boucle existe bien, puis valider que c'est le lien attendu qui est bloqué (priorités STP).

??? question "Un switch flood en permanence vers tous les ports, même pour du trafic unicast — qu'est-ce qui peut causer ça ?"
    Deux causes principales :
    
    - **Table MAC pleine ou saturée** (CAM overflow) — soit attaque active, soit topologie qui dépasse la capacité du switch. Le switch passe en fail-open et flood tout.
    - **Apprentissage cassé** : si les hôtes ne parlent que dans un sens (ex. flux UDP unidirectionnel), le switch n'apprend jamais la MAC du destinataire et flood en permanence vers elle.
    
    Vérifier la table MAC (`show mac address-table` sur la CLI du switch) et sa taille vs capacité.

??? question "Tu vois plusieurs MACs apprises sur un même port de switch — qu'est-ce que ça implique ?"
    Le port n'est pas connecté à une seule machine end-host, mais à un **équipement qui bridge plusieurs MACs** en aval :
    
    - Un autre **switch** branché en cascade.
    - Une **borne Wi-Fi** (chaque client Wi-Fi remonte sa propre MAC).
    - Un **hyperviseur** avec bridge réseau (chaque VM a sa MAC).
    
    Ce n'est pas anormal en soi, mais si tu attendais une seule MAC, c'est le signe d'un équipement intermédiaire que tu n'avais pas en tête.

??? question "Tu soupçonnes un ARP spoofing sur le LAN — comment l'identifier ?"
    Surveiller les **changements anormaux d'association IP/MAC** :
    
    - `arpwatch` envoie une alerte quand une IP change de MAC.
    - Un **IDS** (Suricata, Snort) peut détecter les patterns ARP suspects (flood de reply non sollicités).
    - Manuellement : `ip neigh` sur plusieurs machines, comparer la MAC vue pour la gateway. Si elles divergent, ou si elle change soudainement, c'est suspect.

??? question "Tu mets un filtre par MAC sur ton Wi-Fi mais des smartphones échappent au filtrage — pourquoi ?"
    **MAC randomization** côté client. Les smartphones modernes génèrent une MAC aléatoire par SSID, et la régénèrent périodiquement.
    
    Le filtre par MAC est de toute façon une **fausse sécurité** — un attaquant peut sniffer une MAC autorisée et la spoofer trivialement. Pour authentifier des appareils Wi-Fi, utiliser **WPA2/WPA3 Enterprise** (802.1X) ou des certificats.

??? question "Tu veux détecter automatiquement les conflits d'IP sur le réseau — quel mécanisme ARP est utilisé ?"
    Le **gratuitous ARP**.
    
    Au boot, la machine annonce sa propre association IP/MAC. Si une autre machine du segment a déjà cette IP, elle voit l'annonce et peut signaler le conflit (log, alerte, abandon de l'IP). Beaucoup d'OS le font automatiquement.
