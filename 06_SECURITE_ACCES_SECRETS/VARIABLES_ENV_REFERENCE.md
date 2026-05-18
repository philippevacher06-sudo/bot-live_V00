# Variables Env Reference - bot-live_V00

Statut : reference securite
Projet : bot-live_V00
Date : 2026-05-18

## Objet

Ce fichier documente les noms de variables d'environnement connues ou attendues, sans stocker leurs valeurs.

## Variables Capital.com connues

```text
CAPITAL_API_KEY
CAPITAL_IDENTIFIER
CAPITAL_LOGIN
CAPITAL_PASSWORD
CAPITAL_EMAIL
X_CAP_API_KEY
API_KEY
IDENTIFIER
LOGIN
CAPITAL_API_PASSWORD
PASSWORD
```

## Regle

Ce fichier ne doit contenir aucune valeur de secret.

Les valeurs reelles doivent rester dans l'environnement d'execution ou dans un coffre de secrets adapte.

## Interdiction

Ne jamais coller ici :

```text
cle API reelle
mot de passe reel
token CST
token X-SECURITY-TOKEN
contenu complet d'un fichier .env
```
