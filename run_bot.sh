#!/bin/bash

if [ -z "$1" ]; then
  echo "Erreur: Précisez l'actif. Exemple: ./run_bot.sh US500"
  exit 1
fi

if [ -f ".env" ]; then
  set -a
  source .env
  set +a
else
  echo "Erreur: Fichier .env introuvable !"
  exit 1
fi

export ASSET=$1

# Version d'extraction ultra-robuste pour Python qui tolère les sauts de ligne
export CONFIRM=$(python3 -c "import json; f=open('config_assets.json'); d=json.load(f); print(d.get('$ASSET', {}).get('confirm_asset', ''))" 2>/dev/null)
export BASE_SIZE=$(python3 -c "import json; f=open('config_assets.json'); d=json.load(f); print(d.get('$ASSET', {}).get('base_size', '0.01'))" 2>/dev/null)
export MAX_MARGIN=$(python3 -c "import json; f=open('config_assets.json'); d=json.load(f); print(d.get('$ASSET', {}).get('max_margin', '10.0'))" 2>/dev/null)

if [ -z "$CONFIRM" ]; then
  echo "Erreur: Impossible de lire ou de trouver l'actif $ASSET dans config_assets.json !"
  exit 1
fi

export V2446I_ASSET="$ASSET"
export V2446J_CONFIRM_ASSET="$CONFIRM"
export MARKET="$ASSET"
export V2446I_L1_MAX_MARGIN_EUR="$MAX_MARGIN"
export V2446I_BASE_SIZE="$BASE_SIZE"
export V244_BASE_SIZE="$BASE_SIZE"
export BASE_SIZE="$BASE_SIZE"

export V244_STATE_FILE="state_v2447_${ASSET}.json"
export V244_LOCK_FILE="lock_v2447_${ASSET}.lock"
export V2446_ADVERSE_STATE_FILE="adverse_v2447_${ASSET}.json"

echo "============================================="
echo " DÉMARRAGE RUNNER V2447"
echo " Actif principal : $ASSET"
echo " Actif double    : $CONFIRM"
echo " Taille (Size)   : $BASE_SIZE"
echo " Marge Max       : $MAX_MARGIN EUR"
echo "============================================="

./venv/bin/python BOT_PIVOT_24_4_forced_audit_runner.py
