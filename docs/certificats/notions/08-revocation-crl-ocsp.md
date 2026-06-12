# 08 — Révocation : CRL, OCSP, et où on en est en 2026

> **Type** : Notion · **Sujet** : Certificats · **Prérequis** : [Chaîne de confiance & PKI](./03-chaine-de-confiance-pki.md), [Certificats X.509](./02-certificats-x509.md)

## En une phrase

Un certificat est émis pour une durée fixe, mais il peut devenir **invalide avant son expiration** (clé compromise, fin de contrat, erreur d'émission). Les mécanismes de **révocation** — CRL, OCSP, OCSP stapling, CT logs, certs courte durée — visent à propager rapidement cette information aux clients TLS. Le paysage **bouge fortement en 2025-2026**.

## Pourquoi révoquer

Cas classiques :

- **Clé privée compromise** : un attaquant l'a, peut désormais faire passer son serveur pour le tien
- **Domaine perdu** : le détenteur du DNS a changé, le cert ne devrait plus être valide
- **Émission erronée** : la CA a signé un cert qu'elle n'aurait pas dû
- **Fin de service** : un cert client mTLS d'un employé qui quitte l'entreprise

La révocation est l'**équivalent d'une carte d'identité invalidée** avant sa date d'expiration. La difficulté n'est pas de la déclarer (la CA peut), mais de **la faire connaître aux navigateurs et clients TLS**, partout, rapidement.

## Mécanisme 1 — CRL (Certificate Revocation List)

Le plus ancien. La CA publie une **liste de tous les certs révoqués**, signée par elle, à une URL connue.

```
GET https://crl.example-ca.com/example-ca.crl
→ Liste signée : [serial1, serial2, serial3, ...]
```

Chaque cert contient dans son extension `CRL Distribution Points` l'URL où trouver la CRL applicable :
```
X509v3 CRL Distribution Points:
    URI:http://crl.example-ca.com/example-ca.crl
```

### Avantages
- Simple à comprendre, mécanisme robuste
- Le client peut cacher la CRL et fonctionner offline

### Inconvénients
- **CRL volumineuse** : pour une grosse CA, la liste peut faire des **dizaines de mégaoctets**
- **Fraîcheur** : la CRL est typiquement mise à jour toutes les 24h, donc un cert révoqué peut rester accepté pendant un jour
- **Téléchargement** à chaque connexion (sauf cache local) : coûteux

En 2026, la CRL **n'est plus consultée par les navigateurs grand public** pour les certs end-entity. Elle reste utile pour les certs de CA (intermédiaires, racines), et dans certains contextes spécifiques (entreprises, mTLS interne).

## Mécanisme 2 — OCSP (Online Certificate Status Protocol)

Réponse à la lourdeur de la CRL : au lieu de télécharger toute la liste, le client **interroge la CA en temps réel** sur un cert précis.

```
Client → OCSP responder : "Le cert #serial XYZ est-il valide ?"
OCSP responder → Client : "good" / "revoked" / "unknown"
```

L'URL du responder est dans l'extension `Authority Information Access` du cert :
```
Authority Information Access:
    OCSP - URI:http://ocsp.example-ca.com
```

### Avantages
- Plus léger que la CRL (une question, une réponse)
- Information potentiellement plus fraîche

### Inconvénients majeurs
- **Latence supplémentaire** à chaque connexion TLS (un appel HTTP avant de finaliser le handshake)
- **Fuite de vie privée** : le responder de la CA voit **quels sites tu visites** (cert XYZ = site Z)
- **Single point of failure** : si le responder est down, fallback "soft-fail" (accepter le cert) ou "hard-fail" (rejeter) → en pratique les navigateurs font soft-fail, ce qui annule l'intérêt sécurité

## Mécanisme 3 — OCSP Stapling

Réponse aux limites d'OCSP. Le **serveur web lui-même** récupère périodiquement la réponse OCSP de son cert auprès de la CA, et l'agrafe (`staple`) à son handshake TLS :

```
Client → Serveur : ClientHello
Serveur → Client : Certificate + ServerKeyExchange + [OCSP Response signée] + ...
```

Le client n'a plus à interroger la CA — il a la réponse signée directement. Plus de fuite de vie privée, plus de latence, plus de SPOF.

### OCSP Must-Staple

Une extension X.509 (`tlsfeature`, OID 1.3.6.1.5.5.7.1.24) qui dit : "ce cert **doit** être servi avec stapling, sinon refuse-le". Évite le fallback soft-fail si le serveur ne staple pas.

Peu déployé en pratique — quelques CAs le proposent.

## Le grand virage 2025-2026 : Let's Encrypt arrête OCSP

En juillet 2024, Let's Encrypt a annoncé l'**arrêt progressif de son service OCSP** entre 2025 et 2026. Raisons :

- Coût d'infrastructure énorme (milliards de requêtes/jour)
- Problème de vie privée non résolu
- Les navigateurs modernes ne le consultent plus de toute façon

À partir de mai 2025, **les certs Let's Encrypt n'incluent plus de pointeur OCSP**. Le service est éteint courant 2026. Les CRLs continuent d'être publiées pour les cas spécifiques.

Conséquence concrète : **si tu comptais sur l'OCSP stapling avec Let's Encrypt, ce n'est plus possible**. Tu n'as plus besoin de configurer cette option dans Nginx/Apache pour les certs LE.

## La nouvelle approche : CRLite et certs courte durée

### CRLite (Mozilla)

Une compression cryptographique très efficace de l'ensemble des révocations connues, distribuée **dans le navigateur lui-même** (mises à jour fréquentes). Pas de requête à la CA à chaque visite.

Déployé dans Firefox depuis 2020, en pleine adoption ailleurs.

### Certs à durée de vie réduite

L'idée plus radicale : **réduire la durée de validité des certs**, pour que la révocation soit moins critique.

- Certs publics historiques : **825 jours** (~ 2 ans)
- Aujourd'hui : **398 jours** (~ 13 mois) — imposé par les navigateurs
- Let's Encrypt : **90 jours** par défaut, déjà depuis 2016
- **Apple a annoncé en 2025** un calendrier pour passer les certs publics à **47 jours** maximum d'ici 2029
- Let's Encrypt expérimente des certs de **6 jours** (programme "Short-Lived")

Idée : si un cert expire dans X jours et que la révocation prend Y jours à se propager, peu importe Y si X ≤ Y. La révocation devient quasi-inutile.

Coût : automatisation **obligatoire** (ACME devient un prérequis pour exister sur le web).

## CT logs comme complément

Les **Certificate Transparency logs** (cf. [chaîne de confiance](./03-chaine-de-confiance-pki.md)) ne sont **pas un mécanisme de révocation**, mais aident à **détecter** les certs mal émis. Si un attaquant convainc une CA d'émettre un cert pour ton domaine, ça apparaît dans les CT logs, tu peux le repérer et demander révocation.

Outils utiles :
- [crt.sh](https://crt.sh) — recherche dans les CT logs
- [Cert Spotter](https://sslmate.com/certspotter/) — alertes sur émission de cert pour ton domaine

## Comportement actuel des navigateurs (2026)

| Navigateur | CRL end-entity ? | OCSP ? | OCSP stapling consommé ? | Mécanisme principal |
|------------|-----------------|--------|------------------------|--------------------|
| Firefox | Non | Non (par défaut) | Oui | CRLite |
| Chrome | Non | Non (depuis 2012) | Oui | CRLSets (équivalent compact) |
| Safari | Variable | Limité | Oui | Liste propriétaire Apple |
| Edge | Suivi Chrome | Suivi Chrome | Oui | CRLSets |

🔑 **Conséquence pratique en 2026** : tu ne peux **pas compter** sur la révocation pour neutraliser rapidement un cert compromis vu du grand public. La défense en profondeur passe par :

1. **Durée de vie courte** des certs (LE 90j, plus court à venir)
2. **CT log monitoring** pour détecter les émissions illicites
3. **HPKP** déprécié, plus utilisé
4. **Réémission rapide** après compromission (révoquer + déployer un nouveau cert + faire expirer l'ancien naturellement)

## Comment révoquer un cert

### Cert Let's Encrypt
```bash
certbot revoke --cert-path /etc/letsencrypt/live/example.com/cert.pem \
  --reason keycompromise
```

Raisons valides : `unspecified`, `keycompromise`, `affiliationchanged`, `superseded`, `cessationofoperation`.

### Cert d'une CA interne (OpenSSL)
La CA interne maintient sa propre base de révocation et regénère sa CRL :
```bash
openssl ca -config openssl-ca.cnf -revoke /chemin/cert.pem
openssl ca -config openssl-ca.cnf -gencrl -out crl.pem
```

(Détails dans le workflow de la [CA interne](../methodes/openssl-creer-ca-interne.md).)

### Cert d'une CA commerciale
Via le portail web ou l'API du provider.

## Pièges et idées fausses fréquents

- **"J'ai révoqué, le cert ne sera plus accepté"** → faux pour le grand public en 2026. La révocation prend du temps à se propager, et beaucoup de clients ne consultent rien. Considère un cert révoqué comme **toujours techniquement utilisable par un attaquant** jusqu'à expiration.
- **"OCSP stapling améliore la sécurité"** → améliore les performances et la vie privée, pas vraiment la sécurité (le client doit toujours faire confiance à la réponse signée).
- **CRL très ancienne** : si la CRL n'est pas re-signée régulièrement, certains clients la rejettent comme "stale" et tombent en soft-fail.
- **"Mon cert est révoqué mais Chrome l'accepte"** : normal en 2026 pour les certs end-entity. Chrome consulte ses propres CRLSets (très réduits, ne contiennent que les révocations "majeures").
- **mTLS et révocation** : pour un cert client interne, la CRL/OCSP **est** consultée par certains serveurs/proxies. Bien la configurer dans un déploiement Zero Trust.

## À retenir

- **CRL** = liste signée, mécanisme historique, encore utilisé pour les CAs.
- **OCSP** = requête temps réel, en voie d'extinction côté Let's Encrypt et navigateurs.
- **OCSP stapling** = la version utilisable, mais elle aussi en déclin.
- **2026** = transition vers certs courte durée (90j → 47j → 6j) + CRLite + CT monitoring.
- **Ne compte pas sur la révocation pour réagir vite** à une compromission — préfère raccourcir les durées de vie.
- Pour les **PKIs internes** (mTLS, services internes), CRL/OCSP restent pertinents.

## Pour aller plus loin

- [Chaîne de confiance & PKI](./03-chaine-de-confiance-pki.md) — sur les CT logs et la transparence
- [ACME & Let's Encrypt](./05-acme-letsencrypt.md) — sur l'automatisation et les courtes durées de vie
- [Méthode : Forcer le renouvellement d'un cert Traefik](../methodes/traefik-forcer-renouvellement.md)
- Annonce officielle Let's Encrypt : [Intent to End OCSP Service](https://letsencrypt.org/2024/07/23/replacing-ocsp-with-crls)
- Mozilla : [CRLite](https://blog.mozilla.org/security/2020/01/09/crlite-part-1-all-web-pki-revocations-compressed/)
