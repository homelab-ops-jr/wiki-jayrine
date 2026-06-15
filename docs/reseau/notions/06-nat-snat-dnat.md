# 06 — NAT (SNAT, DNAT, port forwarding)

> **Type** : Notion · **Sujet** : Réseau · **Prérequis** : [Routage L3](./04-routage-l3-inter-vlan.md), [Modèle OSI](./01-modele-osi-tcpip.md)

## En une phrase

Le **NAT** (Network Address Translation) **réécrit les adresses IP et/ou ports** d'un paquet en transit, soit pour partager une IP publique entre plusieurs machines internes (**SNAT** côté sortie), soit pour exposer un service interne via l'IP publique (**DNAT**, alias **port forwarding**, côté entrée).

## Le problème historique : pénurie d'IPv4

L'IPv4 offre ~4 milliards d'adresses (2^32). Avec l'explosion d'Internet, c'est insuffisant. **Le NAT** a permis de prolonger la vie d'IPv4 : un foyer/entreprise utilise **une seule IP publique** côté FAI, et **des milliers d'IPs privées** côté LAN.

Les plages privées RFC 1918 :
- `10.0.0.0/8`
- `172.16.0.0/12`
- `192.168.0.0/16`

Et le link-local : `169.254.0.0/16` (n'est pas du tout routé).

🔑 Toute IP **privée** doit être NATée pour communiquer avec Internet.

## SNAT — Source NAT (le NAT "sortant")

Quand une machine du LAN initie une connexion vers Internet, le routeur **réécrit l'IP source** (et souvent le port source) pour la remplacer par son IP publique.

```
Sans NAT :
  Client (10.0.20.50) ──► Routeur ──► Serveur Internet (1.2.3.4)
                                       Le serveur voit 10.0.20.50 → ne sait pas y répondre
                                       (10.0.20.50 n'est pas routable sur Internet)

Avec SNAT :
  Client (10.0.20.50:54000) ──► Routeur ──► Serveur Internet (1.2.3.4:443)
                                            La source devient 203.0.113.5:54000
                                            Le serveur répond à 203.0.113.5:54000
                                            Le routeur "se souvient" de la traduction
                                            et réécrit l'IP dest en 10.0.20.50:54000 au retour
```

Le routeur maintient une **table d'état NAT** :

```
Tuple original                  Tuple traduit
(10.0.20.50:54000 → 1.2.3.4:443)    (203.0.113.5:54000 → 1.2.3.4:443)
```

Au paquet retour, il fait le mapping inverse.

### NAT vs PAT — vocabulaire

- **NAT pur** : 1 IP interne ↔ 1 IP externe (rare, gaspille des IPs publiques)
- **PAT** (Port Address Translation) ou **NAPT** ou **Masquerading** : plusieurs IPs internes → **1 IP externe**, le port permet de désambiguïser. **C'est ce qui se passe en réalité 99% du temps.**

En pratique, quand on dit "NAT", on veut presque toujours dire **PAT/masquerading**.

## DNAT — Destination NAT (le NAT "entrant", aka port forwarding)

Quand quelqu'un sur Internet veut joindre un service hébergé en interne, le routeur **réécrit l'IP destinataire** pour la transformer en IP privée du service.

```
Visiteur Internet ──► Routeur (203.0.113.5:443) ──► Service interne (10.0.40.50:443)
                       │
                       │  Le routeur reçoit la connexion sur :443
                       │  Sa règle de port forwarding dit :
                       │    "203.0.113.5:443 → 10.0.40.50:443"
                       │  Il réécrit l'IP dest et transmet
                       ▼
                  Service répond depuis 10.0.40.50:443
                  Au retour, le routeur réécrit la source en 203.0.113.5:443
                  pour que le visiteur reconnaisse "sa" connexion
```

🔑 **DNAT = port forwarding = expose un service interne sur l'IP publique** sur un port précis.

## Cas combiné : SNAT + DNAT pour le même flux

Dans une configuration multi-WAN ou hairpin, un paquet peut subir **les deux** :
1. À l'entrée : DNAT (IP dest réécrite)
2. À la sortie vers le backend : SNAT (IP source réécrite vers l'IP du firewall, pour que la réponse repasse par le firewall)

Cas typique : un client interne accède au service exposé via son nom DNS public → le DNS pointe vers l'IP publique → la requête sort puis revient sur le firewall → DNAT vers le backend → mais le backend voit l'IP interne du client et répond directement (sans passer par le firewall) → **réponse hors session NAT, paquet jeté**.

Solution : **hairpin NAT** ou **NAT reflection** = SNAT supplémentaire sur ce flux pour que le backend voit l'IP du firewall comme source, force le retour par le firewall.

## Types de NAT en jargon classique (1-to-1, full cone, etc.)

Cette taxonomie vient surtout du monde des applications P2P et VoIP :

| Type | Description |
|------|-------------|
| **1-to-1 NAT** | Une IP interne ↔ une IP externe dédiée, sans translation de port |
| **Full cone NAT** | Permissive : n'importe qui sur Internet peut atteindre le port mappé une fois ouvert |
| **Restricted cone** | Seulement les IPs que la machine interne a contactées |
| **Port restricted cone** | Seulement les couples IP:port contactés |
| **Symmetric NAT** | La traduction varie selon la destination — strict, casse beaucoup de P2P |

En homelab, on n'a pas besoin de connaître ça en détail. Bon à savoir : **certaines apps P2P/VoIP peinent derrière NAT symétrique**, d'où **STUN/TURN/ICE** pour les contourner.

## CGNAT (Carrier-Grade NAT)

De plus en plus de FAI mettent un **NAT supplémentaire** côté opérateur — le client n'a pas une vraie IP publique, mais une autre IP privée (plage `100.64.0.0/10` réservée pour ça).

Conséquences : **impossible de faire du port forwarding** vers ton réseau. Il faut soit demander une IPv4 dédiée au FAI, soit passer par un service tiers (Cloudflare Tunnel, NgRok, Tailscale Funnel, etc.).

Vérifier si tu es en CGNAT : ton IP "publique" est dans `100.64.0.0/10` → c'est du CGNAT.

## NAT et le pare-feu : ordre des opérations

Sur un firewall comme OPNsense/pfSense (et Linux iptables/nftables sous-jacent), l'ordre de traitement d'un paquet entrant est en gros :

```
Paquet entrant
   │
   ▼
1. PREROUTING — DNAT appliqué ici (réécriture IP dest)
   │
   ▼
2. Décision de routage (où va le paquet maintenant)
   │
   ▼
3. INPUT (si destiné au firewall lui-même) OU FORWARD (si transit)
   │
   ▼
4. Règles de filtrage appliquées ici (sur l'IP dest déjà DNATée)
   │
   ▼
5. POSTROUTING — SNAT appliqué ici (réécriture IP source)
   │
   ▼
Paquet sortant
```

🔑 Conséquence importante : **les règles de pare-feu portent sur l'IP destinataire APRÈS DNAT**. Quand tu écris "autoriser vers 10.0.40.50:443", c'est ce que le firewall voit, même si le client a contacté `203.0.113.5:443`.

## NAT et stateful : indissociables

Le NAT est **par essence stateful** : sans table d'état, impossible de réécrire le paquet retour. Toute connexion NATée passe en mémoire (conntrack sur Linux).

Implications :
- **Limite de capacité** : `nf_conntrack_max` sur Linux (defaults souvent à 65k-260k). Dépassé → connexions jetées
- **Timeout** : une session inactive est purgée (60s à 3600s selon le type)
- **Sessions longue durée** (SSH idle) : keep-alive nécessaires pour ne pas expirer

➡️ Cf. [Pare-feu stateful](./07-pare-feu-stateful.md).

## NAT et IPv6 : presque pas

L'IPv6 a tant d'adresses qu'il **n'a pas besoin de NAT** — chaque machine peut avoir une IP publique. Le NAT IPv6 existe (NAT66, NPTv6) mais est marginal et déconseillé.

En IPv6, le pare-feu fait du **filtrage pur**, sans NAT. C'est conceptuellement plus simple.

⚠️ Conséquence : en passant d'IPv4 (avec NAT) à IPv6 (sans), tu perds le "NAT comme firewall implicite". Une machine IPv6 sans pare-feu est **directement joignable depuis Internet** sur tous ses ports — il faut explicitement un pare-feu IPv6.

## NAT et MTU / fragmentation

Le NAT ne change pas la taille du paquet, **sauf** s'il opère du **NAT-Traversal** pour IPsec/UDP encapsulation, où il peut ajouter des en-têtes. Effet : MTU effectif réduit, ce qui peut causer des **problèmes de fragmentation**.

Symptôme : connexions qui marchent pour les petits paquets (ping, login) mais cassent au transfert de gros fichiers ou en TLS. Solutions : **MSS clamping**, MTU explicite côté tunnel, etc.

## NAT et logs : qui était qui ?

Côté FAI ou pare-feu central, un même log "IP `203.0.113.5` a fait une requête" recouvre **tous les clients du LAN** s'il n'y a pas plus de détail. C'est pourquoi :
- Les FAI gardent les **logs de mappings NAT** (obligation légale dans beaucoup de pays)
- Les entreprises journalisent **avant et après NAT** pour pouvoir remonter à la machine interne

Dans un homelab, garder à l'esprit que **ton FAI sait** quelle machine de chez toi a parlé à quel serveur Internet.

## SNAT statique vs masquerading (Linux/iptables/nft)

Deux variantes côté implémentation Linux/Netfilter :

- **SNAT statique** : "réécrire la source en `203.0.113.5`" (IP fixe codée en dur)
- **MASQUERADE** : "réécrire avec l'IP que mon interface a actuellement" (utile pour DHCP côté WAN, où l'IP peut changer)

OPNsense/pfSense gèrent ça automatiquement selon le contexte.

## NAT en pratique sur un pare-feu type OPNsense

Configurations typiques en homelab :

1. **Outbound NAT** (= SNAT en sortie WAN) : par défaut automatique. Toutes les IPs privées des VLANs sont masqueradées sur l'IP WAN.

2. **Port forwarding** (= DNAT) : règles explicites. "TCP 443 sur WAN → 10.0.40.50:443".

3. **1:1 NAT** : "10.0.10.5 (interne) ↔ 203.0.113.10 (publique alternative)" — utilisé si tu as plusieurs IPs publiques.

4. **NAT reflection / hairpin NAT** : à activer si les utilisateurs internes utilisent le nom DNS public pour accéder aux services.

## Pièges fréquents

| Symptôme | Cause |
|----------|-------|
| Service exposé inaccessible depuis Internet | Port forwarding (DNAT) absent ou règle FW manque |
| Service exposé OK depuis externe, KO depuis interne | Hairpin NAT pas activé |
| VoIP/jeux en ligne capricieux | NAT type "symmetric" — souvent OK avec UPnP/STUN |
| Connexions qui se coupent au bout de minutes | NAT session expirée par inactivité — keep-alive applicatif manquant |
| `nf_conntrack: table full` | Trop de connexions concurrentes — augmenter `nf_conntrack_max` |
| Backend voit l'IP du firewall au lieu du client | Hairpin NAT actif côté interne, ou SNAT sur le LAN |
| Forwarding par défaut KO depuis un VLAN | Outbound NAT pas configuré pour ce VLAN sur le firewall |

## À retenir

- **SNAT** : réécrit l'IP **source**, en sortie (côté Internet).
- **DNAT** = **port forwarding** : réécrit l'IP **destinataire**, en entrée.
- **PAT/masquerading** = NAT avec partage d'une IP via les ports — le 99% des cas.
- NAT est **par essence stateful** : table de mappings maintenue en mémoire.
- Ordre dans le pare-feu : **DNAT (PREROUTING) → règles → SNAT (POSTROUTING)**.
- Les règles de filtrage portent sur l'IP **après DNAT**.
- IPv6 supprime largement le besoin de NAT.
- **Hairpin NAT** pour que les utilisateurs internes accèdent à un service exposé par son nom public.

## Pour aller plus loin

- [Pare-feu stateful](./07-pare-feu-stateful.md)
- [Routage L3 et inter-VLAN](./04-routage-l3-inter-vlan.md)
- [Architecture segmentée](./08-architecture-segmentee.md) — DMZ et NAT
- [Outils de diagnostic](./09-outils-diagnostic.md)
- RFC 3022 (NAT traditionnel) — la spec d'origine
- RFC 1918 — les plages d'IP privées
