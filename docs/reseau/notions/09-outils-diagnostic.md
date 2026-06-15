# 09 — Outils de diagnostic réseau

> **Type** : Notion · **Sujet** : Réseau · **Prérequis** : [Modèle OSI](./01-modele-osi-tcpip.md)

## En une phrase

Diagnostiquer un problème réseau, c'est **isoler la couche défaillante** (cf. [Modèle OSI](./01-modele-osi-tcpip.md)) avec les bons outils. Cette fiche est un **catalogue raisonné** des commandes Linux/Unix essentielles, du simple `ping` au `tcpdump` poussé.

## Démarche générale

Plutôt que de "tester un peu tout", procéder **par couche, de bas en haut** :

```
1. Carte réseau / câble OK ?              → ip link, ethtool
2. IP configurée ?                          → ip addr
3. Default gateway configurée ?             → ip route
4. ARP de la gateway OK ?                   → ip neigh
5. Gateway joignable ?                      → ping <gw>
6. Internet joignable ?                     → ping 1.1.1.1
7. DNS fonctionne ?                         → dig, nslookup
8. Service distant écoute ?                 → nc, telnet, ss
9. TLS OK ?                                 → openssl s_client
10. Application répond ?                    → curl, wget
```

Si une étape échoue, **inutile de tester les suivantes** — corriger d'abord.

## Couche 1-2 : interface, lien, voisinage

### `ip link` — état des interfaces

```bash
$ ip link
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 state UP
3: eth1: <BROADCAST,MULTICAST> mtu 1500 state DOWN
```

`UP,LOWER_UP` = interface active **et** câble branché. `UP` seul = activée mais pas de lien physique.

### `ethtool` — détails physiques

```bash
ethtool eth0
# Speed: 1000Mb/s
# Duplex: Full
# Link detected: yes
```

Pour vérifier négociation auto, full-duplex, etc. Utile quand un câble suspect.

### `ip addr` — IPs configurées

```bash
$ ip addr show eth0
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 10.0.10.50/24 brd 10.0.10.255 scope global dynamic eth0
    inet6 fe80::a00:27ff:fe00:1/64 scope link
```

Vérifie : la machine a-t-elle une IP ? La bonne ? Dans le bon subnet ?

⚠️ Si tu vois `169.254.x.x` → DHCP a échoué (APIPA). Cf. [DHCP](./05-dhcp.md).

### `ip neigh` (= `arp -a`) — table ARP

```bash
$ ip neigh
10.0.10.1 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE
10.0.10.5 dev eth0 lladdr 11:22:33:44:55:66 STALE
```

États : `REACHABLE` (récent OK), `STALE` (ancien, à reconfirmer), `FAILED` (pas de réponse ARP).

🔑 Pas d'entrée pour la gateway = la machine ne peut pas joindre le L2 → problème de switch ou de VLAN.

## Couche 3 : routage

### `ip route` — table de routage

```bash
$ ip route
default via 10.0.10.1 dev eth0 proto dhcp metric 100
10.0.10.0/24 dev eth0 proto kernel scope link src 10.0.10.50 metric 100
```

Vérifie :
- Y'a-t-il une **default route** ? Sinon, pas d'Internet.
- Le subnet local est-il connu ?
- Si plusieurs interfaces, la "metric" (préférence) est-elle correcte ?

### `ip route get` — quelle route serait choisie pour une IP

```bash
$ ip route get 8.8.8.8
8.8.8.8 via 10.0.10.1 dev eth0 src 10.0.10.50
```

Diagnostic instantané "comment je sortirais pour joindre cette IP". Très utile.

### `ping` — l'outil fondamental

```bash
ping 10.0.10.1               # IP locale
ping -c 4 8.8.8.8            # 4 paquets puis stop
ping -I eth1 8.8.8.8         # forcer une interface source
ping -M do -s 1472 8.8.8.8   # tester MTU sans fragmentation (1472 + 28 headers = 1500)
ping6 fe80::1%eth0           # IPv6 link-local (interface obligatoire)
```

Échec ping = pas forcément "pas joignable" — beaucoup de pare-feu bloquent ICMP echo. Compléter avec d'autres tests.

⚠️ Bloquer **tout** ICMP est mauvais — voir [Pare-feu stateful](./07-pare-feu-stateful.md#icmp-a-ne-pas-bloquer-aveuglement).

### `traceroute` / `mtr` — chemin pris

```bash
traceroute 8.8.8.8
# 1  10.0.10.1   1ms 1ms 1ms
# 2  100.64.0.1  10ms ...    (CGNAT FAI ?)
# 3  ...
# 4  ...
# 11 8.8.8.8     20ms

mtr 8.8.8.8     # version interactive, voit les pertes par saut
```

Identifie **où ça casse** sur le chemin. Étoiles (`* * *`) = pas de réponse ICMP de ce saut (souvent normal, certains routeurs ignorent).

🔑 `mtr` est préférable en diagnostic actif — il continue de pinger et montre les pertes par saut sur la durée.

## Couche 4 : ports, connexions

### `ss` — sockets actifs (remplace `netstat`)

```bash
# Ports en écoute (TCP, listening, numérique, processus)
ss -tlnp

# Connexions UDP
ss -ulnp

# Connexions établies
ss -tan state established

# Statistiques globales
ss -s
```

Sortie typique :
```
LISTEN  0  128  0.0.0.0:22   0.0.0.0:*   users:(("sshd",pid=1234,fd=3))
```

Lecture : SSHD écoute sur le port 22 de toutes les interfaces (`0.0.0.0`), PID 1234.

🔑 **Le couple `ss -tlnp` + `ss -ulnp`** répond à "qu'est-ce qui écoute sur ma machine ?".

### `nc` (netcat) — test de connectivité L4

```bash
# Tester si un port TCP est ouvert
nc -zv 10.0.30.5 443
# Connection to 10.0.30.5 443 port [tcp/https] succeeded!

# Idem UDP (moins fiable)
nc -zvu 10.0.30.5 53

# Scan rapide d'une plage
for p in 22 80 443; do nc -zv 10.0.30.5 $p; done

# Serveur d'écoute pour tester (côté serveur)
nc -l 9999
# Côté client : nc 10.0.30.5 9999, puis taper du texte
```

Diagnostic ultime "est-ce qu'un port est joignable", indépendant du protocole applicatif.

### `telnet` — historique mais utile

```bash
telnet 10.0.30.5 443
# Trying 10.0.30.5...
# Connected to 10.0.30.5.    ← le port répond
```

Plus simple que `nc` pour beaucoup de gens. Limité à TCP.

## Couches applicatives : DNS, HTTP

### `dig` — résolution DNS

```bash
# Résolution standard
dig example.com

# Type spécifique (A, AAAA, MX, TXT, NS, CNAME, ...)
dig example.com MX
dig example.com NS

# Via un serveur DNS spécifique
dig @1.1.1.1 example.com
dig @10.0.10.1 example.com

# Mode court (juste la réponse)
dig +short example.com

# Trace complète depuis la racine
dig +trace example.com
```

🔑 Test de base : la résolution DNS marche-t-elle ? Et avec mon DNS, ou seulement avec un public ?

### `nslookup` — alternative simple

```bash
nslookup example.com
nslookup example.com 1.1.1.1
```

Plus rustique que `dig`, présent partout (y compris Windows).

### `host` — encore plus simple

```bash
host example.com
host -a example.com    # all records
```

### `curl` / `wget` — applicatif HTTP

```bash
# Test simple, voir l'en-tête de réponse
curl -I https://example.com

# Verbose : voir tout le détail (DNS, TLS, headers, etc.)
curl -v https://example.com

# Forcer une IP de destination (utile pour tester un serveur derrière son nom DNS)
curl --resolve example.com:443:10.0.30.5 https://example.com

# Sans vérification TLS (debug uniquement)
curl -k https://...
```

`curl -v` est le couteau suisse pour tester HTTP de bout en bout.

## Inspection brute : tcpdump

L'outil ultime de diag réseau : **capture les paquets** en temps réel.

### Bases

```bash
# Capturer sur une interface, sortie en clair
sudo tcpdump -i eth0

# Limiter à un host
sudo tcpdump -i eth0 host 10.0.30.5

# Limiter à un port
sudo tcpdump -i eth0 port 443

# Combinaison
sudo tcpdump -i eth0 host 10.0.30.5 and port 443

# DHCP
sudo tcpdump -i eth0 port 67 or port 68

# DNS
sudo tcpdump -i eth0 port 53

# Capturer en pcap (Wireshark)
sudo tcpdump -i eth0 -w capture.pcap host 10.0.30.5
```

### Options utiles

| Option | Effet |
|--------|-------|
| `-n` | Pas de résolution DNS des IPs (plus rapide) |
| `-nn` | Pas de résolution DNS ni de service ports |
| `-i any` | Toutes les interfaces |
| `-v`, `-vv` | Plus de détails |
| `-c 10` | Stop après 10 paquets |
| `-s 0` | Capturer le paquet entier (sinon tronqué à 96 octets) |
| `-A` | Affichage ASCII (utile HTTP) |
| `-X` | Affichage hex + ASCII (forensic) |

### Exemples d'usage forensic

```bash
# Que fait cette machine sur Internet ?
sudo tcpdump -i eth0 -n 'src 10.0.20.50 and not (dst net 10.0.0.0/8)'

# Y'a-t-il du trafic anormal sur ce port ?
sudo tcpdump -i any -n port 22 -c 100

# Capturer SYN sans ACK (scan port)
sudo tcpdump -i eth0 'tcp[tcpflags] & (tcp-syn) != 0 and tcp[tcpflags] & (tcp-ack) = 0'
```

🔑 `tcpdump` est **l'outil de dernier recours** quand "rien ne marche" : il montre **ce qui passe vraiment** sur le câble.

## nmap — scan de réseau

```bash
# Scan rapide d'un host
nmap 10.0.30.5

# Scan d'un subnet pour découvrir ce qui répond
nmap -sn 10.0.30.0/24

# Scan TCP complet d'un host
nmap -p- 10.0.30.5

# Avec détection de version
nmap -sV 10.0.30.5

# Scan UDP (lent)
nmap -sU --top-ports 100 10.0.30.5
```

🔒 Outil **agressif** — ne scanne que des hôtes que tu administres ou pour lesquels tu as l'autorisation explicite.

## Outils Linux complémentaires

### `ip` (le couteau suisse moderne)

```bash
ip a              # adresses (= ip addr)
ip l              # links (= ip link)
ip r              # routes (= ip route)
ip n              # neighbors / ARP (= ip neigh)
ip -s link        # statistiques par interface (paquets, erreurs)
ip rule           # règles de routage avancé
```

### `ss` avancé

```bash
ss -tlnp                         # ports en écoute
ss -tan dport = :443             # toutes connexions vers port 443
ss -i                            # avec stats RTT, congestion
```

### `iperf3` — bande passante

```bash
# Serveur (sur machine A)
iperf3 -s

# Client (sur machine B)
iperf3 -c <IP_A>
iperf3 -c <IP_A> -u -b 100M     # UDP à 100 Mbit/s
```

Mesure le débit réel entre deux machines. Indispensable pour valider une nouvelle config réseau.

### Wi-Fi : `iw`, `wpa_supplicant`

```bash
iw dev wlan0 scan          # SSIDs visibles
iw dev wlan0 link          # SSID connecté, RSSI
iw dev wlan0 station dump  # stations associées (mode AP)
```

## Diagnostic Windows (rappel)

| Linux | Windows équivalent |
|-------|-------------------|
| `ip addr` | `ipconfig` ou `ipconfig /all` |
| `ip route` | `route print` |
| `ip neigh` | `arp -a` |
| `ping` | `ping` |
| `traceroute` | `tracert` |
| `dig` | `nslookup` |
| `ss -tlnp` | `netstat -anob` (admin) |
| `tcpdump` | Wireshark, ou `pktmon` (depuis Win 10 1809) |

## Stratégies par symptôme

### Pas d'IP / `169.254.x.x`

1. `ip link` : interface UP ?
2. `journalctl -u systemd-networkd` ou `dhclient -v eth0` pour voir le dialogue DHCP
3. `tcpdump port 67 or 68` pour voir si le serveur DHCP répond
4. Vérifier le VLAN du port côté switch

### IP OK mais pas de gateway joignable

1. `ip neigh` : la MAC de la gateway est-elle résolue ?
2. `ping <gw>` : depuis le L2 ça passe ?
3. Vérifier VLAN/access du port
4. `tcpdump arp` pour voir si les requêtes ARP sortent et reviennent

### Gateway OK mais pas d'Internet

1. `ping 1.1.1.1` : par IP, pour exclure le DNS
2. `traceroute 1.1.1.1` : où ça casse ?
3. Vérifier NAT côté routeur
4. `dig` : DNS marche ?

### Service spécifique inaccessible

1. `nc -zv host port` : port joignable ?
2. `ss -tlnp` côté serveur : service écoute ?
3. `tcpdump port X` côté serveur : la requête arrive ?
4. Vérifier pare-feu (le serveur ? un FW intermédiaire ?)

### Lent mais ça marche

1. `mtr` pour voir où sont les pertes
2. `iperf3` pour le débit réel
3. `ip -s link` pour les erreurs
4. `ethtool` pour duplex/speed

## À retenir

- **Diagnostiquer par couche** (cf. [Modèle OSI](./01-modele-osi-tcpip.md)).
- **`ip` remplace `ifconfig`/`route`/`arp`** — utiliser le moderne.
- **`ss`** remplace `netstat` — plus rapide, plus complet.
- **`mtr`** > `traceroute` pour le diagnostic actif (perte par saut).
- **`tcpdump`** = outil de dernier recours, montre la vérité du câble.
- **`nc -zv`** pour tester rapidement un port joignable.
- **`dig` > `nslookup`** pour le DNS (plus précis).
- Toujours vérifier **la couche basse en premier** avant de soupçonner les couches hautes.

## Pour aller plus loin

- [Modèle OSI](./01-modele-osi-tcpip.md) — la grille de lecture
- [DHCP](./05-dhcp.md) — diagnostic spécifique
- [NAT (SNAT, DNAT)](./06-nat-snat-dnat.md) — diagnostic NAT
- [Pare-feu stateful](./07-pare-feu-stateful.md) — quand le pare-feu est suspect
- Wireshark — version graphique de `tcpdump`, indispensable pour analyse poussée
- `man ip`, `man ss`, `man tcpdump` — toutes les options
