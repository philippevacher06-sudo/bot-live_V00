# Politique Secrets - bot-live_V00

Statut : reference securite
Projet : bot-live_V00
Date : 2026-05-18

## Objet

Ce fichier fixe la politique de gestion des secrets pour le projet `bot-live_V00`.

## Regle principale

Aucun secret ne doit etre stocke en clair dans les fichiers memoire.

## Secrets concernes

```text
cles API
mots de passe
tokens
identifiants broker
CST
X-SECURITY-TOKEN
fichiers .env complets
cookies
cles SSH privees
```

## Ce qui est autorise

Il est autorise de documenter les noms de variables d'environnement attendues, sans leur valeur.

## Ce qui est interdit

```text
coller une cle API en clair
coller un mot de passe
coller un token de session
committer un fichier .env complet
copier une cle SSH privee
inclure des identifiants broker utilisables
```

## Regle finale

Les fichiers GitHub et Drive servent a memoriser la structure, jamais les secrets.
