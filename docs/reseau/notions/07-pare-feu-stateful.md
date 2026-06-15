# 07 — Pare-feu stateful : règles, ordre, default deny

> **Type** : Notion · **Sujet** : Réseau · **Prérequis** : [Modèle OSI](./01-modele-osi-tcpip.md), [Routage L3](./04-routage-l3-inter-vlan.md)

## En une phrase

Un **pare-feu** filtre les paquets selon des règles. Un pare-feu **stateful** mémorise les connexions actives et autorise automatiquement le trafic de retour — c'est le standard depuis 20 ans. Comprendre l'**ordre d'évaluation**, le **default deny**, et la **direction des flux** est la clé d'une configuration cohérente.

## Stateless vs stateful

### Stateless (sans état)

Le pare-feu examine **chaque paquet indépendamment**, sans mémoire des précédents. Une règle simple :

```
PERMIT  TCP   SRC any   DST 10.0.0.5:443
```

Autorise un paquet TCP vers le port 443 du serveur. Mais le serveur **répond** depuis `10.0.0.5:443 → client:randomPort`. Pour autoriser la réponse, il faut **une deuxième règle** dans le sens inverse :

```
PERMIT  TCP   SRC 10.0.0.5:443   DST any
```

Lourd, double maintenance, fragile.

### Stateful (à état)

Le pare-feu maintient une **table d'état** (connexion tracker, "conntrack" sur Linux). Quand il voit un paquet **nouveau** matcher une règle PERMIT, il enregistre la session :

```
État conntrack :
[SRC=client:54123 → DST=10.0.0.5:443] [PROTO=TCP] [STATE=ESTABLISHED]
```

Tous les paquets suivants (aller ET retour) appartenant à cette session sont **automatiquement autorisés**, **sans relire la table de règles**. Pas besoin de règle inverse pour le retour.

🔑 **Standard moderne** : tous les pare-feu sérieux (OPNsense, pfSense, iptables/nftables, Cisco ASA, Fortigate, etc.) sont stateful par défaut.

## Les états d'une connexion (conntrack Linux)

Sur Linux/Netfilter, chaque flux est dans un **état** :

| État | Sens |
|------|------|
| **NEW** | Premier paquet d'une nouvelle session |
| **ESTABLISHED** | Session en cours, paquets aller/retour |
| **RELATED** | Connexion liée à une autre (ex. data FTP lié au contrôle FTP) |
| **INVALID** | Paquet incohérent (pas attendu pour aucune session) |

Une règle stateful typique :

```
PERMIT TCP NEW → 10.0.0.5:443
```

Et **automatiquement**, les paquets ESTABLISHED et RELATED de cette session sont autorisés sans règle supplémentaire.

⚠️ Beaucoup d'attaques exploitent les paquets **INVALID** (paquets forgés sans session associée). Une bonne pratique : `DROP INVALID` en premier dans la chaîne.

## Anatomie d'une règle

Une règle de pare-feu typique précise :

| Champ | Exemple | Description |
|-------|---------|-------------|
| **Action** | PERMIT / DROP / REJECT | Quoi faire |
| **Interface** | LAN, WAN, VLAN10 | Où évaluer cette règle (entrée ou sortie) |
| **Direction** | IN / OUT | Entrant ou sortant (selon le firewall) |
| **Protocole** | TCP, UDP, ICMP, any | Protocole de couche 4 |
| **Source** | IP/subnet/alias | Qui émet |
| **Source port** | 22, range, any | Port source (rarement utile, souvent any) |
| **Destination** | IP/subnet/alias | Qui reçoit |
| **Destination port** | 443, range, any | Port destinataire (souvent ce qui compte) |
| **State** | NEW, ESTABLISHED, any | État acceptable |
| **Log** | oui/non | Journaliser le match |
| **Description** | texte libre | Pour ton futur toi |

## DROP vs REJECT vs PERMIT

Trois actions principales :

- **PERMIT (accept)** : le paquet passe.
- **DROP** : le paquet est jeté **silencieusement**. L'expéditeur ne sait pas, il attend, finit par timeout.
- **REJECT** : le paquet est jeté **avec une réponse explicite** (ICMP "destination unreachable" ou TCP RST). L'expéditeur reçoit une erreur immédiate.

Quand utiliser quoi :
- **REJECT** : pour le LAN interne. Plus rapide et plus poli — la machine du dev reçoit "Connection refused" tout de suite, peut diagnostiquer.
- **DROP** : pour la WAN / scans externes. Évite de leaker l'existence du firewall (mais ne le cache pas — le silence sur des ports précis est suspect).
- **PERMIT** : explicite, pour ce qu'on veut.

## L'ordre des règles : critique

Les pare-feu évaluent les règles **du haut vers le bas** et **prennent la première qui matche**. Conséquences :

```
1. PERMIT  TCP  10.0.10.0/24  →  any  port 22       (SSH depuis Mgmt)
2. DROP    TCP  any            →  any  port 22       (bloque tout autre SSH)
3. PERMIT  any  any            →  any                (allow par défaut, MAUVAIS)
```

Évalué pour une requête SSH depuis VLAN 10 :
- Règle 1 matche → PERMIT → arrêt. ✓

Évalué pour une requête SSH depuis VLAN 20 :
- Règle 1 ne matche pas (mauvaise source)
- Règle 2 matche → DROP → arrêt. ✓

Évalué pour une requête HTTP depuis VLAN 20 :
- Règle 1 ne matche pas
- Règle 2 ne matche pas (mauvais port)
- Règle 3 matche → PERMIT. (Discutable, voir plus bas)

🔑 **Plus la règle est spécifique, plus elle doit être en haut.**

## Default deny — la règle d'or

À la fin de toute table de règles, il y a une **règle implicite**. Sa nature dépend du pare-feu :

- **Default deny (recommandé)** : tout ce qui n'a pas été explicitement autorisé est rejeté
- **Default allow** : tout ce qui n'a pas été explicitement bloqué est autorisé

🔒 **Toujours configurer en default deny.** Sur OPNsense/pfSense, c'est le comportement par défaut sur chaque interface.

Conséquence : tu écris des règles **PERMIT** pour ce que tu autorises, et tout le reste tombe. Plus sûr, plus simple à auditer.

🔑 La règle finale visible des tables iptables/nftables est souvent :
```
DROP all  →  all   (or REJECT)
```

C'est le default deny matérialisé.

## Direction du trafic : IN vs OUT

Sur un pare-feu multi-interface (le cas type d'un OPNsense entre VLANs), la **direction** des règles compte. Convention OPNsense/pfSense :

- **Règle sur interface VLAN 20 (direction IN)** = paquet **entrant** sur l'interface VLAN 20, donc **émis depuis VLAN 20**, et destiné ailleurs

Donc la règle "permettre VLAN 20 → VLAN 10" se met sur l'interface VLAN 20, en direction IN.

⚠️ C'est contre-intuitif : on filtre **à l'entrée** du firewall, pas à la sortie. La raison : on connaît tout du paquet à l'entrée (avant routage). À la sortie, on n'a plus d'info sur d'où il vient.

## Pare-feu d'une seule machine vs pare-feu réseau

Deux types très différents :

### Host-based (sur la machine elle-même)
- `iptables`/`nftables` sur Linux, Windows Defender Firewall, etc.
- Protège **une seule machine** des connexions entrantes
- Inspecte les paquets que **la machine va recevoir** (chaîne INPUT) ou **émettre** (OUTPUT)
- Utile en complément, surtout pour les serveurs exposés

### Network firewall (pare-feu d'infrastructure)
- OPNsense, pfSense, Fortigate, Palo Alto, etc.
- Protège **un segment entier** des paquets qui traversent
- Inspecte les paquets en **forwarding** (chaîne FORWARD) entre interfaces
- C'est ce qu'on fait dans un homelab segmenté

Les deux sont compatibles et complémentaires.

## Pare-feu de couche 7 (next-gen, WAF)

Au-delà du pare-feu L3/L4 classique, certains pare-feu inspectent **le contenu applicatif** :

- **WAF** (Web Application Firewall) : analyse les requêtes HTTP, bloque les SQL injections, XSS, etc.
- **DPI** (Deep Packet Inspection) : analyse les payloads pour catégoriser le trafic (Skype, BitTorrent, etc.)
- **IDS/IPS** : détection / prévention d'intrusion (Suricata, Snort)

Sur OPNsense, des plugins fournissent ces capacités (Suricata, Zenarmor). Pas le cœur du sujet en homelab, mais bon à savoir.

## La matrice de flux : l'outil de conception

Avant d'écrire des règles, **dessiner la matrice de flux** qui dit qui peut parler à qui :

```
Source ↓ / Dest →    │ Mgmt │ Dev │ Services │ DMZ │ Internet │
────────────────────┼──────┼─────┼──────────┼─────┼──────────┤
Mgmt                │  —   │  ✅  │   ✅     │ ✅  │   ✅     │
Dev                 │  ❌  │  —  │   ✅     │ ✅  │   ✅     │
Services            │  ❌  │  ❌  │   —      │ ❌  │   ✅     │
DMZ                 │  ❌  │  ❌  │   ❌     │ —   │   ✅     │
```

Principe de design typique : **les VLANs "bas" ne remontent pas vers les VLANs "haut"**. Mgmt peut tout atteindre (pour administrer), DMZ ne peut rien atteindre côté interne (elle est exposée à Internet, donc potentiellement hostile).

➡️ Détails : [Architecture segmentée](./08-architecture-segmentee.md).

## Les "aliases" pour la maintenabilité

Plutôt que d'écrire `10.0.10.5, 10.0.10.6, 10.0.10.7` partout, créer un **alias** :

```
Alias "AdminHosts" = [10.0.10.5, 10.0.10.6, 10.0.10.7]
```

Et l'utiliser dans les règles : `PERMIT TCP AdminHosts → any port 22`.

Avantages :
- Lisibilité des règles
- Modification centralisée (ajouter un admin = modifier 1 alias, pas 20 règles)
- Maintenable à long terme

OPNsense, pfSense, et les pare-feu d'entreprise supportent tous des aliases (parfois sous d'autres noms : "object groups", "address sets").

## Logging : quoi journaliser

Loguer **trop** = bruit, espace disque saturé, perfs.
Loguer **trop peu** = pas de visibilité en cas d'incident.

Pratique raisonnable :
- **Logguer les DROP/REJECT** explicites côté WAN (qui essaie quoi)
- **Logguer les PERMIT** sur les flux sensibles (admin SSH, DMZ → interne)
- **Ne pas logguer** les flux ordinaires hyper-volumineux (LAN → Internet HTTP)
- **Logguer les INVALID** systématiquement (paquets bizarres)

## Pièges fréquents

| Symptôme | Cause |
|----------|-------|
| Trafic bloqué malgré une règle PERMIT | Règle DROP plus haute matche d'abord |
| Réponse pas reçue alors que la requête passe | Pas en stateful, ou règle de retour manquante (rare en 2026) |
| Tout marche mais c'est très lent | `nf_conntrack_max` saturé, paquets jetés |
| Connexions longue durée coupées | Timeout conntrack — réduire le keep-alive applicatif |
| Règle "depuis VLAN 10" ne match jamais | Règle posée sur la mauvaise interface, ou mauvaise direction |
| ICMP bloqué cause un MTU PMTUD KO | Bloquer ICMP type 3 code 4 casse la découverte de MTU. **Toujours autoriser ICMP**. |
| Tout est ouvert sans qu'on comprenne | "Default allow" implicite, ou règle trop large en haut |
| Trafic intercepté par DNAT au mauvais endroit | Règle de port forwarding qui matche plus largement que prévu |

## ICMP : à ne pas bloquer aveuglément

🔒 Tentation classique : "bloquer tout ICMP, c'est plus sûr". **Non**.

Certains messages ICMP sont **essentiels** au fonctionnement IP :
- **Destination unreachable (type 3)** : sans, les connexions à des ports fermés timeoutent au lieu d'échouer vite
- **Fragmentation needed / Packet Too Big (type 3, code 4)** : essentiel pour Path MTU Discovery. Bloquer = TCP qui marche en local mais casse via certains tunnels
- **Time exceeded (type 11)** : utilisé par traceroute, utile pour diagnostiquer

Ce qu'on **peut** filtrer sans risque :
- ICMP echo request / reply (ping) entrant depuis Internet — souvent désactivé
- ICMP redirect (vieux, peut être abusé) — drop OK

Pour le reste : **autoriser ICMP par défaut** ou utiliser les règles spécifiques de ton firewall qui gardent l'essentiel.

## À retenir

- **Stateful = standard moderne** : la table conntrack autorise le retour automatiquement.
- **Default deny** par défaut, on autorise explicitement ce qui doit passer.
- **Ordre des règles compte** : la première qui matche gagne. **Plus spécifique en haut.**
- **DROP** (silencieux) vs **REJECT** (réponse explicite) : REJECT en interne, DROP en externe.
- **Direction IN** des règles = paquets émis depuis l'interface concernée.
- **ICMP : autoriser au minimum types 3 et 11**, sinon casses subtiles.
- **Matrice de flux** + **aliases** = maintenabilité.

## Pour aller plus loin

- [Architecture segmentée](./08-architecture-segmentee.md) — concevoir une matrice de flux
- [NAT (SNAT, DNAT)](./06-nat-snat-dnat.md) — l'ordre NAT-firewall
- [Outils de diagnostic](./09-outils-diagnostic.md) — `tcpdump`, `nft list ruleset`
- Doc OPNsense : [Firewall](https://docs.opnsense.org/manual/firewall.html)
- nftables wiki : [https://wiki.nftables.org/](https://wiki.nftables.org/)
