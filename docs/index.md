# Wiki — Administration Réseau

Base de connaissance personnelle pour la formation continue en administration réseau, orientée pratique homelab / self-hosting.

!!! tip "Recherche"
    Utilise la barre de recherche en haut (raccourci <kbd>S</kbd> ou <kbd>/</kbd>) — l'index couvre tout le contenu du wiki et les résultats sont mis en surbrillance. Tu peux aussi basculer entre thème clair et sombre en haut à droite.

## Organisation

Le wiki est structuré par **sujets**. Chaque sujet contient deux types de fiches :

- **Notions** — Le **quoi** et le **pourquoi**. Comprendre les fondamentaux avant de manipuler.
- **Méthodes** — Le **comment je fais**. Procédures applicables face à une situation concrète, souvent dans le contexte Traefik + Linux + Docker.

Chaque fiche est autonome et lisible en moins de 10 minutes. Les renvois entre fiches se font par liens internes.

## Sujets

| Sujet | État | Description |
|-------|------|-------------|
| [Certificats](./certificats/index.md) | 🟢 En cours | TLS, PKI, Let's Encrypt, mTLS, gestion avec Traefik et OpenSSL |
| [Reverse proxy & routage](./reverse-proxy/index.md) | 🟢 En cours | Traefik approfondi : middlewares, headers, auth, rate limiting, debug |
| DNS | ⚪ Planifié | Zones, enregistrements, DNS challenge, DNS over TLS |
| Firewall & sécurité réseau | ⚪ Planifié | UFW, iptables, nftables, CrowdSec, fail2ban |
| VPN & accès distant | ⚪ Planifié | Tailscale, WireGuard, OpenVPN, exposition de services |
| Monitoring & supervision | ⚪ Planifié | Métriques, logs, alerting |

## Conventions

- **Commandes shell** : présentées dans des blocs `bash` directement copiables.
- **Chemins d'exemple** : `/data/services/<stack>/` pour ce qui touche au homelab, `/tmp/demo/` pour les exemples isolés.
- **Domaines d'exemple** : `example.com` pour les fiches génériques, `jayrine.com` quand un détail propre au homelab est nécessaire.
- **Mises en garde** : préfixées par `⚠️` (piège fréquent) ou `🔒` (implication sécurité).
- **Astuces** : préfixées par `💡`.
