# ---------- Stage 1 : build du site statique ----------
FROM python:3.12-alpine AS builder

WORKDIR /docs

# Dépendances système minimales pour les plugins (cairo pour les icônes SVG, etc.)
RUN apk add --no-cache --virtual .build-deps \
    gcc musl-dev libffi-dev

# Installation MkDocs Material + plugins
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code source du wiki
COPY mkdocs.yml .
COPY docs/ ./docs/

# Build (--strict fait échouer le build sur tout warning : liens cassés, fichiers orphelins, etc.)
RUN mkdocs build --strict --site-dir /site

# ---------- Stage 2 : serveur nginx non-privilégié ----------
FROM nginxinc/nginx-unprivileged:1.27-alpine

# Configuration nginx custom
COPY --chown=nginx:nginx nginx.conf /etc/nginx/conf.d/default.conf

# Contenu statique
COPY --from=builder --chown=nginx:nginx /site /usr/share/nginx/html

# nginx-unprivileged écoute sur 8080 par défaut (pas besoin de capabilities)
EXPOSE 8080

# 127.0.0.1 explicite (cf. learning Traefik : éviter les confusions IPv4/IPv6 avec localhost)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://127.0.0.1:8080/ || exit 1
