# Convention — cartes d'entraînement Anki

Ce document décrit comment les **cartes d'entraînement** sont rédigées dans le wiki, et comment elles sont automatiquement extraites pour générer un deck Anki que je révise sur mobile.

## Principe

Chaque page de notion (`docs/<sujet>/notions/*.md`) peut contenir une section finale `## Cartes d'entraînement`. Les cartes y sont écrites sous forme de **blocs dépliables** qui :

- s'affichent comme un mini-quizz auto-évaluatif sur le site,
- sont automatiquement exportées vers Anki par un script CI à chaque commit.

## Syntaxe d'une carte

Une carte est une admonition `pymdownx.details` de type `question`, repliée par défaut (`???`, pas `???+`) :

````markdown
??? question "Le texte de la question, qui apparaît au recto"
    La réponse au verso, indentée de 4 espaces.
    
    Peut contenir plusieurs paragraphes, du **gras**, de l'`inline code`, etc.
````

### Plusieurs paragraphes dans la réponse

Séparer par une ligne vide, en conservant l'indentation à 4 espaces :

````markdown
??? question "..."
    Premier paragraphe.
    
    Deuxième paragraphe.
````

### Bloc de code dans la réponse

La fence ```` ``` ```` doit aussi être indentée à 4 espaces. Le contenu interne du code n'est pas indenté en plus. Seules les fences le sont :

````markdown
??? question "Quelle commande pour lister les ports en écoute ?"
```bash
    ss -tlnp
```
    
    `-t` TCP, `-l` listening, `-n` numérique, `-p` processus.
````

### Listes

Indentées normalement à 4 espaces, comme tout le reste de la réponse :

````markdown
??? question "Cite les 7 couches OSI."
    1. Physique
    2. Liaison
    3. Réseau
    4. Transport
    5. Session
    6. Présentation
    7. Application
````

## Emplacement dans la page

Toutes les cartes vont dans une section unique **en fin de page** :

````markdown
## Cartes d'entraînement

### Faits & terminologie

??? question "..."
    ...

### Concepts

??? question "..."
    ...

### Diagnostic

??? question "..."
    ...

### Outils

??? question "..."
    ...
````

Les sous-titres H3 (`### Faits & terminologie`, etc.) sont là pour la **lisibilité sur le site uniquement**. Le script d'extraction les ignore : toutes les cartes d'une page sont regroupées sous le même tag.

Les catégories suggérées sont :

- **Faits & terminologie** : faits atomiques, valeurs, définitions courtes
- **Concepts** : explications de mécanismes, comparaisons, "pourquoi"
- **Diagnostic** : situations "tu vois X, que cherches-tu", premier réflexe
- **Outils** : commandes pratiques

On peut ajouter, retirer ou renommer des catégories selon la page. Elles n'ont aucun effet technique.

## Métadonnées attendues

Pour qu'une page contribue des cartes au deck Anki, elle doit avoir, en plus de la section `## Cartes d'entraînement` :

1. **Un H1** (titre de la page) : sert au libellé "page d'origine" au verso des cartes.
2. **Une blockquote de méta-info** au début, dans le format :
   
````markdown
   > **Type** : Notion · **Sujet** : Réseau · **Prérequis** : ...
````
   
   Le champ `Sujet` sert à construire le tag Anki hiérarchique et le préfixe affiché au verso.

Les autres pages (méthodes, index) ne sont pas parsées par le script. Seuls les fichiers sous `docs/<sujet>/notions/*.md` sont considérés.

## Identifiant stable des cartes

Le script génère un **identifiant déterministe** par carte à partir de :

- le chemin du fichier (par exemple `reseau/notions/01-modele-osi-tcpip.md`)
- le texte exact de la question (entre guillemets)

Conséquences pratiques :

- **Reformuler la réponse** d'une carte la met à jour sans casser ton historique de révision Anki.
- **Reformuler la question** la crée comme une nouvelle carte (l'ancienne devient orpheline).
- **Déplacer une page** d'un dossier à un autre invalide tous les identifiants des cartes de cette page.

Donc : **reformuler les questions est un acte significatif**, à éviter une fois que la carte a été révisée plusieurs fois.

## Tags Anki et libellé au verso

Pour une carte vivant dans `docs/reseau/notions/01-modele-osi-tcpip.md` :

- **Tag Anki** : `reseau::notions::modele-osi-tcpip`. Permet de filtrer ses sessions par sujet ou par page.
- **Mention au verso** : `Réseau · 01 — Modèle OSI et TCP/IP`, affichée en gris discret sous la réponse.

Les deux sont générés automatiquement par le script. Rien à écrire à la main.

## En résumé

Pour ajouter une carte sur une page :

1. Aller dans la section `## Cartes d'entraînement` de la page.
2. Choisir une sous-section (`### Faits`, `### Concepts`, etc.) selon le type.
3. Écrire une admonition `??? question "..."` avec la réponse indentée.
4. Commit, push. Le workflow GitHub Actions régénère le deck et le synchronise vers le serveur Anki.

Si la page n'a pas encore de section `Cartes d'entraînement`, créer la section et un H3 selon les sous-sections suggérées.
