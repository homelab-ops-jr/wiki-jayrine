# Virtualisation

Tout ce qui concerne **les hyperviseurs et la virtualisation côté serveur** : les types d'hyperviseurs, la stack Linux KVM/QEMU (= ce qu'utilise Proxmox), les disques virtuels, le réseau virtuel, l'intégration des VLANs, la différence avec les conteneurs. Le sujet est volontairement complémentaire du sujet [Réseau](../reseau/index.md) — les couches réseau y sont vues côté hyperviseur, mais les concepts réseau eux-mêmes (VLAN, routage, etc.) sont dans le sujet Réseau.

## Parcours suggéré

1. [Hyperviseurs : type 1 vs type 2](./notions/01-hyperviseurs.md) — situer Proxmox
2. [KVM, QEMU, libvirt](./notions/02-kvm-qemu-libvirt.md) — la stack Linux native
3. [Disques virtuels](./notions/03-disques-virtuels.md) — raw, qcow2, LVM, thin/thick
4. [Réseau virtuel : bridges, virtio, tap](./notions/04-reseau-virtuel.md) — comment une VM "parle" au réseau
5. [VLANs dans la virtualisation](./notions/05-vlans-virtualisation.md) — bridges VLAN-aware, modes de tagging
6. [VMs vs conteneurs](./notions/06-vms-vs-containers.md) — KVM, LXC, Docker
7. [Cloud-init et provisioning](./notions/07-cloud-init.md) — automatiser le premier boot
8. [Haute dispo et clustering](./notions/08-haute-dispo-clustering.md) — notions générales

## Fiches notions

| Fiche | À comprendre avant de… |
|-------|------------------------|
| [01 — Hyperviseurs (type 1 vs 2)](./notions/01-hyperviseurs.md) | Installer Proxmox, choisir un hyperviseur |
| [02 — KVM, QEMU, libvirt](./notions/02-kvm-qemu-libvirt.md) | Comprendre ce que fait Proxmox sous le capot |
| [03 — Disques virtuels](./notions/03-disques-virtuels.md) | Choisir un format/stockage pour une VM |
| [04 — Réseau virtuel](./notions/04-reseau-virtuel.md) | Configurer un bridge dans Proxmox |
| [05 — VLANs dans la virtualisation](./notions/05-vlans-virtualisation.md) | Faire passer plusieurs VLANs aux VMs |
| [06 — VMs vs conteneurs](./notions/06-vms-vs-containers.md) | Choisir entre VM et conteneur pour un service |
| [07 — Cloud-init et provisioning](./notions/07-cloud-init.md) | Automatiser la création de VMs identiques |
| [08 — Haute dispo et clustering](./notions/08-haute-dispo-clustering.md) | Comprendre Proxmox cluster, failover |

## À ajouter plus tard

- [ ] Live migration (concept + impact réseau et stockage)
- [ ] PCI passthrough et IOMMU avancé (GPU, NIC)
- [ ] SR-IOV et VFIO
- [ ] Snapshots et backup (méthode)
- [ ] Proxmox spécifiquement (méthode d'install et premier setup)
- [ ] LXC (containers system) en détail
- [ ] Docker dans une VM vs Docker bare-metal
- [ ] OpenStack, vSphere, Hyper-V (panorama des alternatives à Proxmox)
