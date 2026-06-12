# Méthode — Forcer le renouvellement d'un certificat Traefik

> **Type** : Méthode · **Outil** : Traefik v3 · **Difficulté** : ⭐ Débutant

## Quand l'utiliser

- **Test post-config** : tu viens de modifier la config ACME, tu veux voir si l'émission marche
- **Suspicion de compromission** de la clé privée d'un cert
- **Cert expiré** ou trop proche de l'expiration sans renouvellement automatique
- **Changement de SAN** : ajout/retrait d'un domaine sur un cert existant
- **Debug** : tu veux forcer Traefik à refaire un challenge complet
- **Migration** : tu passes de HTTP challenge à DNS challenge (ou inversement) et veux régénérer les certs

⚠️ Avant de forcer, **toujours commencer en staging** Let's Encrypt pour ne pas griller les rate limits (cf. [HTTP challenge](./traefik-letsencrypt-http-challenge.md#rate-limits-lets-encrypt-a-connaitre)).

## Comprendre le mécanisme

Traefik renouvelle automatiquement les certs **30 jours avant expiration** par défaut. Cet automatisme est suffisant pour la routine, mais ne permet pas de forcer un renouvellement à la demande.

Le contenu de l'`acme.json` est ce qui guide Traefik : si un cert valide pour un domaine est dans le fichier, Traefik le sert ; sinon, il le demande à Let's Encrypt.

🔑 **Forcer un renouvellement = supprimer l'entrée du cert dans `acme.json` et redémarrer Traefik**.

## Procédure pas à pas

### Étape 1 — Localiser et sauvegarder `acme.json`

```bash
# Localisation typique
ls -la /data/services/traefik/letsencrypt/acme.json

# Sauvegarde de sécurité avant manipulation
cp /data/services/traefik/letsencrypt/acme.json \
   /data/services/traefik/letsencrypt/acme.json.bak-$(date +%Y%m%d-%H%M%S)
```

⚠️ La sauvegarde est essentielle. Si tu casses la structure JSON, tu perds **tous les certs** d'un coup, pas seulement celui ciblé.

### Étape 2 — Identifier l'entrée à supprimer

```bash
sudo jq '.letsencrypt.Certificates[] | {domain: .domain, store: .Store}' \
  /data/services/traefik/letsencrypt/acme.json
```

(Le nom `letsencrypt` correspond au nom du certresolver dans `traefik.yml` — adapter si différent.)

Sortie type :
```json
{
  "domain": { "main": "app.example.com", "sans": null },
  "store": "default"
}
{
  "domain": { "main": "wiki.example.com", "sans": ["www.wiki.example.com"] },
  "store": "default"
}
```

### Étape 3 — Supprimer l'entrée du domaine

**Option A — Tout supprimer (rare, à utiliser uniquement pour un reset complet)** :

```bash
echo '{}' | sudo tee /data/services/traefik/letsencrypt/acme.json
sudo chmod 600 /data/services/traefik/letsencrypt/acme.json
```

⚠️ Cela supprime aussi la clé du **compte ACME** — au prochain démarrage, Traefik créera un nouveau compte. Pas un problème en soi, mais évitable.

**Option B — Supprimer un cert précis (recommandé)** :

```bash
sudo jq 'del(.letsencrypt.Certificates[] | select(.domain.main == "app.example.com"))' \
  /data/services/traefik/letsencrypt/acme.json | sudo tee /tmp/acme-new.json

# Vérifier le résultat
sudo jq '.letsencrypt.Certificates[].domain.main' /tmp/acme-new.json

# Si OK, remplacer
sudo mv /tmp/acme-new.json /data/services/traefik/letsencrypt/acme.json
sudo chmod 600 /data/services/traefik/letsencrypt/acme.json
```

### Étape 4 — Redémarrer Traefik (pas restart)

```bash
cd /data/services/traefik
docker compose down && docker compose up -d
```

⚠️ `docker compose restart` peut ne pas suffire selon les versions. Toujours `down && up` pour être certain.

### Étape 5 — Vérifier le nouveau cert

```bash
# Suivre les logs en temps réel
docker compose logs -f traefik | grep -iE 'acme|certificate'

# Attendre ~30 secondes le temps du challenge

# Vérifier la nouvelle date d'émission
openssl s_client -connect app.example.com:443 -servername app.example.com </dev/null 2>/dev/null \
  | openssl x509 -noout -dates -issuer
```

`notBefore` doit être très récent → cert renouvelé. Si l'`issuer` mentionne **STAGING**, tu es encore en staging — repasser en prod.

➡️ Voir [Inspecter et valider un certificat](./openssl-inspecter-valider-cert.md) pour les détails de vérification.

## Méthode "en staging d'abord" — recommandée

Pour éviter de griller les rate limits LE en cas de problème :

### 1. Passer le certresolver en staging

Dans `traefik.yml` :
```yaml
certificatesResolvers:
  letsencrypt:
    acme:
      email: admin@example.com
      storage: /letsencrypt/acme.json
      caServer: https://acme-staging-v02.api.letsencrypt.org/directory  # ← ajouter
      httpChallenge:
        entryPoint: web
```

### 2. Vider `acme.json`

```bash
echo '{}' | sudo tee /data/services/traefik/letsencrypt/acme.json
sudo chmod 600 /data/services/traefik/letsencrypt/acme.json
```

(Le passage de prod → staging requiert un reset complet, les deux comptes sont distincts côté LE.)

### 3. Redémarrer et observer

```bash
docker compose down && docker compose up -d
docker compose logs -f traefik | grep -iE 'acme|certificate'
```

Les certs émis seront **non reconnus par les navigateurs** (warning HTTPS attendu), mais ils valident que la mécanique fonctionne sans consommer les rate limits prod.

### 4. Repasser en prod

- Retirer la ligne `caServer` dans `traefik.yml`
- Vider à nouveau `acme.json`
- `docker compose down && up`

## Forcer le renouvellement sans tout casser (script)

Pour automatiser, un petit script :

```bash
#!/bin/bash
# force-renew.sh — force le renouvellement d'un cert Traefik
set -euo pipefail

DOMAIN="${1:?Usage: $0 <domain>}"
ACME_FILE="/data/services/traefik/letsencrypt/acme.json"
RESOLVER_NAME="letsencrypt"
TRAEFIK_DIR="/data/services/traefik"

if [[ ! -f "$ACME_FILE" ]]; then
  echo "Erreur : $ACME_FILE introuvable"
  exit 1
fi

# Sauvegarde
cp "$ACME_FILE" "${ACME_FILE}.bak-$(date +%Y%m%d-%H%M%S)"

# Suppression de l'entrée
jq --arg dom "$DOMAIN" --arg res "$RESOLVER_NAME" \
  'del(.[$res].Certificates[] | select(.domain.main == $dom))' \
  "$ACME_FILE" > "${ACME_FILE}.new"

mv "${ACME_FILE}.new" "$ACME_FILE"
chmod 600 "$ACME_FILE"

# Redémarrage Traefik
(cd "$TRAEFIK_DIR" && docker compose down && docker compose up -d)

echo "Renouvellement initié pour $DOMAIN. Vérifie les logs :"
echo "  docker compose -f $TRAEFIK_DIR/docker-compose.yml logs -f traefik | grep -i acme"
```

Usage :
```bash
sudo ./force-renew.sh app.example.com
```

## Cas particuliers

### Changement d'email du compte ACME

Pour changer l'adresse de contact du compte LE, modifier `email:` dans `traefik.yml` ne suffit pas — le compte LE garde l'ancien email. Pour forcer un nouveau compte :

```bash
# Reset complet de acme.json
echo '{}' | sudo tee /data/services/traefik/letsencrypt/acme.json
sudo chmod 600 /data/services/traefik/letsencrypt/acme.json
# docker compose down && up
```

### Renouvellement après ajout d'un SAN

Tu as ajouté un domaine à la rule d'un router :
```yaml
- "traefik.http.routers.app.tls.domains[0].sans=newdomain.example.com"
```

Traefik **ne renouvelle pas automatiquement** le cert pour inclure ce nouveau SAN — il considère qu'il a déjà un cert pour le domaine principal. Forcer le renouvellement comme ci-dessus.

### Migration HTTP → DNS challenge

Tu passes d'un certresolver HTTP à DNS pour ajouter des wildcards :

1. Ajouter le nouveau certresolver dans `traefik.yml` :
```yaml
certificatesResolvers:
  letsencrypt:
    acme:
      # ... ancien HTTP challenge
  letsencrypt-dns:
    acme:
      email: admin@example.com
      storage: /letsencrypt/acme-dns.json
      dnsChallenge:
        provider: cloudflare
```
2. Sur les routers concernés : `tls.certresolver=letsencrypt-dns`
3. Pas besoin de vider `acme.json` — Traefik émettra des certs sous le nouveau resolver, séparément.

## Pièges fréquents

| Symptôme | Cause |
|----------|-------|
| Cert non renouvelé après suppression | `docker compose restart` au lieu de `down && up` |
| `urn:ietf:params:acme:error:rateLimited` | Trop de tentatives — attendre, basculer en staging |
| `unable to obtain ACME certificate: timeout` | Port 80 fermé (HTTP) ou clés API DNS invalides (DNS) |
| acme.json corrompu après édition | JSON mal formé — restaurer le `.bak` |
| Tous les certs régénérés au lieu d'un seul | `del()` jq avec sélecteur trop large, ou reset complet |
| Cert "Traefik default" servi après renouvellement | L'émission a échoué — voir [debug acme.json](./traefik-debug-acme-json.md) |
| L'ancien cert toujours servi malgré renouvellement | Cache navigateur ou intermédiaire — tester avec `openssl s_client` |
| `permissions are not 0600` après édition | `chmod 600 acme.json` |

## À retenir

- Forcer un renouvellement = **supprimer l'entrée dans `acme.json`** et redémarrer.
- **Toujours sauvegarder** `acme.json` avant de l'éditer.
- Préférer la suppression ciblée (`jq del`) à un reset complet, sauf changement de compte.
- **Tester en staging** d'abord pour ne pas griller les rate limits.
- `docker compose down && up`, pas `restart`.

## Pour aller plus loin

- [Méthode : Diagnostiquer un acme.json cassé](./traefik-debug-acme-json.md)
- [Méthode : Traefik + Let's Encrypt DNS challenge](./traefik-letsencrypt-dns-challenge.md)
- [Méthode : Traefik + Let's Encrypt HTTP challenge](./traefik-letsencrypt-http-challenge.md)
- [ACME & Let's Encrypt](../notions/05-acme-letsencrypt.md)
- [Inspecter et valider un certificat](./openssl-inspecter-valider-cert.md)
- [Let's Encrypt rate limits](https://letsencrypt.org/docs/rate-limits/)
