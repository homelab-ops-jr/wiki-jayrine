# Manuel de génération des cartes d'entraînement

Ce document définit la **philosophie pédagogique** et les **règles de design** 
à appliquer quand on génère des cartes Anki pour le wiki. La convention 
syntaxique est dans `convention-cartes.md` ; ce manuel-ci décrit ce que les 
cartes doivent contenir et pourquoi.

## L'objectif réel

L'utilisateur (Pezd) prépare une **compétence opérationnelle d'admin réseau / 
homelab**, pas un QCM scolaire. Le jour où il aura un problème de production, 
il devra **localiser un problème, mobiliser des faits, choisir un outil**. 
C'est à ça que les cartes doivent l'entraîner.

Conséquence : il ne suffit pas de réciter des faits. Il faut aussi savoir 
expliquer un mécanisme et diagnostiquer une situation.

## L'école pédagogique choisie

On utilise une approche **hybride à trois niveaux cognitifs**, inspirée de la 
taxonomie de Bloom appliquée aux compétences techniques. Pour chaque page de 
notion, on génère trois types de cartes distincts.

### Type A — Faits atomiques

Une carte = **un seul fait**, indivisible. La question est courte, la réponse
est courte (souvent une ligne).

Exemples :
- "Quel port utilise HTTPS ?" → "443."
- "Quelle est la taille d'une adresse MAC ?" → "48 bits."
- "Quel EtherType identifie IPv6 ?" → "`0x86DD`."

Règles pour Type A :
- Une carte par fait. Ne pas regrouper "Quels sont les ports HTTPS, SSH, DNS ?" en une seule carte — ça doit être 3 cartes.
- Exception : les énumérations ordonnées qui forment un tout indissociable 
  (les 7 couches OSI, le 5-tuple TCP). Ces énumérations sont **une seule carte** 
  avec liste numérotée en réponse.
- Réponse sèche, 1 ligne. Pas de commentaire additionnel sauf si une nuance 
  technique est indispensable (genre `traceroute` vs `mtr`).

### Type B — Concepts

Une carte = **une explication de mécanisme**. Question commence souvent par 
"Pourquoi", "Comment", "Explique", "Quelle est la différence entre".

Exemples :
- "Pourquoi une trame Ethernet ne traverse jamais un routeur ?"
- "Explique la différence entre TCP et UDP."
- "Quelle est la différence entre middleware via labels Docker et via fileProvider ?"

Règles pour Type B :
- Réponse en 2 à 5 phrases, idéalement avec un cas concret ou une analogie.
- Ajouter des compléments pédagogiques qui aident à relier ce concept à d'autres 
  (ex : "C'est aussi pour ça que la MAC source change à chaque saut visible 
  dans traceroute, alors que l'IP source reste la même").
- Utiliser des paragraphes séparés par des lignes vides pour la lisibilité 
  visuelle (un paragraphe = une idée).
- Mettre en **gras** les notions clés (TCP, UDP, MAC, etc.) pour que l'œil 
  attrape les ancres.

### Type C — Diagnostic / application

Une carte = **une situation → une action**. Format "tu vois X, où cherches-tu ?".

Exemples :
- "Tu obtiens `Connection refused` sur un port — couche probable et premier outil ?"
- "Tu obtiens HTTP 502 Bad Gateway — couche et où chercher ?"
- "Tu veux protéger Authelia elle-même contre un brute-force. Quelle architecture de chaîne ?"

Règles pour Type C :
- La question pose un symptôme ou un objectif opérationnel.
- La réponse donne la couche/cause probable, l'outil à utiliser en premier, 
  et une justification courte.
- Si possible, mentionner les pièges (ex : "vérifier d'abord côté serveur que 
  le service écoute, sinon problème applicatif").

### Sous-catégorie de Type A — Outils

Quand la page documente des commandes ou outils, créer une carte par commande 
importante. Format : recto demande la commande, verso donne la commande dans 
un bloc de code + une ligne d'explication des flags.

Exemple :
```
??? question "Quelle commande pour lister les ports en écoute avec le processus associé ?"
    ​```bash
    ss -tlnp
    ​```
    
    `-t` TCP, `-l` listening, `-n` numérique (pas de DNS), `-p` processus. Pour UDP : `ss -ulnp`.
```

## Granularité des cartes

Principe directeur : **une carte teste une chose**.

Si la question implique de retenir 7 éléments dans le désordre, c'est 7 cartes.
Si la question implique de retenir 7 éléments **dans l'ordre** comme un tout 
(couches OSI), c'est 1 carte (le tout est indissociable).
Si la question demande "explique X et donne un exemple", c'est probablement 1 
carte de Type B.

En cas de doute sur la granularité, préférer **plus de petites cartes** que 
moins de grosses. Une carte ratée à cause d'1 élément sur 5 est frustrante.

## Couverture d'une page

Pour une page de notion typique (300-500 lignes), viser **entre 25 et 60 cartes**. 
Au-delà, la page est trop dense ou trop atomisée. En deçà, on ne couvre 
probablement pas assez.

Couvrir toutes les sections substantielles de la page. Une section "Pour aller 
plus loin" ou des liens vers d'autres fiches ne génère pas de cartes — c'est 
de la navigation, pas du contenu à mémoriser.

Les tableaux du type "symptôme → couche → outil" doivent **chacun** devenir une 
carte de Type C (une ligne du tableau = une carte).

Les schémas ASCII (diagrammes OSI, matriochkas d'encapsulation) sont source 
de cartes Type B "décris X" — la réponse formalise en texte ce que le schéma 
montre visuellement.

## Style et ton

- Tutoiement systématique dans les questions et réponses (l'utilisateur est 
  seul utilisateur).
- Pas de jargon scolaire ("nous allons voir", "il convient de noter").
- Ton direct, factuel, parfois technique. Comme un mentor expérimenté qui 
  briefe rapidement.
- Pas d'emojis.
- Code inline avec backticks pour : noms de commandes, noms de protocoles 
  techniques, valeurs hex, noms de fichiers/variables.
- Gras pour les notions clés et les éléments à retenir absolument.
- Numéros de port et de protocole bruts (443, 22, 53) pas en code inline.
- Valeurs hex en code inline (`0x0800`).

## Sources interdites et arbitrages

- Ne JAMAIS inventer de contenu absent de la page source. Si un fait pourrait 
  aider mais n'est pas dans la page, signaler le manque plutôt que combler.
- Ne pas extrapoler depuis une autre page du wiki pour enrichir une réponse.

## Pas de doublons entre pages

Chaque carte existe à **un seul endroit** dans l'ensemble du deck. La première 
page qui aborde un fait, un concept ou une commande l'incorpore ; les pages 
suivantes le mentionnent éventuellement en prose mais **ne le re-cartisent pas**.

Pour vérifier : la knowledge base contient toutes les pages déjà cartisées du 
wiki. Avant de proposer une carte, vérifier qu'aucune carte équivalente n'existe 
déjà dans une page de la knowledge base.

Si la couverture est ambiguë (par exemple "le format hex d'une MAC" est mentionné 
dans page 01 mais sans carte dédiée, et la page courante en parle plus en détail), 
**demander explicitement à l'utilisateur** dans la phase 1 plutôt que décider 
unilatéralement.

## En cas de subjectivité, demander

Pour toute carte dont la pertinence est subjective, **ne pas trancher seul**. 
Inclure la carte dans la liste de la phase 1 avec un point d'interrogation 
explicite et une justification courte.

Cas typiques où l'on doit demander plutôt que décider :

- **Faits historiques / RFC** : "RFC 826 définit ARP" — utile pour la culture 
  technique mais rarement mobilisé en pratique. Inclure et demander.
- **Mécanismes anciens ou rares** : "Proxy ARP est un vieux mécanisme rarement 
  utilisé" — peut tomber en diagnostic d'une bizarrerie. Inclure et demander.
- **Constantes numériques peu mémorables** : capacité MAC table, timeouts ARP 
  par défaut — utile en troubleshooting mais peu marquant. Inclure et demander.
- **Comparaisons de gammes** : "home vs entreprise", "ancien vs récent" — 
  pertinent ou pas selon le contexte d'usage de l'utilisateur. Inclure et 
  demander.

Format de la mention dans la phase 1 :

> - **[A14]** Quels RFC définissent ARP et le bridging ? — RFC 826, IEEE 802.1D 
>   **⚠ utilité subjective**, à confirmer

## Cartes de synthèse

Quand plusieurs cartes Type A ou Type B couvrent des aspects d'un même 
mécanisme, **proposer en plus** une carte Type B de synthèse qui demande 
d'articuler l'ensemble.

Exemple : si on a `[B1]` "Comment un switch apprend ?", `[B2]` "Que fait un 
switch d'une trame inconnue ?", `[B3]` "Résume les 3 comportements de 
transfert" — proposer en plus `[B-syn]` "Décris le scénario complet 
d'apprentissage du switch sur 2 trames successives" qui force à mobiliser 
les 3 cartes ensemble.

Ces cartes de synthèse sont **additionnelles**, pas substitutives. Les cartes 
atomiques sous-jacentes restent toutes.

Indicateur visuel : nommer la carte de synthèse `[B-syn-N]` au lieu de `[BN]` 
pour qu'elle soit reconnaissable.

## Process de génération en deux temps

Toute génération de cartes pour une page suit obligatoirement ce process :

**Étape 1 — Liste en prose, classée par catégorie.**

Le modèle liste les cartes qu'il identifie, organisées en 4 catégories 
(Faits & terminologie / Concepts / Diagnostic / Outils). Format de chaque 
ligne : `[ID] question — courte motivation`. Pas de réponses à ce stade.

Exemple :
> Faits & terminologie
> - A1. Combien de couches a le modèle OSI ? — fait atomique fondamental
> - A2. Cite les 7 couches OSI dans l'ordre. — énumération ordonnée
> - A3. À quelle couche correspond Ethernet ? — fait par couche
> ...
> 
> Concepts
> - B1. Pourquoi une trame Ethernet ne traverse pas un routeur ? — concept central
> ...

**Étape 2 — Attendre validation explicite.**

Le modèle s'arrête après l'étape 1 et demande à l'utilisateur de valider, 
amender, ou retirer des cartes. Il ne génère JAMAIS la syntaxe Markdown 
avant validation.

**Étape 3 — Génération syntaxique.**

Une fois l'utilisateur OK, le modèle génère la section `## Cartes d'entraînement` 
complète, prête à coller en fin de la page Markdown source. Respecter strictement 
la syntaxe documentée dans `convention-cartes.md`.

## Tableau de référence

| Caractéristique | Type A (Faits) | Type B (Concepts) | Type C (Diagnostic) | Outils |
|---|---|---|---|---|
| Longueur question | très courte | moyenne (1-2 lignes) | moyenne, scénarisée | courte |
| Longueur réponse | 1 ligne | 2-5 phrases | 2-4 phrases | code + 1 ligne |
| Granularité | atomique | un mécanisme | une situation | une commande |
| Nombre typique par page | 15-30 | 5-15 | 3-10 | 0-10 selon page |
