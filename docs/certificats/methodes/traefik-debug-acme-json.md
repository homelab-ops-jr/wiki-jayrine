# Méthode — Diagnostiquer un `acme.json` cassé dans Traefik

> **Type** : Méthode · **Outil** : Traefik v3 · **Difficulté** : ⭐⭐ Intermédiaire

## Quand l'utiliser

- Traefik démarre mais ne sert que son cert auto-signé (`TRAEFIK DEFAULT CERT`)
- Aucun cert ne se génère / renouvelle, **ou bien il y a une erreur dans les logs**
- Tu viens de migrer staging → prod et le navigateur dit "not secure"
- Tu as changé d'email ACME ou de provider et plus rien ne marche

## Avant de tout casser : sauvegarder

```bash
cp letsencrypt/acme.json letsencrypt/acme.json.bak-$(date +%F)
```

`acme.json` contient ta **clé de compte ACME** et tous tes certs valides. Le perdre = repartir de zéro (+1 émission consommée du rate limit).

## Diagnostic : lire `acme.json` proprement

Le fichier est en JSON sur une seule ligne (parfois). Pour le rendre lisible :

```bash
sudo cat letsencrypt/acme.json | jq .
```

Sortie typique (extrait simplifié) :
```json
{
  "myresolver": {
    "Account": {
      "Email": "admin@example.com",
      "Registration": { ... },
      "PrivateKey": "...base64..."
    },
    "Certificates": [
      {
        "domain": {
          "main": "example.com",
          "sans": ["*.example.com"]
        },
        "certificate": "...base64...",
        "key": "...base64..."
      }
    ]
  }
}
```

Points à vérifier :
- `"myresolver"` est bien la clé racine (= nom de ton certresolver dans `traefik.yml`)
- `Account.Email` correspond bien à ce que tu as configuré
- `Certificates[].domain.main` et `.sans` couvrent ce que tu attends
- Le tableau `Certificates` n'est pas vide ou `null`

### Cas 1 — `acme.json` vide ou contenant juste `{}`

C'est le cas après création initiale du fichier, ou après suppression manuelle.

**À vérifier dans les logs au démarrage** :
```bash
docker compose logs traefik | grep -i -E 'acme|certif|error|warn' | head -50
```

Recherche les erreurs explicites. Cas typiques :

#### `the permissions on /letsencrypt/acme.json are too open`
```bash
chmod 600 letsencrypt/acme.json
docker compose restart traefik
```

#### `cannot retrieve credentials from environment`
Le provider DNS ne reçoit pas ses credentials. Vérifier :
```bash
docker compose exec traefik env | grep -E 'OVH_|CF_'
```
Si vide → l'`env_file` n'est pas chargé. Vérifier `secrets.sops.env` déchiffré, le chemin dans `docker-compose.yml`, et que le compose a bien été appliqué (`docker compose up -d`, pas `docker restart`).

#### `acme: error: 400 :: urn:ietf:params:acme:error:rejectedIdentifier`
Le domaine demandé n'est pas autorisé pour ton compte (mauvaise zone DNS chez le provider, ou domaine inexistant).

#### `cannot get ACME client: account does not exist`
Tu utilises un email différent de celui avec lequel le compte a été créé. Soit revenir à l'email d'origine, soit vider `acme.json` pour repartir d'un nouveau compte.

### Cas 2 — `acme.json` contient un compte staging

Symptôme : le cert généré est valide mais l'issuer est `(STAGING) Pretend Pear X1` ou similaire.

Cause : `caServer:` pointait vers staging, ou tu n'as pas vidé `acme.json` en passant à la prod.

**Solution** :
```bash
docker compose stop traefik
mv letsencrypt/acme.json letsencrypt/acme.json.staging-bak
touch letsencrypt/acme.json
chmod 600 letsencrypt/acme.json
# Vérifier que caServer staging est commenté/retiré dans traefik.yml
docker compose up -d traefik
```

Traefik recrée un compte ACME en prod et un nouveau cert.

### Cas 3 — Fichier corrompu (JSON invalide)

Symptôme : Traefik râle au démarrage avec `unable to parse acme.json` ou `unexpected end of JSON input`.

```bash
sudo cat letsencrypt/acme.json | jq . > /dev/null
# Si erreur → fichier mal formé
```

Causes possibles :
- Coupure brutale pendant écriture (kill -9, host crash)
- Édition manuelle à la main qui a oublié une virgule

**Solution** :
- Restaurer depuis backup (`acme.json.bak-…`)
- Si pas de backup : repartir de zéro (vider et redémarrer)

### Cas 4 — Certs présents mais Traefik ne les sert pas

Symptôme : `acme.json` contient bien le cert pour `example.com`, mais `curl https://example.com` retourne le cert par défaut Traefik.

**À vérifier** :

1. **Le nom dans les SAN du router matche-t-il celui dans acme.json ?**
   ```bash
   sudo jq '.myresolver.Certificates[].domain' letsencrypt/acme.json
   ```
   Si ton router demande `app.example.com` et que le cert contient `*.other.com`, pas de match.

2. **Le router a-t-il bien `tls.certresolver=myresolver` ?**
   ```bash
   docker compose exec traefik traefik show config 2>/dev/null
   # ou via le dashboard si activé
   ```

3. **Un cert statique fileProvider prend-il le dessus ?** Si tu as un `tls.certificates` qui couvre le hostname, le fileProvider gagne sur l'ACME.

### Cas 5 — Renouvellement bloqué

Traefik renouvelle automatiquement à 30 jours avant expiration. Si un cert reste vieux :

1. **Lire `acme.json`** : la date d'expiration y est-elle encore lointaine ? Si oui, normal qu'il ne renouvelle pas.

2. **Forcer le renouvellement** d'un cert spécifique :
   - Méthode propre : éditer `acme.json` et supprimer le bloc du cert concerné
   - Méthode simple : vider `acme.json` complètement (recrée tout)

3. **Vérifier le rate limit** : si tu as déjà fait 5 émissions cette semaine pour le même domaine, Let's Encrypt refuse. Attendre, ou passer en staging pour le debug.

### Cas 6 — Email ACME à changer

Modifier dans `traefik.yml` :
```yaml
certificatesResolvers:
  myresolver:
    acme:
      email: nouveau@example.com  # ← changement
```

⚠️ Le compte ACME existant est lié à l'ancien email. Traefik va probablement refuser de l'utiliser avec le nouveau. Deux options :

- **Garder le compte, juste changer le contact** : nécessite un appel ACME `account update`, non géré par Traefik à ma connaissance → vider `acme.json`.
- **Repartir d'un compte neuf** : vider `acme.json`, Traefik crée un nouveau compte avec le nouvel email.

Dans tous les cas, vider `acme.json` est la solution la plus simple. Coût : 1 émission de cert (rate limit), pas dramatique.

## Commandes utiles de debug

### Lister tous les certs présents dans acme.json

```bash
sudo jq -r '.myresolver.Certificates[] | "\(.domain.main) (SANs: \(.domain.sans // []))"' letsencrypt/acme.json
```

### Voir la date d'expiration d'un cert dans acme.json

```bash
sudo jq -r '.myresolver.Certificates[] | select(.domain.main=="example.com") | .certificate' letsencrypt/acme.json \
  | base64 -d \
  | openssl x509 -noout -enddate
```

### Suivre les tentatives ACME en direct

```bash
docker compose logs -f traefik | grep -i 'acme\|certif\|challenge'
```

### Tester un certresolver en isolation (Traefik dashboard)

Si le dashboard Traefik est activé (`api.dashboard: true` dans la config statique), aller dans `https://traefik.example.com/dashboard/#/http/services` pour voir l'état des certs et routers en temps réel.

## Bonnes pratiques préventives

- **Sauvegarder `acme.json`** régulièrement (intégrer dans la stratégie Restic à venir)
- **Toujours debug en staging** avant la prod
- **Vérifier `chmod 600`** dans une checklist de déploiement
- **Ne pas committer `acme.json`** dans Git (contient ta clé de compte ACME et tes clés privées de cert)
- **Documenter quel certresolver fait quoi** si tu en as plusieurs (rare)

## Quand tout est cassé : reset complet

Procédure nucléaire :

```bash
# 1. Stop Traefik
docker compose stop traefik

# 2. Backup au cas où
mv letsencrypt/acme.json letsencrypt/acme.json.backup-$(date +%F-%H%M)

# 3. Fichier vierge
touch letsencrypt/acme.json
chmod 600 letsencrypt/acme.json

# 4. Optionnel : passer en staging pour vérifier que la conf est bonne
# Décommenter caServer: https://acme-staging-v02.api.letsencrypt.org/directory dans traefik.yml

# 5. Restart
docker compose up -d traefik

# 6. Observer
docker compose logs -f traefik | grep -i acme

# 7. Si staging OK → recommenter caServer, vider à nouveau acme.json, restart pour prod
```

Coût : 1 cert reconstruit (rate limit), 5 minutes.

## À retenir

- `acme.json` = état complet du certresolver. Backup. `chmod 600`. Pas dans Git.
- 90 % des problèmes se diagnostiquent dans les logs Traefik (`grep -i acme`).
- Quand le doute s'installe : **vider et repartir** est souvent plus rapide que comprendre.
- **Toujours debug en staging** — c'est gratuit, illimité, et ça évite les rate limit.
- `docker restart` ≠ `docker compose down && up` : seul le second relit `.env` et la config statique.

## Voir aussi

- [Traefik + Let's Encrypt DNS challenge](./traefik-letsencrypt-dns-challenge.md)
- [Notion : ACME & Let's Encrypt](../notions/05-acme-letsencrypt.md)
