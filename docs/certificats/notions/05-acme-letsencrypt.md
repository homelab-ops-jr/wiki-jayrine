# 05 — ACME & Let's Encrypt

> **Type** : Notion · **Sujet** : Certificats · **Prérequis** : [Chaîne de confiance & PKI](./03-chaine-de-confiance-pki.md)

## En une phrase

**ACME** (Automatic Certificate Management Environment, RFC 8555) est un protocole standardisé qui permet à un serveur de **demander, prouver son contrôle sur un domaine, et obtenir un certificat** auprès d'une CA, sans intervention humaine. **Let's Encrypt** est la première CA à l'avoir massivement déployé, gratuitement, à grande échelle.

## Le problème historique

Avant ACME (avant ~2016), obtenir un cert TLS, c'était :

1. Générer une CSR à la main avec OpenSSL
2. Aller sur le site d'un revendeur SSL (DigiCert, Sectigo…)
3. Payer entre 30 et 300 € par an
4. Recevoir un mail avec un lien de validation
5. Cliquer sur le lien (ou prouver le contrôle DNS/email)
6. Télécharger le cert
7. L'installer manuellement
8. **Refaire tout ça tous les ans**

Résultat : la majorité des sites web étaient en HTTP en clair, et l'écrasante majorité des admins laissait expirer ses certs.

ACME automatise tout, avec des certs **gratuits, valides 90 jours, renouvelables sans intervention**.

## Les acteurs

- **Let's Encrypt** (ISRG, fondé en 2016) — la CA pionnière, encore la plus utilisée
- **ZeroSSL** — alternative gratuite avec aussi du payant
- **Buypass Go SSL** — alternative norvégienne
- **BuyPass**, **Google Trust Services**, **SSL.com** — d'autres CA qui ont ouvert un endpoint ACME
- Côté **clients** : `certbot` (officiel EFF), `acme.sh`, `lego` (Go, utilisé par Traefik), `caddy` (intégré), etc.

Traefik **intègre nativement** un client ACME (basé sur `lego`). C'est ce qu'on appelle un **certresolver**.

## Le flux ACME en 4 étapes

```
Client (Traefik)                    CA (Let's Encrypt)
      │                                     │
      │ 1. newAccount / register ────────►  │
      │   (clé publique du compte)          │
      │                                     │
      │ 2. newOrder (domaines voulus) ───►  │
      │                              ◄───── │ liste de challenges
      │                                     │
      │ 3. répondre aux challenges :        │
      │    • HTTP-01 (fichier sur :80)      │
      │    • DNS-01 (TXT _acme-challenge)   │
      │    • TLS-ALPN-01 (ALPN extension)   │
      │                                     │
      │ 4. finalize (envoie la CSR) ─────►  │
      │                              ◄───── │ certificat émis
```

À tout moment, l'ordre passe par les états : `pending` → `ready` → `processing` → `valid`.

## Les trois types de challenges

C'est le cœur du protocole. La CA doit s'assurer que tu **contrôles vraiment** le domaine demandé. Trois mécanismes :

### HTTP-01

Le client crée un fichier sur le serveur web à un chemin spécifique :
```
http://example.com/.well-known/acme-challenge/<token>
```
La CA fait un GET sur cette URL et vérifie le contenu.

- ✅ Simple, marche dès qu'on a un serveur web sur le port 80
- ❌ **Pas de wildcard** possible (Let's Encrypt refuse HTTP-01 pour `*.example.com`)
- ❌ Nécessite que le port 80 soit accessible publiquement
- ❌ Ne marche pas pour des services sans HTTP (ex: un SMTP-only)

### DNS-01

Le client crée un enregistrement DNS TXT :
```
_acme-challenge.example.com  IN  TXT  "<valeur attendue>"
```
La CA résout ce TXT et vérifie la valeur.

- ✅ **Seul moyen d'obtenir un wildcard** (`*.example.com`)
- ✅ Marche même si le port 80 est fermé / serveur derrière un firewall
- ✅ Marche pour des services non-HTTP
- ❌ Nécessite que ton fournisseur DNS expose une API (et que le client ACME ait un plugin pour)
- ❌ Délai de propagation DNS à gérer

### TLS-ALPN-01

Le client présente une réponse spécifique sur le port 443 via une extension TLS ALPN. La CA initie une connexion TLS et vérifie.

- ✅ Utilise le 443 uniquement, pas besoin du 80
- ❌ Plus rare, moins de clients le supportent bien
- ❌ Conflit possible avec un service TLS déjà actif sur le 443

**Recommandation** : en homelab, **DNS-01** dès que tu veux un wildcard ; HTTP-01 sinon. TLS-ALPN-01 reste un cas particulier.

## Les limites de Let's Encrypt à connaître

Let's Encrypt a des **rate limits** stricts (anti-abus) :

- **5 émissions identiques** par semaine pour un même set de noms (piège majeur quand on debug — on s'épuise vite)
- **50 certs par domaine racine** par semaine
- **300 ordres** par compte par 3h
- **300 nouveaux comptes** par IP par 3h

⚠️ Quand tu **debug une config ACME**, **toujours commencer en environnement de staging** (`https://acme-staging-v02.api.letsencrypt.org/directory`). Les certs staging sont émis par une fake CA non-fiable mais sans rate limit serré. Tu passes en prod une fois que ça marche. Voir la fiche méthode dédiée.

Validité des certs : **90 jours**. Renouvellement recommandé à **30 jours avant expiration** (donc tous les 60 jours). Les clients automatiques font ça tout seuls.

🔒 Depuis 2024/2025, Let's Encrypt expérimente des certs **plus courts** (90 → 6 jours testé). Le principe ne change pas, l'automatisation devient juste indispensable.

## ACME dans Traefik (vue d'ensemble)

Dans la config statique de Traefik, tu définis un ou plusieurs **certresolvers** :

```yaml
# traefik.yml (config statique)
certificatesResolvers:
  myresolver:
    acme:
      email: admin@example.com
      storage: /letsencrypt/acme.json
      # un seul challenge par certresolver :
      dnsChallenge:
        provider: ovh        # ou cloudflare, route53, etc.
        delayBeforeCheck: 30
      # caServer: https://acme-staging-v02.api.letsencrypt.org/directory  # pour staging
```

Puis sur chaque router, tu actives :
```yaml
labels:
  - "traefik.http.routers.app.tls.certresolver=myresolver"
```

Et **éventuellement** un certificat wildcard à pré-générer :
```yaml
labels:
  - "traefik.http.routers.app.tls.domains[0].main=example.com"
  - "traefik.http.routers.app.tls.domains[0].sans=*.example.com"
```

Traefik gère tout : émission initiale, stockage dans `acme.json`, renouvellement automatique.

💡 Sur ton homelab : ton certresolver s'appelle `myresolver` (pas `letsencrypt`, c'est un piège classique à mémoriser). Cf. la fiche méthode [Traefik + Let's Encrypt DNS challenge](../methodes/traefik-letsencrypt-dns-challenge.md).

## Le fichier `acme.json`

Là où Traefik stocke ses certs, sa clé de compte ACME, et l'état de ses orders. Format JSON, propriété de root, permissions **strictes** :

```bash
chmod 600 acme.json
```

Si les permissions sont laxistes, Traefik refuse de le lire au démarrage. Si le fichier est corrompu, plus aucun cert ne se génère. Voir [Diagnostiquer un acme.json cassé](../methodes/traefik-debug-acme-json.md).

## ACME ailleurs que pour Traefik

Le protocole étant standard, tu peux émettre des certs Let's Encrypt avec :

- `certbot` directement sur une machine
- `acme.sh` (shell pur, très portable, idéal sur des routeurs/NAS)
- `lego` en CLI (le moteur de Traefik, utilisable seul)
- Caddy (intégré)
- step-ca en client (pour faire du relai)

Et tu peux même monter **ta propre CA interne qui parle ACME** avec `step-ca` ou `smallstep`. Tu auras alors un Let's Encrypt privé pour ton réseau.

## À retenir

- ACME = automatisation de l'émission de certs, standardisée (RFC 8555).
- Let's Encrypt = la CA gratuite la plus utilisée, certs valides **90 jours**.
- Trois challenges : **HTTP-01** (simple), **DNS-01** (seul à supporter le wildcard), **TLS-ALPN-01** (niche).
- **Toujours debug en staging** pour éviter les rate limits.
- Dans Traefik, l'ACME se configure via un **certresolver** dans la config statique.
- `acme.json` est l'état central — permissions 600, sauvegarde recommandée.

## Pour aller plus loin

- [Traefik + Let's Encrypt DNS challenge](../methodes/traefik-letsencrypt-dns-challenge.md)
- [Diagnostiquer un acme.json cassé](../methodes/traefik-debug-acme-json.md)
- RFC 8555 — la spec ACME elle-même
- [letsencrypt.org/docs](https://letsencrypt.org/docs/) — doc officielle, claire et à jour
