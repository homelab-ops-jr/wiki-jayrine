# Stack — wiki

Wiki personnel d'admin réseau servi via MkDocs Material + nginx. URL : `https://wiki.jayrine.com`.

## Architecture

```
mkdocs.yml + docs/  ──build──►  site/ (HTML statique)  ──serve──►  nginx-unprivileged
                                        (multi-stage Dockerfile, image finale ~25 MB)
```

- **Build** : `python:3.12-alpine` + `mkdocs-material` → produit `/site` (HTML + CSS + JS + index de recherche).
- **Serve** : `nginxinc/nginx-unprivileged:alpine` qui sert `/site` sur le port 8080, derrière Traefik.
- **TLS** : certresolver `myresolver` (Let's Encrypt DNS challenge OVH, wildcard `*.jayrine.com` déjà présent).

## Structure

```
stacks/wiki/
├── docker-compose.yml      # service wiki, network proxy-tier, labels Traefik
├── Dockerfile              # multi-stage build → nginx
├── nginx.conf              # config nginx custom (security headers, cache, gzip)
├── mkdocs.yml              # config MkDocs Material (theme, plugins, nav)
├── requirements.txt        # mkdocs-material pinné
├── .dockerignore
├── .gitignore              # ignore site/ (build output local)
└── docs/                   # contenu du wiki (markdown)
    ├── index.md            # page d'accueil
    ├── stylesheets/
    │   └── extra.css       # surcharges CSS minimales
    └── certificats/
        ├── index.md
        ├── notions/
        └── methodes/
```

## Workflow d'édition

### Édition locale (Chromebook / Crostini)

Pour itérer rapidement sur le contenu **sans rebuilder l'image Docker** à chaque fois :

```bash
# Une fois : créer un venv local
cd stacks/wiki
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Puis : serveur de dev avec live reload
mkdocs serve
# → http://127.0.0.1:8000 — rebuild auto à chaque save
```

### Déploiement en production

Workflow GitOps habituel :

```bash
# 1. Commit les modifs (depuis Chromebook)
git add stacks/wiki/docs/
git commit -m "wiki: <description>"
git push

# 2. Déploiement sur le serveur (depuis le user gitops)
./scripts/deploy.sh wiki
# → pull du repo, docker compose build, docker compose up -d
```

Le `--strict` dans le Dockerfile fait échouer le build si un lien est cassé ou un fichier orphelin → le serveur refuse de déployer une version cassée.

## Première mise en route

### Pré-requis

- Network Docker `proxy-tier` existant (créé par le stack Traefik)
- DNS `wiki.jayrine.com` qui pointe vers `54.37.51.217` (CNAME ou A)
- Wildcard `*.jayrine.com` déjà couvert par Let's Encrypt côté Traefik

### Premier déploiement

```bash
# Sur le serveur
cd /data/services/wiki
docker compose build
docker compose up -d
docker compose logs -f wiki
```

Vérifier :
```bash
curl -I https://wiki.jayrine.com
# HTTP/2 200 attendu
```

## Sécurité

- Container nginx-unprivileged : tourne en non-root, écoute sur 8080 (pas de capability `NET_BIND_SERVICE` requise).
- Headers de sécurité activés dans `nginx.conf` (CSP, X-Frame-Options, Referrer-Policy, Permissions-Policy).
- Pas de secret dans l'image (rien à chiffrer avec SOPS pour ce stack).
- **Pour rendre le wiki privé** : décommenter le label `traefik.http.routers.wiki.middlewares=authelia@docker` dans `docker-compose.yml`.

## Maintenance

### Mettre à jour MkDocs Material

```bash
# 1. Bumper la version dans requirements.txt
# 2. Tester en local
source .venv/bin/activate
pip install -r requirements.txt --upgrade
mkdocs build --strict

# 3. Commit + deploy
```

### Inspecter le site buildé en local

```bash
mkdocs build
ls site/
# Le contenu peut être servi par n'importe quel serveur HTTP statique
```

### Reset complet du container

Pas de données persistantes (tout le contenu vient de l'image au build) :
```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

## À venir

- Pipeline CI dans Forgejo pour `mkdocs build --strict` à chaque PR (pré-validation des liens)
- Plugin `mkdocs-git-revision-date-localized` pour afficher la date de dernière modification de chaque fiche
- Plugin `mkdocs-redirects` si jamais on déplace des fiches (préserver les URLs)
