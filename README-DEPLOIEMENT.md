# Mise à jour wiki — sujet "Reverse proxy & routage"

Cette archive ajoute le sujet Reverse Proxy au wiki existant. Elle contient :
- `mkdocs.yml` — nouvelle version (remplace l'existante)
- `docs/index.md` — index racine mis à jour (reverse-proxy en 🟢 En cours)
- `docs/reverse-proxy/` — 13 nouvelles pages (1 index + 5 notions + 6 méthodes)

## Déploiement

Depuis la racine du repo `homelab-infra` :

```bash
# 1. Dézipper dans le stack wiki (overlay direct)
unzip /chemin/vers/wiki-reverse-proxy.zip -d stacks/wiki/

# 2. Vérifier que les fichiers existants ont bien été écrasés
git status stacks/wiki/

# 3. Test local optionnel (depuis stacks/wiki/)
cd stacks/wiki
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
mkdocs serve   # → http://127.0.0.1:8000

# 4. Commit + déploiement
git add stacks/wiki/
git commit -m "feat(wiki): add reverse proxy & routing topic"
git push

# Sur le serveur, en gitops :
./scripts/deploy.sh wiki
```

## Vérification
- `https://wiki.jayrine.com/reverse-proxy/` doit afficher l'index du sujet
- L'onglet "Reverse proxy" doit apparaître dans la nav du haut
- Tester la recherche sur "middleware" ou "X-Forwarded"
