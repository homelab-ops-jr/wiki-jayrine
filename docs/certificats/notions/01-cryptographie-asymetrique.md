# 01 — Cryptographie asymétrique

> **Type** : Notion · **Sujet** : Certificats · **Prérequis** : Aucun

## En une phrase

La cryptographie asymétrique repose sur une **paire de clés mathématiquement liées** : ce qui est chiffré avec l'une ne peut être déchiffré qu'avec l'autre.

## Le problème qu'elle résout

Avec la cryptographie symétrique (AES, ChaCha20...), la même clé sert à chiffrer et déchiffrer. Problème : comment partager la clé avec le destinataire sans qu'un attaquant l'intercepte ? On ne peut pas la chiffrer puisqu'on n'a pas encore de secret partagé. C'est le **problème de la distribution des clés**.

L'asymétrique résout ça : tu peux publier ta **clé publique** au monde entier. N'importe qui peut chiffrer un message pour toi, mais seul·e celui ou celle qui possède la **clé privée** correspondante pourra le lire.

## Les deux usages fondamentaux

### 1. Chiffrement (confidentialité)

```
Alice veut envoyer un message secret à Bob.
→ Alice chiffre avec la clé PUBLIQUE de Bob.
→ Seul Bob (qui a la clé privée) peut déchiffrer.
```

### 2. Signature (authenticité + intégrité)

```
Bob veut prouver qu'un message vient bien de lui.
→ Bob signe avec sa clé PRIVÉE.
→ N'importe qui peut vérifier avec la clé PUBLIQUE de Bob.
```

C'est ce second usage qui sous-tend toute la PKI : un **certificat** est essentiellement une déclaration ("cette clé publique appartient à `example.com`") **signée** par une autorité de confiance.

## Les algorithmes en pratique

| Algo | Type | Usage typique | Taille de clé |
|------|------|--------------|---------------|
| **RSA** | Historique | Tout-terrain, encore largement déployé | 2048 ou 4096 bits |
| **ECDSA** | Courbes elliptiques | Performances, mobile, embarqué | 256 ou 384 bits |
| **EdDSA** (Ed25519) | Courbes elliptiques modernes | SSH, WireGuard, certaines PKI | 256 bits |

Pour les certificats TLS aujourd'hui : RSA 2048+ ou ECDSA P-256/P-384. Let's Encrypt et la majorité des CA supportent les deux.

## Anatomie d'une paire de clés

Quand tu génères une paire avec OpenSSL :

```bash
openssl genrsa -out server.key 2048
openssl rsa -in server.key -pubout -out server.pub
```

Tu obtiens :

- `server.key` — la **clé privée**. Format PEM, commence par `-----BEGIN PRIVATE KEY-----` ou `-----BEGIN RSA PRIVATE KEY-----`. À protéger absolument (permissions `600`, jamais dans un dépôt Git).
- `server.pub` — la **clé publique**. Peut être diffusée librement.

🔒 La clé privée n'est **jamais** transmise sur le réseau. Si elle fuite, tout certificat lié à elle doit être révoqué.

## Lien avec les certificats

Un certificat X.509 contient (entre autres) :
- La **clé publique** du serveur
- L'identité associée (nom de domaine, organisation…)
- Une **signature** apposée par une autorité de certification

Le serveur garde sa clé privée pour lui ; il présente le certificat (donc sa clé publique + l'attestation signée) à tout client qui se connecte. C'est ce que tu verras dans la fiche [Handshake TLS](./04-tls-handshake.md).

## À retenir

- Une paire = clé publique (à distribuer) + clé privée (à protéger).
- Chiffrement : clé publique du destinataire pour chiffrer, clé privée du destinataire pour déchiffrer.
- Signature : clé privée de l'émetteur pour signer, clé publique de l'émetteur pour vérifier.
- Un certificat = clé publique + identité + signature d'une autorité.
- En 2026, RSA 2048+ ou ECDSA P-256 sont les choix standards pour TLS.

## Pour aller plus loin

- [Certificats X.509](./02-certificats-x509.md) — ce que contient concrètement un certificat
- Article de référence : RFC 8017 (RSA), RFC 8032 (EdDSA)
