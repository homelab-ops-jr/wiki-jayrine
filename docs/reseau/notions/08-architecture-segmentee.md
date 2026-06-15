# 08 — Architecture segmentée : DMZ, defense in depth, moindre privilège

> **Type** : Notion · **Sujet** : Réseau · **Prérequis** : [VLANs](./03-vlans-et-802-1q.md), [Pare-feu stateful](./07-pare-feu-stateful.md)

## En une phrase

Une **architecture réseau segmentée** divise un réseau en zones avec **différents niveaux de confiance**, séparées par des pare-feu, en appliquant le principe du **moindre privilège** : chaque zone ne peut atteindre que ce dont elle a strictement besoin. C'est l'application réseau du concept général de **defense in depth**.

## Pourquoi segmenter

Un réseau **plat** (un seul broadcast domain, tout le monde sur le même subnet) souffre de plusieurs maux :

- **Compromission virale** : si une machine est infectée, elle peut scanner et attaquer tout le LAN sans frein
- **Bruit broadcast** : sur des dizaines/centaines de machines, le bruit ARP/DHCP/mDNS devient pesant
- **Sécurité par confiance implicite** : "il est dans le LAN, donc c'est OK" — modèle fragile
- **Pas de différenciation d'accès** : un imprimante a les mêmes "droits" qu'un serveur de prod
- **Audit impossible** : tout passe partout, traces impossibles à reconstituer

**Segmenter = limiter les rayons d'explosion**.

## Le vocabulaire des zones

Termes classiques (vendor-neutres) :

| Zone | Niveau de confiance | Exemples typiques |
|------|---------------------|-------------------|
| **Management** | Maximal (admin) | Interface admin Proxmox, OPNsense, switches |
| **Trusted / Internal** | Élevé | Postes des employés, serveurs internes |
| **Untrusted / Guest** | Faible | Wi-Fi invités, salle d'attente |
| **DMZ** | Hostile (exposé) | Services exposés Internet (web, mail public) |
| **IoT** | Faible (capteurs) | Caméras, sondes domotiques |
| **External / WAN** | Hostile | Internet |

🔑 Le principe : **plus une zone est hostile, plus elle doit être contenue**, sans pouvoir atteindre les zones plus sûres.

## La DMZ — concept central

**DMZ** = DeMilitarized Zone, par analogie avec les zones tampons entre deux blocs militaires.

C'est une **zone semi-isolée** qui héberge les services **exposés sur Internet** :
- Site web public
- Serveur mail entrant
- Serveur de fichiers public
- Reverse proxy frontal

Le principe :
- **Internet → DMZ** : autorisé (sur les ports des services exposés)
- **DMZ → Internet** : généralement autorisé (mises à jour OS, etc.)
- **Interne → DMZ** : autorisé (les admins doivent pouvoir accéder)
- **DMZ → Interne** : **interdit** — si la DMZ est compromise, l'attaquant ne doit pas rebondir vers le LAN

```
Internet  ←──────► [DMZ]  ←──────  Interne
            ↑                       ↓ admin
            │  exposition           │
            │                       │ ✗
            └─────────────►─────────┘ (DMZ vers interne BLOQUÉ)
```

🔒 Une DMZ bien implémentée signifie qu'un attaquant qui compromet ton serveur web public **ne peut pas** accéder à ta base de données interne ou à tes serveurs de fichiers.

## Le principe du moindre privilège

Concept général de sécurité : **chaque entité (utilisateur, service, machine) ne doit avoir que les permissions strictement nécessaires** à sa fonction.

Appliqué au réseau :

- Une **caméra de surveillance** n'a besoin que de remonter du flux vidéo vers un NVR. Elle n'a aucune raison d'accéder à Internet, ni au LAN administratif.
- Un **serveur de DB** n'a pas besoin d'accéder à Internet (sauf updates). Bloquer sortant minimaliste.
- Un **poste utilisateur** a besoin d'Internet et de quelques services internes. Pas du LAN management.

🔑 Concrètement, ça se traduit par des **règles PERMIT** explicites et minimalistes, sur fond de **default deny**.

## Defense in depth

Stratégie qui empile **plusieurs couches de défense** pour qu'aucune seule défaillance ne soit catastrophique. Pour le réseau :

```
1. Pare-feu périmétrique (Internet → LAN)
2. Segmentation par VLAN
3. Pare-feu inter-VLAN
4. Pare-feu local (host-based) sur les machines
5. Authentification forte sur les services
6. Chiffrement bout en bout (TLS)
7. Monitoring / IDS
```

Aucune n'est complète seule. Toutes ensemble couvrent énormément.

## Modèles d'architecture types

### Modèle "Le Chaudron" (homelab segmenté typique)

```
                    Internet
                       │
                       ▼
              ┌──────────────────┐
              │  Pare-feu        │ (OPNsense, pfSense)
              │  + Routeur       │
              └─┬────┬───┬───┬───┘
                │    │   │   │
        ┌───────┘    │   │   └────────┐
        │            │   │            │
     VLAN 10      VLAN 20  VLAN 30  VLAN 40
   Management   Lab/Dev   Services   DMZ
   10.0.10/24   .20/24   .30/24    .40/24

   Mgmt peut tout atteindre.
   Dev peut atteindre Services, DMZ.
   Services peut sortir Internet uniquement.
   DMZ peut sortir Internet, rien d'autre.
```

Avec la matrice de flux correspondante :

| Source ↓ / Dest → | Mgmt | Dev | Services | DMZ | Internet |
|-------------------|:----:|:---:|:--------:|:---:|:--------:|
| **Mgmt** | — | ✅ | ✅ | ✅ | ✅ |
| **Dev** | ❌ | — | ✅ | ✅ | ✅ |
| **Services** | ❌ | ❌ | — | ❌ | ✅ |
| **DMZ** | ❌ | ❌ | ❌ | — | ✅ |

Lecture : Mgmt peut tout faire (admin). Dev peut accéder à Services et DMZ pour développer. Services et DMZ ne remontent pas. DMZ ne peut joindre rien en interne.

### Modèle "Zero Trust"

Plus récent et plus radical : **aucune zone n'est implicitement sûre**, y compris le LAN interne. Chaque accès est **authentifié et autorisé individuellement**, indépendamment de la zone.

Implications :
- **mTLS** ou équivalent pour chaque flux interne
- **SSO** centralisé pour tous les services
- **Identity-aware proxies** (Cloudflare Access, Tailscale, etc.)

Difficile à implémenter complètement en homelab, mais des éléments sont applicables (Authelia + mTLS sélectif, etc.).

➡️ Voir [Notion : mTLS](../../certificats/notions/09-mtls.md).

## Trois patterns de design

### 1. Single firewall ("router on a stick")

Un seul pare-feu gère toutes les zones. Plus simple, suffisant pour la plupart des cas, **le standard en homelab**.

```
              Internet
                 │
        ┌────────┴───────┐
        │   Pare-feu     │
        │   (toutes les  │
        │    interfaces) │
        └──┬──┬──┬──┬────┘
           │  │  │  │
        VLAN VLAN VLAN VLAN
```

### 2. Dual firewall (sandwich)

Deux pare-feu en série, le second protégeant la DMZ d'éventuelle compromission du premier. Surcoût et complexité.

```
Internet ─► Pare-feu externe ─► DMZ ─► Pare-feu interne ─► LAN
```

Justifié en entreprise sensible, overkill en homelab.

### 3. Multi-firewall par zone

Chaque zone a son propre pare-feu (souvent un pare-feu virtuel par VM ou container). Microsegmentation poussée. Concept utilisé en datacenter / cloud (security groups AWS, etc.).

## Concevoir un plan de segmentation : démarche

1. **Lister les acteurs / services** : qu'est-ce qui existe sur ton réseau ?
2. **Regrouper par fonction et niveau de confiance** : tous les serveurs admin ensemble, toutes les caméras ensemble, etc.
3. **Pour chaque groupe, définir** :
   - Qui doit l'atteindre ?
   - Que doit-il atteindre ?
   - Quels protocoles ?
4. **Tracer la matrice de flux**
5. **Choisir les VLANs et plans d'adressage** :
   - Convention courante : `10.0.<vlan>.0/24`, ex. VLAN 30 → `10.0.30.0/24`
   - VLAN ID significatif (10 = mgmt, 20 = dev, etc.)
6. **Écrire les règles** à partir de la matrice

## Plans d'adressage : conventions utiles

| Convention | Exemple | Avantage |
|------------|---------|----------|
| VLAN ID dans le subnet | VLAN 30 → `10.0.30.0/24` | Lecture immédiate de "à quel VLAN appartient cette IP" |
| `.1` = gateway | `10.0.30.1` | Convention universelle |
| `.0` = réseau, `.255` = broadcast | normal | RFC, à respecter |
| Pool DHCP en haut | `.100`-`.200` | Réservations statiques bas, DHCP haut |
| Documenter chaque réservation | wiki ou commentaires conf | Sinon oublié au bout de 6 mois |

## Cas particulier des invités (Guest)

Un réseau "invités" (Wi-Fi public, salle d'attente) a une logique spécifique :

- **Accès Internet** : oui
- **Accès LAN** : **non**
- **Isolation entre invités** : oui (un invité ne doit pas pouvoir scanner un autre invité)
- **Bande passante limitée** (optionnel)
- **Captive portal** (optionnel)

C'est typiquement un VLAN séparé avec :
- DHCP local
- Aucun accès vers les autres VLANs
- Internet via NAT
- **Client isolation** sur le Wi-Fi (option de la borne)

## VLAN IoT : un cas répandu

Les objets connectés (caméras, ampoules, thermostats, assistants vocaux) sont notoirement insécures : MDP par défaut, firmware non patchés, télémétrie excessive.

Best practice : **VLAN IoT dédié**, sans accès au LAN interne, avec accès Internet limité (parfois bloqué pour certains appareils).

Difficulté : certaines apps (smartphone) doivent communiquer avec les objets — donc autoriser **LAN interne → IoT** mais pas l'inverse. Multicast (mDNS, SSDP) doit parfois traverser → reflector mDNS sur le pare-feu.

## Erreurs classiques de segmentation

| Erreur | Conséquence |
|--------|-------------|
| VLAN 1 utilisé comme management | VLAN hopping facile, exposition par défaut |
| Pas de default deny | Tout passe entre VLANs, segmentation pour la forme |
| Trop de VLANs (15 dans un homelab) | Complexité, maintenance impossible |
| Pas de doc / matrice de flux écrite | "Je sais plus pourquoi cette règle est là" 6 mois après |
| Single point of failure pare-feu | Le pare-feu en panne = tout est coupé |
| LAN admin accessible depuis Internet | Énorme risque, exposition admin |
| Wi-Fi invités joint le LAN | Voisin/passant peut scanner tes serveurs |
| Pas de séparation Dev/Prod | Une faille en Dev impacte la Prod |
| DMZ peut joindre le LAN | Si compromise, accès complet |

## Limites de la segmentation réseau

Important à savoir : **la segmentation par VLAN n'est pas une panacée**.

- Une faille **applicative** sur un service exposé reste exploitable, peu importe le VLAN
- Un **insider** dans le VLAN admin n'a aucun barrage réseau
- **Authentification faible** sur un service le rend vulnérable, segmenté ou non
- Les **flux autorisés** (ex. Mgmt → All) sont des vecteurs d'attaque si Mgmt est compromis

🔑 La segmentation réseau est **une couche parmi d'autres**, pas LA solution. Combiner avec auth forte, durcissement OS, monitoring, mises à jour.

## À retenir

- **Segmenter = limiter le rayon d'explosion** d'une compromission.
- **DMZ** isole les services exposés du LAN interne.
- **Moindre privilège** : chaque zone n'a accès qu'au strict nécessaire.
- **Matrice de flux** = outil de design avant toute règle de pare-feu.
- **Default deny** + règles PERMIT explicites + minimaliste.
- **DMZ → Interne = TOUJOURS BLOQUÉ.**
- **VLAN IoT et Guests** : segmentation indispensable.
- Segmentation = **une couche**, pas le tout. Combiner avec d'autres défenses.

## Pour aller plus loin

- [VLANs et 802.1Q](./03-vlans-et-802-1q.md)
- [Pare-feu stateful](./07-pare-feu-stateful.md)
- [NAT (SNAT, DNAT)](./06-nat-snat-dnat.md) — exposer un service depuis la DMZ
- [Routage L3 et inter-VLAN](./04-routage-l3-inter-vlan.md)
- NIST SP 800-207 — Zero Trust Architecture
