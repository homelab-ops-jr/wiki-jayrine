# 06 — VMs vs conteneurs : KVM, LXC, Docker

> **Type** : Notion · **Sujet** : Virtualisation · **Prérequis** : [Hyperviseurs](./01-hyperviseurs.md)

## En une phrase

Une **VM** (KVM/QEMU) émule un matériel complet et fait tourner un **kernel séparé** ; un **conteneur OS-level** (LXC) partage le kernel de l'hôte mais isole l'espace utilisateur ; un **conteneur applicatif** (Docker) va plus loin dans la légèreté en isolant un **seul processus**. Choisir entre ces trois abstractions est un arbitrage entre **isolation, performance, simplicité, portabilité**.

## Les trois niveaux d'abstraction

```
Plus isolé  ◄────────────────────────────────────────────►  Plus léger

┌────────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│  VM (KVM)              │  │  Conteneur OS (LXC) │  │  Conteneur app      │
│                        │  │                     │  │  (Docker)           │
│  ┌──────────────────┐  │  │  ┌───────────────┐  │  │  ┌──────────────┐   │
│  │ App              │  │  │  │ Apps          │  │  │  │ Une app      │   │
│  ├──────────────────┤  │  │  ├───────────────┤  │  │  ├──────────────┤   │
│  │ libs / userspace │  │  │  │ libs/userspace│  │  │  │ libs/userspace│   │
│  ├──────────────────┤  │  │  ├───────────────┤  │  │  │ minimal      │   │
│  │ Init (systemd)   │  │  │  │ Init (systemd)│  │  │  └──────┬───────┘   │
│  ├──────────────────┤  │  │  └───────┬───────┘  │  │         │           │
│  │ Kernel Linux     │  │  │          │          │  │         │           │
│  │ DÉDIÉ            │  │  │          │          │  │         │           │
│  └────────┬─────────┘  │  │          │          │  │         │           │
│           │            │  │          │          │  │         │           │
│      QEMU+KVM          │  │          │          │  │         │           │
└───────────┼────────────┘  └──────────┼──────────┘  └─────────┼───────────┘
            │                          │                       │
            └──────────────────────────┴───────────────────────┘
                              │
                       ┌──────┴─────────┐
                       │ Kernel hôte    │
                       │ (partagé pour  │
                       │  LXC/Docker)   │
                       ├────────────────┤
                       │   Matériel     │
                       └────────────────┘
```

## Virtual Machine (KVM/QEMU)

### Caractéristiques

- **Émulation complète d'un matériel** (CPU, RAM, disques, cartes réseau)
- **Kernel propre** à chaque VM
- **OS au choix** : Linux, Windows, BSD, autre Linux que l'hôte
- **Isolation forte** : compromission de la VM ne propage pas au kernel hôte (sauf vulnérabilité hyperviseur, rares)
- **Démarrage** : seconde à minute (boot OS complet)
- **Empreinte** : RAM 512 Mo+ par VM minimum, disque GB+

### Cas d'usage

- Workloads où la **diversité OS** compte (Windows + Linux + BSD)
- Services critiques nécessitant **isolation maximale**
- Lab où on veut **multiboot** ou tester un OS
- VM **pare-feu/routeur** (OPNsense, pfSense) — nécessite contrôle bas niveau du réseau
- Cas où le service **dépend du kernel** (modules spécifiques, vieux noyau)

## Conteneur OS-level (LXC)

### Caractéristiques

- **Espace utilisateur isolé** mais **kernel partagé** avec l'hôte
- Ressemble à une "VM légère" : init, systemd, plusieurs processus, fichiers de config classiques
- Pas d'émulation matériel
- **Démarrage** : milliseconde à seconde
- **Empreinte** : 10-100 Mo de RAM, quelques 100 Mo de disque
- Performance **quasi-bare-metal**

### Comment ça marche (briques Linux)

Les conteneurs Linux reposent sur des fonctions du kernel :

- **Namespaces** : isolent ce que le conteneur voit
  - **PID** : ses propres processus, ses PIDs comptent depuis 1
  - **Network** : ses propres interfaces, ses propres routes
  - **Mount** : son propre arbre FS
  - **UTS** : son propre hostname
  - **IPC** : ses propres mécanismes inter-processus
  - **User** : ses propres UID (depuis Linux 3.8)
  - **Cgroup** : sa vue des cgroups
- **Cgroups** : limitent ce que le conteneur peut consommer (CPU, RAM, I/O, processus)
- **Capabilities** : retire des privilèges sensibles (CAP_NET_ADMIN, CAP_SYS_ADMIN…)
- **Seccomp** : filtre les syscalls autorisés
- **AppArmor / SELinux** : MAC (Mandatory Access Control) sur le conteneur

LXC orchestre tout ça pour présenter un conteneur "à l'apparence d'une mini-VM".

### Avantages

- **Densité** : centaines de conteneurs sur un host modeste
- **Démarrage instantané**
- **Pas d'overhead CPU/RAM** notable
- **Stockage économique**

### Limites

- **Kernel partagé** : une vulnérabilité kernel peut compromettre tout
- **OS limité au Linux** (et même au kernel de l'hôte)
- **Moins isolé** qu'une VM (sécurité plus difficile, surface kernel énorme)
- **Modules kernel** non chargeables par le conteneur (il utilise ceux de l'hôte)

🔑 Proxmox supporte LXC nativement (`pct` CLI, UI dédiée). C'est l'alternative ultra-légère aux VMs pour les services Linux.

## Conteneur applicatif (Docker, Podman)

### Caractéristiques

- **Un processus principal** par conteneur (philosophie)
- **Image immutable** construite en couches (layers)
- **Démarrage** : milliseconde
- **Empreinte** : MB de RAM, MB-GB de disque
- Conçu pour **déployer/scaler/recréer** à la volée

### Différence vs LXC

LXC = "petite VM Linux" : tu fais `lxc-start`, tu obtiens un système complet avec init et services. Tu y entres en SSH, c'est un "petit serveur".

Docker = "processus isolé portable" : tu fais `docker run`, **un seul processus** démarre. Pas de init complet, pas de SSH (sauf ajout), pas de "système" — juste l'app et ses libs.

| Aspect | LXC | Docker |
|--------|-----|--------|
| Modèle | OS-like (init, plusieurs processus) | Process-like (un processus principal) |
| Mise à jour | apt/yum dans le conteneur | reconstruire et redéployer l'image |
| Volumes | Optionnel | Quasi obligatoire pour persister |
| Réseau | Comme une "machine" | Réseaux Docker abstraits |
| Image | Snapshot OS | Layers immuables (registry) |
| Usage | Apps qui aiment l'environnement Linux complet | Microservices, apps stateless |

🔑 **Docker n'est pas vraiment un "format de conteneur"** — c'est un orchestrateur + un format d'image + un outil. Sous le capot, c'est aussi namespaces+cgroups, comme LXC.

### Quand Docker excelle

- **Microservices** déployables individuellement
- **CI/CD** : `docker build`, `docker push`, `docker run` partout pareil
- **Stateless apps** qu'on scale horizontalement
- **Dev local** : "docker compose up" reproductible
- **Apps avec dépendances complexes** : "tout est dans l'image"

### Limites de Docker

- **Stateful** est plus dur (volumes, backup, migration de données)
- Un conteneur "et tout dedans" violant la philosophie 1-process devient un anti-pattern (mais courant pour des apps legacy)
- **Multi-process** non triviale (nécessite supervisord ou autre)
- L'écosystème Docker (Kubernetes…) est complexe

## Combinaisons et patterns courants

### Docker dans une VM

Très commun : tu as **un host bare-metal** Linux ou Proxmox. Tu installes une **VM** (Ubuntu Server par ex.) et tu fais tourner **Docker dedans**, gérant des dizaines de conteneurs applicatifs.

Pourquoi pas Docker direct sur le host ? Plusieurs raisons :
- **Isolation supplémentaire** : si Docker host est compromis, la VM reste isolée du reste
- **Migration / backup** : sauvegarder la VM entière = backup du tout
- **Rollback facile** : snapshot VM
- **Multi-Docker** : plusieurs VMs Docker pour différents projets/clients

Léger surcoût en perfs (~5-10%) mais souvent acceptable.

### Docker bare-metal

Possible et plus performant. Bon pour un homelab très dense ou un serveur dédié à Docker. Manque la couche d'abstraction VM pour migration/backup.

### LXC pour les services système, Docker pour les apps

Modèle homelab fréquent :
- **LXC** pour DNS, reverse proxy, services internes (Pihole, AdGuard) — gestion type OS
- **Docker** pour les apps web, microservices, CI/CD

Proxmox supporte les deux nativement.

### Kubernetes au-dessus

Pour orchestrer Docker à plus grande échelle, **Kubernetes** est le standard. Il gère scheduling, scaling, services, networking, etc. Hors scope homelab simple, mais c'est l'évolution naturelle de Docker à grande échelle.

## Comparatif complet

| Critère | VM (KVM) | LXC | Docker |
|---------|----------|-----|--------|
| Kernel | Dédié | Partagé hôte | Partagé hôte |
| OS supportés | Tout | Linux | Linux (Windows containers sur Win uniquement) |
| Démarrage | sec-min | ms-sec | ms |
| RAM minimale | ~512 Mo | ~10 Mo | ~MB |
| Disque par instance | GB | 100 Mo | MB |
| Isolation | Forte | Moyenne | Moyenne |
| Performance | Très bonne (avec virtio) | Quasi native | Native |
| Densité par host | Dizaines | Centaines | Milliers |
| Backup/snapshot | Excellent | Très bon | Via volume + image |
| Live migration | Oui | Oui | Limité |
| Cas typique | OS isolé, multi-OS | Services Linux multi-process | Apps stateless |

## Sécurité comparée

Ordre **typique** d'isolation, du plus au moins fort :
1. **VM** (KVM) — kernel séparé, breakout très difficile
2. **LXC unprivileged** (user namespace + retire de capabilities) — bon
3. **Docker rootless** — bon, croissant en adoption
4. **Docker classique** (process dans le namespace root) — moyen
5. **LXC privileged** — équivalent à des processus root sur l'hôte, peu d'isolation

🔒 Pour héberger du code **non confiance** (multi-tenant, CTF, etc.) : **VM** est le seul vrai cloisonnement. LXC/Docker sont plus poreux.

## Compatibilité kernel

VM : indépendante. Tu peux faire tourner du kernel 2.6 ancien dans une VM sur un host 6.x.

LXC/Docker : **dépendent du kernel hôte**. Implications :
- Un module kernel non chargé sur l'hôte n'est pas dispo dans le conteneur
- Une syscall trop neuve par rapport au kernel hôte plante dans le conteneur
- Migrer un conteneur vers un host kernel plus ancien peut casser

## Choisir : règles pragmatiques

| Situation | Choix conseillé |
|-----------|-----------------|
| Pare-feu OPNsense / pfSense | **VM** (besoin de contrôle réseau) |
| Windows quelque part | **VM** |
| Database PostgreSQL dédiée | **VM** ou **LXC** (selon préférence) |
| Reverse proxy Traefik | **Docker** ou **LXC** |
| App web (Node, Python) | **Docker** |
| Pihole / AdGuard | **LXC** ou **Docker** |
| Lab d'apprentissage Linux | **LXC** (rapide, isolé, léger) |
| Plex/Jellyfin | **Docker** ou **LXC** |
| Build CI éphémère | **Docker** |
| Service avec drivers spécifiques GPU | **VM** avec PCI passthrough |

## En homelab : la combinaison classique

```
Host Proxmox (bare-metal)
│
├─ VM OPNsense      (pare-feu, isolation forte)
├─ VM TrueNAS       (passthrough HBA, OS différent BSD)
├─ VM Docker-host   (Ubuntu Server avec docker compose)
│  │
│  ├─ container nginx
│  ├─ container nextcloud
│  └─ container ...
│
├─ LXC Pihole       (léger, simple)
├─ LXC HomeAssistant (privileged si Zigbee USB)
└─ LXC dev          (tests Linux divers)
```

Mix VM (services critiques, OS atypiques) + LXC (services Linux propres) + Docker dans VM (apps web).

## Pièges fréquents

| Symptôme | Cause |
|----------|-------|
| Docker dans LXC qui ne marche pas | LXC unprivileged restreint, Docker peut nécessiter privileged |
| Conteneur "lourd" qui devient une mini-VM | Anti-pattern — utiliser une VM ou découper en plusieurs conteneurs |
| Modules kernel manquants dans LXC | Charger sur l'hôte (`modprobe`), pas dans le conteneur |
| Performance Docker dégradée sur HDD | Layered FS amplifie les I/O — privilégier SSD |
| Persistance perdue après recréation Docker | Pas de volume nommé → données dans le layer mutable, perdues |
| Réseau Docker compliqué | Bridges, overlays, macvlan — beaucoup d'options à digérer |
| LXC privileged "kebab" la sécurité de l'hôte | Préférer unprivileged sauf besoin spécifique |
| Conteneur qui démarre puis s'arrête | Pas de processus en foreground (Docker s'attend à un PID 1 long-running) |

## À retenir

- **VM (KVM)** = kernel propre, OS indépendant, isolation forte, ressources importantes.
- **LXC** = conteneur "OS-like", kernel partagé, super léger, parfait pour services Linux.
- **Docker** = conteneur "process-like", image immutable, idéal microservices / déploiements reproductibles.
- Sous le capot : tous les conteneurs Linux = **namespaces + cgroups + capabilities**.
- VM > LXC > Docker en terme d'**isolation**. Inverse en terme de **densité/légèreté**.
- **Docker dans VM** est un pattern très commun et sain en production/homelab.
- Pour des **OS non Linux** ou un **kernel différent** : VM obligatoire.

## Pour aller plus loin

- [Hyperviseurs](./01-hyperviseurs.md)
- [KVM, QEMU, libvirt](./02-kvm-qemu-libvirt.md)
- [Réseau virtuel](./04-reseau-virtuel.md) — comment les conteneurs/VMs se connectent
- Doc LXC : [linuxcontainers.org](https://linuxcontainers.org/)
- Doc Docker : [docs.docker.com](https://docs.docker.com/)
- "Containers from scratch" (talks YouTube) — pour comprendre les briques kernel
